from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
CAPTURE_ENDPOINT = "/api/v1/ingestion/captures"


def test_submit_text_capture_persists_raw_content() -> None:
    response = client.post(
        CAPTURE_ENDPOINT,
        json={
            "input_type": "text",
            "content": "A note to save for later.",
            "intent": "knowledge_capture",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "received"
    assert body["storage_status"] == "stored"
    assert body["source_type"] == "text"
    assert body["capture_id"].startswith("cap_")
    assert body["raw_content_id"].startswith("raw_")
    assert body["message"] == "Capture received successfully"

    raw = client.get(f"/api/v1/ingestion/raw-contents")
    assert raw.status_code == 200
    assert any(item["id"] == body["raw_content_id"] for item in raw.json())


def test_submit_url_capture_is_stored_without_fetching() -> None:
    response = client.post(
        CAPTURE_ENDPOINT,
        json={
            "input_type": "url",
            "content": "https://example.com/article",
            "intent": "knowledge_capture",
            "metadata": {"platform": "web"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source_type"] == "url"
    assert body["storage_status"] == "needs_fetch"
    assert body["duplicate"] is False


def test_duplicate_text_capture_reuses_raw_content() -> None:
    payload = {
        "input_type": "text",
        "content": "Idempotent capture content.",
        "intent": "knowledge_capture",
    }
    first = client.post(CAPTURE_ENDPOINT, json=payload).json()
    second = client.post(CAPTURE_ENDPOINT, json=payload).json()

    assert second["duplicate"] is True
    assert second["raw_content_id"] == first["raw_content_id"]
    assert second["capture_id"] != first["capture_id"]


def test_missing_required_field_is_rejected() -> None:
    response = client.post(
        CAPTURE_ENDPOINT,
        json={"input_type": "url", "content": "https://example.com"},
    )

    assert response.status_code == 422


def test_whitespace_only_content_is_rejected() -> None:
    response = client.post(
        CAPTURE_ENDPOINT,
        json={
            "input_type": "text",
            "content": "   ",
            "intent": "knowledge_capture",
        },
    )

    assert response.status_code == 422


def test_whitespace_only_intent_is_rejected() -> None:
    response = client.post(
        CAPTURE_ENDPOINT,
        json={
            "input_type": "text",
            "content": "A note to save for later.",
            "intent": "   ",
        },
    )

    assert response.status_code == 422


def test_unsupported_input_type_is_rejected() -> None:
    response = client.post(
        CAPTURE_ENDPOINT,
        json={
            "input_type": "image",
            "content": "https://example.com/image.png",
            "intent": "knowledge_capture",
        },
    )

    assert response.status_code == 422


def test_capture_route_is_in_openapi_schema() -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    operation = response.json()["paths"][CAPTURE_ENDPOINT]["post"]
    assert operation["x-audience"] == "CLIENT"
    assert "200" in operation["responses"]


def test_upload_text_file() -> None:
    response = client.post(
        "/api/v1/ingestion/captures/files",
        files={"file": ("notes.md", b"# Notes\n\nA durable idea about PostgreSQL backups.", "text/markdown")},
        data={"intent": "knowledge_capture"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source_type"] == "file"
    assert body["storage_status"] == "stored"


def test_upload_unsupported_file_is_rejected() -> None:
    response = client.post(
        "/api/v1/ingestion/captures/files",
        files={"file": ("binary.exe", b"MZ\x00\x00binary", "application/octet-stream")},
        data={"intent": "knowledge_capture"},
    )

    assert response.status_code == 415
