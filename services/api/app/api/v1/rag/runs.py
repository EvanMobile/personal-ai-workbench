"""Execution Run HTTP endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.rag.errors import to_http_error
from app.api.v1.rag.schemas import (
    CancelRunResponse,
    EventPageSchema,
    RunDetailSchema,
)
from app.core.db import get_session
from app.modules.evaluation.facades.execution import ExecutionFacade

router = APIRouter(prefix="/runs", tags=["rag"])


@router.get("/{run_id}", response_model=RunDetailSchema)
def get_run(
    run_id: str,
    session: Session = Depends(get_session),
) -> RunDetailSchema:
    try:
        result = ExecutionFacade.get_run(session, run_id=run_id)
    except Exception as exc:  # noqa: BLE001
        raise to_http_error(exc) from exc
    return RunDetailSchema.model_validate(result)


@router.get("/{run_id}/events", response_model=EventPageSchema)
def list_run_events(
    run_id: str,
    after_id: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
) -> EventPageSchema:
    try:
        result = ExecutionFacade.list_events(
            session, run_id=run_id, after_id=after_id, limit=limit
        )
    except Exception as exc:  # noqa: BLE001
        raise to_http_error(exc) from exc
    return EventPageSchema.model_validate(result)


@router.post("/{run_id}/cancel", response_model=CancelRunResponse)
def cancel_run(
    run_id: str,
    session: Session = Depends(get_session),
) -> CancelRunResponse:
    try:
        result = ExecutionFacade.cancel_run(session, run_id=run_id)
    except Exception as exc:  # noqa: BLE001
        raise to_http_error(exc) from exc
    return CancelRunResponse.model_validate(result)
