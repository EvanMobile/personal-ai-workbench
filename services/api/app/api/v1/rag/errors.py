"""RAG Lab HTTP error envelope and domain-to-HTTP mapping."""

from __future__ import annotations

import logging

from fastapi import Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.modules.evaluation.errors import (
    DossierArchived,
    DossierNotFound,
    EvaluationError,
    InvalidDossierRunParams,
    RunNotFound,
    UnsupportedDossierRunKind,
)
from app.modules.execution.errors import (
    IdempotencyConflict,
    RunIncomplete,
    RunNotCancellable,
    StaleLease,
)

logger = logging.getLogger(__name__)


class RagAPIError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        recoverable: bool = False,
        details: dict | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.recoverable = recoverable
        self.details = details
        super().__init__(message)

    def body(self) -> dict:
        payload: dict = {
            "code": self.code,
            "message": self.message,
            "recoverable": self.recoverable,
        }
        if self.details is not None:
            payload["details"] = self.details
        return payload


def to_http_error(exc: Exception) -> RagAPIError:
    """Map known domain errors; unknown errors become a safe 500."""
    if isinstance(exc, DossierNotFound):
        return RagAPIError(
            status_code=404,
            code="RAG_DOSSIER_NOT_FOUND",
            message="RAG Dossier not found.",
            details={"dossier_id": str(exc)},
        )
    if isinstance(exc, RunNotFound):
        return RagAPIError(
            status_code=404,
            code="RAG_RUN_NOT_FOUND",
            message="Execution Run not found.",
            details={"run_id": str(exc)},
        )
    if isinstance(exc, DossierArchived):
        return RagAPIError(
            status_code=409,
            code="RAG_DOSSIER_ARCHIVED",
            message="The RAG Dossier is archived and cannot start a Run.",
            details={"dossier_id": str(exc)},
        )
    if isinstance(exc, UnsupportedDossierRunKind):
        return RagAPIError(
            status_code=422,
            code="RAG_UNSUPPORTED_RUN_KIND",
            message="The requested Dossier run kind is not supported.",
        )
    if isinstance(exc, InvalidDossierRunParams):
        return RagAPIError(
            status_code=422,
            code="RAG_INVALID_RUN_PARAMS",
            message="The requested Dossier run parameters are invalid.",
        )
    if isinstance(exc, IdempotencyConflict):
        return RagAPIError(
            status_code=409,
            code="RAG_IDEMPOTENCY_CONFLICT",
            message="Idempotency-Key was already used with a different payload.",
        )
    if isinstance(exc, RunIncomplete):
        return RagAPIError(
            status_code=409,
            code="RAG_RUN_INCOMPLETE",
            message="The idempotent Run is missing its Step or Job.",
            details={"run_id": exc.run_id, "missing": exc.missing},
        )
    if isinstance(exc, RunNotCancellable):
        return RagAPIError(
            status_code=409,
            code="RAG_RUN_NOT_CANCELLABLE",
            message="The Run cannot be cancelled in its current state.",
        )
    if isinstance(exc, StaleLease):
        return RagAPIError(
            status_code=409,
            code="RAG_EXECUTION_CONFLICT",
            message="The execution ownership changed before the request completed.",
        )
    if isinstance(exc, EvaluationError):
        return RagAPIError(
            status_code=409,
            code="RAG_DOMAIN_CONFLICT",
            message="The request conflicts with the current Dossier state.",
        )
    logger.exception("unexpected RAG API error", exc_info=exc)
    return RagAPIError(
        status_code=500,
        code="RAG_INTERNAL_ERROR",
        message="An internal error occurred.",
    )


async def rag_api_error_handler(_request: Request, exc: RagAPIError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.body())


async def rag_request_validation_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    # Preserve the existing FastAPI error shape outside the RAG namespace.
    path = request.url.path
    if not (path == "/api/v1/rag" or path.startswith("/api/v1/rag/")):
        return await request_validation_exception_handler(request, exc)
    errors = exc.errors()
    if any(
        tuple(error.get("loc", ()))[-1:] == ("Idempotency-Key",)
        and error.get("type") == "missing"
        for error in errors
    ):
        return JSONResponse(
            status_code=422,
            content={
                "code": "RAG_IDEMPOTENCY_KEY_REQUIRED",
                "message": "Idempotency-Key header is required.",
                "recoverable": False,
            },
        )
    details = [
        {
            "loc": list(error.get("loc", ())),
            "msg": error.get("msg", "Invalid value."),
            "type": error.get("type", "value_error"),
        }
        for error in errors
    ]
    return JSONResponse(
        status_code=422,
        content={
            "code": "RAG_VALIDATION_ERROR",
            "message": "The request parameters are invalid.",
            "recoverable": False,
            "details": {"errors": details},
        },
    )
