"""Capture and Raw Content persistence models (module: capture)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.utils import new_id, utcnow


class Capture(Base):
    """An ingestion request: text, URL or uploaded file."""

    __tablename__ = "captures"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("cap"))
    raw_content_id: Mapped[str | None] = mapped_column(
        ForeignKey("raw_contents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    input_type: Mapped[str] = mapped_column(String(16), nullable=False)
    intent: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="received")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    raw_content: Mapped["RawContent | None"] = relationship(back_populates="capture")


class RawContent(Base):
    """Original material, stored separately from any generated knowledge."""

    __tablename__ = "raw_contents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("raw"))
    capture_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    source_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="Untitled")
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="stored")
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    capture: Mapped["Capture | None"] = relationship(back_populates="raw_content")
