"""PostgreSQL-backed execution lifecycle service.

This module is deliberately synchronous and RAG-agnostic.  It owns the
transaction boundaries for claim/heartbeat/result/recovery and the pure
Step/Run aggregation calls.  It never imports M03 or M06.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import case, exists, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.utils import new_id, utcnow
from app.modules.execution.aggregation import aggregate_statuses, has_non_terminal
from app.modules.execution.config import ExecutionConfig
from app.modules.execution.errors import (
    IdempotencyConflict,
    RunIncomplete,
    RunNotCancellable,
    StaleLease,
)
from app.modules.execution.models import (
    ExecutionEvent,
    ExecutionJob,
    ExecutionJobAttempt,
    ExecutionRun,
    ExecutionStep,
)
from app.modules.execution.read_models import (
    AttemptView,
    CancelOutcome,
    EventPage,
    EventView,
    ExecutionEvidencePresence,
    JobView,
    RunDetail,
    RunExecutionCounts,
    RunSummary,
    ScopeExecutionStats,
    StepView,
    sanitize_json,
    sanitize_text,
)
from app.modules.execution.results import StepResult

STEP_NON_TERMINAL = frozenset({"pending", "running"})


@dataclass(frozen=True)
class RunCreationResult:
    run_id: str
    step_id: str
    job_id: str
    reused: bool
    run: RunSummary


@dataclass(frozen=True)
class ClaimedJob:
    job_id: str
    run_id: str
    step_id: str
    attempt_id: str
    attempt_no: int
    lease_token: int
    kind: str
    payload: dict[str, Any]


def payload_hash(payload: dict[str, Any]) -> str:
    """Canonical JSON SHA-256 used for Run idempotency comparison."""
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def create_run(
    session: Session,
    *,
    scope_type: str,
    scope_id: str,
    pipeline: str,
    stage: str,
    config_snapshot: dict[str, Any],
    config_hash: str,
    fingerprint: str,
    idempotency_key: str | None = None,
    idempotency_payload_hash: str | None = None,
    parent_run_id: str | None = None,
    app_git_sha: str | None = None,
) -> tuple[ExecutionRun, bool]:
    """Create a Run, or return the existing Run for an identical idempotency key."""
    if idempotency_key is not None and idempotency_payload_hash is None:
        raise ValueError("idempotency_payload_hash is required with idempotency_key")
    if idempotency_key is not None:
        existing = session.scalar(
            select(ExecutionRun).where(
                ExecutionRun.scope_type == scope_type,
                ExecutionRun.scope_id == scope_id,
                ExecutionRun.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            if existing.idempotency_payload_hash != idempotency_payload_hash:
                raise IdempotencyConflict(
                    "idempotency key reused with a different payload"
                )
            return existing, True

    run = ExecutionRun(
        id=new_id("rrun"),
        scope_type=scope_type,
        scope_id=scope_id,
        pipeline=pipeline,
        stage=stage,
        status="queued",
        config_snapshot=config_snapshot,
        config_hash=config_hash,
        fingerprint=fingerprint,
        idempotency_key=idempotency_key,
        idempotency_payload_hash=idempotency_payload_hash,
        parent_run_id=parent_run_id,
        app_git_sha=app_git_sha,
    )
    session.add(run)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.scalar(
            select(ExecutionRun).where(
                ExecutionRun.scope_type == scope_type,
                ExecutionRun.scope_id == scope_id,
                ExecutionRun.idempotency_key == idempotency_key,
            )
        )
        if existing is None:
            raise
        if existing.idempotency_payload_hash != idempotency_payload_hash:
            raise IdempotencyConflict(
                "idempotency key reused with a different payload"
            ) from None
        return existing, True
    session.refresh(run)
    return run, False


def create_step(
    session: Session,
    *,
    run_id: str,
    step_key: str,
    ordinal: int,
) -> ExecutionStep:
    step = ExecutionStep(
        id=new_id("rstp"),
        run_id=run_id,
        step_key=step_key,
        ordinal=ordinal,
        status="pending",
        progress=0,
        processed_count=0,
        failed_count=0,
    )
    session.add(step)
    session.commit()
    session.refresh(step)
    return step


def create_job(
    session: Session,
    *,
    run_id: str,
    step_id: str,
    job_key: str,
    kind: str,
    payload: dict[str, Any] | None = None,
    max_attempts: int = 3,
) -> ExecutionJob:
    job = ExecutionJob(
        id=new_id("rjob"),
        run_id=run_id,
        step_id=step_id,
        job_key=job_key,
        kind=kind,
        status="queued",
        payload=payload or {},
        attempts=0,
        max_attempts=max_attempts,
        lease_token=0,
        available_at=utcnow(),
        processed_count=0,
        failed_count=0,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def _find_idempotent_run(
    session: Session,
    *,
    scope_type: str,
    scope_id: str,
    idempotency_key: str | None,
) -> ExecutionRun | None:
    if idempotency_key is None:
        return None
    return session.scalar(
        select(ExecutionRun).where(
            ExecutionRun.scope_type == scope_type,
            ExecutionRun.scope_id == scope_id,
            ExecutionRun.idempotency_key == idempotency_key,
        )
    )


def _existing_creation(
    session: Session,
    *,
    run: ExecutionRun,
    step_key: str,
    job_key: str,
) -> RunCreationResult:
    step = session.scalar(
        select(ExecutionStep).where(
            ExecutionStep.run_id == run.id,
            ExecutionStep.step_key == step_key,
        )
    )
    if step is None:
        raise RunIncomplete(run.id, "step")
    job = session.scalar(
        select(ExecutionJob).where(
            ExecutionJob.run_id == run.id,
            ExecutionJob.job_key == job_key,
        )
    )
    if job is None or job.step_id != step.id:
        raise RunIncomplete(run.id, "job")
    return RunCreationResult(
        run_id=run.id,
        step_id=step.id,
        job_id=job.id,
        reused=True,
        run=_run_summary(run),
    )


def create_run_with_step_job(
    session: Session,
    *,
    scope_type: str,
    scope_id: str,
    pipeline: str,
    stage: str,
    config_snapshot: dict[str, Any],
    config_hash: str,
    fingerprint: str,
    step_key: str,
    ordinal: int,
    job_key: str,
    kind: str,
    payload: dict[str, Any] | None = None,
    max_attempts: int = 3,
    idempotency_key: str | None = None,
    idempotency_payload_hash: str | None = None,
    parent_run_id: str | None = None,
    app_git_sha: str | None = None,
    now: datetime | None = None,
) -> RunCreationResult:
    """Create Run + Step + Job atomically, or reuse an idempotent Run.

    The entire aggregate is flushed and committed exactly once.  A failure in
    any insert rolls back the whole transaction; no Run-only/Step-only row is
    left behind.  On an idempotency unique-constraint race, the failed
    transaction is rolled back before a fresh lookup.
    """
    if idempotency_key is not None and idempotency_payload_hash is None:
        raise ValueError("idempotency_payload_hash is required with idempotency_key")
    now = now or utcnow()

    existing = _find_idempotent_run(
        session,
        scope_type=scope_type,
        scope_id=scope_id,
        idempotency_key=idempotency_key,
    )
    if existing is not None:
        if existing.idempotency_payload_hash != idempotency_payload_hash:
            raise IdempotencyConflict("idempotency key reused with a different payload")
        return _existing_creation(
            session, run=existing, step_key=step_key, job_key=job_key
        )

    run = ExecutionRun(
        id=new_id("rrun"),
        scope_type=scope_type,
        scope_id=scope_id,
        pipeline=pipeline,
        stage=stage,
        status="queued",
        config_snapshot=config_snapshot,
        config_hash=config_hash,
        fingerprint=fingerprint,
        idempotency_key=idempotency_key,
        idempotency_payload_hash=idempotency_payload_hash,
        parent_run_id=parent_run_id,
        app_git_sha=app_git_sha,
    )
    step = ExecutionStep(
        id=new_id("rstp"),
        run_id=run.id,
        step_key=step_key,
        ordinal=ordinal,
        status="pending",
        progress=0,
        processed_count=0,
        failed_count=0,
    )
    job = ExecutionJob(
        id=new_id("rjob"),
        run_id=run.id,
        step_id=step.id,
        job_key=job_key,
        kind=kind,
        status="queued",
        payload=payload or {},
        attempts=0,
        max_attempts=max_attempts,
        lease_token=0,
        available_at=now,
        processed_count=0,
        failed_count=0,
    )
    try:
        # Explicit flush order keeps the FK graph deterministic (Run → Step →
        # Job) while still using one transaction and exactly one COMMIT.
        session.add(run)
        session.flush()
        session.add(step)
        session.flush()
        session.add(job)
        session.flush()
        session.commit()
    except IntegrityError:
        # The failed transaction must be discarded before any new read.
        session.rollback()
        session.expire_all()
        existing = _find_idempotent_run(
            session,
            scope_type=scope_type,
            scope_id=scope_id,
            idempotency_key=idempotency_key,
        )
        if existing is None:
            raise
        if existing.idempotency_payload_hash != idempotency_payload_hash:
            raise IdempotencyConflict(
                "idempotency key reused with a different payload"
            ) from None
        return _existing_creation(
            session, run=existing, step_key=step_key, job_key=job_key
        )
    except Exception:
        session.rollback()
        raise

    return RunCreationResult(
        run_id=run.id,
        step_id=step.id,
        job_id=job.id,
        reused=False,
        run=_run_summary(run),
    )


def _event(
    session: Session,
    *,
    run_id: str,
    step_id: str | None,
    job_id: str | None,
    event_type: str,
    message: str,
    payload: dict[str, Any] | None = None,
    level: str = "info",
) -> None:
    session.add(
        ExecutionEvent(
            run_id=run_id,
            step_id=step_id,
            job_id=job_id,
            type=event_type,
            level=level,
            message=message,
            payload=payload or {},
        )
    )


def claim_job(
    session: Session,
    *,
    worker_id: str,
    lease_seconds: int,
    now: datetime | None = None,
) -> ClaimedJob | None:
    """Claim one queued Job with FOR UPDATE SKIP LOCKED.

    Lock order is Job → Step → Run everywhere that mutates execution state.
    """
    now = now or utcnow()
    job = session.scalar(
        select(ExecutionJob)
        .where(
            ExecutionJob.status == "queued",
            ExecutionJob.available_at <= now,
        )
        .order_by(ExecutionJob.created_at, ExecutionJob.id)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if job is None:
        session.rollback()
        return None

    step = session.get(ExecutionStep, job.step_id, with_for_update=True)
    run = session.get(ExecutionRun, job.run_id, with_for_update=True)
    if step is None or run is None:
        session.rollback()
        raise StaleLease("job references a missing Run/Step")

    job.status = "running"
    job.locked_at = now
    job.locked_by = worker_id
    job.lease_token += 1
    job.attempts += 1
    job.last_heartbeat_at = now
    job.lease_expires_at = now + timedelta(seconds=lease_seconds)
    job.error_code = None
    job.error_detail = None
    job.updated_at = now
    if run.cancel_requested_at is not None:
        job.cancel_requested_at = run.cancel_requested_at

    if step.status == "pending":
        step.status = "running"
        step.updated_at = now
    if run.status == "queued":
        run.status = "running"
        run.updated_at = now

    attempt = ExecutionJobAttempt(
        id=new_id("ratt"),
        job_id=job.id,
        attempt_no=job.attempts,
        status="running",
        worker_id=worker_id,
        fencing_token=job.lease_token,
        started_at=now,
        metrics={},
    )
    session.add(attempt)
    _event(
        session,
        run_id=job.run_id,
        step_id=job.step_id,
        job_id=job.id,
        event_type="job.claimed",
        message="job claimed",
        payload={
            "worker_id": worker_id,
            "attempt_no": attempt.attempt_no,
            "lease_token": job.lease_token,
        },
    )
    session.commit()
    return ClaimedJob(
        job_id=job.id,
        run_id=job.run_id,
        step_id=job.step_id,
        attempt_id=attempt.id,
        attempt_no=attempt.attempt_no,
        lease_token=job.lease_token,
        kind=job.kind,
        payload=dict(job.payload or {}),
    )


@dataclass(frozen=True)
class HeartbeatResult:
    valid: bool
    cancel_requested: bool


def heartbeat(
    session: Session,
    *,
    job_id: str,
    lease_token: int,
    lease_seconds: int,
    now: datetime | None = None,
) -> HeartbeatResult:
    """Renew a lease only while it is still unexpired and token-current."""
    now = now or utcnow()
    row = session.execute(
        update(ExecutionJob)
        .where(
            ExecutionJob.id == job_id,
            ExecutionJob.status == "running",
            ExecutionJob.lease_token == lease_token,
            ExecutionJob.lease_expires_at > now,
        )
        .values(
            last_heartbeat_at=now,
            lease_expires_at=now + timedelta(seconds=lease_seconds),
            updated_at=now,
        )
        .returning(ExecutionJob.cancel_requested_at)
    ).first()
    session.commit()
    if row is None:
        return HeartbeatResult(valid=False, cancel_requested=False)
    return HeartbeatResult(valid=True, cancel_requested=row[0] is not None)


def _refresh_step(session: Session, *, step_id: str, run_id: str) -> None:
    """Recompute a Step from its full Job set while holding the Step row lock."""
    step = session.get(ExecutionStep, step_id, with_for_update=True)
    if step is None:
        return
    if step.run_id != run_id:
        raise StaleLease("step does not belong to run")

    jobs = list(
        session.scalars(select(ExecutionJob).where(ExecutionJob.step_id == step_id)).all()
    )
    if not jobs:
        if step.status != "cancelled":
            step.status = "skipped"
        step.progress = 100
        step.updated_at = utcnow()
        return
    statuses = [job.status for job in jobs]
    if has_non_terminal(statuses):
        if "running" in statuses or step.status not in STEP_NON_TERMINAL:
            step.status = "running"
        elif step.status != "pending":
            step.status = "running"
        step.updated_at = utcnow()
        return

    step.status = aggregate_statuses(statuses)
    step.processed_count = sum(job.processed_count for job in jobs)
    step.failed_count = sum(job.failed_count for job in jobs)
    step.progress = 100
    step.updated_at = utcnow()


def _refresh_run(session: Session, *, run_id: str) -> None:
    """Recompute a Run from its full Step set while holding the Run row lock."""
    run = session.get(ExecutionRun, run_id, with_for_update=True)
    if run is None:
        return
    steps = list(
        session.scalars(select(ExecutionStep).where(ExecutionStep.run_id == run_id)).all()
    )
    statuses = [step.status for step in steps]
    if has_non_terminal(statuses):
        if "running" in statuses:
            run.status = "running"
        elif run.status not in {"queued", "running"}:
            run.status = "running"
        run.updated_at = utcnow()
        return
    run.status = aggregate_statuses(statuses)
    run.updated_at = utcnow()


def _lock_current_job(
    session: Session,
    *,
    job_id: str,
    lease_token: int,
    now: datetime,
) -> ExecutionJob | None:
    return session.scalar(
        select(ExecutionJob)
        .where(
            ExecutionJob.id == job_id,
            ExecutionJob.status == "running",
            ExecutionJob.lease_token == lease_token,
            ExecutionJob.lease_expires_at > now,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def _lock_current_attempt(
    session: Session,
    *,
    job_id: str,
    attempt_id: str,
    lease_token: int,
) -> ExecutionJobAttempt | None:
    return session.scalar(
        select(ExecutionJobAttempt)
        .where(
            ExecutionJobAttempt.id == attempt_id,
            ExecutionJobAttempt.job_id == job_id,
            ExecutionJobAttempt.status == "running",
            ExecutionJobAttempt.fencing_token == lease_token,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def _commit_cancelled_job(
    session: Session,
    *,
    job: ExecutionJob,
    attempt: ExecutionJobAttempt,
    now: datetime,
    processed_count: int,
    failed_count: int,
    detail: str,
) -> ExecutionJob:
    """Commit cancellation after the Job lock proves Cancel won the race."""
    attempt.status = "cancelled"
    attempt.finished_at = now
    attempt.error_code = "CANCELLED"
    attempt.error_detail = detail
    attempt.metrics = {"job_status": "cancelled"}
    job.status = "cancelled"
    job.processed_count = processed_count
    job.failed_count = failed_count
    job.error_code = "CANCELLED"
    job.error_detail = detail
    job.locked_at = None
    job.locked_by = None
    job.lease_expires_at = None
    job.updated_at = now
    _event(
        session,
        run_id=job.run_id,
        step_id=job.step_id,
        job_id=job.id,
        event_type="job.cancelled",
        message="job cancelled before result commit",
        payload={
            "attempt_no": attempt.attempt_no,
            "processed_count": processed_count,
            "failed_count": failed_count,
        },
    )
    _refresh_step(session, step_id=job.step_id, run_id=job.run_id)
    _refresh_run(session, run_id=job.run_id)
    session.commit()
    session.refresh(job)
    return job


def finish_job(
    session: Session,
    *,
    job_id: str,
    lease_token: int,
    attempt_id: str,
    result: StepResult,
    now: datetime | None = None,
) -> ExecutionJob:
    """Commit a handler result only if the caller still owns the lease."""
    now = now or utcnow()
    job = _lock_current_job(session, job_id=job_id, lease_token=lease_token, now=now)
    attempt = _lock_current_attempt(
        session, job_id=job_id, attempt_id=attempt_id, lease_token=lease_token
    )
    if job is None or attempt is None:
        session.rollback()
        raise StaleLease("lease/token no longer owns this job attempt")

    # Cancel and Finish both lock the Job row.  Whichever locks first wins.
    # If Cancel already committed, never let a late Handler result overwrite it.
    if job.cancel_requested_at is not None:
        return _commit_cancelled_job(
            session,
            job=job,
            attempt=attempt,
            now=now,
            processed_count=result.processed_count,
            failed_count=result.failed_count,
            detail="cancel requested before result commit",
        )

    attempt.finished_at = now
    attempt.error_code = result.error_code
    attempt.metrics = {"job_status": result.status}
    if result.status in {"succeeded", "partial", "skipped"}:
        attempt.status = "succeeded"
    elif result.status == "cancelled":
        attempt.status = "cancelled"
    else:
        attempt.status = "failed"

    job.status = result.status
    job.processed_count = result.processed_count
    job.failed_count = result.failed_count
    job.error_code = result.error_code
    job.error_detail = None
    job.locked_at = None
    job.locked_by = None
    job.lease_expires_at = None
    job.updated_at = now
    _event(
        session,
        run_id=job.run_id,
        step_id=job.step_id,
        job_id=job.id,
        event_type=f"job.{result.status}",
        message=f"job {result.status}",
        payload={
            "attempt_no": attempt.attempt_no,
            "processed_count": result.processed_count,
            "failed_count": result.failed_count,
        },
    )
    _refresh_step(session, step_id=job.step_id, run_id=job.run_id)
    _refresh_run(session, run_id=job.run_id)
    if result.result is not None:
        # _refresh_run already locked the Run row; keep the Step → Run lock order.
        run = session.get(ExecutionRun, job.run_id)
        if run is not None:
            run.result = result.result
    session.commit()
    session.refresh(job)
    return job


def fail_job(
    session: Session,
    *,
    job_id: str,
    lease_token: int,
    attempt_id: str,
    error_code: str,
    error_detail: str,
    retryable: bool,
    config: ExecutionConfig,
    now: datetime | None = None,
) -> ExecutionJob:
    """Mark an Attempt failed and either requeue with backoff or fail the Job."""
    now = now or utcnow()
    job = _lock_current_job(session, job_id=job_id, lease_token=lease_token, now=now)
    attempt = _lock_current_attempt(
        session, job_id=job_id, attempt_id=attempt_id, lease_token=lease_token
    )
    if job is None or attempt is None:
        session.rollback()
        raise StaleLease("lease/token no longer owns this job attempt")

    if job.cancel_requested_at is not None:
        return _commit_cancelled_job(
            session,
            job=job,
            attempt=attempt,
            now=now,
            processed_count=job.processed_count,
            failed_count=job.failed_count,
            detail="cancel requested before failure commit",
        )

    attempt.status = "failed"
    attempt.finished_at = now
    attempt.error_code = error_code
    attempt.error_detail = error_detail
    job.error_code = error_code
    job.error_detail = error_detail
    job.locked_at = None
    job.locked_by = None
    job.lease_expires_at = None
    job.updated_at = now

    should_retry = retryable and job.attempts < job.max_attempts
    if should_retry:
        job.status = "queued"
        job.available_at = now + timedelta(seconds=config.retry_delay(job.attempts))
        event_type = "job.retrying"
        message = "job failed; retry scheduled"
    else:
        job.status = "failed"
        event_type = "job.failed"
        message = "job failed terminally"
    _event(
        session,
        run_id=job.run_id,
        step_id=job.step_id,
        job_id=job.id,
        event_type=event_type,
        message=message,
        payload={"attempt_no": attempt.attempt_no, "error_code": error_code},
        level="warning",
    )
    _refresh_step(session, step_id=job.step_id, run_id=job.run_id)
    _refresh_run(session, run_id=job.run_id)
    session.commit()
    session.refresh(job)
    return job


def abandon_for_shutdown(
    session: Session,
    *,
    job_id: str,
    lease_token: int,
    attempt_id: str,
    config: ExecutionConfig,
    now: datetime | None = None,
) -> bool:
    """End an in-flight Attempt during graceful shutdown and requeue/fail its Job."""
    now = now or utcnow()
    job = _lock_current_job(session, job_id=job_id, lease_token=lease_token, now=now)
    attempt = _lock_current_attempt(
        session, job_id=job_id, attempt_id=attempt_id, lease_token=lease_token
    )
    if job is None or attempt is None:
        session.rollback()
        return False

    if job.cancel_requested_at is not None:
        _commit_cancelled_job(
            session,
            job=job,
            attempt=attempt,
            now=now,
            processed_count=job.processed_count,
            failed_count=job.failed_count,
            detail="cancel requested before shutdown abandon",
        )
        return True

    attempt.status = "abandoned"
    attempt.finished_at = now
    attempt.error_code = "WORKER_SHUTDOWN"
    attempt.error_detail = "worker graceful shutdown"
    if job.attempts >= job.max_attempts:
        job.status = "failed"
    else:
        job.status = "queued"
        job.available_at = now
    job.error_code = "WORKER_SHUTDOWN"
    job.error_detail = "worker graceful shutdown; attempt abandoned"
    job.locked_at = None
    job.locked_by = None
    job.lease_expires_at = None
    job.updated_at = now
    _event(
        session,
        run_id=job.run_id,
        step_id=job.step_id,
        job_id=job.id,
        event_type="job.attempt_abandoned",
        message="attempt abandoned during graceful shutdown",
        payload={"attempt_no": attempt.attempt_no, "error_code": "WORKER_SHUTDOWN"},
        level="warning",
    )
    _event(
        session,
        run_id=job.run_id,
        step_id=job.step_id,
        job_id=job.id,
        event_type="job.requeued" if job.status == "queued" else "job.failed",
        message=f"job {job.status} after shutdown",
        payload={"attempt_no": attempt.attempt_no},
    )
    _refresh_step(session, step_id=job.step_id, run_id=job.run_id)
    _refresh_run(session, run_id=job.run_id)
    session.commit()
    return True


def recover_expired(
    session: Session,
    *,
    config: ExecutionConfig,
    now: datetime | None = None,
) -> int:
    """Reclaim running Jobs whose lease expired; only expired leases are touched."""
    now = now or utcnow()
    jobs = list(
        session.scalars(
            select(ExecutionJob)
            .where(
                ExecutionJob.status == "running",
                ExecutionJob.lease_expires_at < now,
            )
            .order_by(ExecutionJob.id)
            .with_for_update(skip_locked=True)
        ).all()
    )
    for job in jobs:
        attempts = list(
            session.scalars(
                select(ExecutionJobAttempt)
                .where(
                    ExecutionJobAttempt.job_id == job.id,
                    ExecutionJobAttempt.status == "running",
                )
                .with_for_update()
            ).all()
        )
        for attempt in attempts:
            attempt.status = "abandoned"
            attempt.finished_at = now
            attempt.error_code = "WORKER_LOST"
            attempt.error_detail = "worker lease expired; recovery reclaimed job"
        if job.cancel_requested_at is not None:
            job.status = "cancelled"
            job.error_code = "CANCELLED"
            job.error_detail = "cancel requested before lease expiry recovery"
            event_type = "job.cancelled"
        elif job.attempts >= job.max_attempts:
            job.status = "failed"
            job.error_code = "WORKER_LOST"
            job.error_detail = "worker lease expired; attempt abandoned"
            event_type = "job.failed"
        else:
            job.status = "queued"
            job.available_at = now
            job.error_code = "WORKER_LOST"
            job.error_detail = "worker lease expired; attempt abandoned"
            event_type = "job.requeued"
        job.locked_at = None
        job.locked_by = None
        job.lease_expires_at = None
        job.updated_at = now
        _event(
            session,
            run_id=job.run_id,
            step_id=job.step_id,
            job_id=job.id,
            event_type="job.attempt_abandoned",
            message="attempt abandoned after lease expiry",
            payload={"attempt_no": attempts[0].attempt_no if attempts else None},
            level="warning",
        )
        _event(
            session,
            run_id=job.run_id,
            step_id=job.step_id,
            job_id=job.id,
            event_type=event_type,
            message=f"job {job.status} after recovery",
            payload={"error_code": "WORKER_LOST"},
        )
        _refresh_step(session, step_id=job.step_id, run_id=job.run_id)
        _refresh_run(session, run_id=job.run_id)
    session.commit()
    return len(jobs)


def _request_cancel_locked(
    session: Session,
    *,
    run_id: str,
    now: datetime,
) -> tuple[ExecutionRun, bool]:
    """Shared Cancel implementation; locks Job → Step → Run before writes."""
    run = session.get(ExecutionRun, run_id)
    if run is None:
        raise RunNotCancellable("run not found")
    if run.status not in {"queued", "running"}:
        raise RunNotCancellable("terminal run cannot be cancelled")

    # Lock in the global order Job → Step → Run before any dirty Run state.
    with session.no_autoflush:
        jobs = list(
            session.scalars(
                select(ExecutionJob)
                .where(
                    ExecutionJob.run_id == run_id,
                    ExecutionJob.status.in_(("queued", "running")),
                )
                .order_by(ExecutionJob.id)
                .with_for_update()
            ).all()
        )
        steps = list(
            session.scalars(
                select(ExecutionStep)
                .where(ExecutionStep.run_id == run_id)
                .order_by(ExecutionStep.ordinal)
                .with_for_update()
            ).all()
        )
        run = session.scalar(
            select(ExecutionRun)
            .where(ExecutionRun.id == run_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    if run is None or run.status not in {"queued", "running"}:
        session.rollback()
        raise RunNotCancellable("terminal run cannot be cancelled")

    # Idempotent repeated Cancel: all locks are held, but no Event is written.
    if run.cancel_requested_at is not None:
        session.commit()
        session.refresh(run)
        return run, True

    touched_steps: set[str] = set()
    for job in jobs:
        if job.status == "queued":
            job.status = "cancelled"
            job.error_code = "CANCELLED"
            job.error_detail = "run cancelled before claim"
            job.available_at = now
            job.updated_at = now
            _event(
                session,
                run_id=job.run_id,
                step_id=job.step_id,
                job_id=job.id,
                event_type="job.cancelled",
                message="queued job cancelled",
                payload={},
            )
        else:
            job.cancel_requested_at = now
            job.updated_at = now
            _event(
                session,
                run_id=job.run_id,
                step_id=job.step_id,
                job_id=job.id,
                event_type="job.cancel_requested",
                message="running job cancellation requested",
                payload={},
            )
        touched_steps.add(job.step_id)

    # Cancel pending Steps that have no Jobs; otherwise such a Run can never
    # reach a terminal state after cancellation.
    for step in steps:
        has_job = session.scalar(
            select(ExecutionJob.id).where(ExecutionJob.step_id == step.id).limit(1)
        )
        if has_job is None and step.status in {"pending", "running"}:
            step.status = "cancelled"
            step.updated_at = now
            touched_steps.add(step.id)
            _event(
                session,
                run_id=run_id,
                step_id=step.id,
                job_id=None,
                event_type="step.cancelled",
                message="empty step cancelled",
                payload={},
            )

    run.cancel_requested_at = now
    run.updated_at = now

    for step_id in sorted(touched_steps):
        _refresh_step(session, step_id=step_id, run_id=run_id)
    _refresh_run(session, run_id=run_id)
    if run.status == "skipped" and run.cancel_requested_at is not None:
        run.status = "cancelled"
    session.commit()
    session.refresh(run)
    return run, False


def request_cancel(session: Session, *, run_id: str, now: datetime | None = None) -> ExecutionRun:
    """Backward-compatible Cancel entry point returning the ORM Run."""
    run, _ = _request_cancel_locked(session, run_id=run_id, now=now or utcnow())
    return run


def request_cancel_outcome(
    session: Session,
    *,
    run_id: str,
    now: datetime | None = None,
) -> CancelOutcome:
    """Cancel with lock-held idempotency, returning an immutable DTO."""
    run, already_requested = _request_cancel_locked(
        session, run_id=run_id, now=now or utcnow()
    )
    return CancelOutcome(run=_run_summary(run), already_requested=already_requested)


def _run_summary(run: ExecutionRun) -> RunSummary:
    return RunSummary(
        id=run.id,
        scope_type=run.scope_type,
        scope_id=run.scope_id,
        pipeline=run.pipeline,
        stage=run.stage,
        status=run.status,
        created_at=run.created_at,
        updated_at=run.updated_at,
        cancel_requested_at=run.cancel_requested_at,
        error_code=run.error_code,
    )


def _attempt_view(attempt: ExecutionJobAttempt) -> AttemptView:
    return AttemptView(
        id=attempt.id,
        job_id=attempt.job_id,
        attempt_no=attempt.attempt_no,
        status=attempt.status,
        worker_id=attempt.worker_id,
        started_at=attempt.started_at,
        finished_at=attempt.finished_at,
        error_code=attempt.error_code,
        error_detail=sanitize_text(attempt.error_detail),
        metrics=sanitize_json(attempt.metrics or {}),
    )


def _job_view(job: ExecutionJob, attempts: tuple[ExecutionJobAttempt, ...]) -> JobView:
    return JobView(
        id=job.id,
        run_id=job.run_id,
        step_id=job.step_id,
        job_key=job.job_key,
        kind=job.kind,
        status=job.status,
        attempts=job.attempts,
        max_attempts=job.max_attempts,
        available_at=job.available_at,
        locked_by=job.locked_by,
        last_heartbeat_at=job.last_heartbeat_at,
        lease_expires_at=job.lease_expires_at,
        cancel_requested_at=job.cancel_requested_at,
        processed_count=job.processed_count,
        failed_count=job.failed_count,
        error_code=job.error_code,
        error_detail=sanitize_text(job.error_detail),
        created_at=job.created_at,
        updated_at=job.updated_at,
        attempts_history=tuple(_attempt_view(attempt) for attempt in attempts),
    )


def _step_view(step: ExecutionStep, jobs: tuple[JobView, ...]) -> StepView:
    return StepView(
        id=step.id,
        run_id=step.run_id,
        step_key=step.step_key,
        ordinal=step.ordinal,
        status=step.status,
        progress=step.progress,
        processed_count=step.processed_count,
        failed_count=step.failed_count,
        error_code=step.error_code,
        error_detail=sanitize_text(step.error_detail),
        created_at=step.created_at,
        updated_at=step.updated_at,
        jobs=jobs,
    )


def get_run_summary(session: Session, *, run_id: str) -> RunSummary | None:
    run = session.get(ExecutionRun, run_id)
    return _run_summary(run) if run is not None else None


def list_job_attempts(session: Session, *, job_id: str) -> tuple[AttemptView, ...]:
    attempts = tuple(
        session.scalars(
            select(ExecutionJobAttempt)
            .where(ExecutionJobAttempt.job_id == job_id)
            .order_by(ExecutionJobAttempt.attempt_no)
        ).all()
    )
    return tuple(_attempt_view(attempt) for attempt in attempts)


def list_step_jobs(session: Session, *, step_id: str) -> tuple[JobView, ...]:
    jobs = tuple(
        session.scalars(
            select(ExecutionJob)
            .where(ExecutionJob.step_id == step_id)
            .order_by(ExecutionJob.created_at, ExecutionJob.id)
        ).all()
    )
    return tuple(
        _job_view(
            job,
            tuple(
                session.scalars(
                    select(ExecutionJobAttempt)
                    .where(ExecutionJobAttempt.job_id == job.id)
                    .order_by(ExecutionJobAttempt.attempt_no)
                ).all()
            ),
        )
        for job in jobs
    )


def list_run_steps(session: Session, *, run_id: str) -> tuple[StepView, ...]:
    steps = tuple(
        session.scalars(
            select(ExecutionStep)
            .where(ExecutionStep.run_id == run_id)
            .order_by(ExecutionStep.ordinal, ExecutionStep.id)
        ).all()
    )
    return tuple(
        _step_view(
            step,
            tuple(
                _job_view(
                    job,
                    tuple(
                        session.scalars(
                            select(ExecutionJobAttempt)
                            .where(ExecutionJobAttempt.job_id == job.id)
                            .order_by(ExecutionJobAttempt.attempt_no)
                        ).all()
                    ),
                )
                for job in session.scalars(
                    select(ExecutionJob)
                    .where(ExecutionJob.step_id == step.id)
                    .order_by(ExecutionJob.created_at, ExecutionJob.id)
                ).all()
            ),
        )
        for step in steps
    )


def get_run_detail(session: Session, *, run_id: str) -> RunDetail | None:
    run = session.get(ExecutionRun, run_id)
    if run is None:
        return None
    return RunDetail(
        run=_run_summary(run),
        config_snapshot=sanitize_json(run.config_snapshot or {}),
        config_hash=run.config_hash,
        fingerprint=run.fingerprint,
        parent_run_id=run.parent_run_id,
        app_git_sha=run.app_git_sha,
        result=sanitize_json(run.result) if run.result is not None else None,
        error_detail=sanitize_text(run.error_detail),
        steps=list_run_steps(session, run_id=run_id),
    )


def list_run_events(
    session: Session,
    *,
    run_id: str,
    after_id: int = 0,
    limit: int = 50,
) -> EventPage | None:
    if after_id < 0:
        raise ValueError("after_id must be non-negative")
    if not 1 <= limit <= 200:
        raise ValueError("limit must be between 1 and 200")
    if session.get(ExecutionRun, run_id) is None:
        return None

    rows = tuple(
        session.scalars(
            select(ExecutionEvent)
            .where(
                ExecutionEvent.run_id == run_id,
                ExecutionEvent.id > after_id,
            )
            .order_by(ExecutionEvent.id)
            .limit(limit + 1)
        ).all()
    )
    has_more = len(rows) > limit
    visible = rows[:limit]
    items = tuple(
        EventView(
            id=event.id,
            run_id=event.run_id,
            step_id=event.step_id,
            job_id=event.job_id,
            type=event.type,
            level=event.level,
            message=sanitize_text(event.message) or "",
            payload=sanitize_json(event.payload or {}),
            created_at=event.created_at,
        )
        for event in visible
    )
    next_after_id = items[-1].id if items else after_id
    return EventPage(items=items, next_after_id=next_after_id, has_more=has_more)


def get_scope_execution_stats_bulk(
    session: Session,
    *,
    scope_type: str,
    scope_ids: list[str] | tuple[str, ...] | set[str],
    stage: str | None = None,
) -> dict[str, ScopeExecutionStats]:
    """Return one grouped query for all requested scopes (no N+1)."""
    unique_ids = sorted({scope_id for scope_id in scope_ids if scope_id})
    if not unique_ids:
        return {}

    stmt = (
        select(
            ExecutionRun.scope_id.label("scope_id"),
            func.count().label("run_count"),
            func.count()
            .filter(ExecutionRun.status.in_(("queued", "running")))
            .label("active_run_count"),
            func.count()
            .filter(ExecutionRun.status == "failed")
            .label("failed_run_count"),
            func.max(ExecutionRun.created_at).label("latest_run_at"),
            func.max(
                case((ExecutionRun.status == "succeeded", ExecutionRun.updated_at), else_=None)
            ).label("latest_success_at"),
        )
        .where(
            ExecutionRun.scope_type == scope_type,
            ExecutionRun.scope_id.in_(unique_ids),
        )
        .group_by(ExecutionRun.scope_id)
    )
    if stage is not None:
        stmt = stmt.where(ExecutionRun.stage == stage)

    rows = session.execute(stmt).all()
    by_scope = {row.scope_id: row for row in rows}
    result: dict[str, ScopeExecutionStats] = {}
    for scope_id in unique_ids:
        row = by_scope.get(scope_id)
        result[scope_id] = ScopeExecutionStats(
            scope_id=scope_id,
            run_count=int(row.run_count) if row is not None else 0,
            active_run_count=int(row.active_run_count) if row is not None else 0,
            failed_run_count=int(row.failed_run_count) if row is not None else 0,
            latest_run_at=row.latest_run_at if row is not None else None,
            latest_success_at=row.latest_success_at if row is not None else None,
        )
    return result


def get_scope_execution_stats(
    session: Session,
    *,
    scope_type: str,
    scope_id: str,
    stage: str | None = None,
) -> ScopeExecutionStats:
    if not scope_id:
        return ScopeExecutionStats(
            scope_id="",
            run_count=0,
            active_run_count=0,
            failed_run_count=0,
            latest_run_at=None,
            latest_success_at=None,
        )
    return get_scope_execution_stats_bulk(
        session,
        scope_type=scope_type,
        scope_ids=[scope_id],
        stage=stage,
    )[scope_id]


def list_run_summaries_for_scopes(
    session: Session,
    *,
    scope_type: str,
    scope_ids: list[str] | tuple[str, ...] | set[str],
    limit_per_scope: int = 5,
    stage: str | None = None,
) -> dict[str, tuple[RunSummary, ...]]:
    """Return recent Run summaries for many scopes in one query."""
    unique_ids = sorted({scope_id for scope_id in scope_ids if scope_id})
    if not unique_ids:
        return {}
    limit = max(1, min(int(limit_per_scope), 50))
    ranked = (
        select(
            ExecutionRun.id.label("run_id"),
            func.row_number()
            .over(
                partition_by=ExecutionRun.scope_id,
                order_by=(ExecutionRun.created_at.desc(), ExecutionRun.id.desc()),
            )
            .label("row_number"),
        )
        .where(
            ExecutionRun.scope_type == scope_type,
            ExecutionRun.scope_id.in_(unique_ids),
        )
    )
    if stage is not None:
        ranked = ranked.where(ExecutionRun.stage == stage)
    ranked_subquery = ranked.subquery()
    stmt = (
        select(ExecutionRun)
        .join(ranked_subquery, ExecutionRun.id == ranked_subquery.c.run_id)
        .where(ranked_subquery.c.row_number <= limit)
        .order_by(
            ExecutionRun.scope_id,
            ExecutionRun.created_at.desc(),
            ExecutionRun.id.desc(),
        )
    )
    runs = session.scalars(stmt).all()
    grouped: dict[str, list[RunSummary]] = {scope_id: [] for scope_id in unique_ids}
    for run in runs:
        bucket = grouped.get(run.scope_id)
        if bucket is not None:
            bucket.append(_run_summary(run))
    return {scope_id: tuple(items) for scope_id, items in grouped.items()}


def list_run_summaries_for_scope(
    session: Session,
    *,
    scope_type: str,
    scope_id: str,
    limit: int = 5,
    stage: str | None = None,
) -> tuple[RunSummary, ...]:
    if not scope_id:
        return ()
    return list_run_summaries_for_scopes(
        session,
        scope_type=scope_type,
        scope_ids=[scope_id],
        limit_per_scope=limit,
        stage=stage,
    )[scope_id]


def get_run_execution_counts(
    session: Session,
    *,
    run_id: str,
) -> RunExecutionCounts | None:
    """Return public, business-neutral Run/Job/Event counts for a Run.

    The Run's own ``scope_id`` is used for the Run count, matching the existing
    Dossier rollup statistic rather than interpreting the scope's business
    meaning.  No M06 semantics are added to M05.
    """
    run = session.get(ExecutionRun, run_id)
    if run is None:
        return None
    run_count = int(
        session.scalar(
            select(func.count())
            .select_from(ExecutionRun)
            .where(ExecutionRun.scope_id == run.scope_id)
        )
        or 0
    )
    job_count = int(
        session.scalar(
            select(func.count())
            .select_from(ExecutionJob)
            .where(ExecutionJob.run_id == run_id)
        )
        or 0
    )
    event_count = int(
        session.scalar(
            select(func.count())
            .select_from(ExecutionEvent)
            .where(ExecutionEvent.run_id == run_id)
        )
        or 0
    )
    return RunExecutionCounts(
        run_id=run.id,
        scope_id=run.scope_id,
        run_count=run_count,
        job_count=job_count,
        event_count=event_count,
    )


def get_run_evidence_presence(
    session: Session,
    *,
    run_id: str,
) -> ExecutionEvidencePresence:
    """Return object-type presence using full-table existence queries.

    This is deliberately a public M05 read capability so M06 can verify
    persistence through a new Session without importing M05 ORM.
    """
    run = session.get(ExecutionRun, run_id)
    if run is None:
        return ExecutionEvidencePresence(
            run_exists=False,
            steps_exists=False,
            jobs_exists=False,
            attempts_exists=False,
            events_exists=False,
        )
    steps_exists = bool(
        session.scalar(
            select(exists().where(ExecutionStep.run_id == run_id))
        )
    )
    jobs_exists = bool(
        session.scalar(
            select(exists().where(ExecutionJob.run_id == run_id))
        )
    )
    attempts_exists = (
        session.scalar(
            select(ExecutionJobAttempt.id)
            .join(
                ExecutionJob,
                ExecutionJobAttempt.job_id == ExecutionJob.id,
            )
            .where(ExecutionJob.run_id == run_id)
            .limit(1)
        )
        is not None
    )
    events_exists = bool(
        session.scalar(
            select(exists().where(ExecutionEvent.run_id == run_id))
        )
    )
    return ExecutionEvidencePresence(
        run_exists=True,
        steps_exists=steps_exists,
        jobs_exists=jobs_exists,
        attempts_exists=attempts_exists,
        events_exists=events_exists,
    )
