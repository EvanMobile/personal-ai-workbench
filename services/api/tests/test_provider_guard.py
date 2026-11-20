"""Provider guard: no real external LLM call without explicit authorization."""

from __future__ import annotations

import pytest

from app.ai.provider import ProviderNotAuthorized, get_provider
from app.core.config import get_settings


def test_openai_provider_is_refused_by_default(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("ALLOW_REAL_LLM", "false")
    get_settings.cache_clear()
    try:
        with pytest.raises(ProviderNotAuthorized):
            get_provider()
    finally:
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        monkeypatch.delenv("ALLOW_REAL_LLM", raising=False)
        get_settings.cache_clear()


def test_mock_provider_is_default() -> None:
    get_settings.cache_clear()
    provider = get_provider()
    assert provider.name == "mock"
