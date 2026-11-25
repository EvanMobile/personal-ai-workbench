"""R3.1: public Execution read DTOs and cursor event pagination."""

from __future__ import annotations

from app.core.db import SessionLocal
from app.modules.execution.models import ExecutionEvent, ExecutionRun
from app.modules.execution.read_models import sanitize_text
from app.modules.execution.results import StepResult
from app.modules.execution.service import (
    claim_job,
    create_run,
    create_run_with_step_job,
    finish_job,
    get_run_detail,
    get_run_execution_counts,
    get_run_summary,
    list_job_attempts,
    list_run_events,
    list_run_steps,
    list_step_jobs,
    payload_hash,
)


def _created_run():
    with SessionLocal() as session:
        created = create_run_with_step_job(
            session,
            scope_type="test_scope",
            scope_id="scope_read",
            pipeline="test_pipeline",
            stage="test_stage",
            config_snapshot={"kind": "test.read", "api_key": "config-secret"},
            config_hash="a" * 64,
            fingerprint="b" * 64,
            step_key="stage",
            ordinal=1,
            job_key="job",
            kind="test.read",
            payload={"secret": "payload-secret"},
            idempotency_key="read-key",
            idempotency_payload_hash=payload_hash({"kind": "test.read"}),
        )
    return created


def test_run_detail_steps_jobs_attempts_and_safe_fields() -> None:
    created = _created_run()
    with SessionLocal() as session:
        claimed = claim_job(session, worker_id="read-worker", lease_seconds=60)
        assert claimed is not None and claimed.run_id == created.run_id
        finish_job(
            session,
            job_id=claimed.job_id,
            lease_token=claimed.lease_token,
            attempt_id=claimed.attempt_id,
            result=StepResult(
                status="succeeded",
                processed_count=1,
                result={"count": 1, "api_key": "result-secret"},
                error_code="OK",
            ),
        )
        run = session.get(ExecutionRun, created.run_id)
        assert run is not None
        run.error_detail = "failed at /Users/private/source.txt"
        run.config_snapshot = {"safe": 1, "authorization": "Bearer secret"}
        session.commit()
        session.add(
            ExecutionEvent(
                run_id=created.run_id,
                type="test.secret",
                message="path /Users/private/source.txt",
                payload={"password": "event-secret", "count": 2},
            )
        )
        session.commit()

    with SessionLocal() as session:
        detail = get_run_detail(session, run_id=created.run_id)
        assert detail is not None
        assert detail.run.status == "succeeded"
        assert detail.result is not None
        assert detail.result["count"] == 1
        assert detail.result["api_key"] == "[REDACTED]"
        assert detail.config_snapshot["safe"] == 1
        assert detail.config_snapshot["authorization"] == "[REDACTED]"
        assert detail.error_detail == "[REDACTED_PATH]"
        assert len(detail.steps) == 1
        step = detail.steps[0]
        assert step.step_key == "stage"
        assert len(step.jobs) == 1
        job = step.jobs[0]
        assert job.kind == "test.read"
        assert job.status == "succeeded"
        assert len(job.attempts_history) == 1
        attempt = job.attempts_history[0]
        assert attempt.status == "succeeded"
        assert not hasattr(job, "lease_token")
        assert not hasattr(job, "fencing_token")
        assert not hasattr(attempt, "fencing_token")

        summary = get_run_summary(session, run_id=created.run_id)
        assert summary is not None and summary.id == detail.run.id
        assert list_run_steps(session, run_id=created.run_id) == detail.steps
        assert list_step_jobs(session, step_id=step.id) == step.jobs
        assert list_job_attempts(session, job_id=job.id) == job.attempts_history

        events = list_run_events(session, run_id=created.run_id, after_id=0, limit=200)
        assert events is not None
        secret_event = next(event for event in events.items if event.type == "test.secret")
        assert secret_event.payload["password"] == "[REDACTED]"
        assert secret_event.payload["count"] == 2
        assert secret_event.message == "[REDACTED_PATH]"


def test_event_cursor_pagination_uses_limit_plus_one() -> None:
    created = _created_run()
    with SessionLocal() as session:
        for index in range(3):
            session.add(
                ExecutionEvent(
                    run_id=created.run_id,
                    type="test.event",
                    message=f"event {index}",
                    payload={"index": index},
                )
            )
        session.commit()

    with SessionLocal() as session:
        first = list_run_events(session, run_id=created.run_id, after_id=0, limit=2)
        assert first is not None
        assert len(first.items) == 2
        assert first.has_more is True
        assert first.next_after_id == first.items[-1].id

        second = list_run_events(
            session, run_id=created.run_id, after_id=first.next_after_id, limit=2
        )
        assert second is not None
        assert len(second.items) >= 1
        assert second.next_after_id >= first.next_after_id
        ids = [item.id for item in first.items] + [item.id for item in second.items]
        assert ids == sorted(ids)
        assert len(ids) == len(set(ids))

        all_ids = [item.id for item in first.items]
        cursor = first.next_after_id
        while second.has_more:
            page = list_run_events(
                session, run_id=created.run_id, after_id=cursor, limit=2
            )
            assert page is not None
            all_ids.extend(item.id for item in page.items)
            cursor = page.next_after_id
            second = page
        assert len(all_ids) == len(set(all_ids))


def test_event_page_rejects_bad_cursor_and_missing_run() -> None:
    with SessionLocal() as session:
        assert list_run_events(session, run_id="missing", after_id=0, limit=10) is None
        try:
            list_run_events(session, run_id="missing", after_id=-1, limit=10)
        except ValueError:
            pass
        else:
            raise AssertionError("negative cursor must be rejected")


def test_sanitize_text_covers_common_credential_shapes() -> None:
    samples = [
        "Bearer abcdef",
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.signature",
        "AKIAIOSFODNN7EXAMPLE",
        "ghp_abcdefghijklmnopqrstuvwxyz123456",
        "AIzaSyA1234567890abcdefghijklmnopqrst",
        "C:\\Users\\alice\\secret.txt",
        "-----BEGIN PRIVATE KEY-----",
        "postgresql://user:password@localhost/db",
        "api_key=super-secret",
    ]
    for sample in samples:
        assert sanitize_text(sample) == "[REDACTED_PATH]", sample


def test_run_execution_counts_are_public_and_business_neutral() -> None:
    created = _created_run()
    with SessionLocal() as session:
        counts = get_run_execution_counts(session, run_id=created.run_id)
        assert counts is not None
        assert counts.run_id == created.run_id
        assert counts.scope_id == "scope_read"
        assert (counts.run_count, counts.job_count, counts.event_count) == (1, 1, 0)

    with SessionLocal() as session:
        claimed = claim_job(session, worker_id="counts-worker", lease_seconds=60)
        assert claimed is not None and claimed.run_id == created.run_id
        finish_job(
            session,
            job_id=claimed.job_id,
            lease_token=claimed.lease_token,
            attempt_id=claimed.attempt_id,
            result=StepResult(status="succeeded", processed_count=1),
        )

    with SessionLocal() as session:
        counts = get_run_execution_counts(session, run_id=created.run_id)
        assert counts is not None
        assert counts.event_count >= 2

        # A Run without a Job/Event still has a valid zero-count read.
        empty, _ = create_run(
            session,
            scope_type="test_scope",
            scope_id="scope_read",
            pipeline="test_pipeline",
            stage="test_stage",
            config_snapshot={"kind": "empty"},
            config_hash="c" * 64,
            fingerprint="d" * 64,
        )
        empty_counts = get_run_execution_counts(session, run_id=empty.id)
        assert empty_counts is not None
        assert (empty_counts.run_count, empty_counts.job_count, empty_counts.event_count) == (2, 0, 0)
        assert get_run_execution_counts(session, run_id="missing") is None
