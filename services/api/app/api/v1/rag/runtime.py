"""Worker runtime HTTP endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.rag.errors import to_http_error
from app.api.v1.rag.schemas import WorkerSnapshotSchema
from app.modules.evaluation.facades.execution import ExecutionFacade

router = APIRouter(prefix="/runtime", tags=["rag"])


@router.get("/worker", response_model=WorkerSnapshotSchema)
def get_worker_status() -> WorkerSnapshotSchema:
    try:
        result = ExecutionFacade.worker_status()
    except Exception as exc:  # noqa: BLE001
        raise to_http_error(exc) from exc
    return WorkerSnapshotSchema.model_validate(result)
