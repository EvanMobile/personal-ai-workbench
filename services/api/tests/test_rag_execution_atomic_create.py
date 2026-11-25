"""R3.1: atomic Run + Step + Job creation and idempotency races."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.db import SessionLocal
from app.modules.execution.errors import IdempotencyConflict, RunIncomplete
from app.modules.execution.models import (
    ExecutionJob,
    ExecutionRun,
    ExecutionStep,
)
from app.modules.execution.service import (
    create_run_with_step_job,
    create_step,
    payload_hash,
)


def _kwargs(
    *,
    scope_id: str = "scope_atomic",
    key: str | None = "atomic-key",
    kind: str = "test.atomic",
    payload: dict | None = None,
    step_key: str = "stage",
    job_key: str = "job",
    max_attempts: int = 3,
):
    return {
        "scope_type": "test_scope",
        "scope_id": scope_id,
        "pipeline": "test_pipeline",
        "stage": "test_stage",
        "config_snapshot": {"kind": kind},
        "config_hash": "a" * 64,
        "fingerprint": "b" * 64,
        "step_key": step_key,
        "ordinal": 1,
        "job_key": job_key,
        "kind": kind,
        "payload": payload or {"kind": kind},
        "max_attempts": max_attempts,
        "idempotency_key": key,
        "idempotency_payload_hash": payload_hash({"kind": kind, "payload": payload or {}})
        if key is not None
        else None,
    }


def _counts() -> tuple[int, int, int]:
    with SessionLocal() as session:
        return (
            int(session.scalar(select(func.count()).select_from(ExecutionRun)) or 0),
            int(session.scalar(select(func.count()).select_from(ExecutionStep)) or 0),
            int(session.scalar(select(func.count()).select_from(ExecutionJob)) or 0),
        )


def test_create_run_with_step_job_commits_all_in_one_transaction() -> None:
    with SessionLocal() as session:
        result = create_run_with_step_job(session, **_kwargs())
        assert result.reused is False
        assert result.run.status == "queued"
        assert result.run_id.startswith("rrun_")
        assert result.step_id.startswith("rstp_")
        assert result.job_id.startswith("rjob_")

    with SessionLocal() as session:
        run = session.get(ExecutionRun, result.run_id)
        step = session.get(ExecutionStep, result.step_id)
        job = session.get(ExecutionJob, result.job_id)
        assert run is not None and step is not None and job is not None
        assert step.run_id == run.id
        assert job.run_id == run.id and job.step_id == step.id
        assert job.status == "queued"
        assert _counts() == (1, 1, 1)


def test_create_run_with_step_job_rolls_back_step_failure() -> None:
    # VARCHAR(64) overflow produces a DB error during the aggregate flush.
    with pytest.raises(SQLAlchemyError):
        with SessionLocal() as session:
            create_run_with_step_job(
                session,
                **_kwargs(key=None, step_key="x" * 65),
            )
    assert _counts() == (0, 0, 0)


def test_create_run_with_step_job_rolls_back_job_failure() -> None:
    # CHECK max_attempts >= 1 fires after Run and Step have been flushed.
    with pytest.raises(IntegrityError):
        with SessionLocal() as session:
            create_run_with_step_job(
                session,
                **_kwargs(key=None, max_attempts=0),
            )
    assert _counts() == (0, 0, 0)


def test_idempotent_reuse_returns_same_aggregate() -> None:
    with SessionLocal() as session:
        first = create_run_with_step_job(session, **_kwargs())
    with SessionLocal() as session:
        second = create_run_with_step_job(session, **_kwargs())
    assert first.reused is False
    assert second.reused is True
    assert (second.run_id, second.step_id, second.job_id) == (
        first.run_id,
        first.step_id,
        first.job_id,
    )
    assert _counts() == (1, 1, 1)


def test_idempotency_conflict_does_not_create_duplicate() -> None:
    with SessionLocal() as session:
        create_run_with_step_job(session, **_kwargs())
    with SessionLocal() as session:
        with pytest.raises(IdempotencyConflict):
            create_run_with_step_job(session, **_kwargs(kind="different"))
    assert _counts() == (1, 1, 1)


def test_run_incomplete_is_not_repaired() -> None:
    with SessionLocal() as session:
        created = create_run_with_step_job(session, **_kwargs())
        job = session.get(ExecutionJob, created.job_id)
        assert job is not None
        session.delete(job)
        session.commit()

    with SessionLocal() as session:
        with pytest.raises(RunIncomplete) as exc_info:
            create_run_with_step_job(session, **_kwargs())
        assert exc_info.value.run_id == created.run_id
        assert exc_info.value.missing == "job"
    assert _counts() == (1, 1, 0)


def test_run_incomplete_missing_step_is_not_repaired() -> None:
    with SessionLocal() as session:
        created = create_run_with_step_job(session, **_kwargs(key="missing-step"))
        job = session.get(ExecutionJob, created.job_id)
        step = session.get(ExecutionStep, created.step_id)
        assert job is not None and step is not None
        session.delete(job)
        session.delete(step)
        session.commit()

    with SessionLocal() as session:
        with pytest.raises(RunIncomplete) as exc_info:
            create_run_with_step_job(session, **_kwargs(key="missing-step"))
        assert exc_info.value.run_id == created.run_id
        assert exc_info.value.missing == "step"
    assert _counts() == (1, 0, 0)


def test_existing_job_must_belong_to_found_step() -> None:
    with SessionLocal() as session:
        created = create_run_with_step_job(session, **_kwargs(key="wrong-step"))
        other = create_step(session, run_id=created.run_id, step_key="other", ordinal=2)
    with SessionLocal() as session:
        job = session.get(ExecutionJob, created.job_id)
        assert job is not None
        job.step_id = other.id
        session.commit()

    with SessionLocal() as session:
        with pytest.raises(RunIncomplete) as exc_info:
            create_run_with_step_job(session, **_kwargs(key="wrong-step"))
        assert exc_info.value.run_id == created.run_id
        assert exc_info.value.missing == "job"
    assert _counts() == (1, 2, 1)


def test_concurrent_same_key_same_payload_creates_one_aggregate() -> None:
    barrier = threading.Barrier(8)
    results: list = []
    errors: list[BaseException] = []

    def create() -> None:
        try:
            with SessionLocal() as session:
                barrier.wait(timeout=5)
                results.append(create_run_with_step_job(session, **_kwargs()))
        except BaseException as exc:  # noqa: BLE001 - asserted below
            errors.append(exc)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: create(), range(8)))

    assert not errors, errors
    assert len(results) == 8
    assert len({result.run_id for result in results}) == 1
    assert sum(1 for result in results if not result.reused) == 1
    assert _counts() == (1, 1, 1)


def test_concurrent_same_key_different_payload_has_one_winner() -> None:
    barrier = threading.Barrier(2)
    results: list = []
    conflicts: list[IdempotencyConflict] = []

    def create(kind: str) -> None:
        try:
            with SessionLocal() as session:
                barrier.wait(timeout=5)
                results.append(create_run_with_step_job(session, **_kwargs(kind=kind)))
        except IdempotencyConflict as exc:
            conflicts.append(exc)
            # The losing session must be usable after the service's rollback.
            assert session.scalar(select(1)) == 1

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(create, ("kind-a", "kind-b")))

    assert len(results) == 1, (results, conflicts)
    assert len(conflicts) == 1
    assert _counts() == (1, 1, 1)
