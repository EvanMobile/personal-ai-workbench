"""Real-PostgreSQL schema contracts for the M1-A RAG Lab foundation."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import BigInteger, inspect, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError

from app.core.db import Base, engine
from app.core.utils import utcnow

TABLES = {
    "rag_dossiers",
    "execution_runs",
    "execution_steps",
    "execution_jobs",
    "execution_job_attempts",
    "execution_events",
}


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _run_values(**overrides):
    now = utcnow()
    values = {
        "id": _id("rrun"),
        "scope_type": "rag_dossier",
        "scope_id": _id("rdos"),
        "pipeline": "dossier",
        "stage": "dossier_rollup",
        "status": "queued",
        "config_snapshot": {"kind": "dossier_rollup"},
        "config_hash": "a" * 64,
        "fingerprint": "b" * 64,
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    return values


def _step_values(**overrides):
    now = utcnow()
    values = {
        "id": _id("rstp"),
        "step_key": "dossier_rollup",
        "ordinal": 1,
        "status": "pending",
        "progress": 0,
        "processed_count": 0,
        "failed_count": 0,
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    return values


def _job_values(**overrides):
    now = utcnow()
    values = {
        "id": _id("rjob"),
        "job_key": "dossier_rollup",
        "kind": "dossier_rollup",
        "status": "queued",
        "payload": {},
        "attempts": 0,
        "max_attempts": 3,
        "lease_token": 0,
        "available_at": now,
        "processed_count": 0,
        "failed_count": 0,
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    return values


def _attempt_values(**overrides):
    values = {
        "id": _id("ratt"),
        "attempt_no": 1,
        "status": "running",
        "worker_id": "worker-test",
        "fencing_token": 1,
        "started_at": utcnow(),
        "metrics": {},
    }
    values.update(overrides)
    return values


def _insert(name: str, values: dict, *, connection) -> None:
    connection.execute(Base.metadata.tables[name].insert().values(**values))


def _create_run_step(connection):
    run = _run_values()
    _insert("execution_runs", run, connection=connection)
    step = _step_values(run_id=run["id"])
    _insert("execution_steps", step, connection=connection)
    return run, step


def test_six_tables_exist() -> None:
    inspector = inspect(engine)
    assert TABLES <= set(inspector.get_table_names())


def test_key_columns_and_types() -> None:
    inspector = inspect(engine)

    run_columns = {column["name"]: column for column in inspector.get_columns("execution_runs")}
    assert isinstance(run_columns["config_snapshot"]["type"], JSONB)
    assert isinstance(run_columns["result"]["type"], JSONB)
    assert run_columns["idempotency_payload_hash"]["type"].length == 64

    job_columns = {column["name"]: column for column in inspector.get_columns("execution_jobs")}
    assert isinstance(job_columns["lease_token"]["type"], BigInteger)
    assert isinstance(job_columns["payload"]["type"], JSONB)

    attempt_columns = {
        column["name"]: column for column in inspector.get_columns("execution_job_attempts")
    }
    assert isinstance(attempt_columns["fencing_token"]["type"], BigInteger)
    assert isinstance(attempt_columns["metrics"]["type"], JSONB)

    event_columns = {column["name"]: column for column in inspector.get_columns("execution_events")}
    assert isinstance(event_columns["id"]["type"], BigInteger)

    dossier_columns = {column["name"]: column for column in inspector.get_columns("rag_dossiers")}
    assert dossier_columns["title"]["type"].length == 200


def test_foreign_keys() -> None:
    inspector = inspect(engine)

    def fks(table: str):
        return [
            (
                tuple(item["constrained_columns"]),
                item["referred_table"],
                tuple(item.get("referred_columns") or ()),
            )
            for item in inspector.get_foreign_keys(table)
        ]

    assert (("run_id",), "execution_runs", ("id",)) in fks("execution_steps")
    job_fks = fks("execution_jobs")
    assert (("run_id",), "execution_runs", ("id",)) in job_fks
    assert (
        ("step_id", "run_id"),
        "execution_steps",
        ("id", "run_id"),
    ) in job_fks
    assert (("job_id",), "execution_jobs", ("id",)) in fks("execution_job_attempts")
    event_fks = fks("execution_events")
    assert (("run_id",), "execution_runs", ("id",)) in event_fks
    assert (("step_id", "run_id"), "execution_steps", ("id", "run_id")) in event_fks
    assert (("job_id", "run_id"), "execution_jobs", ("id", "run_id")) in event_fks


def test_unique_constraints() -> None:
    inspector = inspect(engine)

    def uniques(table: str):
        return {
            tuple(item["column_names"])
            for item in inspector.get_unique_constraints(table)
        }

    assert ("run_id", "step_key") in uniques("execution_steps")
    assert ("run_id", "ordinal") in uniques("execution_steps")
    assert ("id", "run_id") in uniques("execution_steps")
    assert ("run_id", "job_key") in uniques("execution_jobs")
    assert ("id", "run_id") in uniques("execution_jobs")
    assert ("job_id", "attempt_no") in uniques("execution_job_attempts")


def test_partial_idempotency_index() -> None:
    with engine.connect() as connection:
        indexdef = connection.scalar(
            text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE schemaname = 'public' AND indexname = 'ux_execution_runs_idempotency'"
            )
        )
    assert indexdef is not None
    assert "CREATE UNIQUE INDEX" in indexdef
    assert "WHERE (idempotency_key IS NOT NULL)" in indexdef


def test_status_checks_include_skipped_and_exclude_attempt() -> None:
    with engine.connect() as connection:
        definitions = dict(
            connection.execute(
                text(
                    "SELECT conname, pg_get_constraintdef(oid) "
                    "FROM pg_constraint "
                    "WHERE conrelid IN ("
                    "'execution_runs'::regclass, 'execution_jobs'::regclass, "
                    "'execution_job_attempts'::regclass) AND contype = 'c'"
                )
            ).all()
        )
    assert "'skipped'" in definitions["ck_execution_runs_status"]
    assert "'skipped'" in definitions["ck_execution_jobs_status"]
    assert "'skipped'" not in definitions["ck_execution_job_attempts_status"]
    assert "finished_at" in definitions["ck_execution_job_attempts_terminal_finished"]


def test_status_checks_enforced() -> None:
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            _insert("execution_runs", _run_values(status="bogus"), connection=connection)

    with engine.begin() as connection:
        run = _run_values(status="skipped")
        _insert("execution_runs", run, connection=connection)
        step = _step_values(run_id=run["id"], status="skipped")
        _insert("execution_steps", step, connection=connection)
        _insert(
            "execution_jobs",
            _job_values(run_id=run["id"], step_id=step["id"], status="skipped"),
            connection=connection,
        )

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            run, step = _create_run_step(connection)
            job = _job_values(run_id=run["id"], step_id=step["id"])
            _insert("execution_jobs", job, connection=connection)
            _insert(
                "execution_job_attempts",
                _attempt_values(job_id=job["id"], status="skipped"),
                connection=connection,
            )


def test_attempt_terminal_requires_finished_at() -> None:
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            run, step = _create_run_step(connection)
            job = _job_values(run_id=run["id"], step_id=step["id"])
            _insert("execution_jobs", job, connection=connection)
            _insert(
                "execution_job_attempts",
                _attempt_values(job_id=job["id"], status="succeeded"),
                connection=connection,
            )


def test_attempt_unique_and_fencing_positive() -> None:
    with engine.begin() as connection:
        run, step = _create_run_step(connection)
        job = _job_values(run_id=run["id"], step_id=step["id"])
        _insert("execution_jobs", job, connection=connection)
        _insert("execution_job_attempts", _attempt_values(job_id=job["id"]), connection=connection)

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            _insert(
                "execution_job_attempts",
                _attempt_values(job_id=job["id"], attempt_no=1, fencing_token=2),
                connection=connection,
            )

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            run, step = _create_run_step(connection)
            job = _job_values(run_id=run["id"], step_id=step["id"])
            _insert("execution_jobs", job, connection=connection)
            _insert(
                "execution_job_attempts",
                _attempt_values(job_id=job["id"], fencing_token=0),
                connection=connection,
            )


def test_step_and_job_unique_keys() -> None:
    with engine.begin() as connection:
        run, step = _create_run_step(connection)

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            _insert(
                "execution_steps",
                _step_values(run_id=run["id"], step_key="dossier_rollup", ordinal=2),
                connection=connection,
            )

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            _insert(
                "execution_steps",
                _step_values(run_id=run["id"], step_key="other", ordinal=1),
                connection=connection,
            )

    with engine.begin() as connection:
        _insert(
            "execution_jobs",
            _job_values(run_id=run["id"], step_id=step["id"]),
            connection=connection,
        )

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            _insert(
                "execution_jobs",
                _job_values(run_id=run["id"], step_id=step["id"], id=_id("rjob")),
                connection=connection,
            )


def test_valid_event_insert() -> None:
    with engine.begin() as connection:
        run, step = _create_run_step(connection)
        job = _job_values(run_id=run["id"], step_id=step["id"])
        _insert("execution_jobs", job, connection=connection)
        _insert(
            "execution_events",
            {
                "run_id": run["id"],
                "step_id": step["id"],
                "job_id": job["id"],
                "type": "job.started",
                "level": "info",
                "message": "job started",
                "payload": {"job_id": job["id"]},
                "created_at": utcnow(),
            },
            connection=connection,
        )
        event_count = connection.scalar(text("SELECT count(*) FROM execution_events"))
    assert event_count == 1


def test_composite_fk_prevents_cross_run_step() -> None:
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            run_a, step_a = _create_run_step(connection)
            run_b = _run_values(scope_id=_id("rdos"))
            _insert("execution_runs", run_b, connection=connection)
            _insert(
                "execution_jobs",
                _job_values(run_id=run_b["id"], step_id=step_a["id"]),
                connection=connection,
            )


def test_event_composite_fk_and_not_null_run() -> None:
    with engine.begin() as connection:
        run_a, step_a = _create_run_step(connection)
        job_a = _job_values(run_id=run_a["id"], step_id=step_a["id"])
        _insert("execution_jobs", job_a, connection=connection)
        run_b = _run_values(scope_id=_id("rdos"))
        _insert("execution_runs", run_b, connection=connection)

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            _insert(
                "execution_events",
                {
                    "run_id": run_b["id"],
                    "step_id": step_a["id"],
                    "job_id": job_a["id"],
                    "type": "job.started",
                    "level": "info",
                    "message": "cross-run event",
                    "payload": {},
                    "created_at": utcnow(),
                },
                connection=connection,
            )

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            _insert(
                "execution_events",
                {
                    "run_id": None,
                    "type": "run.created",
                    "level": "info",
                    "message": "missing run",
                    "payload": {},
                    "created_at": utcnow(),
                },
                connection=connection,
            )


def test_idempotency_unique_and_payload_hash_check() -> None:
    key = _id("idem")
    scope = _id("rdos")
    with engine.begin() as connection:
        _insert(
            "execution_runs",
            _run_values(scope_id=scope, idempotency_key=key, idempotency_payload_hash="c" * 64),
            connection=connection,
        )

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            _insert(
                "execution_runs",
                _run_values(
                    scope_id=scope,
                    idempotency_key=key,
                    idempotency_payload_hash="c" * 64,
                ),
                connection=connection,
            )

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            _insert(
                "execution_runs",
                _run_values(idempotency_key=_id("idem"), idempotency_payload_hash=None),
                connection=connection,
            )


def test_running_job_requires_lease_expiry() -> None:
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            run, step = _create_run_step(connection)
            _insert(
                "execution_jobs",
                _job_values(run_id=run["id"], step_id=step["id"], status="running"),
                connection=connection,
            )

    with engine.begin() as connection:
        run, step = _create_run_step(connection)
        _insert(
            "execution_jobs",
            _job_values(
                run_id=run["id"],
                step_id=step["id"],
                status="running",
                lease_expires_at=utcnow() + timedelta(seconds=60),
            ),
            connection=connection,
        )


def test_migration_upgrade_downgrade_reupgrade() -> None:
    cfg = Config(str(Path(__file__).parent.parent / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).parent.parent / "migrations"))
    head = ScriptDirectory.from_config(cfg).get_current_head()

    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == head

    command.downgrade(cfg, "-1")
    try:
        downgraded = inspect(engine)
        assert not (TABLES & set(downgraded.get_table_names()))
    finally:
        command.upgrade(cfg, "head")

    upgraded = inspect(engine)
    assert TABLES <= set(upgraded.get_table_names())

    # Re-running upgrade at head must be a no-op.
    command.upgrade(cfg, "head")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == head
