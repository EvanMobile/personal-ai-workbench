"""R3.1: lock-held idempotent Cancel with independent Sessions."""

from __future__ import annotations

import threading

from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.modules.execution.errors import RunNotCancellable
from app.modules.execution.models import (
    ExecutionEvent,
    ExecutionJob,
    ExecutionJobAttempt,
)
from app.modules.execution.results import StepResult
from app.modules.execution.service import (
    claim_job,
    create_run_with_step_job,
    finish_job,
    payload_hash,
    request_cancel,
    request_cancel_outcome,
)


def _create():
    with SessionLocal() as session:
        return create_run_with_step_job(
            session,
            scope_type="test_scope",
            scope_id="scope_cancel",
            pipeline="test_pipeline",
            stage="test_stage",
            config_snapshot={"kind": "test.cancel"},
            config_hash="a" * 64,
            fingerprint="b" * 64,
            step_key="stage",
            ordinal=1,
            job_key="job",
            kind="test.cancel",
            payload={},
            idempotency_key="cancel-key",
            idempotency_payload_hash=payload_hash({"kind": "test.cancel"}),
        )


def _create_running():
    created = _create()
    with SessionLocal() as session:
        claimed = claim_job(session, worker_id="cancel-worker", lease_seconds=60)
        assert claimed is not None and claimed.run_id == created.run_id
    return created, claimed


def _cancel_event_count(run_id: str) -> int:
    with SessionLocal() as session:
        return int(
            session.scalar(
                select(func.count())
                .select_from(ExecutionEvent)
                .where(
                    ExecutionEvent.run_id == run_id,
                    ExecutionEvent.type == "job.cancel_requested",
                )
            )
            or 0
        )


def test_repeated_cancel_returns_already_requested_without_duplicate_event() -> None:
    created, _ = _create_running()
    with SessionLocal() as session:
        first = request_cancel_outcome(session, run_id=created.run_id)
        assert first.already_requested is False
        assert first.run.cancel_requested_at is not None
    with SessionLocal() as session:
        second = request_cancel_outcome(session, run_id=created.run_id)
        assert second.already_requested is True
        assert second.run.id == created.run_id

    assert _cancel_event_count(created.run_id) == 1
    with SessionLocal() as session:
        # The running Job keeps the Run non-terminal after the first request;
        # a legacy call must still observe the requested state, not duplicate it.
        third = request_cancel(session, run_id=created.run_id)
        assert third.cancel_requested_at is not None
    assert _cancel_event_count(created.run_id) == 1


def test_concurrent_cancel_from_two_sessions_has_no_duplicate_event() -> None:
    created, _ = _create_running()
    barrier = threading.Barrier(2)
    outcomes = []
    terminal_errors = []
    unexpected: list[BaseException] = []

    def cancel() -> None:
        try:
            with SessionLocal() as session:
                barrier.wait(timeout=5)
                outcomes.append(request_cancel_outcome(session, run_id=created.run_id))
        except RunNotCancellable as exc:
            terminal_errors.append(exc)
        except BaseException as exc:  # noqa: BLE001 - asserted below
            unexpected.append(exc)

    threads = [threading.Thread(target=cancel) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert not any(thread.is_alive() for thread in threads), "cancel deadlocked"
    assert not unexpected, unexpected
    assert len(outcomes) + len(terminal_errors) == 2
    if len(outcomes) == 2:
        assert sorted(outcome.already_requested for outcome in outcomes) == [False, True]
    else:
        assert len(outcomes) == 1 and len(terminal_errors) == 1
    assert _cancel_event_count(created.run_id) == 1


def _terminal_events(run_id: str) -> list[str]:
    with SessionLocal() as session:
        return [
            event.type
            for event in session.scalars(
                select(ExecutionEvent)
                .where(
                    ExecutionEvent.run_id == run_id,
                    ExecutionEvent.type.in_(("job.succeeded", "job.cancelled")),
                )
                .order_by(ExecutionEvent.id)
            ).all()
        ]


def test_cancel_committed_before_finish_wins() -> None:
    created, claimed = _create_running()
    with SessionLocal() as session:
        outcome = request_cancel_outcome(session, run_id=created.run_id)
        assert outcome.already_requested is False

    with SessionLocal() as session:
        finished = finish_job(
            session,
            job_id=claimed.job_id,
            lease_token=claimed.lease_token,
            attempt_id=claimed.attempt_id,
            result=StepResult(status="succeeded", processed_count=1),
        )
        assert finished.status == "cancelled"

    with SessionLocal() as session:
        job = session.get(ExecutionJob, claimed.job_id)
        attempt = session.get(ExecutionJobAttempt, claimed.attempt_id)
        assert job is not None and job.status == "cancelled"
        assert attempt is not None and attempt.status == "cancelled"
    assert _terminal_events(created.run_id) == ["job.cancelled"]


def test_finish_committed_before_cancel_is_terminal() -> None:
    created, claimed = _create_running()
    with SessionLocal() as session:
        finished = finish_job(
            session,
            job_id=claimed.job_id,
            lease_token=claimed.lease_token,
            attempt_id=claimed.attempt_id,
            result=StepResult(status="succeeded", processed_count=1),
        )
        assert finished.status == "succeeded"

    with SessionLocal() as session:
        try:
            request_cancel_outcome(session, run_id=created.run_id)
        except RunNotCancellable:
            pass
        else:
            raise AssertionError("a terminal Run must not be cancellable")

    with SessionLocal() as session:
        job = session.get(ExecutionJob, claimed.job_id)
        assert job is not None and job.status == "succeeded"
    assert _terminal_events(created.run_id) == ["job.succeeded"]


def test_finish_and_cancel_concurrently_only_one_terminal_wins() -> None:
    created, claimed = _create_running()
    barrier = threading.Barrier(2)
    finish_results = []
    finish_errors: list[BaseException] = []
    cancel_outcomes = []
    cancel_errors: list[BaseException] = []

    def finish() -> None:
        try:
            with SessionLocal() as session:
                barrier.wait(timeout=5)
                finish_results.append(
                    finish_job(
                        session,
                        job_id=claimed.job_id,
                        lease_token=claimed.lease_token,
                        attempt_id=claimed.attempt_id,
                        result=StepResult(status="succeeded", processed_count=1),
                    )
                )
        except BaseException as exc:  # noqa: BLE001 - asserted below
            finish_errors.append(exc)

    def cancel() -> None:
        try:
            with SessionLocal() as session:
                barrier.wait(timeout=5)
                cancel_outcomes.append(
                    request_cancel_outcome(session, run_id=created.run_id)
                )
        except RunNotCancellable as exc:
            cancel_errors.append(exc)
        except BaseException as exc:  # noqa: BLE001
            cancel_errors.append(exc)

    threads = [threading.Thread(target=finish), threading.Thread(target=cancel)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert not any(thread.is_alive() for thread in threads), "finish/cancel deadlocked"
    assert not finish_errors, finish_errors
    with SessionLocal() as session:
        job = session.get(ExecutionJob, claimed.job_id)
        attempt = session.get(ExecutionJobAttempt, claimed.attempt_id)
        assert job is not None and attempt is not None
        events = _terminal_events(created.run_id)

    if job.status == "succeeded":
        assert attempt.status == "succeeded"
        assert events == ["job.succeeded"]
        assert not cancel_outcomes
        assert len(cancel_errors) == 1
        assert isinstance(cancel_errors[0], RunNotCancellable)
    else:
        assert job.status == "cancelled"
        assert attempt.status == "cancelled"
        assert events == ["job.cancelled"]
        assert len(cancel_outcomes) == 1
        assert cancel_outcomes[0].already_requested is False
