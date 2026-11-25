"""Runtime-only Worker observation.

A heartbeat file is process liveness metadata, not an execution domain entity.
Reading it must never mutate Run/Step/Job/Attempt/Event state.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from app.core.utils import utcnow
from app.modules.execution.read_models import WorkerSnapshot

_DEFAULT_ROOT = Path(__file__).resolve().parents[5]
_DEFAULT_HEARTBEAT = _DEFAULT_ROOT / ".run" / "worker.heartbeat"


def worker_heartbeat_path() -> Path:
    """Resolve the shared heartbeat path used by Worker and API processes."""
    return Path(os.getenv("RAG_WORKER_HEARTBEAT_FILE", str(_DEFAULT_HEARTBEAT)))


def _stale_after_seconds(value: float | None) -> float:
    if value is not None:
        return max(1.0, float(value))
    try:
        return max(1.0, float(os.getenv("RAG_WORKER_STALE_SECONDS", "20")))
    except ValueError:
        return 20.0


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def read_worker_snapshot(
    *,
    path: Path | None = None,
    now: datetime | None = None,
    stale_after_seconds: float | None = None,
) -> WorkerSnapshot:
    """Read Worker liveness without touching execution tables or raising."""
    current = now or utcnow()
    stale_after = _stale_after_seconds(stale_after_seconds)
    heartbeat_path = path or worker_heartbeat_path()

    try:
        raw = heartbeat_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return WorkerSnapshot(
            available=False,
            heartbeat_at=None,
            expired=True,
            pid=None,
            worker_id=None,
            current_job_id=None,
            state=None,
            age_seconds=None,
            stale_after_seconds=stale_after,
            reason_code="HEARTBEAT_MISSING",
        )
    except (OSError, UnicodeError):
        return WorkerSnapshot(
            available=False,
            heartbeat_at=None,
            expired=True,
            pid=None,
            worker_id=None,
            current_job_id=None,
            state=None,
            age_seconds=None,
            stale_after_seconds=stale_after,
            reason_code="HEARTBEAT_UNREADABLE",
        )

    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        payload = None
    if not isinstance(payload, dict):
        return WorkerSnapshot(
            available=False,
            heartbeat_at=None,
            expired=True,
            pid=None,
            worker_id=None,
            current_job_id=None,
            state=None,
            age_seconds=None,
            stale_after_seconds=stale_after,
            reason_code="HEARTBEAT_INVALID",
        )

    heartbeat_at = _parse_datetime(payload.get("last_seen"))
    if heartbeat_at is None:
        return WorkerSnapshot(
            available=False,
            heartbeat_at=None,
            expired=True,
            pid=None,
            worker_id=None,
            current_job_id=None,
            state=None,
            age_seconds=None,
            stale_after_seconds=stale_after,
            reason_code="HEARTBEAT_INVALID",
        )

    # A badly skewed/future timestamp must not keep a dead Worker "available"
    # indefinitely.  Allow only a small clock-skew window.
    if (heartbeat_at - current).total_seconds() > 300:
        return WorkerSnapshot(
            available=False,
            heartbeat_at=heartbeat_at,
            expired=True,
            pid=None,
            worker_id=None,
            current_job_id=None,
            state=None,
            age_seconds=None,
            stale_after_seconds=stale_after,
            reason_code="HEARTBEAT_FUTURE_TIMESTAMP",
        )

    raw_pid = payload.get("pid")
    pid = raw_pid if isinstance(raw_pid, int) and not isinstance(raw_pid, bool) and raw_pid > 0 else None
    worker_id = payload.get("worker_id")
    current_job_id = payload.get("current_job_id")
    worker_id = worker_id if isinstance(worker_id, str) and worker_id else None
    current_job_id = current_job_id if isinstance(current_job_id, str) and current_job_id else None
    stopped = payload.get("status") == "stopped"
    state = "stopped" if stopped else ("busy" if current_job_id else "idle")

    age = max(0.0, (current - heartbeat_at).total_seconds())
    if stopped:
        return WorkerSnapshot(
            available=False,
            heartbeat_at=heartbeat_at,
            expired=False,
            pid=pid,
            worker_id=worker_id,
            current_job_id=None,
            state=state,
            age_seconds=round(age, 3),
            stale_after_seconds=stale_after,
            reason_code="HEARTBEAT_STOPPED",
        )

    expired = age > stale_after
    return WorkerSnapshot(
        available=not expired,
        heartbeat_at=heartbeat_at,
        expired=expired,
        pid=pid,
        worker_id=worker_id,
        current_job_id=current_job_id,
        state=state,
        age_seconds=round(age, 3),
        stale_after_seconds=stale_after,
        reason_code="HEARTBEAT_STALE" if expired else None,
    )
