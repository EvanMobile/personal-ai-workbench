"""M06 RAG Lab experiment organization models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.utils import new_id, utcnow


class RagDossier(Base):
    """A RAG Lab experiment dossier.

    This is deliberately separate from the M02 Personal Knowledge ``dossiers``
    table. It owns no execution or dataset rows; stage state is derived.
    """

    __tablename__ = "rag_dossiers"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: new_id("rdos")
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'archived')",
            name="ck_rag_dossiers_status",
        ),
        Index("ix_rag_dossiers_status_updated", "status", "updated_at"),
    )
