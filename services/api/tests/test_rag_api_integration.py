"""R3.4.1: real API + real Worker + real PostgreSQL integration evidence."""

from __future__ import annotations

import signal
import time
from typing import Any

from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.core.utils import utcnow
from app.modules.execution.models import (
    ExecutionEvent,
    ExecutionJob,
    ExecutionJobAttempt,
    ExecutionRun,
    ExecutionStep,
)
from app.modules.execution.service import create_run_with_step_job, payload_hash
from test_rag_worker import WorkerProcess, _job_state, _wait_for

RAG = "/api/v1/rag"


def _create_dossier(client, title: str = "Integration Dossier") -> str:
    response = client.post(f"{RAG}/dossiers", json={"title": title})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _start(client, dossier_id: str, key: str):
    return client.post(
        f"{RAG}/dossiers/{dossier_id}/runs",
        headers={"Idempotency-Key": key},
        json={"kind": "dossier_rollup", "params": {}},
    )


def _seed_test_run(
    dossier_id: str,
    *,
    kind: str,
    key: str,
    seconds: float | None = None,
    payload: dict | None = None,
):
    if payload is None:
        payload = {"seconds": seconds} if seconds is not None else {}
    with SessionLocal() as session:
        return create_run_with_step_job(
            session,
            scope_type="rag_dossier",
            scope_id=dossier_id,
            pipeline="dossier",
            stage="dossier_rollup",
            config_snapshot={"kind": kind},
            config_hash="a" * 64,
            fingerprint="b" * 64,
            step_key=kind,
            ordinal=1,
            job_key=kind,
            kind=kind,
            payload=payload,
            idempotency_key=key,
            idempotency_payload_hash=payload_hash({"kind": kind, "key": key}),
        )


def _api_run(client, run_id: str) -> dict[str, Any]:
    response = client.get(f"{RAG}/runs/{run_id}")
    assert response.status_code == 200, response.text
    return response.json()


def _api_events(client, run_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
    response = client.get(f"{RAG}/runs/{run_id}/events?limit={limit}")
    assert response.status_code == 200, response.text
    return response.json()["items"]


def _wait_api_run(client, run_id: str, expected: set[str], *, timeout: float = 20.0, workers=None):
    def check():
        response = client.get(f"{RAG}/runs/{run_id}")
        if response.status_code != 200:
            return False
        return response.json()["run"]["status"] in expected

    try:
        _wait_for(check, timeout=timeout, workers=workers)
    except AssertionError:
        with SessionLocal() as session:
            run = session.get(ExecutionRun, run_id)
            dump = {
                "run": run.status if run else None,
                "steps": [step.status for step in session.scalars(select(ExecutionStep).where(ExecutionStep.run_id == run_id)).all()],
                "jobs": [job.status for job in session.scalars(select(ExecutionJob).where(ExecutionJob.run_id == run_id)).all()],
            }
        raise AssertionError(f"run {run_id} did not reach {expected}: {dump}")


def test_api_worker_success_end_to_end(client, tmp_path, monkeypatch) -> None:
    worker_name = "integration-success"
    monkeypatch.setenv(
        "RAG_WORKER_HEARTBEAT_FILE", str(tmp_path / f"{worker_name}.heartbeat")
    )
    dossier_id = _create_dossier(client)
    start = _start(client, dossier_id, "success-1")
    assert start.status_code == 202, start.text
    assert start.json()["reused"] is False
    run_id = start.json()["run"]["id"]

    with SessionLocal() as session:
        assert session.get(ExecutionRun, run_id).status == "queued"  # type: ignore[union-attr]
        step = session.scalar(select(ExecutionStep).where(ExecutionStep.run_id == run_id))
        job = session.scalar(select(ExecutionJob).where(ExecutionJob.run_id == run_id))
        assert step is not None and step.status == "pending"
        assert job is not None and job.status == "queued"

    with WorkerProcess(tmp_path, name=worker_name) as worker:
        _wait_api_run(client, run_id, {"succeeded"}, workers=[worker])
        worker.stop(signal.SIGTERM)

    detail = _api_run(client, run_id)
    assert detail["run"]["status"] == "succeeded"
    assert detail["steps"][0]["status"] == "succeeded"
    assert detail["steps"][0]["jobs"][0]["status"] == "succeeded"
    assert detail["steps"][0]["jobs"][0]["attempts_history"][0]["status"] == "succeeded"
    assert detail["result"] is not None and detail["result"]["dossier_count"] >= 1
    evidence = detail["evidence_state"]
    assert evidence["readback_session"] == "new"
    for key in ("run", "steps", "jobs", "attempts", "events"):
        assert evidence[key] == {"exists": True, "read_back": True}
    events = _api_events(client, run_id)
    types = {event["type"] for event in events}
    assert {"job.claimed", "job.succeeded"}.issubset(types)

    with SessionLocal() as session:
        run = session.get(ExecutionRun, run_id)
        job = session.scalar(select(ExecutionJob).where(ExecutionJob.run_id == run_id))
        attempts = session.scalars(
            select(ExecutionJobAttempt).where(ExecutionJobAttempt.job_id == job.id)
        ).all()
        events_count = int(
            session.scalar(
                select(func.count())
                .select_from(ExecutionEvent)
                .where(ExecutionEvent.run_id == run_id)
            )
            or 0
        )
        assert run is not None and run.status == "succeeded"
        assert job is not None and job.status == "succeeded"
        assert len(attempts) == 1 and attempts[0].status == "succeeded"
        assert events_count >= 2


def test_api_worker_offline_enqueues_and_warns(client, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv(
        "RAG_WORKER_HEARTBEAT_FILE", str(tmp_path / "offline.heartbeat")
    )
    dossier_id = _create_dossier(client)
    response = _start(client, dossier_id, "offline-1")
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["worker_available"] is False
    assert body["warnings"] == ["WORKER_UNAVAILABLE"]

    with SessionLocal() as session:
        run = session.get(ExecutionRun, body["run"]["id"])
        step = session.scalar(
            select(ExecutionStep).where(ExecutionStep.run_id == body["run"]["id"])
        )
        job = session.scalar(
            select(ExecutionJob).where(ExecutionJob.run_id == body["run"]["id"])
        )
        assert run is not None and run.status == "queued"
        assert step is not None and step.status == "pending"
        assert job is not None and job.status == "queued"


def test_api_worker_terminal_failure_aggregates_run(client, tmp_path, monkeypatch) -> None:
    worker_name = "integration-failure"
    monkeypatch.setenv(
        "RAG_WORKER_HEARTBEAT_FILE", str(tmp_path / f"{worker_name}.heartbeat")
    )
    dossier_id = _create_dossier(client)
    created = _seed_test_run(dossier_id, kind="test.terminal_failure", key="failure-1")

    with WorkerProcess(tmp_path, name=worker_name) as worker:
        _wait_api_run(client, created.run_id, {"failed"}, workers=[worker])
        worker.stop(signal.SIGTERM)

    detail = _api_run(client, created.run_id)
    assert detail["run"]["status"] == "failed"
    assert detail["steps"][0]["status"] == "failed"
    assert detail["steps"][0]["jobs"][0]["status"] == "failed"
    assert detail["steps"][0]["jobs"][0]["attempts_history"][0]["status"] == "failed"
    assert detail["steps"][0]["jobs"][0]["attempts_history"][0]["error_code"] == "JobTerminalError"
    events = _api_events(client, created.run_id)
    assert "job.failed" in {event["type"] for event in events}

    with SessionLocal() as session:
        run = session.get(ExecutionRun, created.run_id)
        step = session.get(ExecutionStep, created.step_id)
        job = session.get(ExecutionJob, created.job_id)
        assert run is not None and run.status == "failed"
        assert step is not None and step.status == "failed"
        assert job is not None and job.status == "failed"


def test_api_cancel_coordinates_with_running_worker(client, tmp_path, monkeypatch) -> None:
    worker_name = "integration-cancel"
    monkeypatch.setenv(
        "RAG_WORKER_HEARTBEAT_FILE", str(tmp_path / f"{worker_name}.heartbeat")
    )
    dossier_id = _create_dossier(client)
    ready = tmp_path / "handler.ready"
    cancelled = tmp_path / "handler.cancelled"
    created = _seed_test_run(
        dossier_id,
        kind="test.cancel_ready",
        key="cancel-1",
        payload={
            "ready_file": str(ready),
            "cancelled_file": str(cancelled),
            "seconds": 30,
        },
    )

    with WorkerProcess(tmp_path, name=worker_name) as worker:
        # The signal is written by the Handler itself, not inferred from Job
        # state or emitted by the test process.
        _wait_for(lambda: ready.exists(), timeout=10, workers=[worker])
        first = client.post(f"{RAG}/runs/{created.run_id}/cancel")
        assert first.status_code == 200, first.text
        assert first.json()["already_requested"] is False
        second = client.post(f"{RAG}/runs/{created.run_id}/cancel")
        assert second.status_code == 200, second.text
        assert second.json()["already_requested"] is True
        _wait_for(lambda: cancelled.exists(), timeout=10, workers=[worker])
        _wait_api_run(client, created.run_id, {"cancelled"}, workers=[worker])
        worker.stop(signal.SIGTERM)

    detail = _api_run(client, created.run_id)
    assert detail["run"]["status"] == "cancelled"
    assert detail["steps"][0]["status"] == "cancelled"
    assert detail["steps"][0]["jobs"][0]["status"] == "cancelled"
    assert detail["steps"][0]["jobs"][0]["attempts_history"][-1]["status"] == "cancelled"
    assert cancelled.read_text(encoding="utf-8") == "cancelled"
    events = _api_events(client, created.run_id)
    assert {"job.cancel_requested", "job.cancelled"}.issubset(
        {event["type"] for event in events}
    )


def test_api_worker_graceful_shutdown_abandons_running_job(client, tmp_path, monkeypatch) -> None:
    worker_name = "integration-shutdown"
    monkeypatch.setenv(
        "RAG_WORKER_HEARTBEAT_FILE", str(tmp_path / f"{worker_name}.heartbeat")
    )
    dossier_id = _create_dossier(client)
    created = _seed_test_run(dossier_id, kind="test.sleep", key="shutdown-1", seconds=30)

    worker = WorkerProcess(tmp_path, name=worker_name)
    try:
        _wait_for(
            lambda: _job_state(created.job_id)[0].status == "running",
            timeout=10,
            workers=[worker],
        )
        worker.stop(signal.SIGTERM)
    finally:
        worker.kill()

    job, attempts = _job_state(created.job_id)
    assert job is not None and job.status == "queued"
    assert attempts[-1].status == "abandoned"
    assert attempts[-1].error_code == "WORKER_SHUTDOWN"
    detail = _api_run(client, created.run_id)
    assert detail["steps"][0]["jobs"][0]["status"] == "queued"
    with SessionLocal() as session:
        status = client.get(f"{RAG}/runtime/worker").json()
        assert status["available"] is False
        assert session.scalars(
            select(ExecutionJobAttempt).where(ExecutionJobAttempt.status == "running")
        ).all() == []


def test_api_worker_recovery_takes_over_expired_lease(client, tmp_path, monkeypatch) -> None:
    worker_name = "integration-recovery"
    monkeypatch.setenv(
        "RAG_WORKER_HEARTBEAT_FILE", str(tmp_path / f"{worker_name}.heartbeat")
    )
    dossier_id = _create_dossier(client)
    created = _seed_test_run(dossier_id, kind="test.sleep", key="recovery-1", seconds=2)

    first = WorkerProcess(tmp_path, name=f"{worker_name}-a")
    second = None
    try:
        _wait_for(
            lambda: _job_state(created.job_id)[0].status == "running",
            timeout=10,
            workers=[first],
        )
        first.kill()
        _wait_for(
            lambda: _job_state(created.job_id)[0].lease_expires_at < utcnow(),
            timeout=10,
        )
        second = WorkerProcess(tmp_path, name=f"{worker_name}-b")
        _wait_api_run(client, created.run_id, {"succeeded"}, timeout=20, workers=[second])
        second.stop(signal.SIGTERM)
    finally:
        first.kill()
        if second is not None:
            second.kill()

    job, attempts = _job_state(created.job_id)
    assert job is not None and job.status == "succeeded"
    assert [attempt.status for attempt in attempts] == ["abandoned", "succeeded"]
    assert attempts[0].error_code == "WORKER_LOST"
    events = _api_events(client, created.run_id)
    types = {event["type"] for event in events}
    assert "job.attempt_abandoned" in types
    assert "job.succeeded" in types
    assert (tmp_path / f"{worker_name}-a.log").exists()
    assert (tmp_path / f"{worker_name}-b.log").exists()
