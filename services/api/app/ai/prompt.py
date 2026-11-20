"""Digest prompt definition.

The prompt is versioned in code for P1.M1 so that generated drafts can record
which instruction set produced them. It follows the six-section contract of
``skills/knowledge-analysis/SKILL.md`` without executing that document as a
runtime Skill.
"""

from __future__ import annotations

DIGEST_PROMPT_VERSION = "digest-v0.1"

SYSTEM_PROMPT = """你是 Personal AI Workbench 的知识整理助手。
把用户提供的原始材料整理为一张知识卡片草稿，必须使用以下六个二级标题，顺序固定：
## What
## Accuracy
## Decision
## Value
## Action
## Pipeline

要求：
1. 只依据给定材料，不编造事实、来源或数据。
2. 无法核实的内容明确标注“未核实”。
3. 不要输出发布状态；草稿必须由用户人工确认后才可发布。
"""


def build_user_prompt(raw_text: str, source_type: str, source_title: str) -> str:
    return (
        f"来源类型：{source_type}\n"
        f"来源标题：{source_title}\n\n"
        "原始材料：\n"
        "---\n"
        f"{raw_text}\n"
        "---\n"
        "请输出六节知识卡片草稿。"
    )
