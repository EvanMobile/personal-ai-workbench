"""Pydantic request/response schemas for the RAG Lab M1-A API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

RunStatus = Literal[
    "queued",
    "running",
    "succeeded",
    "partial",
    "failed",
    "cancelled",
    "skipped",
]
StageStatus = Literal[
    "not_started",
    "active",
    "queued",
    "running",
    "succeeded",
    "partial",
    "failed",
    "cancelled",
    "skipped",
]
JobStatus = Literal[
    "queued",
    "running",
    "succeeded",
    "partial",
    "failed",
    "cancelled",
    "skipped",
]
AttemptStatus = Literal["running", "succeeded", "failed", "abandoned", "cancelled"]
StepStatus = Literal[
    "pending",
    "running",
    "succeeded",
    "partial",
    "failed",
    "cancelled",
    "skipped",
]


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DossierCreateRequest(APIModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("title must not be blank")
        return cleaned


class StartRunRequest(APIModel):
    kind: str = Field(default="dossier_rollup", max_length=64)
    params: dict[str, Any] = Field(default_factory=dict)


class RunSummarySchema(APIModel):
    id: str
    scope_type: str
    scope_id: str
    pipeline: str
    stage: str
    status: RunStatus
    created_at: datetime
    updated_at: datetime
    cancel_requested_at: datetime | None
    error_code: str | None


class DossierSummarySchema(APIModel):
    id: str
    title: str
    description: str
    status: Literal["active", "archived"]
    created_at: datetime
    updated_at: datetime
    last_run: RunSummarySchema | None
    run_count: int
    active_run_count: int


class DossierListSchema(APIModel):
    items: list[DossierSummarySchema]
    total: int
    limit: int
    offset: int


class ExecutionStatsSchema(APIModel):
    run_count: int
    active_run_count: int
    failed_run_count: int
    latest_run_at: datetime | None
    latest_success_at: datetime | None


class LastErrorSchema(APIModel):
    code: str
    detail: str | None


class StageSummarySchema(APIModel):
    stage_key: str
    status: StageStatus
    active_run_count: int
    latest_run: RunSummarySchema | None
    latest_terminal_run: RunSummarySchema | None
    run_count: int
    failed_run_count: int
    last_activity_at: datetime | None
    latest_result: dict[str, Any] | None
    last_error: LastErrorSchema | None
    next_actions: list[str]


class EvidenceCapabilitiesSchema(APIModel):
    generated: bool
    db_persisted: bool
    artifact_persisted: str
    verified: str


class EvidenceObjectStateSchema(APIModel):
    exists: bool | None
    read_back: bool


class EvidenceStateSchema(APIModel):
    readback_session: str
    run: EvidenceObjectStateSchema
    steps: EvidenceObjectStateSchema
    jobs: EvidenceObjectStateSchema
    attempts: EvidenceObjectStateSchema
    events: EvidenceObjectStateSchema


class WorkerSnapshotSchema(APIModel):
    available: bool
    heartbeat_at: datetime | None
    expired: bool
    pid: int | None
    worker_id: str | None
    current_job_id: str | None
    state: str | None
    age_seconds: float | None
    stale_after_seconds: float
    reason_code: str | None


class DossierDetailSchema(APIModel):
    dossier: DossierSummarySchema
    stages: list[StageSummarySchema]
    execution: ExecutionStatsSchema
    recent_runs: list[RunSummarySchema]
    worker: WorkerSnapshotSchema
    evidence_capabilities: EvidenceCapabilitiesSchema
    blocking: list[str]
    next_actions: list[str]


class AttemptSchema(APIModel):
    id: str
    job_id: str
    attempt_no: int
    status: AttemptStatus
    worker_id: str
    started_at: datetime
    finished_at: datetime | None
    error_code: str | None
    error_detail: str | None
    metrics: dict[str, Any]


class JobSchema(APIModel):
    id: str
    run_id: str
    step_id: str
    job_key: str
    kind: str
    status: JobStatus
    attempts: int
    max_attempts: int
    available_at: datetime
    locked_by: str | None
    cancel_requested_at: datetime | None
    processed_count: int
    failed_count: int
    error_code: str | None
    error_detail: str | None
    created_at: datetime
    updated_at: datetime
    attempts_history: list[AttemptSchema]


class StepSchema(APIModel):
    id: str
    run_id: str
    step_key: str
    ordinal: int
    status: StepStatus
    progress: int
    processed_count: int
    failed_count: int
    error_code: str | None
    error_detail: str | None
    created_at: datetime
    updated_at: datetime
    jobs: list[JobSchema]


class RunDetailSchema(APIModel):
    run: RunSummarySchema
    config_snapshot: dict[str, Any]
    config_hash: str
    fingerprint: str
    parent_run_id: str | None
    app_git_sha: str | None
    result: dict[str, Any] | None
    error_detail: str | None
    steps: list[StepSchema]
    evidence_capabilities: EvidenceCapabilitiesSchema
    evidence_state: EvidenceStateSchema


class StartRunResponse(APIModel):
    run: RunSummarySchema
    reused: bool
    worker_available: bool
    warnings: list[str]


class CancelRunResponse(APIModel):
    run: RunSummarySchema
    already_requested: bool


class EventSchema(APIModel):
    id: int
    run_id: str
    step_id: str | None
    job_id: str | None
    type: str
    level: str
    message: str
    payload: dict[str, Any]
    created_at: datetime


class EventPageSchema(APIModel):
    items: list[EventSchema]
    next_after_id: int
    has_more: bool


class ErrorResponse(APIModel):
    code: str
    message: str
    recoverable: bool
    details: dict[str, Any] | None = None
