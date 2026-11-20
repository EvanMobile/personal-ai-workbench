"""replace misleading mock accuracy wording

Revision ID: 4c239bff00b0
Revises: a9dc714d8f34
Create Date: 2026-11-20 02:04:00

Historical mock drafts used an Accuracy sentence that could read as if the
system had verified facts. This migration replaces only that disclaimer text;
all knowledge claims and generated sections remain unchanged.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = '4c239bff00b0'
down_revision: Union[str, None] = 'a9dc714d8f34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_NUMERIC = (
    "材料包含具体数字或强结论，P1.M1 的 Mock Digest 未做外部核对，需人工对照原始来源复核。"
)
OLD_GENERIC = "未发现需要外部核验的强断言；仍建议保留来源并人工确认。"
NEW_TEXT = "当前为规则模拟结果，未执行语义分析或外部事实核验。请对照原始来源自行复核。"


def upgrade() -> None:
    for table in ("drafts", "knowledge_assets", "asset_versions"):
        op.execute(
            f"UPDATE {table} SET body_markdown = replace(body_markdown, '{OLD_NUMERIC}', '{NEW_TEXT}')"
        )
        op.execute(
            f"UPDATE {table} SET body_markdown = replace(body_markdown, '{OLD_GENERIC}', '{NEW_TEXT}')"
        )


def downgrade() -> None:
    # Intentionally no automatic restore: the previous wording was misleading.
    pass
