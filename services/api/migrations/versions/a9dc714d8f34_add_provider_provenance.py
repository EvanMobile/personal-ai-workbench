"""add provider provenance

Revision ID: a9dc714d8f34
Revises: 5ed6407ef6a8
Create Date: 2026-11-20 02:01:33.617689

Adds an explicit provider / processing mode / mock flag to drafts, revisions,
published assets and artifacts. Historical rows are classified only when the
stored model name is unambiguous (``mock*``); everything else is marked
``unknown`` and ``is_mock = NULL`` rather than being presented as a real LLM.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a9dc714d8f34'
down_revision: Union[str, None] = '5ed6407ef6a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ("drafts", "draft_revisions", "knowledge_assets", "artifacts")


def upgrade() -> None:
    for table in TABLES:
        op.add_column(
            table,
            sa.Column("provider", sa.String(length=32), nullable=False, server_default="unknown"),
        )
        op.add_column(
            table,
            sa.Column(
                "processing_mode", sa.String(length=32), nullable=False, server_default="unknown"
            ),
        )
        op.add_column(table, sa.Column("is_mock", sa.Boolean(), nullable=True))

    op.add_column(
        "draft_revisions",
        sa.Column("prompt_version", sa.String(length=64), nullable=False, server_default="unknown"),
    )

    # Only rows whose model name unambiguously identifies the offline mock are
    # marked as mock. Anything else is left unknown, never as a real provider.
    for table in ("drafts", "draft_revisions", "knowledge_assets"):
        op.execute(
            f"UPDATE {table} SET provider = 'mock', processing_mode = 'rule_based', "
            "is_mock = true WHERE model LIKE 'mock%'"
        )
        op.execute(
            f"UPDATE {table} SET provider = 'unknown', processing_mode = 'unknown', "
            "is_mock = NULL WHERE model IS NULL OR model NOT LIKE 'mock%'"
        )

    op.execute(
        """
        UPDATE artifacts AS a
        SET provider = ka.provider,
            processing_mode = ka.processing_mode,
            is_mock = ka.is_mock
        FROM knowledge_assets AS ka
        WHERE a.target_type = 'knowledge_asset' AND a.target_id = ka.id
        """
    )

    for table in TABLES:
        op.alter_column(table, "provider", server_default=None)
        op.alter_column(table, "processing_mode", server_default=None)
    op.alter_column("draft_revisions", "prompt_version", server_default=None)


def downgrade() -> None:
    op.drop_column("draft_revisions", "prompt_version")
    for table in TABLES:
        op.drop_column(table, "is_mock")
        op.drop_column(table, "processing_mode")
        op.drop_column(table, "provider")
