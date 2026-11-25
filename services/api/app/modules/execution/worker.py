"""Synchronous PostgreSQL-backed worker loop and handler contract."""

from __future__ import annotations

import json
import logging
import os
import signal
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.core.db import SessionLocal
from app.core.utils import utcnow
from app.modules.execution.config import ExecutionConfig
from app.modules.execution.errors import (
    HandlerNotFound,
    JobCancelled,
    JobInterrupted,
    JobLost,
    JobRetryableError,
    JobTerminalError,
    StaleLease,
)
from app.modules.execution.results import StepResult
from app.modules.execution.runtime import worker_heartbeat_path
from app.modules.execution.service import (
    ClaimedJob,
    abandon_for_shutdown,
    claim_job,
    fail_job,
    finish_job,
    heartbeat,
    recover_expired,
)

logger = logging.getLogger(__name__)

Handler = Callable[["JobContext"], StepResult]


@dataclass
class WorkerState:
    shutdown_event: threading.Event = field(default_factory=threading.Event)
    shutdown_started_at: float | None = None
    grace_seconds: float = 25.0
    current_job_id: str | None = None


@dataclass
class JobContext:
    """Handler-visible execution context; never exposes a long-lived Session."""

    job: ClaimedJob
    state: WorkerState
    config: ExecutionConfig
    cancel_event: threading.Event
    lost_event: threading.Event

    @property
    def payload(self) -> dict[str, Any]:
        return self.job.payload

    def check_stop(self) -> None:
        if self.lost_event.is_set():
            raise JobLost("lease lost")
        if self.cancel_event.is_set():
            raise JobCancelled("run/job cancelled")
        if self.state.shutdown_event.is_set():
            started = self.state.shutdown_started_at or time.monotonic()
            if time.monotonic() - started >= self.state.grace_seconds:
                raise JobInterrupted("graceful shutdown grace elapsed")

    def sleep(self, seconds: float, quantum: float = 0.05) -> None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self.check_stop()
            time.sleep(min(quantum, max(0.0, deadline - time.monotonic())))


class JobHeartbeat(threading.Thread):
    """Renews the Job lease on a separate Session thread while a handler runs."""

    def __init__(
        self,
        *,
        job: ClaimedJob,
        config: ExecutionConfig,
        cancel_event: threading.Event,
        lost_event: threading.Event,
    ) -> None:
        super().__init__(name=f"job-heartbeat-{job.job_id}", daemon=True)
        self._job = job
        self._config = config
        self._cancel_event = cancel_event
        self._lost_event = lost_event
        self._stopped = threading.Event()

    def run(self) -> None:
        failures = 0
        while not self._stopped.wait(self._config.heartbeat_seconds):
            try:
                with SessionLocal() as session:
                    result = heartbeat(
                        session,
                        job_id=self._job.job_id,
                        lease_token=self._job.lease_token,
                        lease_seconds=self._config.lease_seconds,
                    )
                failures = 0
                if not result.valid:
                    self._lost_event.set()
                    return
                if result.cancel_requested:
                    self._cancel_event.set()
            except Exception:  # noqa: BLE001 - retry transient DB errors, bounded
                failures += 1
                logger.exception(
                    "heartbeat failed for job %s (%s/%s)",
                    self._job.job_id,
                    failures,
                    self._config.heartbeat_max_failures,
                )
                if failures >= self._config.heartbeat_max_failures:
                    logger.error(
                        "heartbeat failed repeatedly for job %s; marking lease lost",
                        self._job.job_id,
                    )
                    self._lost_event.set()
                    return

    def stop(self) -> None:
        self._stopped.set()


class ProcessHeartbeat(threading.Thread):
    """Writes the optional .run/worker.heartbeat process-liveness file."""

    def __init__(self, state: WorkerState, worker_id: str) -> None:
        super().__init__(name="worker-process-heartbeat", daemon=True)
        self._state = state
        self._worker_id = worker_id
        self._stopped = threading.Event()
        self._lock = threading.Lock()
        self._path = worker_heartbeat_path()

    def _read_current(self) -> dict[str, Any] | None:
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, TypeError, ValueError):
            return None
        return payload if isinstance(payload, dict) else None

    def _owns_current_file(self) -> bool:
        payload = self._read_current()
        return bool(
            payload
            and payload.get("pid") == os.getpid()
            and payload.get("worker_id") == self._worker_id
        )

    def _write_unlocked(self, *, status: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "status": status,
            "pid": os.getpid(),
            "worker_id": self._worker_id,
            "last_seen": utcnow().isoformat(),
            "current_job_id": self._state.current_job_id if status == "running" else None,
        }
        temp = self._path.with_name(f"{self._path.name}.{os.getpid()}.tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        temp.replace(self._path)

    def _write(self) -> None:
        with self._lock:
            if self._stopped.is_set():
                return
            self._write_unlocked(status="running")

    def run(self) -> None:
        # Publish immediately so a freshly started Worker is observable before
        # the first five-second heartbeat interval elapses.
        try:
            self._write()
        except OSError:
            logger.exception("could not write worker heartbeat file")
        while not self._stopped.wait(5.0):
            try:
                self._write()
            except OSError:
                logger.exception("could not write worker heartbeat file")

    def stop(self) -> None:
        self._stopped.set()
        # Publish an explicit stopped state only if this process still owns the
        # shared file.  Never overwrite another Worker's heartbeat.
        with self._lock:
            if not self._owns_current_file():
                return
            try:
                self._write_unlocked(status="stopped")
            except OSError:
                pass


class Worker:
    """Claim → execute → commit/fail/abandon loop."""

    def __init__(
        self,
        *,
        config: ExecutionConfig,
        handlers: Mapping[str, Handler],
    ) -> None:
        self.config = config
        self.handlers = dict(handlers)
        self.state = WorkerState(grace_seconds=config.shutdown_grace_seconds)
        self._process_heartbeat = ProcessHeartbeat(self.state, config.worker_id)
        self._last_recovery = 0.0

    def _install_signals(self) -> None:
        def _handle(signum: int, _frame: object) -> None:
            if not self.state.shutdown_event.is_set():
                self.state.shutdown_started_at = time.monotonic()
            self.state.shutdown_event.set()
            logger.info("received signal %s; draining worker", signum)

        signal.signal(signal.SIGTERM, _handle)
        signal.signal(signal.SIGINT, _handle)

    def _recover_if_due(self) -> None:
        now = time.monotonic()
        if self._last_recovery and now - self._last_recovery < self.config.recovery_seconds:
            return
        self._last_recovery = now
        try:
            with SessionLocal() as session:
                count = recover_expired(session, config=self.config)
            if count:
                logger.info("recovered %s expired job(s)", count)
        except Exception:  # noqa: BLE001 - recovery must keep the loop alive
            logger.exception("recovery scan failed")

    def run_forever(self) -> None:
        self._install_signals()
        self._process_heartbeat.start()
        try:
            while not self.state.shutdown_event.is_set():
                self._recover_if_due()
                if self.state.shutdown_event.is_set():
                    break
                with SessionLocal() as session:
                    claimed = claim_job(
                        session,
                        worker_id=self.config.worker_id,
                        lease_seconds=self.config.lease_seconds,
                    )
                if claimed is None:
                    time.sleep(self.config.poll_seconds)
                    continue
                self.state.current_job_id = claimed.job_id
                try:
                    self._execute(claimed)
                finally:
                    self.state.current_job_id = None
        finally:
            self._process_heartbeat.stop()
            self._process_heartbeat.join(timeout=2.0)

    def _shutdown_expired(self) -> bool:
        started = self.state.shutdown_started_at
        return (
            self.state.shutdown_event.is_set()
            and started is not None
            and time.monotonic() - started >= self.state.grace_seconds
        )

    def _execute(self, claimed: ClaimedJob) -> None:
        cancel_event = threading.Event()
        lost_event = threading.Event()
        context = JobContext(
            job=claimed,
            state=self.state,
            config=self.config,
            cancel_event=cancel_event,
            lost_event=lost_event,
        )
        job_heartbeat = JobHeartbeat(
            job=claimed,
            config=self.config,
            cancel_event=cancel_event,
            lost_event=lost_event,
        )
        job_heartbeat.start()
        try:
            handler = self.handlers.get(claimed.kind)
            if handler is None:
                raise HandlerNotFound(f"no handler registered for kind={claimed.kind}")
            result = handler(context)
            if not isinstance(result, StepResult):
                raise JobTerminalError("handler must return StepResult")
            # Final stop check after Handler return and before result commit.
            if lost_event.is_set():
                logger.warning(
                    "job %s lost its lease before finish; not committing", claimed.job_id
                )
                return
            if self._shutdown_expired():
                logger.warning(
                    "job %s returned after shutdown grace; abandoning instead of committing",
                    claimed.job_id,
                )
                self._abandon_for_shutdown(claimed)
                return
            if cancel_event.is_set():
                logger.info(
                    "job %s observed cancellation before finish; committing cancelled",
                    claimed.job_id,
                )
                self._finish(
                    claimed,
                    StepResult(status="cancelled", error_code="CANCELLED"),
                )
                return
            self._finish(claimed, result)
        except JobCancelled:
            if self._shutdown_expired():
                self._abandon_for_shutdown(claimed)
            else:
                self._finish(
                    claimed,
                    StepResult(
                        status="cancelled",
                        error_code="CANCELLED",
                    ),
                )
        except JobInterrupted:
            self._abandon_for_shutdown(claimed)
        except (JobLost, StaleLease):
            logger.warning("job %s lost its lease; recovery will take over", claimed.job_id)
        except Exception as exc:  # noqa: BLE001
            if self._shutdown_expired():
                logger.warning(
                    "job %s raised after shutdown grace; abandoning instead of failing",
                    claimed.job_id,
                )
                self._abandon_for_shutdown(claimed)
            elif isinstance(exc, JobRetryableError):
                self._fail(claimed, exc, retryable=True)
            elif isinstance(exc, (JobTerminalError, HandlerNotFound)):
                self._fail(claimed, exc, retryable=False)
            else:
                logger.exception("handler failed for job %s", claimed.job_id)
                self._fail(claimed, exc, retryable=True)
        finally:
            job_heartbeat.stop()
            job_heartbeat.join(timeout=2.0)

    def _finish(self, claimed: ClaimedJob, result: StepResult) -> None:
        try:
            with SessionLocal() as session:
                finish_job(
                    session,
                    job_id=claimed.job_id,
                    lease_token=claimed.lease_token,
                    attempt_id=claimed.attempt_id,
                    result=result,
                )
        except StaleLease:
            logger.warning("stale lease while finishing job %s", claimed.job_id)

    def _fail(self, claimed: ClaimedJob, exc: Exception, *, retryable: bool) -> None:
        try:
            with SessionLocal() as session:
                fail_job(
                    session,
                    job_id=claimed.job_id,
                    lease_token=claimed.lease_token,
                    attempt_id=claimed.attempt_id,
                    error_code=type(exc).__name__,
                    error_detail=str(exc)[:1000],
                    retryable=retryable,
                    config=self.config,
                )
        except StaleLease:
            logger.warning("stale lease while failing job %s", claimed.job_id)

    def _abandon_for_shutdown(self, claimed: ClaimedJob) -> None:
        try:
            with SessionLocal() as session:
                abandoned = abandon_for_shutdown(
                    session,
                    job_id=claimed.job_id,
                    lease_token=claimed.lease_token,
                    attempt_id=claimed.attempt_id,
                    config=self.config,
                )
            if not abandoned:
                logger.warning("could not abandon job %s; lease already expired", claimed.job_id)
        except StaleLease:
            logger.warning("stale lease while abandoning job %s", claimed.job_id)
