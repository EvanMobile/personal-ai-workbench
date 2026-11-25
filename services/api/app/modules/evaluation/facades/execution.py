"""M06 ExecutionFacade: Dossier-facing composition over M05 public APIs."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.modules.evaluation.errors import (
    DossierArchived,
    DossierNotFound,
    InvalidDossierRunParams,
    RunNotFound,
    UnsupportedDossierRunKind,
)
from app.modules.evaluation.models import RagDossier
from app.modules.evaluation.read_models import (
    CancelRunResult,
    EvidenceCapabilities,
    EvidenceObjectState,
    EvidenceState,
    RunDetail,
    StartRunResult,
)
from app.modules.execution import service as execution_service
from app.modules.execution.read_models import (
    EventPage,
    RunSummary,
    ScopeExecutionStats,
    WorkerSnapshot,
)
from app.modules.execution.runtime import read_worker_snapshot
from app.core.db import SessionLocal

DOSSIER_SCOPE_TYPE = "rag_dossier"
DOSSIER_PIPELINE = "dossier"
DOSSIER_ROLLUP_STAGE = "dossier_rollup"
DOSSIER_ROLLUP_KIND = "dossier_rollup"
DOSSIER_ROLLUP_STEP_KEY = "dossier_rollup"
DOSSIER_ROLLUP_JOB_KEY = "dossier_rollup"

logger = logging.getLogger(__name__)


def _evidence_object(exists: bool) -> EvidenceObjectState:
    return EvidenceObjectState(exists=exists, read_back=True)


def _read_evidence_state(run_id: str) -> EvidenceState:
    """Prove persistence via a distinct DB Session, never the request Session."""
    try:
        with SessionLocal() as readback_session:
            presence = execution_service.get_run_evidence_presence(
                readback_session, run_id=run_id
            )
    except Exception:  # noqa: BLE001 - surface safe read failure state
        logger.exception("evidence readback failed for run %s", run_id)
        return EvidenceState.unreadable()
    return EvidenceState(
        readback_session="new",
        run=_evidence_object(presence.run_exists),
        steps=_evidence_object(presence.steps_exists),
        jobs=_evidence_object(presence.jobs_exists),
        attempts=_evidence_object(presence.attempts_exists),
        events=_evidence_object(presence.events_exists),
    )


def _canonical_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ExecutionFacade:
    """Read/write composition for RAG Dossier execution.

    M05 owns Run/Step/Job/Attempt transactions and state transitions.  M06
    only validates Dossier semantics, computes the Dossier run config, and
    delegates persistence to M05 public functions.
    """

    @staticmethod
    def start_dossier_rollup(
        session: Session,
        *,
        dossier_id: str,
        idempotency_key: str,
        params: dict[str, Any] | None = None,
        kind: str = DOSSIER_ROLLUP_KIND,
    ) -> StartRunResult:
        if not idempotency_key:
            raise InvalidDossierRunParams("idempotency_key is required")
        if kind != DOSSIER_ROLLUP_KIND:
            raise UnsupportedDossierRunKind(f"unsupported dossier run kind: {kind}")
        if params:
            raise InvalidDossierRunParams("dossier_rollup does not accept params")

        dossier = session.get(RagDossier, dossier_id)
        if dossier is None:
            raise DossierNotFound(dossier_id)
        if dossier.status != "active":
            raise DossierArchived(dossier_id)

        config_snapshot = {
            "run_kind": kind,
            "pipeline": DOSSIER_PIPELINE,
            "stage": DOSSIER_ROLLUP_STAGE,
            "scope_type": DOSSIER_SCOPE_TYPE,
            "scope_id": dossier.id,
            "params": {},
        }
        config_hash = _canonical_hash(config_snapshot)
        fingerprint = _canonical_hash(
            {
                "scope_type": DOSSIER_SCOPE_TYPE,
                "scope_id": dossier.id,
                "pipeline": DOSSIER_PIPELINE,
                "stage": DOSSIER_ROLLUP_STAGE,
                "config_hash": config_hash,
            }
        )
        idempotency_payload_hash = execution_service.payload_hash(
            {
                "kind": kind,
                "params": {},
                "dossier_id": dossier.id,
            }
        )
        created = execution_service.create_run_with_step_job(
            session,
            scope_type=DOSSIER_SCOPE_TYPE,
            scope_id=dossier.id,
            pipeline=DOSSIER_PIPELINE,
            stage=DOSSIER_ROLLUP_STAGE,
            config_snapshot=config_snapshot,
            config_hash=config_hash,
            fingerprint=fingerprint,
            step_key=DOSSIER_ROLLUP_STEP_KEY,
            ordinal=1,
            job_key=DOSSIER_ROLLUP_JOB_KEY,
            kind=kind,
            payload={},
            max_attempts=3,
            idempotency_key=idempotency_key,
            idempotency_payload_hash=idempotency_payload_hash,
        )
        worker = ExecutionFacade.worker_status()
        warnings = () if worker.available else ("WORKER_UNAVAILABLE",)
        return StartRunResult(
            run=created.run,
            reused=created.reused,
            worker_available=worker.available,
            warnings=warnings,
        )

    @staticmethod
    def get_run(session: Session, *, run_id: str) -> RunDetail:
        detail = execution_service.get_run_detail(session, run_id=run_id)
        if detail is None:
            raise RunNotFound(run_id)
        return RunDetail(
            run=detail.run,
            config_snapshot=detail.config_snapshot,
            config_hash=detail.config_hash,
            fingerprint=detail.fingerprint,
            parent_run_id=detail.parent_run_id,
            app_git_sha=detail.app_git_sha,
            result=detail.result,
            error_detail=detail.error_detail,
            steps=detail.steps,
            evidence_capabilities=EvidenceCapabilities(),
            evidence_state=_read_evidence_state(run_id),
        )

    @staticmethod
    def list_events(
        session: Session,
        *,
        run_id: str,
        after_id: int = 0,
        limit: int = 50,
    ) -> EventPage:
        page = execution_service.list_run_events(
            session, run_id=run_id, after_id=after_id, limit=limit
        )
        if page is None:
            raise RunNotFound(run_id)
        return page

    @staticmethod
    def cancel_run(session: Session, *, run_id: str) -> CancelRunResult:
        if execution_service.get_run_summary(session, run_id=run_id) is None:
            raise RunNotFound(run_id)
        outcome = execution_service.request_cancel_outcome(session, run_id=run_id)
        return CancelRunResult(
            run=outcome.run,
            already_requested=outcome.already_requested,
        )

    @staticmethod
    def worker_status() -> WorkerSnapshot:
        return read_worker_snapshot()

    @staticmethod
    def scope_stats(
        session: Session,
        *,
        scope_id: str,
        stage: str | None = None,
    ) -> ScopeExecutionStats:
        return execution_service.get_scope_execution_stats(
            session,
            scope_type=DOSSIER_SCOPE_TYPE,
            scope_id=scope_id,
            stage=stage,
        )

    @staticmethod
    def bulk_scope_stats(
        session: Session,
        *,
        scope_ids: list[str] | tuple[str, ...] | set[str],
    ) -> dict[str, ScopeExecutionStats]:
        return execution_service.get_scope_execution_stats_bulk(
            session,
            scope_type=DOSSIER_SCOPE_TYPE,
            scope_ids=scope_ids,
        )

    @staticmethod
    def recent_runs(
        session: Session,
        *,
        scope_id: str,
        limit: int = 5,
        stage: str | None = None,
    ) -> tuple[RunSummary, ...]:
        return execution_service.list_run_summaries_for_scope(
            session,
            scope_type=DOSSIER_SCOPE_TYPE,
            scope_id=scope_id,
            limit=limit,
            stage=stage,
        )

    @staticmethod
    def bulk_recent_runs(
        session: Session,
        *,
        scope_ids: list[str] | tuple[str, ...] | set[str],
        limit_per_scope: int = 5,
    ) -> dict[str, tuple[RunSummary, ...]]:
        return execution_service.list_run_summaries_for_scopes(
            session,
            scope_type=DOSSIER_SCOPE_TYPE,
            scope_ids=scope_ids,
            limit_per_scope=limit_per_scope,
        )
