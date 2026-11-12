"""Capture API routes for client-submitted knowledge sources."""

from fastapi import APIRouter, status

from app.schemas.capture import CaptureResponse, CreateCaptureRequest
from app.services.capture_service import create_capture

router = APIRouter(prefix="/api/v1/ingestion", tags=["CLIENT", "ingestion"])


@router.post(
    "/captures",
    response_model=CaptureResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit a knowledge source for capture",
    description=(
        "Accepts and confirms a knowledge source submitted by the client. Capture is "
        "not persisted. No Fetch, Parse, Normalize, or downstream Ingestion is performed."
    ),
    openapi_extra={"x-audience": "CLIENT"},
)
def submit_capture(request: CreateCaptureRequest) -> CaptureResponse:
    """Confirm receipt of the client submission without persistence or processing."""
    return create_capture()
