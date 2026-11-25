"""RAG Dossier HTTP endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy.orm import Session

from app.api.v1.rag.errors import RagAPIError, to_http_error
from app.api.v1.rag.schemas import (
    DossierCreateRequest,
    DossierDetailSchema,
    DossierListSchema,
    DossierSummarySchema,
    StartRunRequest,
    StartRunResponse,
)
from app.core.db import get_session
from app.modules.evaluation.facades.dossiers import DossierFacade
from app.modules.evaluation.facades.execution import ExecutionFacade

router = APIRouter(prefix="/dossiers", tags=["rag"])


@router.get("", response_model=DossierListSchema)
def list_dossiers(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> DossierListSchema:
    try:
        result = DossierFacade.list(session, limit=limit, offset=offset)
    except Exception as exc:  # noqa: BLE001 - mapped to safe HTTP error
        raise to_http_error(exc) from exc
    return DossierListSchema.model_validate(result)


@router.post("", response_model=DossierSummarySchema, status_code=201)
def create_dossier(
    payload: DossierCreateRequest,
    session: Session = Depends(get_session),
) -> DossierSummarySchema:
    try:
        result = DossierFacade.create(
            session, title=payload.title, description=payload.description
        )
    except Exception as exc:  # noqa: BLE001
        raise to_http_error(exc) from exc
    return DossierSummarySchema.model_validate(result)


@router.get("/{dossier_id}", response_model=DossierDetailSchema)
def get_dossier(
    dossier_id: str,
    session: Session = Depends(get_session),
) -> DossierDetailSchema:
    try:
        result = DossierFacade.detail(session, dossier_id=dossier_id)
    except Exception as exc:  # noqa: BLE001
        raise to_http_error(exc) from exc
    return DossierDetailSchema.model_validate(result)


@router.post("/{dossier_id}/runs", response_model=StartRunResponse)
def start_dossier_run(
    dossier_id: str,
    payload: StartRunRequest,
    response: Response,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    session: Session = Depends(get_session),
) -> StartRunResponse:
    if not idempotency_key.strip():
        raise RagAPIError(
            status_code=422,
            code="RAG_IDEMPOTENCY_KEY_REQUIRED",
            message="Idempotency-Key header is required.",
        )
    if len(idempotency_key) > 128:
        raise RagAPIError(
            status_code=422,
            code="RAG_INVALID_IDEMPOTENCY_KEY",
            message="Idempotency-Key must be at most 128 characters.",
        )
    try:
        result = ExecutionFacade.start_dossier_rollup(
            session,
            dossier_id=dossier_id,
            idempotency_key=idempotency_key,
            params=payload.params,
            kind=payload.kind,
        )
    except Exception as exc:  # noqa: BLE001
        raise to_http_error(exc) from exc
    response.status_code = 200 if result.reused else 202
    return StartRunResponse.model_validate(result)
