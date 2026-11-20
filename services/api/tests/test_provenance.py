"""Provider provenance and Mock transparency tests."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.ai.provider import MockProvider, get_provider
from app.core.config import get_settings
from app.modules.capture.models import RawContent
from app.modules.knowledge.models import AssetVersion, Draft
from app.modules.knowledge.service import draft_payload
from app.modules.artifact.renderer import format_source_line

MOCK_ACCURACY = (
    "当前为规则模拟结果，未执行语义分析或外部事实核验。请对照原始来源自行复核。"
)


def test_mock_identity_is_independent_of_llm_model(monkeypatch) -> None:
    monkeypatch.setenv("LLM_MODEL", "gpt-4o-pretend-real")
    get_settings.cache_clear()
    try:
        provider = get_provider()
        assert provider.name == "mock"
        assert provider.model == "mock-digest-v1"
        assert provider.processing_mode == "rule_based"
        assert provider.is_mock is True
    finally:
        monkeypatch.delenv("LLM_MODEL", raising=False)
        get_settings.cache_clear()


def test_mock_accuracy_never_claims_fact_checking() -> None:
    result = MockProvider().digest(
        "A claim with 42 percent improvement and no source.", "text", "claim"
    )
    assert result.sections["Accuracy"] == MOCK_ACCURACY
    assert "未发现需要外部核验" not in result.body_markdown
    assert "规则模拟" in result.body_markdown


def test_keyword_false_positives_are_removed() -> None:
    provider = MockProvider()
    storage = provider.digest("Storage growth is a concern.", "text", "storage")
    rapid = provider.digest("Rapid growth is a concern.", "text", "rapid")

    assert "RAG" not in storage.tags
    assert storage.category == "通用知识"
    assert "API" not in rapid.tags
    assert rapid.category == "通用知识"


def test_nested_chinese_keyword_does_not_double_count() -> None:
    provider = MockProvider()
    single = provider.digest("大模型", "text", "one")
    repeated = provider.digest("大模型 大模型 大模型", "text", "many")

    # One distinct keyword -> score 1 -> selective, not absorb (score >= 3).
    assert single.sections["Decision"].startswith("选择性吸收")
    assert repeated.sections["Decision"].startswith("选择性吸收")


def test_draft_revision_and_publish_keep_provenance(client: TestClient, db) -> None:
    capture = client.post(
        "/api/v1/ingestion/captures",
        json={
            "input_type": "text",
            "content": "PostgreSQL migrations must be reviewed before applying.",
            "intent": "knowledge_capture",
        },
    ).json()

    draft = client.post(
        f"/api/v1/knowledge/raw-contents/{capture['raw_content_id']}/digest"
    ).json()["draft"]
    assert draft["provider"] == "mock"
    assert draft["model"] == "mock-digest-v1"
    assert draft["processing_mode"] == "rule_based"
    assert draft["is_mock"] is True

    revised = client.post(
        f"/api/v1/knowledge/drafts/{draft['id']}/revisions",
        json={"instruction": "请更简洁。"},
    ).json()["draft"]
    assert revised["provider"] == "mock"
    assert revised["is_mock"] is True

    published = client.post(
        f"/api/v1/knowledge/drafts/{draft['id']}/publish", json={}
    ).json()
    asset = published["asset"]
    assert asset["provider"] == "mock"
    assert asset["processing_mode"] == "rule_based"
    assert asset["is_mock"] is True
    assert asset["model"] == "mock-digest-v1"

    artifact = published["artifact"]
    assert artifact["provider"] == "mock"
    assert artifact["processing_mode"] == "rule_based"
    assert artifact["is_mock"] is True

    version = db.scalar(
        select(AssetVersion).where(AssetVersion.asset_id == asset["id"])
    )
    assert version is not None
    assert version.snapshot["provider"] == "mock"
    assert version.snapshot["is_mock"] is True
    assert version.snapshot["processing_mode"] == "rule_based"
    assert version.snapshot["prompt_version"] == "digest-v0.1"


def test_legacy_rows_are_not_presented_as_real(db) -> None:
    raw = RawContent(
        source_type="text",
        title="Legacy",
        text="Legacy content",
        meta={},
        status="stored",
    )
    db.add(raw)
    db.flush()
    legacy = Draft(
        raw_content_id=raw.id,
        title="Legacy draft",
        summary="",
        conclusion="",
        body_markdown="",
        category="General",
        tags=[],
        provider="unknown",
        model="legacy-model",
        prompt_version="unknown",
        processing_mode="unknown",
        is_mock=None,
        status="draft",
    )
    db.add(legacy)
    db.commit()
    db.refresh(legacy)

    payload = draft_payload(legacy)
    assert payload["provider"] == "unknown"
    assert payload["processing_mode"] == "unknown"
    assert payload["is_mock"] is None


def test_artifact_source_labels() -> None:
    mock = format_source_line(
        category="Backend",
        provider="mock",
        model="mock-digest-v1",
        version=1,
        processing_mode="rule_based",
        is_mock=True,
    )
    assert "MOCK" in mock and "RULE_BASED" in mock

    legacy = format_source_line(
        category="Backend",
        provider="unknown",
        model="unknown",
        version=1,
        processing_mode="unknown",
        is_mock=None,
    )
    assert "UNKNOWN" in legacy and "MOCK" not in legacy

    real = format_source_line(
        category="Backend",
        provider="openai",
        model="real-model",
        version=1,
        processing_mode="llm",
        is_mock=False,
    )
    assert "openai" in real and "MOCK" not in real
