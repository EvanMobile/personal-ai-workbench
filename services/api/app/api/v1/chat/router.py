"""Chat API for the Workbench AI panel."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.modules.chat import service

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


class ConversationCreate(BaseModel):
    title: str | None = None


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


@router.get("/conversations")
def list_conversations(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return service.list_conversations(session)


@router.post("/conversations")
def create_conversation(
    payload: ConversationCreate | None = None, session: Session = Depends(get_session)
) -> dict[str, Any]:
    conversation = service.create_conversation(session, payload.title if payload else None)
    return {
        "id": conversation.id,
        "title": conversation.title,
        "created_at": conversation.created_at.isoformat(),
    }


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    detail = service.conversation_detail(session, conversation_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Conversation 不存在")
    return detail


@router.post("/conversations/{conversation_id}/messages")
def post_message(
    conversation_id: str, payload: MessageCreate, session: Session = Depends(get_session)
) -> dict[str, Any]:
    result = service.add_message(session, conversation_id, payload.content)
    if result is None:
        raise HTTPException(status_code=404, detail="Conversation 不存在")
    return result


@router.get("/suggestions")
def read_suggestions(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return service.suggestions(session)
