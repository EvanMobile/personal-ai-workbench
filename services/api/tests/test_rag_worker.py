"""Real subprocess + real PostgreSQL tests for the M1-A Worker."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.utils import utcnow
from app.modules.execution.config import ExecutionConfig
from app.modules.evaluation.models import RagDossier
from app.modules.execution.errors import StaleLease
from app.modules.execution.models import (
    ExecutionJob,
    ExecutionEvent,
    ExecutionJobAttempt,
    ExecutionRun,
    ExecutionStep,
)
from app.modules.execution.service import ClaimedJob, HeartbeatResult
from app.modules.execution.results import StepResult
from app.modules.execution.service import (
    claim_job,
    create_job,
    create_run,
    create_step,
    finish_job,
    heartbeat,
    request_cancel,
)
from app.modules.execution.runtime import read_worker_snapshot
from app.modules.execution.worker import JobHeartbeat


API_DIR = Path(__file__).resolve().parents[1]


class WorkerProcess:
    """A real Worker subprocess with test-only handlers enabled."""

    def __init__(self, tmp_path: Path, name: str = "worker") -> None:
        env = os.environ.copy()
        env.update(
            {
                "DATABASE_URL": os.environ["DATABASE_URL"],
                "RAG_WORKER_TEST_HANDLERS": "1",
                "RAG_JOB_LEASE_SECONDS": "2",
                "RAG_JOB_HEARTBEAT_SECONDS": "0.5",
                "RAG_WORKER_POLL_SECONDS": "0.1",
                "RAG_RECOVERY_SECONDS": "0.5",
                "RAG_RETRY_BASE_SECONDS": "0.1",
                "RAG_RETRY_MAX_SECONDS": "0.3",
                "RAG_SHUTDOWN_GRACE_SECONDS": "1",
                "RAG_WORKER_ID": name,
                "RAG_WORKER_HEARTBEAT_FILE": str(tmp_path / f"{name}.heartbeat"),
                "PYTHONUNBUFFERED": "1",
            }
        )
        self.name = name
        self._log_path = tmp_path / f"{name}.log"
        self._log_file = self._log_path.open("a", encoding="utf-8")
        try:
            self.proc = subprocess.Popen(
                [sys.executable, "-m", "app.workers.rag_worker"],
                cwd=str(API_DIR),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=self._log_file,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except Exception:
            self._log_file.close()
            raise

    def _close_log(self) -> None:
        if not self._log_file.closed:
            self._log_file.close()

    def stop(self, sig: int = signal.SIGTERM, timeout: float = 15.0) -> int:
        try:
            if self.proc.poll() is None:
                self.proc.send_signal(sig)
            try:
                return self.proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                return self.proc.wait(timeout=5.0)
        finally:
            self._close_log()

    def kill(self) -> int:
        try:
            if self.proc.poll() is None:
                self.proc.kill()
            return self.proc.wait(timeout=5.0)
        finally:
            self._close_log()

    def output(self) -> str:
        # The child writes directly to the file; no PIPE can fill.  Read the
        # current file even while the Worker is still running.
        try:
            self._log_file.flush()
        except (OSError, ValueError):
            pass
        try:
            return self._log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""

    def __enter__(self) -> "WorkerProcess":
        return self

    def __exit__(self, *_args) -> None:
        self.stop()


def _bundle(
    *,
    kind: str,
    payload: dict | None = None,
    max_attempts: int = 3,
    job_key: str = "job",
    step_key: str = "stage",
):
    with SessionLocal() as session:
        dossier = RagDossier(title="Worker test dossier")
        session.add(dossier)
        session.commit()
        run, _ = create_run(
            session,
            scope_type="rag_dossier",
            scope_id=dossier.id,
            pipeline="dossier",
            stage="dossier_rollup",
            config_snapshot={"kind": kind},
            config_hash="a" * 64,
            fingerprint="b" * 64,
        )
        step = create_step(session, run_id=run.id, step_key=step_key, ordinal=1)
        job = create_job(
            session,
            run_id=run.id,
            step_id=step.id,
            job_key=job_key,
            kind=kind,
            payload=payload or {},
            max_attempts=max_attempts,
        )
        return run.id, step.id, job.id


def _wait_for(predicate, *, timeout: float = 15.0, workers: list[WorkerProcess] | None = None):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.1)
    logs = "\n".join(worker.output() for worker in workers or [])
    raise AssertionError(f"condition not met within {timeout}s\n{logs}")


def _run_status(run_id: str) -> str | None:
    with SessionLocal() as session:
        run = session.get(ExecutionRun, run_id)
        return run.status if run else None


def _job_state(job_id: str):
    with SessionLocal() as session:
        job = session.get(ExecutionJob, job_id)
        attempts = list(
            session.scalars(
                select(ExecutionJobAttempt)
                .where(ExecutionJobAttempt.job_id == job_id)
                .order_by(ExecutionJobAttempt.attempt_no)
            ).all()
        )
        return job, attempts


def test_e1_real_dossier_rollup_job() -> None:
    run_id, step_id, job_id = _bundle(kind="dossier_rollup")
    with WorkerProcess(Path("/tmp"), name="e1") as worker:
        _wait_for(lambda: _run_status(run_id) == "succeeded", timeout=15, workers=[worker])

    with SessionLocal() as session:
        run = session.get(ExecutionRun, run_id)
        step = session.get(ExecutionStep, step_id)
        job = session.get(ExecutionJob, job_id)
        attempts = list(
            session.scalars(
                select(ExecutionJobAttempt).where(ExecutionJobAttempt.job_id == job_id)
            ).all()
        )
        assert run is not None and run.status == "succeeded"
        assert run.result is not None and run.result["dossier_count"] >= 1
        assert run.result["run_count"] >= 1
        assert run.result["job_count"] == 1
        assert run.result["event_count"] >= 1
        assert step is not None and step.status == "succeeded"
        assert job is not None and job.status == "succeeded"
        assert len(attempts) == 1 and attempts[0].status == "succeeded"
        event_types = [
            event.type
            for event in session.scalars(
                select(ExecutionEvent).where(ExecutionEvent.run_id == run_id).order_by(ExecutionEvent.id)
            ).all()
        ]
        assert "job.claimed" in event_types
        assert "job.succeeded" in event_types


def test_dossier_rollup_handler_uses_m05_public_read_api() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "app/modules/evaluation/handlers/dossier_rollup.py"
    ).read_text(encoding="utf-8")
    assert "app.modules.execution.models" not in source
    assert "select(func.count()).select_from(ExecutionRun)" not in source
    assert "get_run_execution_counts" in source


def test_e4_e10c_sigkill_recovery() -> None:
    run_id, step_id, job_id = _bundle(
        kind="test.sleep", payload={"seconds": 2.0}
    )
    worker = WorkerProcess(Path("/tmp"), name="e4-a")
    try:
        _wait_for(
            lambda: _job_state(job_id)[0].status == "running",
            timeout=10,
            workers=[worker],
        )
        worker.kill()
        try:
            _wait_for(
                lambda: _job_state(job_id)[0].lease_expires_at < utcnow(),
                timeout=10,
            )
        except TypeError:
            # lease_expires_at may be None after recovery; the next assertion catches it.
            pass
        with WorkerProcess(Path("/tmp"), name="e4-b") as worker_b:
            _wait_for(lambda: _run_status(run_id) == "succeeded", timeout=20, workers=[worker_b])
    finally:
        worker.kill()

    job, attempts = _job_state(job_id)
    assert job is not None and job.status == "succeeded"
    assert [a.status for a in attempts] == ["abandoned", "succeeded"]
    assert attempts[0].error_code == "WORKER_LOST"
    assert attempts[1].attempt_no == 2


def test_e5_expired_lease_recovery() -> None:
    run_id, step_id, job_id = _bundle(kind="test.sleep", payload={"seconds": 0.1})
    with SessionLocal() as session:
        claimed = claim_job(session, worker_id="stale-worker", lease_seconds=1)
        assert claimed is not None
        job = session.get(ExecutionJob, job_id)
        assert job is not None
        job.lease_expires_at = utcnow() - timedelta(seconds=1)
        session.commit()

    with WorkerProcess(Path("/tmp"), name="e5") as worker:
        _wait_for(lambda: _run_status(run_id) == "succeeded", timeout=15, workers=[worker])

    job, attempts = _job_state(job_id)
    assert job is not None and job.status == "succeeded"
    assert attempts[0].status == "abandoned" and attempts[0].error_code == "WORKER_LOST"
    assert attempts[1].attempt_no == 2


def test_e6_retry_and_terminal_failure() -> None:
    run_id, step_id, job_id = _bundle(
        kind="test.retryable_failure", max_attempts=2
    )
    with WorkerProcess(Path("/tmp"), name="e6") as worker:
        _wait_for(lambda: _run_status(run_id) == "failed", timeout=15, workers=[worker])

    job, attempts = _job_state(job_id)
    assert job is not None and job.status == "failed"
    assert len(attempts) == 2
    assert all(attempt.status == "failed" for attempt in attempts)


def test_e7_cancel_running_job() -> None:
    run_id, step_id, job_id = _bundle(
        kind="test.cancel_wait", payload={"seconds": 30}
    )
    with WorkerProcess(Path("/tmp"), name="e7") as worker:
        _wait_for(
            lambda: _job_state(job_id)[0].status == "running",
            timeout=10,
            workers=[worker],
        )
        with SessionLocal() as session:
            request_cancel(session, run_id=run_id)
        _wait_for(lambda: _run_status(run_id) == "cancelled", timeout=15, workers=[worker])

    job, attempts = _job_state(job_id)
    assert job is not None and job.status == "cancelled"
    assert attempts[-1].status == "cancelled"


def test_e8_partial_success() -> None:
    run_id, step_id, job_id = _bundle(kind="test.partial")
    with WorkerProcess(Path("/tmp"), name="e8") as worker:
        _wait_for(lambda: _run_status(run_id) == "partial", timeout=15, workers=[worker])

    job, attempts = _job_state(job_id)
    assert job is not None and job.status == "partial"
    assert job.processed_count == 2 and job.failed_count == 1
    assert attempts[-1].status == "succeeded"


def test_e9_event_timeline() -> None:
    run_id, step_id, job_id = _bundle(kind="dossier_rollup")
    with WorkerProcess(Path("/tmp"), name="e9") as worker:
        _wait_for(lambda: _run_status(run_id) == "succeeded", timeout=15, workers=[worker])

    with SessionLocal() as session:
        events = list(
            session.scalars(
                select(ExecutionEvent)
                .where(ExecutionEvent.run_id == run_id)
                .order_by(ExecutionEvent.id)
            ).all()
        )
    assert events
    ids = [event.id for event in events]
    assert ids == sorted(ids)
    assert {"job.claimed", "job.succeeded"}.issubset({event.type for event in events})
    assert all("password" not in str(event.payload).lower() for event in events)


def test_e10a_graceful_shutdown_abandons_running_job() -> None:
    run_id, step_id, job_id = _bundle(kind="test.sleep", payload={"seconds": 30})
    worker = WorkerProcess(Path("/tmp"), name="e10a")
    try:
        _wait_for(
            lambda: _job_state(job_id)[0].status == "running",
            timeout=10,
            workers=[worker],
        )
        worker.stop(signal.SIGTERM)
    finally:
        worker.kill()

    job, attempts = _job_state(job_id)
    assert job is not None and job.status == "queued"
    assert job.locked_at is None and job.locked_by is None and job.lease_expires_at is None
    assert attempts[-1].status == "abandoned"
    assert attempts[-1].error_code == "WORKER_SHUTDOWN"
    with SessionLocal() as session:
        running_attempts = session.scalars(
            select(ExecutionJobAttempt).where(ExecutionJobAttempt.status == "running")
        ).all()
        running_jobs = session.scalars(
            select(ExecutionJob).where(ExecutionJob.status == "running")
        ).all()
    assert running_attempts == []
    assert running_jobs == []


def test_e10b_graceful_shutdown_after_completion() -> None:
    run_id, step_id, job_id = _bundle(kind="dossier_rollup")
    worker = WorkerProcess(Path("/tmp"), name="e10b")
    try:
        _wait_for(lambda: _run_status(run_id) == "succeeded", timeout=15, workers=[worker])
        worker.stop(signal.SIGTERM)
    finally:
        worker.kill()

    job, attempts = _job_state(job_id)
    assert job is not None and job.status == "succeeded"
    assert attempts[-1].status == "succeeded"


def test_finish_after_cancel_wins_over_handler_success() -> None:
    run_id, step_id, job_id = _bundle(
        kind="test.ignore_cancel", payload={"seconds": 1.5}
    )
    with WorkerProcess(Path("/tmp"), name="cancel-ignore") as worker:
        _wait_for(
            lambda: _job_state(job_id)[0].status == "running",
            timeout=10,
            workers=[worker],
        )
        with SessionLocal() as session:
            request_cancel(session, run_id=run_id)
        _wait_for(lambda: _run_status(run_id) == "cancelled", timeout=20, workers=[worker])

    job, attempts = _job_state(job_id)
    assert job is not None and job.status == "cancelled"
    assert attempts[-1].status == "cancelled"
    with SessionLocal() as session:
        events = [
            event.type
            for event in session.scalars(
                select(ExecutionEvent)
                .where(ExecutionEvent.run_id == run_id)
                .order_by(ExecutionEvent.id)
            ).all()
        ]
    assert "job.cancelled" in events
    assert "job.succeeded" not in events


def test_cancel_after_handler_final_check_before_finish(tmp_path) -> None:
    ready = tmp_path / "ready.flag"
    release = tmp_path / "release.flag"
    run_id, step_id, job_id = _bundle(
        kind="test.pause_then_succeed",
        payload={"ready_file": str(ready), "release_file": str(release)},
    )
    with WorkerProcess(tmp_path, name="cancel-after-check") as worker:
        _wait_for(lambda: ready.exists(), timeout=10, workers=[worker])
        with SessionLocal() as session:
            request_cancel(session, run_id=run_id)
        release.write_text("go", encoding="utf-8")
        _wait_for(lambda: _run_status(run_id) == "cancelled", timeout=20, workers=[worker])

    job, attempts = _job_state(job_id)
    assert job is not None and job.status == "cancelled"
    assert attempts[-1].status == "cancelled"


def test_worker_normal_shutdown_heartbeat_becomes_stopped(tmp_path) -> None:
    worker = WorkerProcess(tmp_path, name="normal-heartbeat")
    path = tmp_path / "normal-heartbeat.heartbeat"
    try:
        _wait_for(lambda: path.exists(), timeout=10, workers=[worker])
        running = read_worker_snapshot(path=path, now=utcnow(), stale_after_seconds=20)
        assert running.available is True
        worker.stop(signal.SIGTERM)
        stopped = read_worker_snapshot(path=path, now=utcnow(), stale_after_seconds=20)
        assert stopped.available is False
        assert stopped.reason_code == "HEARTBEAT_STOPPED"
    finally:
        worker.kill()


def test_e10d_handler_returns_after_shutdown_grace_is_abandoned() -> None:
    run_id, step_id, job_id = _bundle(
        kind="test.ignore_shutdown", payload={"seconds": 2.5}
    )
    worker = WorkerProcess(Path("/tmp"), name="e10d")
    try:
        _wait_for(
            lambda: _job_state(job_id)[0].status == "running",
            timeout=10,
            workers=[worker],
        )
        worker.stop(signal.SIGTERM)
    finally:
        worker.kill()

    job, attempts = _job_state(job_id)
    assert job is not None and job.status == "queued"
    assert attempts[-1].status == "abandoned"
    assert attempts[-1].error_code == "WORKER_SHUTDOWN"
    with SessionLocal() as session:
        events = [
            event.type
            for event in session.scalars(
                select(ExecutionEvent)
                .where(ExecutionEvent.run_id == run_id)
                .order_by(ExecutionEvent.id)
            ).all()
        ]
    assert "job.attempt_abandoned" in events
    assert "job.succeeded" not in events


def test_sigkill_heartbeat_becomes_stale(tmp_path) -> None:
    worker = WorkerProcess(tmp_path, name="sigkill-runtime")
    path = tmp_path / "sigkill-runtime.heartbeat"
    try:
        _wait_for(lambda: path.exists(), timeout=10, workers=[worker])
        running = read_worker_snapshot(path=path, now=utcnow(), stale_after_seconds=20)
        assert running.available is True
        worker.kill()
        stale = read_worker_snapshot(
            path=path,
            now=utcnow() + timedelta(seconds=30),
            stale_after_seconds=20,
        )
        assert stale.available is False
        assert stale.reason_code == "HEARTBEAT_STALE"
    finally:
        worker.kill()


def test_worker_process_captures_log_file_without_pipe_blocking(tmp_path) -> None:
    worker = WorkerProcess(tmp_path, name="log-capture")
    try:
        # Reading while the process is alive must not depend on PIPE EOF.
        running_output = worker.output()
        assert isinstance(running_output, str)
        assert (tmp_path / "log-capture.log").exists()
        _wait_for(
            lambda: (tmp_path / "log-capture.heartbeat").exists(),
            timeout=10,
            workers=[worker],
        )
        worker.stop(signal.SIGTERM)
        assert worker._log_file.closed
    finally:
        worker.kill()

    combined = worker.output()
    assert "received signal 15" in combined


def test_w1_two_workers_claim_one_job() -> None:
    run_id, step_id, job_id = _bundle(kind="test.sleep", payload={"seconds": 0.5})
    a = WorkerProcess(Path("/tmp"), name="w1-a")
    b = WorkerProcess(Path("/tmp"), name="w1-b")
    try:
        _wait_for(lambda: _run_status(run_id) == "succeeded", timeout=15, workers=[a, b])
    finally:
        a.stop()
        b.stop()

    job, attempts = _job_state(job_id)
    assert job is not None and job.status == "succeeded"
    assert len(attempts) == 1


def test_w2_w3_expired_heartbeat_takeover_and_stale_write() -> None:
    run_id, step_id, job_id = _bundle(
        kind="test.sleep", payload={"seconds": 2.5}
    )
    worker_a = WorkerProcess(Path("/tmp"), name="w2-a")
    try:
        _wait_for(
            lambda: _job_state(job_id)[0].status == "running",
            timeout=10,
            workers=[worker_a],
        )
        old_job, old_attempts = _job_state(job_id)
        old_attempt = old_attempts[-1]
        os.kill(worker_a.proc.pid, signal.SIGSTOP)
        _wait_for(
            lambda: _job_state(job_id)[0].lease_expires_at < utcnow(),
            timeout=10,
        )
        with SessionLocal() as session:
            expired_heartbeat = heartbeat(
                session,
                job_id=job_id,
                lease_token=old_job.lease_token,
                lease_seconds=2,
            )
        assert expired_heartbeat.valid is False

        with WorkerProcess(Path("/tmp"), name="w2-b") as worker_b:
            _wait_for(
                lambda: _job_state(job_id)[0].attempts >= 2,
                timeout=15,
                workers=[worker_b],
            )
            with SessionLocal() as session:
                with pytest.raises(StaleLease):
                    finish_job(
                        session,
                        job_id=job_id,
                        lease_token=old_job.lease_token,
                        attempt_id=old_attempt.id,
                        result=StepResult(status="succeeded"),
                    )
            _wait_for(lambda: _run_status(run_id) == "succeeded", timeout=20, workers=[worker_b])
    finally:
        os.kill(worker_a.proc.pid, signal.SIGKILL)
        worker_a.kill()

    job, attempts = _job_state(job_id)
    assert job is not None and job.status == "succeeded"
    assert attempts[0].status == "abandoned"
    assert attempts[0].error_code == "WORKER_LOST"
    assert attempts[-1].attempt_no == 2


def test_p1_heartbeat_db_failures_mark_lost(monkeypatch) -> None:
    import threading

    import app.modules.execution.worker as worker_module

    def boom(*_args, **_kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(worker_module, "heartbeat", boom)
    config = ExecutionConfig(
        lease_seconds=5,
        heartbeat_seconds=0.02,
        heartbeat_max_failures=2,
        poll_seconds=0.05,
        recovery_seconds=1.0,
        retry_base_seconds=0.1,
        retry_max_seconds=0.2,
        shutdown_grace_seconds=1.0,
        worker_id="heartbeat-test",
    )
    job = ClaimedJob(
        job_id="rjob_test",
        run_id="rrun_test",
        step_id="rstp_test",
        attempt_id="ratt_test",
        attempt_no=1,
        lease_token=1,
        kind="test.sleep",
        payload={},
    )
    cancel = threading.Event()
    lost = threading.Event()
    heartbeat_thread = JobHeartbeat(
        job=job,
        config=config,
        cancel_event=cancel,
        lost_event=lost,
    )
    heartbeat_thread.start()
    assert lost.wait(2.0)
    heartbeat_thread.stop()
    heartbeat_thread.join(timeout=2.0)
    assert lost.is_set()


def test_p1_transient_heartbeat_failure_does_not_lose_lease(monkeypatch) -> None:
    import threading

    import app.modules.execution.worker as worker_module

    calls = [0]

    def flaky(*_args, **_kwargs):
        calls[0] += 1  # type: ignore[index]
        if calls[0] == 1:  # type: ignore[index]
            raise RuntimeError("transient database error")
        return HeartbeatResult(valid=True, cancel_requested=False)

    monkeypatch.setattr(worker_module, "heartbeat", flaky)
    config = ExecutionConfig(
        lease_seconds=5,
        heartbeat_seconds=0.02,
        heartbeat_max_failures=3,
        poll_seconds=0.05,
        recovery_seconds=1.0,
        retry_base_seconds=0.1,
        retry_max_seconds=0.2,
        shutdown_grace_seconds=1.0,
        worker_id="heartbeat-test",
    )
    job = ClaimedJob(
        job_id="rjob_test",
        run_id="rrun_test",
        step_id="rstp_test",
        attempt_id="ratt_test",
        attempt_no=1,
        lease_token=1,
        kind="test.sleep",
        payload={},
    )
    cancel = threading.Event()
    lost = threading.Event()
    heartbeat_thread = JobHeartbeat(
        job=job,
        config=config,
        cancel_event=cancel,
        lost_event=lost,
    )
    heartbeat_thread.start()
    deadline = time.monotonic() + 2.0
    while calls[0] < 2 and time.monotonic() < deadline:  # type: ignore[index]
        time.sleep(0.01)
    heartbeat_thread.stop()
    heartbeat_thread.join(timeout=2.0)
    assert calls[0] >= 2  # type: ignore[index]
    assert not lost.is_set()
