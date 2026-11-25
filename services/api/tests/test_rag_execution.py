"""Real-PostgreSQL tests for the M1-A execution service and aggregation."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import threading
import time

import pytest
from sqlalchemy import select, text

from app.core.db import SessionLocal
from app.core.utils import utcnow
from app.modules.evaluation.models import RagDossier
from app.modules.execution.aggregation import aggregate_statuses
from app.modules.execution.config import ExecutionConfig
from app.modules.execution.errors import IdempotencyConflict, StaleLease
from app.modules.execution.models import (
    ExecutionJob,
    ExecutionJobAttempt,
    ExecutionRun,
    ExecutionStep,
)
from app.modules.execution.results import StepResult
from app.modules.execution.service import (
    claim_job,
    create_job,
    request_cancel,
    create_run,
    create_step,
    finish_job,
    payload_hash,
)


def _new_run(session, **overrides):
    values = {
        "scope_type": "rag_dossier",
        "scope_id": "rdos_test",
        "pipeline": "dossier",
        "stage": "dossier_rollup",
        "config_snapshot": {"kind": "dossier_rollup"},
        "config_hash": "a" * 64,
        "fingerprint": "b" * 64,
    }
    values.update(overrides)
    return create_run(session, **values)


def _bundle(*, job_keys=("dossier_rollup",), kind="test.sleep"):
    with SessionLocal() as session:
        dossier = RagDossier(title="Test dossier")
        session.add(dossier)
        session.commit()
        run, _ = _new_run(session, scope_id=dossier.id)
        step = create_step(session, run_id=run.id, step_key="stage", ordinal=1)
        jobs = [
            create_job(
                session,
                run_id=run.id,
                step_id=step.id,
                job_key=key,
                kind=kind,
                payload={"seconds": 0.05},
            )
            for key in job_keys
        ]
        return run.id, step.id, [job.id for job in jobs]


def test_idempotent_create_run() -> None:
    with SessionLocal() as session:
        values = {
            "scope_type": "rag_dossier",
            "scope_id": "rdos_idem",
            "pipeline": "dossier",
            "stage": "dossier_rollup",
            "config_snapshot": {"kind": "dossier_rollup"},
            "config_hash": "a" * 64,
            "fingerprint": "b" * 64,
            "idempotency_key": "key-1",
            "idempotency_payload_hash": payload_hash({"kind": "dossier_rollup"}),
        }
        first, reused = create_run(session, **values)
        second, reused_again = create_run(session, **values)
        assert reused is False
        assert reused_again is True
        assert second.id == first.id

        with pytest.raises(IdempotencyConflict):
            create_run(
                session,
                **{
                    **values,
                    "idempotency_payload_hash": payload_hash({"kind": "different"}),
                },
            )


def test_claim_and_finish_aggregates_step_and_run() -> None:
    run_id, step_id, job_ids = _bundle(job_keys=("a", "b"))
    with SessionLocal() as session:
        claimed = claim_job(
            session,
            worker_id="worker-test",
            lease_seconds=60,
        )
        assert claimed is not None
        finish_job(
            session,
            job_id=claimed.job_id,
            lease_token=claimed.lease_token,
            attempt_id=claimed.attempt_id,
            result=StepResult(status="succeeded", processed_count=1),
        )

    with SessionLocal() as session:
        step = session.get(ExecutionStep, step_id)
        run = session.get(ExecutionRun, run_id)
        assert step is not None and run is not None
        assert step.status == "running"
        assert run.status == "running"

        claimed = claim_job(session, worker_id="worker-test", lease_seconds=60)
        assert claimed is not None
        finish_job(
            session,
            job_id=claimed.job_id,
            lease_token=claimed.lease_token,
            attempt_id=claimed.attempt_id,
            result=StepResult(status="failed", failed_count=1, error_code="SYNTHETIC"),
        )

    with SessionLocal() as session:
        step = session.get(ExecutionStep, step_id)
        run = session.get(ExecutionRun, run_id)
        assert step is not None and run is not None
        assert step.status == "partial"
        assert run.status == "partial"


def test_cancel_run_with_empty_step() -> None:
    with SessionLocal() as session:
        run, _ = _new_run(session)
        create_step(session, run_id=run.id, step_key="empty", ordinal=1)
        run_id = run.id

    with SessionLocal() as session:
        cancelled = request_cancel(session, run_id=run_id)
        assert cancelled.status == "cancelled"

    with SessionLocal() as session:
        step = session.scalar(
            select(ExecutionStep).where(ExecutionStep.run_id == run_id)
        )
        assert step is not None and step.status == "cancelled"


def test_run_waits_for_all_steps() -> None:
    with SessionLocal() as session:
        run, _ = _new_run(session)
        step1 = create_step(session, run_id=run.id, step_key="one", ordinal=1)
        step2 = create_step(session, run_id=run.id, step_key="two", ordinal=2)
        job1 = create_job(
            session,
            run_id=run.id,
            step_id=step1.id,
            job_key="one",
            kind="test.sleep",
            payload={"seconds": 0.05},
        )
        create_job(
            session,
            run_id=run.id,
            step_id=step2.id,
            job_key="two",
            kind="test.sleep",
            payload={"seconds": 0.05},
        )
        run_id = run.id

    with SessionLocal() as session:
        claimed = claim_job(session, worker_id="worker-test", lease_seconds=60)
        assert claimed is not None
        finish_job(
            session,
            job_id=claimed.job_id,
            lease_token=claimed.lease_token,
            attempt_id=claimed.attempt_id,
            result=StepResult(status="succeeded", processed_count=1),
        )

    with SessionLocal() as session:
        run = session.get(ExecutionRun, run_id)
        assert run is not None and run.status == "running"

    with SessionLocal() as session:
        claimed = claim_job(session, worker_id="worker-test", lease_seconds=60)
        assert claimed is not None
        finish_job(
            session,
            job_id=claimed.job_id,
            lease_token=claimed.lease_token,
            attempt_id=claimed.attempt_id,
            result=StepResult(status="succeeded", processed_count=1),
        )

    with SessionLocal() as session:
        run = session.get(ExecutionRun, run_id)
        assert run is not None and run.status == "succeeded"


def test_skipped_aggregation_matrix() -> None:
    cases = {
        ("succeeded", "skipped"): "succeeded",
        ("failed", "skipped"): "failed",
        ("skipped",): "skipped",
        ("partial", "skipped"): "partial",
        ("cancelled", "skipped"): "cancelled",
        ("succeeded", "failed", "skipped"): "partial",
        ("failed", "cancelled", "skipped"): "failed",
        ("succeeded", "cancelled"): "partial",
        ("cancelled",): "cancelled",
    }
    for inputs, expected in cases.items():
        assert aggregate_statuses(inputs) == expected, (inputs, expected)


def test_stale_token_cannot_finish() -> None:
    with SessionLocal() as session:
        run, _ = _new_run(session)
        step = create_step(session, run_id=run.id, step_key="stage", ordinal=1)
        job = create_job(
            session,
            run_id=run.id,
            step_id=step.id,
            job_key="stage",
            kind="test.sleep",
            payload={"seconds": 0.05},
        )
        claimed = claim_job(session, worker_id="worker-a", lease_seconds=60)
        assert claimed is not None
        # Force a new owner token as if a later Worker had reclaimed the job.
        job = session.get(ExecutionJob, job.id)
        assert job is not None
        job.lease_token += 1
        session.commit()

        with pytest.raises(StaleLease):
            finish_job(
                session,
                job_id=claimed.job_id,
                lease_token=claimed.lease_token,
                attempt_id=claimed.attempt_id,
                result=StepResult(status="succeeded"),
            )


def test_w4_concurrent_idempotent_creation() -> None:
    values = {
        "scope_type": "rag_dossier",
        "scope_id": "rdos_concurrent",
        "pipeline": "dossier",
        "stage": "dossier_rollup",
        "config_snapshot": {"kind": "dossier_rollup"},
        "config_hash": "a" * 64,
        "fingerprint": "b" * 64,
        "idempotency_key": "concurrent-key",
        "idempotency_payload_hash": payload_hash({"kind": "dossier_rollup"}),
    }

    def create_one():
        with SessionLocal() as session:
            run, reused = create_run(session, **values)
            return run.id, reused

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: create_one(), range(8)))

    ids = {run_id for run_id, _ in results}
    assert len(ids) == 1
    assert sum(1 for _, reused in results if not reused) == 1


def _set_lock_timeout(session) -> None:
    session.execute(text("SET LOCAL lock_timeout = '5s'"))


def test_cancel_claim_lock_order_no_deadlock() -> None:
    """Cancel must wait for an in-flight Claim, never take Run before Job."""
    run_id, step_id, job_id = _bundle(job_keys=("only",))
    holder = SessionLocal()
    result: dict[str, object] = {}
    started = threading.Event()
    try:
        _set_lock_timeout(holder)
        holder.scalar(
            select(ExecutionJob).where(ExecutionJob.id == job_id).with_for_update()
        )
        holder.scalar(
            select(ExecutionStep).where(ExecutionStep.id == step_id).with_for_update()
        )

        def cancel() -> None:
            started.set()
            try:
                with SessionLocal() as session:
                    _set_lock_timeout(session)
                    request_cancel(session, run_id=run_id)
                result["ok"] = True
            except Exception as exc:  # noqa: BLE001 - asserted below
                result["error"] = exc

        thread = threading.Thread(target=cancel)
        thread.start()
        started.wait(2)
        time.sleep(0.4)
        holder.scalar(
            select(ExecutionRun).where(ExecutionRun.id == run_id).with_for_update()
        )
        holder.commit()
        thread.join(10)
        assert not thread.is_alive(), "cancel thread deadlocked"
        assert "error" not in result, result
    finally:
        holder.close()

    with SessionLocal() as session:
        run = session.get(ExecutionRun, run_id)
        job = session.get(ExecutionJob, job_id)
        assert run is not None and run.status == "cancelled"
        assert job is not None and job.status == "cancelled"


def test_cancel_finish_lock_order_no_deadlock() -> None:
    """Cancel must also wait for Finish's Job → Attempt → Step → Run locks."""
    run_id, step_id, job_id = _bundle(job_keys=("only",))
    with SessionLocal() as session:
        claimed = claim_job(session, worker_id="finish-holder", lease_seconds=60)
        assert claimed is not None
        attempt_id = claimed.attempt_id

    holder = SessionLocal()
    result: dict[str, object] = {}
    started = threading.Event()
    try:
        _set_lock_timeout(holder)
        holder.scalar(
            select(ExecutionJob).where(ExecutionJob.id == job_id).with_for_update()
        )
        holder.scalar(
            select(ExecutionJobAttempt)
            .where(ExecutionJobAttempt.id == attempt_id)
            .with_for_update()
        )
        holder.scalar(
            select(ExecutionStep).where(ExecutionStep.id == step_id).with_for_update()
        )

        def cancel() -> None:
            started.set()
            try:
                with SessionLocal() as session:
                    _set_lock_timeout(session)
                    request_cancel(session, run_id=run_id)
                result["ok"] = True
            except Exception as exc:  # noqa: BLE001
                result["error"] = exc

        thread = threading.Thread(target=cancel)
        thread.start()
        started.wait(2)
        time.sleep(0.4)
        holder.scalar(
            select(ExecutionRun).where(ExecutionRun.id == run_id).with_for_update()
        )
        holder.commit()
        thread.join(10)
        assert not thread.is_alive(), "cancel thread deadlocked"
        assert "error" not in result, result
    finally:
        holder.close()

    with SessionLocal() as session:
        run = session.get(ExecutionRun, run_id)
        job = session.get(ExecutionJob, job_id)
        assert run is not None and run.cancel_requested_at is not None
        assert job is not None and job.cancel_requested_at is not None
