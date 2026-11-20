"""End-to-end backend pipeline: capture → digest → revise → publish → artifact → dossier → page."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _create_asset(text: str, note: str = "reviewed") -> dict:
    capture = client.post(
        "/api/v1/ingestion/captures",
        json={"input_type": "text", "content": text, "intent": "knowledge_capture"},
    )
    assert capture.status_code == 200, capture.text
    raw_id = capture.json()["raw_content_id"]

    digest = client.post(f"/api/v1/knowledge/raw-contents/{raw_id}/digest")
    assert digest.status_code == 200, digest.text
    draft = digest.json()["draft"]
    assert draft["status"] == "draft"
    for heading in ("What", "Accuracy", "Decision", "Value", "Action", "Pipeline"):
        assert f"## {heading}" in draft["body_markdown"]

    publish = client.post(
        f"/api/v1/knowledge/drafts/{draft['id']}/publish", json={"note": note}
    )
    assert publish.status_code == 200, publish.text
    return publish.json()["asset"]


def test_full_knowledge_pipeline() -> None:
    asset = _create_asset(
        "PostgreSQL backup strategy: use pg_dump custom format and test restore. "
        "RAG pipelines need evaluation. Agent workflows need human approval.",
    )
    assert asset["status"] == "published"
    assert asset["version"] == 1
    assert asset["artifact"] is not None
    assert asset["artifact"]["status"] == "ready"

    image = client.get(asset["artifact"]["url"])
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/png"
    assert len(image.content) > 10_000

    detail = client.get(f"/api/v1/knowledge/assets/{asset['id']}")
    assert detail.status_code == 200
    assert detail.json()["raw_content"]["id"] == asset["raw_content_id"]

    validate = client.get(f"/api/v1/artifacts/{asset['artifact']['id']}/validate")
    assert validate.status_code == 200
    assert validate.json()["hash_matches"] is True

    regenerated = client.post(f"/api/v1/artifacts/{asset['artifact']['id']}/regenerate")
    assert regenerated.status_code == 200
    assert regenerated.json()["status"] == "ready"


def test_draft_revision_does_not_publish_automatically() -> None:
    capture = client.post(
        "/api/v1/ingestion/captures",
        json={
            "input_type": "text",
            "content": "Vector databases store embeddings for retrieval augmented generation.",
            "intent": "knowledge_capture",
        },
    ).json()
    draft = client.post(
        f"/api/v1/knowledge/raw-contents/{capture['raw_content_id']}/digest"
    ).json()["draft"]

    revised = client.post(
        f"/api/v1/knowledge/drafts/{draft['id']}/revisions",
        json={"instruction": "请更简洁，并补充适用边界。"},
    )
    assert revised.status_code == 200
    new_draft = revised.json()["draft"]
    assert new_draft["version"] == draft["version"] + 1
    assert "## Revision" in new_draft["body_markdown"]

    assets = client.get("/api/v1/knowledge/assets").json()
    assert assets == []


def test_dossier_and_page_flow() -> None:
    first = _create_asset("Agent workflow design with RAG and prompt evaluation.")
    second = _create_asset("RAG retrieval evaluation and PostgreSQL vector extension planning.")

    dossier = client.post(
        "/api/v1/knowledge/dossiers",
        json={"name": "AI Engineering Notes", "description": "P1 notes"},
    )
    assert dossier.status_code == 200
    dossier_id = dossier.json()["id"]

    added = client.post(
        f"/api/v1/knowledge/dossiers/{dossier_id}/assets",
        json={"asset_ids": [first["id"], second["id"]]},
    )
    assert added.status_code == 200
    body = added.json()
    assert len(body["cards"]) == 2
    assert body["edges"], "cards sharing RAG tag should produce an edge"

    pages = client.post(
        "/api/v1/knowledge/pages", json={"dossier_id": dossier_id, "title": "AI Notes"}
    )
    assert pages.status_code == 200
    detail = pages.json()
    assert detail["current"]["version"] == 1
    assert detail["current"]["content_json"]["sections"]

    regenerated = client.post(f"/api/v1/knowledge/pages/{detail['page']['id']}/regenerate")
    assert regenerated.status_code == 200
    assert regenerated.json()["current"]["version"] == 2
    assert len(regenerated.json()["versions"]) == 2


def test_chat_and_suggestions() -> None:
    asset = _create_asset("Prompt engineering for LLM evaluation and testing.")
    conversation = client.post("/api/v1/chat/conversations", json={"title": "Review"}).json()

    message = client.post(
        f"/api/v1/chat/conversations/{conversation['id']}/messages",
        json={"content": "哪些卡片还没归档？"},
    )
    assert message.status_code == 200
    assert message.json()["reply"]["role"] == "assistant"

    detail = client.get(f"/api/v1/chat/conversations/{conversation['id']}")
    assert len(detail.json()["messages"]) == 2

    suggestions = client.get("/api/v1/chat/suggestions")
    assert suggestions.status_code == 200
    kinds = {item["kind"] for item in suggestions.json()}
    assert "classify_cards" in kinds


def test_stats_reflect_data() -> None:
    _create_asset("Evaluation run for RAG retrieval quality.")
    stats = client.get("/api/v1/knowledge/stats").json()
    assert stats["raw_contents"] == 1
    assert stats["assets"] == 1
    assert stats["artifacts"] == 1
