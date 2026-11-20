"""Artifact failures must never block publishing or fake success."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_artifact_failure_does_not_block_publish(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise RuntimeError("renderer unavailable")

    monkeypatch.setattr("app.modules.artifact.service.render_knowledge_card", boom)

    capture = client.post(
        "/api/v1/ingestion/captures",
        json={
            "input_type": "text",
            "content": "Knowledge card content that will fail to render.",
            "intent": "knowledge_capture",
        },
    ).json()
    draft = client.post(
        f"/api/v1/knowledge/raw-contents/{capture['raw_content_id']}/digest"
    ).json()["draft"]

    publish = client.post(f"/api/v1/knowledge/drafts/{draft['id']}/publish", json={})
    assert publish.status_code == 200

    body = publish.json()
    assert body["asset"]["status"] == "published"
    assert body["artifact"] is not None
    assert body["artifact"]["status"] == "failed"
    assert body["artifact"]["url"] is None
    assert "renderer unavailable" in body["artifact"]["error"]

    image = client.get(f"/api/v1/artifacts/{body['artifact']['id']}/file")
    assert image.status_code == 404
