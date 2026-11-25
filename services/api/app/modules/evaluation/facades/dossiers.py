"""M06 DossierFacade: Dossier Cover and execution-summary composition."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.evaluation.errors import DossierNotFound
from app.modules.evaluation.facades.execution import (
    DOSSIER_ROLLUP_STAGE,
    ExecutionFacade,
)
from app.modules.evaluation.models import RagDossier
from app.modules.evaluation.read_models import (
    DossierDetail,
    DossierList,
    DossierSummary,
    EvidenceCapabilities,
    ExecutionStats,
    LastError,
    StageSummary,
)
from app.modules.execution.read_models import RunSummary, ScopeExecutionStats

_TERMINAL_RUN_STATUSES = frozenset(
    {"succeeded", "partial", "failed", "cancelled", "skipped"}
)
_FAILURE_STATUSES = frozenset({"failed", "partial"})


def _actions_for(status: str, *, has_run: bool) -> tuple[str, ...]:
    if status == "active":
        return ("CANCEL_RUN", "WAIT", "VIEW_RUN")
    if not has_run or status == "not_started":
        return ("RUN_DOSSIER_ROLLUP",)
    if status in _FAILURE_STATUSES:
        return ("RETRY_DOSSIER_ROLLUP", "VIEW_RUN")
    return ("RUN_DOSSIER_ROLLUP", "VIEW_RUN")


def _summary(
    dossier: RagDossier,
    *,
    stats: ScopeExecutionStats,
    last_run: RunSummary | None,
) -> DossierSummary:
    return DossierSummary(
        id=dossier.id,
        title=dossier.title,
        description=dossier.description,
        status=dossier.status,
        created_at=dossier.created_at,
        updated_at=dossier.updated_at,
        last_run=last_run,
        run_count=stats.run_count,
        active_run_count=stats.active_run_count,
    )


def _execution_stats(stats: ScopeExecutionStats) -> ExecutionStats:
    return ExecutionStats(
        run_count=stats.run_count,
        active_run_count=stats.active_run_count,
        failed_run_count=stats.failed_run_count,
        latest_run_at=stats.latest_run_at,
        latest_success_at=stats.latest_success_at,
    )


class DossierFacade:
    """Dossier use cases and Dossier Cover read model.

    Dossier ownership stays in M06.  Execution facts are read only through
    ``ExecutionFacade``/M05 public DTOs; this class never touches execution_*
    ORM tables.
    """

    @staticmethod
    def create(
        session: Session,
        *,
        title: str,
        description: str = "",
    ) -> DossierSummary:
        clean_title = title.strip()
        if not clean_title:
            raise ValueError("title is required")
        dossier = RagDossier(title=clean_title, description=description)
        session.add(dossier)
        session.commit()
        session.refresh(dossier)
        return _summary(
            dossier,
            stats=ScopeExecutionStats(
                scope_id=dossier.id,
                run_count=0,
                active_run_count=0,
                failed_run_count=0,
                latest_run_at=None,
                latest_success_at=None,
            ),
            last_run=None,
        )

    @staticmethod
    def list(
        session: Session,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> DossierList:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        if offset < 0:
            raise ValueError("offset must be non-negative")

        total = int(
            session.scalar(select(func.count()).select_from(RagDossier)) or 0
        )
        dossiers = tuple(
            session.scalars(
                select(RagDossier)
                .order_by(RagDossier.updated_at.desc(), RagDossier.id.desc())
                .offset(offset)
                .limit(limit)
            ).all()
        )
        if not dossiers:
            return DossierList(items=(), total=total, limit=limit, offset=offset)

        ids = [dossier.id for dossier in dossiers]
        stats = ExecutionFacade.bulk_scope_stats(session, scope_ids=ids)
        recent = ExecutionFacade.bulk_recent_runs(
            session, scope_ids=ids, limit_per_scope=1
        )
        items = tuple(
            _summary(
                dossier,
                stats=stats[dossier.id],
                last_run=(recent[dossier.id][0] if recent[dossier.id] else None),
            )
            for dossier in dossiers
        )
        return DossierList(items=items, total=total, limit=limit, offset=offset)

    @staticmethod
    def detail(session: Session, *, dossier_id: str) -> DossierDetail:
        dossier = session.get(RagDossier, dossier_id)
        if dossier is None:
            raise DossierNotFound(dossier_id)

        stats = ExecutionFacade.scope_stats(session, scope_id=dossier.id)
        recent_all = ExecutionFacade.recent_runs(
            session, scope_id=dossier.id, limit=50
        )

        stage_keys = {run.stage for run in recent_all}
        stage_keys.add(DOSSIER_ROLLUP_STAGE)
        ordered_stage_keys = (DOSSIER_ROLLUP_STAGE,) + tuple(
            sorted(stage_keys - {DOSSIER_ROLLUP_STAGE})
        )
        stages = tuple(
            DossierFacade._stage_summary(session, dossier.id, stage_key)
            for stage_key in ordered_stage_keys
        )
        rollup_stage = next(
            stage for stage in stages if stage.stage_key == DOSSIER_ROLLUP_STAGE
        )
        rollup_terminal = rollup_stage.latest_terminal_run

        worker = ExecutionFacade.worker_status()
        blocking: list[str] = []
        if stats.active_run_count > 0:
            blocking.append("ACTIVE_RUN")
        if not worker.available:
            blocking.append("WORKER_UNAVAILABLE")
        if stats.run_count == 0:
            blocking.append("NO_RUN")
        elif rollup_terminal is not None and rollup_terminal.status == "failed":
            blocking.append("LAST_RUN_FAILED")

        if stats.active_run_count > 0:
            next_actions = ("CANCEL_RUN", "WAIT", "VIEW_RUN")
        elif stats.run_count == 0:
            next_actions = ("RUN_DOSSIER_ROLLUP",)
        elif rollup_terminal is not None and rollup_terminal.status in _FAILURE_STATUSES:
            next_actions = ("RETRY_DOSSIER_ROLLUP", "VIEW_RUN")
        else:
            next_actions = ("RUN_DOSSIER_ROLLUP", "VIEW_RUN")

        return DossierDetail(
            dossier=_summary(
                dossier,
                stats=stats,
                last_run=(recent_all[0] if recent_all else None),
            ),
            stages=stages,
            execution=_execution_stats(stats),
            recent_runs=recent_all[:5],
            worker=worker,
            evidence_capabilities=EvidenceCapabilities(),
            blocking=tuple(blocking),
            next_actions=next_actions,
        )

    @staticmethod
    def _stage_summary(
        session: Session,
        dossier_id: str,
        stage_key: str,
    ) -> StageSummary:
        stats = ExecutionFacade.scope_stats(
            session, scope_id=dossier_id, stage=stage_key
        )
        runs = ExecutionFacade.recent_runs(
            session, scope_id=dossier_id, limit=50, stage=stage_key
        )
        latest_run = runs[0] if runs else None
        latest_terminal = next(
            (run for run in runs if run.status in _TERMINAL_RUN_STATUSES),
            None,
        )
        if stats.active_run_count > 0:
            status = "active"
        elif latest_terminal is not None:
            status = latest_terminal.status
        else:
            status = "not_started"

        latest_result = None
        last_error = None
        if latest_terminal is not None:
            detail = ExecutionFacade.get_run(session, run_id=latest_terminal.id)
            if latest_terminal.status in {"succeeded", "partial"}:
                latest_result = detail.result
            if latest_terminal.status == "failed":
                failed_job = next(
                    (
                        job
                        for step in detail.steps
                        for job in step.jobs
                        if job.status == "failed"
                    ),
                    None,
                )
                last_error = LastError(
                    code=(
                        failed_job.error_code
                        if failed_job is not None and failed_job.error_code
                        else latest_terminal.error_code or "EXECUTION_FAILED"
                    ),
                    detail=(
                        failed_job.error_detail
                        if failed_job is not None
                        else detail.error_detail
                    ),
                )

        return StageSummary(
            stage_key=stage_key,
            status=status,
            active_run_count=stats.active_run_count,
            latest_run=latest_run,
            latest_terminal_run=latest_terminal,
            run_count=stats.run_count,
            failed_run_count=stats.failed_run_count,
            last_activity_at=(
                latest_run.updated_at if latest_run is not None else None
            ),
            latest_result=latest_result,
            last_error=last_error,
            next_actions=_actions_for(
                status, has_run=stats.run_count > 0
            ),
        )
