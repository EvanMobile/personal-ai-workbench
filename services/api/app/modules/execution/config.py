"""Execution/worker configuration read from environment variables."""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from random import uniform


def _int(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _float(name: str, default: float, minimum: float = 0.0) -> float:
    try:
        return max(minimum, float(os.getenv(name, str(default))))
    except ValueError:
        return default


@dataclass(frozen=True)
class ExecutionConfig:
    lease_seconds: int
    heartbeat_seconds: float
    heartbeat_max_failures: int
    poll_seconds: float
    recovery_seconds: float
    retry_base_seconds: float
    retry_max_seconds: float
    shutdown_grace_seconds: float
    worker_id: str

    @classmethod
    def from_env(cls, worker_id: str | None = None) -> "ExecutionConfig":
        return cls(
            lease_seconds=_int("RAG_JOB_LEASE_SECONDS", 60),
            heartbeat_seconds=_float("RAG_JOB_HEARTBEAT_SECONDS", 10.0, 0.1),
            heartbeat_max_failures=_int("RAG_HEARTBEAT_MAX_FAILURES", 3, 1),
            poll_seconds=_float("RAG_WORKER_POLL_SECONDS", 0.5, 0.05),
            recovery_seconds=_float("RAG_RECOVERY_SECONDS", 30.0, 0.2),
            retry_base_seconds=_float("RAG_RETRY_BASE_SECONDS", 5.0, 0.1),
            retry_max_seconds=_float("RAG_RETRY_MAX_SECONDS", 300.0, 0.2),
            shutdown_grace_seconds=_float("RAG_SHUTDOWN_GRACE_SECONDS", 25.0, 0.2),
            worker_id=worker_id
            or os.getenv("RAG_WORKER_ID", f"{socket.gethostname()}:{os.getpid()}"),
        )

    def retry_delay(self, attempts: int) -> float:
        """Exponential backoff with a small deterministic-ish jitter."""
        exponent = max(0, attempts - 1)
        base = min(self.retry_base_seconds * (2**exponent), self.retry_max_seconds)
        return base + uniform(0.0, min(1.0, base * 0.2))
