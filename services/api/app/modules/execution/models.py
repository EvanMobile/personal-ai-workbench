"""M05 execution lifecycle: Run, Step, Job, Attempt and Event.

The tables in this module are intentionally RAG-agnostic. Business scope is
carried by opaque ``scope_type`` / ``scope_id`` values so execution does not
import M03 or M06.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.utils import new_id, utcnow

RUN_STATUSES = (
    "queued",
    "running",
    "succeeded",
    "partial",
    "failed",
    "cancelled",
    "skipped",
)
STEP_STATUSES = (
    "pending",
    "running",
    "succeeded",
    "partial",
    "failed",
    "skipped",
    "cancelled",
)
JOB_STATUSES = (
    "queued",
    "running",
    "succeeded",
    "partial",
    "failed",
    "cancelled",
    "skipped",
)
ATTEMPT_STATUSES = ("running", "succeeded", "failed", "abandoned", "cancelled")

_STATUS_VALUES = lambda values: ", ".join(f"'{value}'" for value in values)


class ExecutionRun(Base):
    """A single Run; never owns RAG business rows directly."""

    __tablename__ = "execution_runs"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: new_id("rrun")
    )
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_id: Mapped[str] = mapped_column(String(64), nullable=False)
    pipeline: Mapped[str] = mapped_column(String(32), nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    config_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    idempotency_payload_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parent_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("execution_runs.id", ondelete="SET NULL"), nullable=True
    )
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    app_git_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            f"status IN ({_STATUS_VALUES(RUN_STATUSES)})",
            name="ck_execution_runs_status",
        ),
        CheckConstraint(
            "idempotency_key IS NULL OR idempotency_payload_hash IS NOT NULL",
            name="ck_execution_runs_idempotency_payload",
        ),
        Index(
            "ux_execution_runs_idempotency",
            "scope_type",
            "scope_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
        Index("ix_execution_runs_scope_created", "scope_type", "scope_id", "created_at"),
        Index("ix_execution_runs_fingerprint", "fingerprint"),
    )


class ExecutionStep(Base):
    """A logical stage inside a Run; aggregates Jobs."""

    __tablename__ = "execution_steps"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: new_id("rstp")
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("execution_runs.id", ondelete="RESTRICT"), nullable=False
    )
    step_key: Mapped[str] = mapped_column(String(64), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            f"status IN ({_STATUS_VALUES(STEP_STATUSES)})",
            name="ck_execution_steps_status",
        ),
        UniqueConstraint("id", "run_id", name="uq_execution_steps_id_run"),
        UniqueConstraint("run_id", "ordinal", name="uq_execution_steps_run_ordinal"),
        UniqueConstraint("run_id", "step_key", name="uq_execution_steps_run_key"),
        Index("ix_execution_steps_run_status", "run_id", "status"),
    )


class ExecutionJob(Base):
    """A schedulable Job inside a Step; owns Lease/fencing state."""

    __tablename__ = "execution_jobs"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: new_id("rjob")
    )
    run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    step_id: Mapped[str] = mapped_column(String(64), nullable=False)
    job_key: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    lease_token: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancel_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    processed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id"],
            ["execution_runs.id"],
            name="fk_execution_jobs_run",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["step_id", "run_id"],
            ["execution_steps.id", "execution_steps.run_id"],
            name="fk_execution_jobs_step_run",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            f"status IN ({_STATUS_VALUES(JOB_STATUSES)})",
            name="ck_execution_jobs_status",
        ),
        CheckConstraint("lease_token >= 0", name="ck_execution_jobs_lease_token"),
        CheckConstraint("attempts >= 0", name="ck_execution_jobs_attempts"),
        CheckConstraint("max_attempts >= 1", name="ck_execution_jobs_max_attempts"),
        CheckConstraint(
            "status <> 'running' OR lease_expires_at IS NOT NULL",
            name="ck_execution_jobs_running_lease",
        ),
        UniqueConstraint("id", "run_id", name="uq_execution_jobs_id_run"),
        UniqueConstraint("run_id", "job_key", name="uq_execution_jobs_run_key"),
        Index(
            "ix_execution_jobs_claim",
            "status",
            "available_at",
            "created_at",
        ),
        Index("ix_execution_jobs_run", "run_id"),
        Index("ix_execution_jobs_step_status", "step_id", "status"),
    )


class ExecutionJobAttempt(Base):
    """One attempt at executing a Job; append-only history."""

    __tablename__ = "execution_job_attempts"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: new_id("ratt")
    )
    job_id: Mapped[str] = mapped_column(
        ForeignKey("execution_jobs.id", ondelete="RESTRICT"), nullable=False
    )
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    worker_id: Mapped[str] = mapped_column(String(64), nullable=False)
    fencing_token: Mapped[int] = mapped_column(BigInteger, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        CheckConstraint(
            f"status IN ({_STATUS_VALUES(ATTEMPT_STATUSES)})",
            name="ck_execution_job_attempts_status",
        ),
        CheckConstraint(
            "status = 'running' OR finished_at IS NOT NULL",
            name="ck_execution_job_attempts_terminal_finished",
        ),
        CheckConstraint("fencing_token > 0", name="ck_execution_job_attempts_fencing_token"),
        UniqueConstraint("job_id", "attempt_no", name="uq_execution_job_attempts_job_no"),
        Index("ix_execution_job_attempts_job_status", "job_id", "status"),
    )


class ExecutionEvent(Base):
    """Append-only, user-readable execution timeline."""

    __tablename__ = "execution_events"

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=False), primary_key=True
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("execution_runs.id", ondelete="RESTRICT"), nullable=False
    )
    step_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    job_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    level: Mapped[str] = mapped_column(String(16), nullable=False, default="info")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["step_id", "run_id"],
            ["execution_steps.id", "execution_steps.run_id"],
            name="fk_execution_events_step_run",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["job_id", "run_id"],
            ["execution_jobs.id", "execution_jobs.run_id"],
            name="fk_execution_events_job_run",
            ondelete="RESTRICT",
        ),
        Index("ix_execution_events_run_id", "run_id", "id"),
    )
