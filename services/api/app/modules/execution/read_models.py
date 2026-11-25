"""Immutable, RAG-agnostic read models for Execution public queries.

These types intentionally expose no SQLAlchemy Session or ORM entity.  They
are the contract consumed by higher-level facades and keep M05 free of Dossier
or other business semantics.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

_SENSITIVE_KEY_PARTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "access_key",
    "authorization",
    "cookie",
    "credential",
    "private_key",
    "session_key",
    "prompt",
)
_SENSITIVE_VALUE_RE = re.compile(
    r"(?:/Users/|/home/|/private/|/var/lib/|/etc/|"
    r"[A-Za-z]:\\|"
    r"Bearer\s+|sk-[A-Za-z0-9]|"
    r"eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+|"
    r"AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20,}|"
    r"AIza[0-9A-Za-z_-]{20,}|xox[baprs]-|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    r"postgres(?:ql)?://|"
    r"(?:password|passwd|secret|token|api[_-]?key|authorization)\s*[=:])",
    re.IGNORECASE,
)
_REDACTED = "[REDACTED]"
_REDACTED_PATH = "[REDACTED_PATH]"


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in _SENSITIVE_KEY_PARTS)


def sanitize_text(value: str | None) -> str | None:
    """Mask obvious secrets/paths while preserving ordinary diagnostics.

    This is defense-in-depth, not a cryptographic guarantee.  M05 must not
    accept arbitrary secret-bearing result/payload shapes from untrusted code.
    """
    if value is None:
        return None
    if _SENSITIVE_VALUE_RE.search(value):
        return _REDACTED_PATH
    return value


def sanitize_json(value: Any) -> Any:
    """Recursively copy JSON-like data with secret/path keys redacted."""
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if _is_sensitive_key(key_text):
                result[key_text] = _REDACTED
            else:
                result[key_text] = sanitize_json(item)
        return result
    if isinstance(value, (list, tuple)):
        return [sanitize_json(item) for item in value]
    if isinstance(value, str):
        return sanitize_text(value)
    return value


@dataclass(frozen=True)
class RunSummary:
    id: str
    scope_type: str
    scope_id: str
    pipeline: str
    stage: str
    status: str
    created_at: datetime
    updated_at: datetime
    cancel_requested_at: datetime | None
    error_code: str | None


@dataclass(frozen=True)
class AttemptView:
    id: str
    job_id: str
    attempt_no: int
    status: str
    worker_id: str
    started_at: datetime
    finished_at: datetime | None
    error_code: str | None
    error_detail: str | None
    metrics: dict[str, Any]


@dataclass(frozen=True)
class JobView:
    id: str
    run_id: str
    step_id: str
    job_key: str
    kind: str
    status: str
    attempts: int
    max_attempts: int
    available_at: datetime
    locked_by: str | None
    last_heartbeat_at: datetime | None
    lease_expires_at: datetime | None
    cancel_requested_at: datetime | None
    processed_count: int
    failed_count: int
    error_code: str | None
    error_detail: str | None
    created_at: datetime
    updated_at: datetime
    attempts_history: tuple[AttemptView, ...]


@dataclass(frozen=True)
class StepView:
    id: str
    run_id: str
    step_key: str
    ordinal: int
    status: str
    progress: int
    processed_count: int
    failed_count: int
    error_code: str | None
    error_detail: str | None
    created_at: datetime
    updated_at: datetime
    jobs: tuple[JobView, ...]


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


@dataclass(frozen=True)
class EventView:
    id: int
    run_id: str
    step_id: str | None
    job_id: str | None
    type: str
    level: str
    message: str
    payload: dict[str, Any]
    created_at: datetime


@dataclass(frozen=True)
class RunExecutionCounts:
    """Public, business-neutral Run/Job/Event counts for a Run scope."""

    run_id: str
    scope_id: str
    run_count: int
    job_count: int
    event_count: int


@dataclass(frozen=True)
class ExecutionEvidencePresence:
    """Business-neutral presence of one Run and its child execution records."""

    run_exists: bool
    steps_exists: bool
    jobs_exists: bool
    attempts_exists: bool
    events_exists: bool


@dataclass(frozen=True)
class EventPage:
    items: tuple[EventView, ...]
    next_after_id: int
    has_more: bool


@dataclass(frozen=True)
class ScopeExecutionStats:
    scope_id: str
    run_count: int
    active_run_count: int
    failed_run_count: int
    latest_run_at: datetime | None
    latest_success_at: datetime | None


@dataclass(frozen=True)
class CancelOutcome:
    run: RunSummary
    already_requested: bool


@dataclass(frozen=True)
class WorkerSnapshot:
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
