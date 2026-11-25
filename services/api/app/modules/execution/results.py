"""Small, provider-neutral execution result types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

JOB_TERMINAL_STATUSES = frozenset(
    {"succeeded", "partial", "failed", "cancelled", "skipped"}
)


@dataclass(frozen=True)
class StepResult:
    """Result returned by a Job handler for one execution attempt.

    Attempts are not ``partial``: the Job can be partial, while the Attempt
    itself completed and is recorded as succeeded.  ``cancelled`` is reserved
    for an explicit cancellation signal handled by the worker.
    """

    status: str
    processed_count: int = 0
    failed_count: int = 0
    result: dict[str, Any] | None = None
    error_code: str | None = None

    def __post_init__(self) -> None:
        if self.status not in JOB_TERMINAL_STATUSES:
            raise ValueError(f"invalid terminal StepResult status: {self.status}")
        if self.processed_count < 0 or self.failed_count < 0:
            raise ValueError("counts must be non-negative")
