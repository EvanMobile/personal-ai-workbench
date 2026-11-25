"""R3.1: generic scope statistics and batch reads (no N+1)."""

from __future__ import annotations

from sqlalchemy import event, select

from app.core.db import SessionLocal, engine
from app.core.utils import utcnow
from app.modules.execution.models import ExecutionRun
from app.modules.execution.results import StepResult
from app.modules.execution.service import (
    claim_job,
    create_run_with_step_job,
    finish_job,
    get_scope_execution_stats,
    get_scope_execution_stats_bulk,
    list_run_summaries_for_scopes,
    payload_hash,
)


def _create(scope_id: str, key: str):
    with SessionLocal() as session:
        return create_run_with_step_job(
            session,
            scope_type="test_scope",
            scope_id=scope_id,
            pipeline="test_pipeline",
            stage="test_stage",
            config_snapshot={"kind": "test.scope"},
            config_hash="a" * 64,
            fingerprint="b" * 64,
            step_key="stage",
            ordinal=1,
            job_key="job",
            kind="test.scope",
            payload={},
            idempotency_key=key,
            idempotency_payload_hash=payload_hash({"key": key}),
        )


def _finish_next(status: str) -> None:
    with SessionLocal() as session:
        claimed = claim_job(session, worker_id="stats-worker", lease_seconds=60)
        assert claimed is not None
        if status == "succeeded":
            result = StepResult(status="succeeded", processed_count=3)
        else:
            result = StepResult(status="failed", failed_count=1, error_code="SYNTHETIC")
        finish_job(
            session,
            job_id=claimed.job_id,
            lease_token=claimed.lease_token,
            attempt_id=claimed.attempt_id,
            result=result,
        )


def test_scope_statistics_and_batch_are_one_query() -> None:
    created_a1 = _create("scope_a", "a-1")
    _finish_next("succeeded")
    _create("scope_a", "a-2")
    _finish_next("failed")
    _create("scope_a", "a-3")
    _create("scope_b", "b-1")
    _create("scope_c", "c-1")

    with SessionLocal() as session:
        a = get_scope_execution_stats(
            session, scope_type="test_scope", scope_id="scope_a", stage="test_stage"
        )
        assert a.run_count == 3
        assert a.active_run_count == 1
        assert a.failed_run_count == 1
        assert a.latest_run_at is not None
        assert a.latest_success_at is not None

        b = get_scope_execution_stats(
            session, scope_type="test_scope", scope_id="scope_b"
        )
        assert (b.run_count, b.active_run_count, b.failed_run_count) == (1, 1, 0)

        c = get_scope_execution_stats(
            session, scope_type="test_scope", scope_id="missing_scope"
        )
        assert (c.run_count, c.active_run_count, c.failed_run_count) == (0, 0, 0)

    select_count = 0

    def count_selects(*_args) -> None:
        nonlocal select_count
        select_count += 1

    event.listen(engine, "before_cursor_execute", count_selects)
    try:
        with SessionLocal() as session:
            stats = get_scope_execution_stats_bulk(
                session,
                scope_type="test_scope",
                scope_ids=["scope_a", "scope_b", "scope_c", "missing_scope"],
                stage="test_stage",
            )
    finally:
        event.remove(engine, "before_cursor_execute", count_selects)

    assert select_count == 1, f"bulk stats issued {select_count} queries"
    assert stats["scope_a"].run_count == 3
    assert stats["scope_b"].run_count == 1
    assert stats["scope_c"].run_count == 1
    assert stats["missing_scope"].run_count == 0
    assert stats["scope_a"].latest_success_at == a.latest_success_at
    assert created_a1.run_id


def test_recent_run_summaries_for_many_scopes_are_one_query() -> None:
    for scope in ("s1", "s2", "s3"):
        for index in range(12):
            _create(scope, f"{scope}-{index}")

    select_count = 0

    def count_selects(*_args) -> None:
        nonlocal select_count
        select_count += 1

    event.listen(engine, "before_cursor_execute", count_selects)
    try:
        with SessionLocal() as session:
            grouped = list_run_summaries_for_scopes(
                session,
                scope_type="test_scope",
                scope_ids=["s1", "s2", "s3", "empty"],
                limit_per_scope=2,
            )
    finally:
        event.remove(engine, "before_cursor_execute", count_selects)

    assert select_count == 1
    for scope in ("s1", "s2", "s3"):
        assert len(grouped[scope]) == 2
        assert grouped[scope][0].created_at >= grouped[scope][1].created_at
    assert grouped["empty"] == ()


def test_recent_runs_tie_break_is_stable_by_id() -> None:
    created = []
    for index in range(5):
        created.append(_create("tie_scope", f"tie-{index}"))
    fixed = utcnow()
    with SessionLocal() as session:
        runs = session.scalars(
            select(ExecutionRun).where(ExecutionRun.scope_id == "tie_scope")
        ).all()
        for run in runs:
            run.created_at = fixed
        session.commit()

    with SessionLocal() as session:
        grouped = list_run_summaries_for_scopes(
            session,
            scope_type="test_scope",
            scope_ids=["tie_scope"],
            limit_per_scope=3,
        )
    ids = [item.id for item in grouped["tie_scope"]]
    assert len(ids) == 3
    assert ids == sorted(
        [created_item.run_id for created_item in created], reverse=True
    )[:3]
