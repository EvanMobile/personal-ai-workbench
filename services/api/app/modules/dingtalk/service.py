"""Send text messages to a DingTalk custom robot webhook."""

from __future__ import annotations

import json
import logging
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class DingTalkError(RuntimeError):
    """Safe, user-facing DingTalk integration error."""


class DingTalkNotConfigured(DingTalkError):
    pass


class DingTalkDeliveryUnknown(DingTalkError):
    """The request may have reached DingTalk, so callers must not retry blindly."""


class DingTalkRejected(DingTalkError):
    pass


def _post_webhook(url: str, payload: bytes, timeout: float) -> bytes:
    request = Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def send_text(content: str) -> dict[str, str]:
    settings = get_settings()
    if not settings.dingtalk_webhook_url:
        raise DingTalkNotConfigured("DingTalk webhook is not configured")

    parsed_url = urlsplit(settings.dingtalk_webhook_url)
    if parsed_url.scheme != "https" or parsed_url.hostname != "oapi.dingtalk.com":
        raise DingTalkError("DingTalk webhook URL is invalid")

    message = content.strip()
    if not message:
        raise ValueError("Message cannot be empty")
    if not settings.dingtalk_keyword or settings.dingtalk_keyword not in message:
        raise ValueError("Message must contain the configured DingTalk keyword")

    payload = json.dumps(
        {"msgtype": "text", "text": {"content": message}}, ensure_ascii=False
    ).encode("utf-8")
    try:
        response_bytes = _post_webhook(settings.dingtalk_webhook_url, payload, timeout=8.0)
    except TimeoutError as exc:
        raise DingTalkDeliveryUnknown(
            "DingTalk response timed out; delivery status is unknown. Check the group before retrying."
        ) from exc
    except HTTPError as exc:
        # Do not include exception text: urllib errors can contain the credential URL.
        raise DingTalkRejected(f"DingTalk returned HTTP {exc.code}") from exc
    except (URLError, OSError) as exc:
        if isinstance(exc, TimeoutError) or isinstance(getattr(exc, "reason", None), TimeoutError):
            raise DingTalkDeliveryUnknown(
                "DingTalk response timed out; delivery status is unknown. Check the group before retrying."
            ) from exc
        raise DingTalkError("Could not connect to DingTalk") from exc

    try:
        result = json.loads(response_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DingTalkDeliveryUnknown(
            "DingTalk returned an unexpected response; delivery status is unknown. Check the group before retrying."
        ) from exc
    if not isinstance(result, dict):
        raise DingTalkDeliveryUnknown(
            "DingTalk returned an unexpected response; delivery status is unknown. Check the group before retrying."
        )
    if result.get("errcode") != 0:
        # Avoid relaying arbitrary platform text that might contain request details.
        logger.warning("DingTalk rejected a message (errcode=%s)", result.get("errcode"))
        raise DingTalkRejected("DingTalk rejected the message")
    return {"status": "accepted", "message": "DingTalk accepted the message"}
