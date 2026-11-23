"""DingTalk test-message API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.modules.dingtalk import service

router = APIRouter(prefix="/api/v1/integrations/dingtalk", tags=["dingtalk"])


class MessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)

    @field_validator("content")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message cannot be empty")
        return value


@router.post("/messages")
def send_message(payload: MessageRequest) -> dict[str, str]:
    try:
        return service.send_text(payload.content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except service.DingTalkNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except service.DingTalkDeliveryUnknown as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except service.DingTalkRejected as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except service.DingTalkError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
