"""R3.1: Worker heartbeat runtime snapshot, separate from execution rows."""

from __future__ import annotations

import json
import time
from datetime import timedelta

from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.core.utils import utcnow
from app.modules.execution.models import ExecutionEvent, ExecutionJob, ExecutionRun
from app.modules.execution.runtime import read_worker_snapshot
from app.modules.execution.service import create_run_with_step_job, payload_hash
from app.modules.execution.worker import ProcessHeartbeat, WorkerState


def _snapshot_payload(*, last_seen: str, current_job_id: str | None = None) -> dict:
    return {
        "pid": 4321,
        "worker_id": "worker-runtime-test",
        "last_seen": last_seen,
        "current_job_id": current_job_id,
    }


def test_worker_snapshot_normal_and_busy(tmp_path) -> None:
    path = tmp_path / "worker.heartbeat"
    now = utcnow()
    path.write_text(
        json.dumps(_snapshot_payload(last_seen=now.isoformat(), current_job_id="rjob_x")),
        encoding="utf-8",
    )
    snapshot = read_worker_snapshot(path=path, now=now, stale_after_seconds=20)
    assert snapshot.available is True
    assert snapshot.expired is False
    assert snapshot.pid == 4321
    assert snapshot.worker_id == "worker-runtime-test"
    assert snapshot.current_job_id == "rjob_x"
    assert snapshot.state == "busy"
    assert snapshot.reason_code is None


def test_worker_snapshot_missing_corrupt_stale(tmp_path) -> None:
    missing = read_worker_snapshot(
        path=tmp_path / "missing.heartbeat", stale_after_seconds=20
    )
    assert missing.available is False
    assert missing.expired is True
    assert missing.reason_code == "HEARTBEAT_MISSING"

    corrupt_path = tmp_path / "corrupt.heartbeat"
    corrupt_path.write_text("not-json", encoding="utf-8")
    corrupt = read_worker_snapshot(path=corrupt_path, stale_after_seconds=20)
    assert corrupt.available is False
    assert corrupt.reason_code == "HEARTBEAT_INVALID"

    now = utcnow()
    stale_path = tmp_path / "stale.heartbeat"
    stale_path.write_text(
        json.dumps(_snapshot_payload(last_seen=(now - timedelta(seconds=60)).isoformat())),
        encoding="utf-8",
    )
    stale = read_worker_snapshot(path=stale_path, now=now, stale_after_seconds=20)
    assert stale.available is False
    assert stale.expired is True
    assert stale.reason_code == "HEARTBEAT_STALE"
    assert stale.age_seconds is not None and stale.age_seconds >= 60


def test_worker_snapshot_does_not_mutate_execution_state(tmp_path) -> None:
    with SessionLocal() as session:
        created = create_run_with_step_job(
            session,
            scope_type="test_scope",
            scope_id="scope_runtime",
            pipeline="test_pipeline",
            stage="test_stage",
            config_snapshot={"kind": "test.runtime"},
            config_hash="a" * 64,
            fingerprint="b" * 64,
            step_key="stage",
            ordinal=1,
            job_key="job",
            kind="test.runtime",
            payload={},
            idempotency_key="runtime-key",
            idempotency_payload_hash=payload_hash({"kind": "test.runtime"}),
        )

    with SessionLocal() as session:
        before_run = session.get(ExecutionRun, created.run_id)
        before_job = session.get(ExecutionJob, created.job_id)
        before_events = int(
            session.scalar(
                select(func.count())
                .select_from(ExecutionEvent)
                .where(ExecutionEvent.run_id == created.run_id)
            )
            or 0
        )
        assert before_run is not None and before_job is not None
        before = (before_run.status, before_job.status, before_events)

    snapshot = read_worker_snapshot(path=tmp_path / "missing.heartbeat")
    assert snapshot.available is False

    with SessionLocal() as session:
        after_run = session.get(ExecutionRun, created.run_id)
        after_job = session.get(ExecutionJob, created.job_id)
        after_events = int(
            session.scalar(
                select(func.count())
                .select_from(ExecutionEvent)
                .where(ExecutionEvent.run_id == created.run_id)
            )
            or 0
        )
        assert after_run is not None and after_job is not None
        assert (after_run.status, after_job.status, after_events) == before


def test_process_heartbeat_normal_shutdown_reports_stopped(tmp_path, monkeypatch) -> None:
    path = tmp_path / "process.heartbeat"
    monkeypatch.setenv("RAG_WORKER_HEARTBEAT_FILE", str(path))
    heartbeat = ProcessHeartbeat(WorkerState(), "worker-stopped")
    heartbeat.start()
    try:
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and not path.exists():
            time.sleep(0.01)
        assert path.exists()
        running = read_worker_snapshot(path=path, stale_after_seconds=20)
        assert running.available is True
        assert running.worker_id == "worker-stopped"
        assert running.state == "idle"
    finally:
        heartbeat.stop()
        heartbeat.join(timeout=2)

    stopped = read_worker_snapshot(path=path, stale_after_seconds=20)
    assert stopped.available is False
    assert stopped.reason_code == "HEARTBEAT_STOPPED"
    assert stopped.state == "stopped"


def test_old_worker_does_not_overwrite_new_worker_heartbeat(tmp_path, monkeypatch) -> None:
    path = tmp_path / "shared.heartbeat"
    monkeypatch.setenv("RAG_WORKER_HEARTBEAT_FILE", str(path))
    now = utcnow()
    path.write_text(
        json.dumps(
            {
                "status": "running",
                "pid": 99999,
                "worker_id": "new-worker",
                "last_seen": now.isoformat(),
                "current_job_id": None,
            }
        ),
        encoding="utf-8",
    )
    old = ProcessHeartbeat(WorkerState(), "old-worker")
    old.stop()

    snapshot = read_worker_snapshot(path=path, now=now, stale_after_seconds=20)
    assert snapshot.available is True
    assert snapshot.worker_id == "new-worker"
    assert snapshot.reason_code is None


def test_worker_snapshot_rejects_future_timestamp(tmp_path) -> None:
    path = tmp_path / "future.heartbeat"
    now = utcnow()
    path.write_text(
        json.dumps(
            {
                "status": "running",
                "pid": 1,
                "worker_id": "future-worker",
                "last_seen": (now + timedelta(hours=1)).isoformat(),
                "current_job_id": None,
            }
        ),
        encoding="utf-8",
    )
    snapshot = read_worker_snapshot(path=path, now=now, stale_after_seconds=20)
    assert snapshot.available is False
    assert snapshot.reason_code == "HEARTBEAT_FUTURE_TIMESTAMP"
