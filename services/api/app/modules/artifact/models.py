"""Visual artifact metadata (cross-business shared service)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.utils import new_id, utcnow


class Artifact(Base):
    """A generated visual for a structured target object.

    The artifact is never the authoritative knowledge data; it references a
    target (``target_type`` + ``target_id``) and the source version/hash used
    to render it.
    """

    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("art"))
    target_type: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(64), nullable=False, default="knowledge_card")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    processing_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    is_mock: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    width: Mapped[int] = mapped_column(Integer, nullable=False, default=1200)
    height: Mapped[int] = mapped_column(Integer, nullable=False, default=1600)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
