from __future__ import annotations

import json
from dataclasses import replace
from urllib.error import URLError

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.modules.dingtalk import service
from app.api.v1.dingtalk.router import router

api_app = FastAPI()
api_app.include_router(router)
test_client = TestClient(api_app)


def configure(
    monkeypatch,
    *,
    webhook: str = "https://oapi.dingtalk.com/robot/send?access_token=do-not-leak",
) -> None:
    settings = replace(get_settings(), dingtalk_webhook_url=webhook, dingtalk_keyword="钉钉测试")
    monkeypatch.setattr("app.modules.dingtalk.service.get_settings", lambda: settings)


def test_blank_message_is_rejected(monkeypatch) -> None:
    configure(monkeypatch)
    response = test_client.post(
        "/api/v1/integrations/dingtalk/messages", json={"content": "  \n"}
    )
    assert response.status_code == 422


def test_send_text_success(monkeypatch) -> None:
    configure(monkeypatch)
    captured = {}

    def fake_post(url: str, payload: bytes, timeout: float) -> bytes:
        captured["url"] = url
        captured["payload"] = json.loads(payload)
        captured["timeout"] = timeout
        return b'{"errcode":0,"errmsg":"ok"}'

    monkeypatch.setattr(service, "_post_webhook", fake_post)
    response = test_client.post(
        "/api/v1/integrations/dingtalk/messages", json={"content": "钉钉测试"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert captured["payload"] == {"msgtype": "text", "text": {"content": "钉钉测试"}}
    assert captured["timeout"] == 8.0
    assert "do-not-leak" not in response.text


def test_webhook_not_configured(monkeypatch) -> None:
    configure(monkeypatch, webhook="")
    response = test_client.post(
        "/api/v1/integrations/dingtalk/messages", json={"content": "钉钉测试"}
    )
    assert response.status_code == 503
    assert "webhook" in response.json()["detail"].lower()


def test_keyword_must_be_present(monkeypatch) -> None:
    configure(monkeypatch)
    response = test_client.post(
        "/api/v1/integrations/dingtalk/messages", json={"content": "hello"}
    )
    assert response.status_code == 422


def test_dingtalk_rejection_is_sanitized(monkeypatch) -> None:
    configure(monkeypatch)
    monkeypatch.setattr(
        service,
        "_post_webhook",
        lambda *_args, **_kwargs: b'{"errcode":310000,"errmsg":"https://secret.invalid"}',
    )
    response = test_client.post(
        "/api/v1/integrations/dingtalk/messages", json={"content": "钉钉测试"}
    )
    assert response.status_code == 502
    assert "secret.invalid" not in response.text
    assert "do-not-leak" not in response.text


def test_network_error_is_sanitized(monkeypatch) -> None:
    configure(monkeypatch)

    def fail(*_args, **_kwargs):
        raise URLError("failed for https://secret.invalid?token=secret")

    monkeypatch.setattr(service, "_post_webhook", fail)
    response = test_client.post(
        "/api/v1/integrations/dingtalk/messages", json={"content": "钉钉测试"}
    )
    assert response.status_code == 502
    assert "secret.invalid" not in response.text
    assert "token=secret" not in response.text


@pytest.mark.parametrize(
    "error_factory",
    [lambda: TimeoutError("timed out"), lambda: URLError(TimeoutError("timed out"))],
)
def test_timeout_is_reported_as_unknown_and_never_retried(
    monkeypatch, error_factory
) -> None:
    configure(monkeypatch)
    calls = 0

    def fail(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise error_factory()

    monkeypatch.setattr(service, "_post_webhook", fail)
    response = test_client.post(
        "/api/v1/integrations/dingtalk/messages", json={"content": "钉钉测试"}
    )
    assert response.status_code == 504
    assert "unknown" in response.json()["detail"]
    assert calls == 1


def test_unexpected_response_is_delivery_unknown(monkeypatch) -> None:
    configure(monkeypatch)
    monkeypatch.setattr(service, "_post_webhook", lambda *_args, **_kwargs: b"not-json")
    response = test_client.post(
        "/api/v1/integrations/dingtalk/messages", json={"content": "钉钉测试"}
    )
    assert response.status_code == 504
    assert "unknown" in response.json()["detail"]


def test_keyword_validation_does_not_call_webhook(monkeypatch) -> None:
    configure(monkeypatch)
    monkeypatch.setattr(service, "_post_webhook", lambda *_args: pytest.fail("must not send"))
    with pytest.raises(ValueError, match="keyword"):
        service.send_text("hello")
