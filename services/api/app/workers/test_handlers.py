"""Test-only handlers.

Imported only when RAG_WORKER_TEST_HANDLERS=1.  Production workers never
register these handlers; they exist to exercise real leases, retries,
cancellation and graceful shutdown in subprocess tests.
"""

from __future__ import annotations

import time
from pathlib import Path

from app.modules.execution.errors import JobCancelled, JobRetryableError, JobTerminalError
from app.modules.execution.results import StepResult
from app.modules.execution.worker import JobContext


def sleep(context: JobContext) -> StepResult:
    seconds = float(context.payload.get("seconds", 30))
    context.sleep(seconds)
    return StepResult(status="succeeded", processed_count=1)


def cancel_wait(context: JobContext) -> StepResult:
    context.sleep(float(context.payload.get("seconds", 30)))
    return StepResult(status="succeeded", processed_count=1)


def retryable_failure(context: JobContext) -> StepResult:
    raise JobRetryableError("synthetic retryable failure")


def terminal_failure(context: JobContext) -> StepResult:
    raise JobTerminalError("synthetic terminal failure")


def cancel_ready(context: JobContext) -> StepResult:
    """Signal Handler entry, then wait for, observe, and re-raise cancellation."""
    ready = Path(context.payload["ready_file"])
    cancelled = Path(context.payload["cancelled_file"])
    ready.write_text("ready", encoding="utf-8")
    try:
        context.sleep(float(context.payload.get("seconds", 30)))
    except JobCancelled:
        cancelled.write_text("cancelled", encoding="utf-8")
        raise
    return StepResult(status="succeeded", processed_count=1)


def pause_then_succeed(context: JobContext) -> StepResult:
    """Pause after a final check, then return success regardless of cancel."""
    context.check_stop()
    ready = Path(context.payload["ready_file"])
    release = Path(context.payload["release_file"])
    ready.write_text("ready", encoding="utf-8")
    deadline = time.monotonic() + 10
    while not release.exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    return StepResult(status="succeeded", processed_count=1)


def ignore_cancel(context: JobContext) -> StepResult:
    """Return success after cancellation; Finish must still win for Cancel."""
    time.sleep(float(context.payload.get("seconds", 1.5)))
    return StepResult(status="succeeded", processed_count=1)


def ignore_shutdown(context: JobContext) -> StepResult:
    """Deliberately ignores shutdown signals; used to test deadline enforcement."""
    time.sleep(float(context.payload.get("seconds", 2.5)))
    return StepResult(status="succeeded", processed_count=1)


def partial(context: JobContext) -> StepResult:
    return StepResult(
        status="partial",
        processed_count=2,
        failed_count=1,
        result={"processed": 2, "failed": 1},
        error_code="PARTIAL_ITEMS_FAILED",
    )


def skipped(context: JobContext) -> StepResult:
    return StepResult(status="skipped", processed_count=0, failed_count=0)


HANDLERS = {
    "test.sleep": sleep,
    "test.cancel_wait": cancel_wait,
    "test.retryable_failure": retryable_failure,
    "test.terminal_failure": terminal_failure,
    "test.cancel_ready": cancel_ready,
    "test.ignore_cancel": ignore_cancel,
    "test.pause_then_succeed": pause_then_succeed,
    "test.ignore_shutdown": ignore_shutdown,
    "test.partial": partial,
    "test.skipped": skipped,
}
