from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
CAPTURE_ENDPOINT = "/api/v1/ingestion/captures"


def test_submit_url_capture() -> None:
    response = client.post(
        CAPTURE_ENDPOINT,
        json={
            "input_type": "url",
            "content": "https://x.com/example/status/123",
            "intent": "knowledge_capture",
            "metadata": {"platform": "x"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"capture_id", "status", "message"}
    assert body["capture_id"].startswith("cap_")
    assert body["status"] == "received"
    assert body["message"] == "Capture received successfully"


def test_submit_text_capture() -> None:
    response = client.post(
        CAPTURE_ENDPOINT,
        json={
            "input_type": "text",
            "content": "A note to save for later.",
            "intent": "knowledge_capture",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "received"


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
