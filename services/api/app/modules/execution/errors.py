"""Execution-domain errors shared by services, workers and tests."""

from __future__ import annotations


class ExecutionError(RuntimeError):
    """Base class for execution lifecycle errors."""


class IdempotencyConflict(ExecutionError):
    """The idempotency key was reused with a different payload."""


class RunIncomplete(ExecutionError):
    """An idempotent Run exists but its expected Step/Job is missing."""

    def __init__(self, run_id: str, missing: str) -> None:
        self.run_id = run_id
        self.missing = missing
        super().__init__(f"run {run_id} is missing {missing}")


class RunNotCancellable(ExecutionError):
    """A terminal Run cannot be cancelled."""


class StaleLease(ExecutionError):
    """The worker no longer owns the Job lease (old token or expired lease)."""


class JobInterrupted(ExecutionError):
    """The worker is shutting down at a safe point."""


class JobCancelled(ExecutionError):
    """The Run/Job was cancelled while executing."""


class JobLost(ExecutionError):
    """The execution lease was lost before a result could be committed."""


class JobRetryableError(ExecutionError):
    """A handler failed transiently and the Job may be retried."""


class JobTerminalError(ExecutionError):
    """A handler failed permanently; do not retry."""


class HandlerNotFound(ExecutionError):
    """No handler is registered for a Job kind."""
