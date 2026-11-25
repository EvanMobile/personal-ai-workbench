"""Real Dossier rollup handler: reads DB counts and returns a Run result."""

from __future__ import annotations

from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.modules.evaluation.models import RagDossier
from app.modules.execution.errors import JobTerminalError
from app.modules.execution.results import StepResult
from app.modules.execution.service import get_run_execution_counts
from app.modules.execution.worker import JobContext


def dossier_rollup(context: JobContext) -> StepResult:
    with SessionLocal() as session:
        counts = get_run_execution_counts(session, run_id=context.job.run_id)
        if counts is None:
            raise JobTerminalError("run no longer exists")

        dossier_count = int(
            session.scalar(select(func.count()).select_from(RagDossier)) or 0
        )

    return StepResult(
        status="succeeded",
        processed_count=4,
        failed_count=0,
        result={
            "dossier_count": dossier_count,
            "run_count": counts.run_count,
            "job_count": counts.job_count,
            "event_count": counts.event_count,
        },
    )
