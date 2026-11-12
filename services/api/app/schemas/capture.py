"""Request and response schemas for Capture."""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class CreateCaptureRequest(BaseModel):
    """Client-submitted source details for a Capture request."""

    input_type: Literal["url", "text"] = Field(
        description="Kind of source supplied by the client."
    )
    content: str = Field(min_length=1, description="Raw URL or text supplied by the client.")
    intent: str = Field(min_length=1, description="The client's reason for submitting the source.")
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Optional source metadata supplied by the client.",
    )

    @field_validator("content", "intent")
    @classmethod
    def reject_whitespace_only(cls, value: str) -> str:
        """Reject blank values while preserving all non-blank input unchanged."""
        if not value.strip():
            raise ValueError("must not be empty or whitespace only")
        return value

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "input_type": "url",
                    "content": "https://x.com/example/status/123",
                    "intent": "knowledge_capture",
                    "metadata": {"platform": "x"},
                }
            ]
        }
    }


class CaptureResponse(BaseModel):
    """Confirmation that a source submission was received."""

    capture_id: str = Field(description="Temporary identifier for this submission.")
    status: Literal["received"]
    message: str
