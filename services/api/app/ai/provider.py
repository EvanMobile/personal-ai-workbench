"""LLM provider abstraction.

P1.M1 runs on a deterministic mock provider. A real external provider is only
constructed when BOTH ``LLM_PROVIDER=openai`` and ``ALLOW_REAL_LLM=true`` are
set; the default configuration never performs network calls. The first real
call still requires explicit Owner authorization.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol

from app.ai.prompt import DIGEST_PROMPT_VERSION, SYSTEM_PROMPT, build_user_prompt
from app.core.config import get_settings


class ProviderNotAuthorized(RuntimeError):
    """Raised when a real provider is requested without authorization."""


@dataclass(frozen=True)
class DigestResult:
    title: str
    summary: str
    conclusion: str
    body_markdown: str
    category: str
    tags: list[str]
    sections: dict[str, str]


class LLMProvider(Protocol):
    name: str
    model: str
    processing_mode: str
    is_mock: bool

    def digest(self, raw_text: str, source_type: str, source_title: str) -> DigestResult: ...

    def revise(self, raw_text: str, source_title: str, instruction: str) -> str: ...


CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "AI 应用工程": (
        "llm", "大模型", "agent", "智能体", "rag", "检索增强", "prompt", "提示词",
        "embedding", "向量", "mcp", "workflow", "工作流", "推理", "微调", "模型",
    ),
    "后端与基础设施": (
        "postgres", "postgresql", "数据库", "python", "api", "fastapi", "redis",
        "队列", "docker", "k8s", "缓存", "事务", "性能", "迁移",
    ),
    "工程方法与架构": (
        "重构", "测试", "架构", "代码", "工程", "规范", "版本", "评审", "设计模式",
    ),
    "产品与交互": (
        "产品", "用户", "交互", "体验", "ux", "ui", "需求", "场景",
    ),
}

TAG_DISPLAY = {
    "llm": "LLM",
    "大模型": "LLM",
    "agent": "Agent",
    "智能体": "Agent",
    "rag": "RAG",
    "检索增强": "RAG",
    "prompt": "Prompt",
    "提示词": "Prompt",
    "embedding": "Embedding",
    "向量": "Embedding",
    "mcp": "MCP",
    "workflow": "Workflow",
    "工作流": "Workflow",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "数据库": "Database",
    "python": "Python",
    "api": "API",
    "fastapi": "FastAPI",
    "redis": "Redis",
    "缓存": "Caching",
    "测试": "Testing",
    "架构": "Architecture",
    "工程": "Engineering",
    "产品": "Product",
    "交互": "Interaction",
}


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _title(raw_text: str, source_title: str) -> str:
    if source_title and source_title.strip() and source_title.strip() != "Untitled":
        return source_title.strip()[:80]
    for line in raw_text.splitlines():
        stripped = line.strip(" #\t")
        if stripped:
            return stripped[:80]
    return "Untitled capture"


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？.!?])\s+|\n+", text)
    return [p.strip() for p in parts if p.strip()]


_ENGLISH_KEYWORD = re.compile(r"^[a-z0-9][a-z0-9 ._-]*$")


def _keyword_present(lowered: str, keyword: str) -> bool:
    """Match English keywords on word boundaries, Chinese by substring.

    Substring matching alone caused false positives such as ``storage`` -> ``rag``
    and ``rapid`` -> ``api``. English keywords therefore require non-alphanumeric
    boundaries; Chinese keywords rely on plain substring matching (no segmenter).
    """
    keyword = keyword.lower()
    if not keyword:
        return False
    if _ENGLISH_KEYWORD.match(keyword):
        pattern = rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])"
        return re.search(pattern, lowered) is not None
    return keyword in lowered


def _matched_keywords(lowered: str, keywords: tuple[str, ...]) -> list[str]:
    """Return distinct matched keywords, dropping nested ones.

    ``大模型`` and ``模型`` would otherwise count twice for one occurrence.
    """
    matched = [keyword for keyword in keywords if _keyword_present(lowered, keyword)]
    return [
        keyword
        for keyword in matched
        if not any(keyword != other and keyword in other for other in matched)
    ]


def _classify(text: str) -> tuple[str, int]:
    lowered = text.lower()
    best = ("通用知识", 0)
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = len(_matched_keywords(lowered, keywords))
        if score > best[1]:
            best = (category, score)
    return best


def _tags(text: str, limit: int = 4) -> list[str]:
    lowered = text.lower()
    found: list[str] = []
    for keyword, display in TAG_DISPLAY.items():
        if _keyword_present(lowered, keyword) and display not in found:
            found.append(display)
        if len(found) >= limit:
            break
    return found or ["General"]


class MockProvider:
    """Deterministic, offline digest generator for P1.M1 acceptance."""

    name = "mock"
    # Fixed identity: changing LLM_MODEL must never make mock output look like
    # a real model. Provider and processing mode are stored separately.
    model = "mock-digest-v1"
    processing_mode = "rule_based"
    is_mock = True

    def digest(self, raw_text: str, source_type: str, source_title: str) -> DigestResult:
        cleaned = _clean(raw_text)
        sentences = _sentences(raw_text)
        title = _title(raw_text, source_title)
        category, score = _classify(raw_text)
        tags = _tags(raw_text)
        summary = (sentences[0] if sentences else cleaned)[:180]
        uncertainty = (
            "当前为规则模拟结果，未执行语义分析或外部事实核验。请对照原始来源自行复核。"
        )
        if score >= 3:
            decision = "建议吸收：材料与当前工程方向高度相关，可进入知识库。"
        elif score >= 1:
            decision = "选择性吸收：保留可复用的概念与做法，忽略与当前阶段无关的部分。"
        else:
            decision = "可作为背景参考：与当前工程阶段关联较弱。"

        what = " ".join(sentences[:3])[:500] or cleaned[:500]
        value_map = {
            "AI 应用工程": "可用于 LLM 应用、Agent 编排与检索增强的工程判断。",
            "后端与基础设施": "可用于服务分层、数据持久化与运行可靠性设计。",
            "工程方法与架构": "可用于架构评审、代码组织与工程流程改进。",
            "产品与交互": "可用于工作台交互与知识组织方式的设计参考。",
            "通用知识": "可作为后续主题研究的背景材料。",
        }
        value = value_map[category]
        action = {
            "AI 应用工程": "- 提取可复用的架构模式，标注适用边界。\n- 对照现有 RAG/Agent 设计，记录差异。\n- 在人工确认后归档到相关 Dossier。",
            "后端与基础设施": "- 核对与当前 PostgreSQL/FastAPI 栈的兼容性。\n- 记录可落地的迁移或运维步骤。\n- 需要时补充 ADR。",
            "工程方法与架构": "- 将结论转为可执行的检查项。\n- 在下一个 Task Brief 中验证。\n- 记录不适用场景。",
            "产品与交互": "- 对照现有三栏工作台评估可用性影响。\n- 记录需要用户确认的交互点。\n- 形成后续设计任务。",
            "通用知识": "- 保留来源链接与原文。\n- 标注与当前项目的关系。\n- 暂不进入施工决策。",
        }[category]
        pipeline = (
            f"保存为 Card，分类“{category}”，标签 {', '.join(tags)}；"
            "经人工确认 Publish 后可归档到 Dossier。"
        )

        sections = {
            "What": what,
            "Accuracy": uncertainty,
            "Decision": decision,
            "Value": value,
            "Action": action,
            "Pipeline": pipeline,
        }
        body = "\n\n".join(f"## {name}\n\n{content}" for name, content in sections.items())
        conclusion = f"该材料属于{category}，核心内容是“{title}”；{decision.split('：')[0]}。"
        return DigestResult(
            title=title,
            summary=summary,
            conclusion=conclusion,
            body_markdown=body,
            category=category,
            tags=tags,
            sections=sections,
        )

    def revise(self, raw_text: str, source_title: str, instruction: str) -> str:
        base = self.digest(raw_text, "text", source_title)
        sections = dict(base.sections)
        instruction_clean = _clean(instruction)
        if any(word in instruction_clean for word in ("简短", "简洁", "压缩")):
            sections["What"] = sections["What"][:240]
            sections["Action"] = "\n".join(sections["Action"].splitlines()[:2])
        if any(word in instruction_clean for word in ("详细", "展开", "补充")):
            sections["Value"] += f" 补充关注点：{instruction_clean[:120]}。"
        sections["Revision"] = (
            f"用户修订指令：{instruction_clean}\n\n"
            "本次修订仍为 Draft，未发布；发布必须由用户在界面中显式确认。"
        )
        order = ["What", "Accuracy", "Decision", "Value", "Action", "Pipeline", "Revision"]
        return "\n\n".join(f"## {name}\n\n{sections[name]}" for name in order)


class OpenAIProvider:
    """Guarded adapter skeleton. Never used in the default P1.M1 configuration."""

    name = "openai"
    processing_mode = "llm"
    is_mock = False

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.allow_real_llm:
            raise ProviderNotAuthorized(
                "真实 Provider 调用未获授权：需要 Owner 明确批准并设置 ALLOW_REAL_LLM=true。"
            )
        if not settings.llm_provider == "openai":
            raise ProviderNotAuthorized("LLM_PROVIDER 不是 openai。")
        self.model = settings.llm_model

    def digest(self, raw_text: str, source_type: str, source_title: str) -> DigestResult:
        raise ProviderNotAuthorized(
            "OpenAI 适配层未在 P1.M1 启用；首次真实调用前须由 Owner 授权并补充实现。"
        )

    def revise(self, raw_text: str, source_title: str, instruction: str) -> str:
        raise ProviderNotAuthorized("OpenAI 适配层未在 P1.M1 启用。")


def get_provider() -> LLMProvider:
    settings = get_settings()
    if settings.llm_provider == "mock":
        return MockProvider()
    if settings.llm_provider == "openai":
        return OpenAIProvider()
    raise ProviderNotAuthorized(f"未知 LLM_PROVIDER: {settings.llm_provider}")


def prompt_metadata() -> dict[str, Any]:
    settings = get_settings()
    return {
        "prompt_version": DIGEST_PROMPT_VERSION,
        "system_prompt": SYSTEM_PROMPT,
        "provider": settings.llm_provider,
        "model": settings.llm_model,
        "build_user_prompt": build_user_prompt,
    }
