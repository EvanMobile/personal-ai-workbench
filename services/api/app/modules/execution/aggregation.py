"""Pure Run/Step status aggregation.

These functions never read Events or mutate the database; they are shared by
the service layer and unit tests so Step and Run use exactly the same rules.
"""

from __future__ import annotations

from collections.abc import Iterable

JOB_TERMINAL = frozenset(
    {"succeeded", "partial", "failed", "cancelled", "skipped"}
)
STEP_TERMINAL = frozenset(
    {"succeeded", "partial", "failed", "cancelled", "skipped"}
)
_RUNNING_STATES = frozenset({"queued", "running", "pending"})


def aggregate_statuses(statuses: Iterable[str]) -> str:
    """Aggregate terminal child statuses into a parent status.

    ``skipped`` is a non-failure terminal state.  It cannot make a parent
    successful on its own: an all-skipped set is ``skipped``.
    """
    values = set(statuses)
    unknown = values - JOB_TERMINAL
    if unknown:
        raise ValueError(f"non-terminal or unknown statuses: {sorted(unknown)}")

    if not values:
        return "skipped"
    if "failed" in values:
        if "succeeded" in values or "partial" in values:
            return "partial"
        return "failed"
    if "partial" in values:
        return "partial"
    if "cancelled" in values:
        if "succeeded" in values:
            return "partial"
        return "cancelled"
    if "succeeded" in values:
        return "succeeded"
    return "skipped"


def has_non_terminal(statuses: Iterable[str]) -> bool:
    return any(status in _RUNNING_STATES for status in statuses)
