"""AI chat panel service: local conversation history and contextual suggestions."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.utils import utcnow
from app.modules.chat.models import ChatMessage, Conversation
from app.modules.dossier.models import Dossier, DossierAsset
from app.modules.knowledge.models import Draft, KnowledgeAsset
from app.modules.page.models import Page, PageVersion


def list_conversations(session: Session) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(Conversation).order_by(Conversation.updated_at.desc())
    ).all()
    return [
        {"id": row.id, "title": row.title, "updated_at": row.updated_at.isoformat()}
        for row in rows
    ]


def create_conversation(session: Session, title: str | None = None) -> Conversation:
    conversation = Conversation(title=(title or "New chat")[:200])
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    return conversation


def get_conversation(session: Session, conversation_id: str) -> Conversation | None:
    return session.get(Conversation, conversation_id)


def conversation_detail(session: Session, conversation_id: str) -> dict[str, Any] | None:
    conversation = get_conversation(session, conversation_id)
    if conversation is None:
        return None
    messages = session.scalars(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation.id)
        .order_by(ChatMessage.created_at.asc())
    ).all()
    return {
        "conversation": {
            "id": conversation.id,
            "title": conversation.title,
            "created_at": conversation.created_at.isoformat(),
        },
        "messages": [
            {
                "id": message.id,
                "role": message.role,
                "content": message.content,
                "created_at": message.created_at.isoformat(),
            }
            for message in messages
        ],
    }


def _reply(session: Session, user_text: str) -> str:
    drafts = session.scalars(select(Draft).where(Draft.status == "draft")).all()
    pages = session.scalars(select(Page)).all()
    return (
        "这是本地工作台助手（P1.M1 未接入外部模型，回复由本地规则生成）。\n\n"
        f"当前知识库：{len(drafts)} 个 Draft 待确认，{len(pages)} 个 Page。\n"
        f"你的问题：{user_text.strip()[:160]}\n\n"
        "建议通过左侧 Context Directory 打开 Card / Dossier / Page 查看；"
        "任何归档、更新或发布操作都需要你明确确认。"
    )


def add_message(session: Session, conversation_id: str, content: str) -> dict[str, Any] | None:
    conversation = get_conversation(session, conversation_id)
    if conversation is None:
        return None
    user_message = ChatMessage(conversation_id=conversation.id, role="user", content=content)
    session.add(user_message)
    session.flush()
    reply = ChatMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=_reply(session, content),
        meta={"generated_by": "local-rules", "provider": "none"},
    )
    session.add(reply)
    conversation.updated_at = utcnow()
    session.commit()
    session.refresh(user_message)
    session.refresh(reply)
    return {
        "user": {
            "id": user_message.id,
            "role": user_message.role,
            "content": user_message.content,
            "created_at": user_message.created_at.isoformat(),
        },
        "reply": {
            "id": reply.id,
            "role": reply.role,
            "content": reply.content,
            "created_at": reply.created_at.isoformat(),
        },
    }


def suggestions(session: Session) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    unarchived = session.scalars(
        select(KnowledgeAsset).where(KnowledgeAsset.archived.is_(False))
    ).all()
    dossier_ids = set(session.scalars(select(DossierAsset.asset_id)).all())
    loose = [asset for asset in unarchived if asset.id not in dossier_ids]
    if loose:
        result.append(
            {
                "id": "sug-classify",
                "kind": "classify_cards",
                "title": f"{len(loose)} 张 Card 尚未归档",
                "description": "可检查分类并归入相关 Dossier；确认后才会生效。",
                "action": {"type": "open_cards", "payload": {"filter": "unarchived"}},
                "related_id": loose[0].id,
            }
        )

    pages = session.scalars(select(Page)).all()
    for page in pages:
        version = session.scalar(
            select(PageVersion).where(
                PageVersion.page_id == page.id, PageVersion.version == page.current_version
            )
        )
        if version is None:
            continue
        cards = [session.get(KnowledgeAsset, asset_id) for asset_id in version.source_asset_ids]
        if any(card and card.updated_at > version.created_at for card in cards):
            dossier = session.get(Dossier, page.dossier_id)
            result.append(
                {
                    "id": f"sug-page-{page.id}",
                    "kind": "regenerate_page",
                    "title": f"Page「{page.title}」的来源已更新",
                    "description": "建议重新生成 Page；需要你确认后才会创建新版本。",
                    "action": {"type": "open_page", "payload": {"page_id": page.id}},
                    "related_id": page.id,
                }
            )
            break

    drafts = session.scalars(select(Draft).where(Draft.status == "draft")).all()
    if drafts:
        result.append(
            {
                "id": "sug-publish",
                "kind": "draft_ready",
                "title": f"{len(drafts)} 个 Draft 等待人工发布",
                "description": "模型输出不会自动发布；请审阅后显式确认。",
                "action": {"type": "open_draft", "payload": {"draft_id": drafts[0].id}},
                "related_id": drafts[0].id,
            }
        )
    return result[:3]
