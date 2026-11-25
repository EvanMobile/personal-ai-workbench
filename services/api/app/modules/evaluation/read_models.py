"""M06 RAG Dossier / Execution facade read models.

These DTOs combine M06 Dossier semantics with M05 public execution DTOs.  They
are intentionally immutable and contain no ORM Session or private M05 entities.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.modules.execution.read_models import RunSummary, StepView, WorkerSnapshot


@dataclass(frozen=True)
class DossierSummary:
    id: str
    title: str
    description: str
    status: str
    created_at: datetime
    updated_at: datetime
    last_run: RunSummary | None
    run_count: int
    active_run_count: int


@dataclass(frozen=True)
class ExecutionStats:
    run_count: int
    active_run_count: int
    failed_run_count: int
    latest_run_at: datetime | None
    latest_success_at: datetime | None


@dataclass(frozen=True)
class LastError:
    code: str
    detail: str | None


@dataclass(frozen=True)
class StageSummary:
    stage_key: str
    status: str
    active_run_count: int
    latest_run: RunSummary | None
    latest_terminal_run: RunSummary | None
    run_count: int
    failed_run_count: int
    last_activity_at: datetime | None
    latest_result: dict[str, Any] | None
    last_error: LastError | None
    next_actions: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceCapabilities:
    generated: bool = True
    db_persisted: bool = True
    artifact_persisted: str = "not_available"
    verified: str = "not_implemented"


@dataclass(frozen=True)
class EvidenceObjectState:
    exists: bool | None
    read_back: bool


@dataclass(frozen=True)
class EvidenceState:
    readback_session: str
    run: EvidenceObjectState
    steps: EvidenceObjectState
    jobs: EvidenceObjectState
    attempts: EvidenceObjectState
    events: EvidenceObjectState

    @classmethod
    def unreadable(cls) -> "EvidenceState":
        failed = EvidenceObjectState(exists=None, read_back=False)
        return cls(
            readback_session="new",
            run=failed,
            steps=failed,
            jobs=failed,
            attempts=failed,
            events=failed,
        )


@dataclass(frozen=True)
class DossierDetail:
    dossier: DossierSummary
    stages: tuple[StageSummary, ...]
    execution: ExecutionStats
    recent_runs: tuple[RunSummary, ...]
    worker: WorkerSnapshot
    evidence_capabilities: EvidenceCapabilities
    blocking: tuple[str, ...]
    next_actions: tuple[str, ...]


@dataclass(frozen=True)
class DossierList:
    items: tuple[DossierSummary, ...]
    total: int
    limit: int
    offset: int


@dataclass(frozen=True)
class RunDetail:
    run: RunSummary
    config_snapshot: dict[str, Any]
    config_hash: str
    fingerprint: str
    parent_run_id: str | None
    app_git_sha: str | None
    result: dict[str, Any] | None
    error_detail: str | None
    steps: tuple[StepView, ...]
    evidence_capabilities: EvidenceCapabilities
    evidence_state: EvidenceState


@dataclass(frozen=True)
class StartRunResult:
    run: RunSummary
    reused: bool
    worker_available: bool
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class CancelRunResult:
    run: RunSummary
    already_requested: bool
