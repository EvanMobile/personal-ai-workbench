"""Request and response schemas for Capture."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class CreateCaptureRequest(BaseModel):
    """Client-submitted source details for a JSON Capture request."""

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
                    "input_type": "text",
                    "content": "A note about PostgreSQL backup strategy.",
                    "intent": "knowledge_capture",
                    "metadata": {"platform": "web"},
                }
            ]
        }
    }


class CaptureResponse(BaseModel):
    """Confirmation that a source submission was received and persisted."""

    capture_id: str = Field(description="Stable identifier for this submission.")
    raw_content_id: str = Field(description="Identifier of the persisted Raw Content.")
    status: Literal["received"] = "received"
    storage_status: Literal["stored", "duplicate", "needs_fetch", "failed"]
    source_type: Literal["text", "url", "file"]
    duplicate: bool = False
    message: str


class CaptureDetail(BaseModel):
    id: str
    raw_content_id: str | None
    input_type: str
    intent: str
    status: str
    error: str | None
    created_at: str


class RawContentSummary(BaseModel):
    id: str
    source_type: str
    title: str
    preview: str
    status: str
    created_at: str
