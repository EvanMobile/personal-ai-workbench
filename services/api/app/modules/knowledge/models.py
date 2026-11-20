"""Draft, published asset, version and publish-record models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.utils import new_id, utcnow


class Draft(Base):
    """AI-generated candidate knowledge, editable by the user before publish."""

    __tablename__ = "drafts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("dft"))
    raw_content_id: Mapped[str] = mapped_column(
        ForeignKey("raw_contents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    conclusion: Mapped[str] = mapped_column(Text, nullable=False, default="")
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(String(80), nullable=False, default="Uncategorized")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    processing_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    is_mock: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class DraftRevision(Base):
    """A user-instruction-driven revision of a draft."""

    __tablename__ = "draft_revisions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("rev"))
    draft_id: Mapped[str] = mapped_column(
        ForeignKey("drafts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    instruction: Mapped[str] = mapped_column(Text, nullable=False)
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    processing_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    is_mock: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class KnowledgeAsset(Base):
    """A published, authoritative knowledge card."""

    __tablename__ = "knowledge_assets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("ast"))
    draft_id: Mapped[str] = mapped_column(
        ForeignKey("drafts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    raw_content_id: Mapped[str] = mapped_column(
        ForeignKey("raw_contents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    conclusion: Mapped[str] = mapped_column(Text, nullable=False, default="")
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(String(80), nullable=False, default="Uncategorized")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    model: Mapped[str] = mapped_column(String(120), nullable=False, default="unknown")
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    processing_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    is_mock: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="published")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class AssetVersion(Base):
    """Immutable snapshot of a published asset version."""

    __tablename__ = "asset_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("avs"))
    asset_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class PublishRecord(Base):
    """Audit record for an explicit human publish action."""

    __tablename__ = "publish_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("pub"))
    draft_id: Mapped[str] = mapped_column(
        ForeignKey("drafts.id", ondelete="SET NULL"), nullable=True
    )
    asset_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    asset_version: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
