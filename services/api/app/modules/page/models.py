"""Page models: versioned rich documents generated from a Dossier."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.utils import new_id, utcnow


class Page(Base):
    __tablename__ = "pages"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("pag"))
    dossier_id: Mapped[str] = mapped_column(
        ForeignKey("dossiers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="published")
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class PageVersion(Base):
    __tablename__ = "page_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("pvs"))
    page_id: Mapped[str] = mapped_column(
        ForeignKey("pages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    source_asset_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    renderer: Mapped[str] = mapped_column(String(80), nullable=False, default="dossier-page-v1")
    model: Mapped[str] = mapped_column(String(120), nullable=False, default="mock-page-v1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
