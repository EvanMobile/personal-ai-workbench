"""Business logic for acknowledging Capture submissions."""

from uuid import uuid4

from app.schemas.capture import CaptureResponse


def create_capture() -> CaptureResponse:
    """Return a temporary confirmation ID without persisting or triggering work."""
    return CaptureResponse(
        capture_id=f"cap_{uuid4().hex}",
        status="received",
        message="Capture received successfully",
    )
