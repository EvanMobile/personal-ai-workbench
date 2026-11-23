"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

API_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(API_ROOT / ".env")


def _flag(name: str) -> bool:
    return os.getenv(name, "false").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    database_url: str
    data_dir: Path
    upload_dir: Path
    artifact_dir: Path
    llm_provider: str
    llm_model: str
    prompt_version: str
    allow_real_llm: bool
    cors_origins: tuple[str, ...]
    max_upload_bytes: int
    dingtalk_webhook_url: str
    dingtalk_keyword: str


@lru_cache
def get_settings() -> Settings:
    data_dir = Path(os.getenv("WORKBENCH_DATA_DIR", API_ROOT / ".data"))
    return Settings(
        database_url=os.getenv(
            "DATABASE_URL", "postgresql+psycopg://127.0.0.1:5432/workbench"
        ),
        data_dir=data_dir,
        upload_dir=data_dir / "uploads",
        artifact_dir=data_dir / "artifacts",
        llm_provider=os.getenv("LLM_PROVIDER", "mock").strip().lower(),
        llm_model=os.getenv("LLM_MODEL", "mock-digest-v1"),
        prompt_version=os.getenv("DIGEST_PROMPT_VERSION", "digest-v0.1"),
        allow_real_llm=_flag("ALLOW_REAL_LLM"),
        cors_origins=tuple(
            origin.strip()
            for origin in os.getenv(
                "CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173"
            ).split(",")
            if origin.strip()
        ),
        max_upload_bytes=int(os.getenv("MAX_UPLOAD_BYTES", str(2 * 1024 * 1024))),
        dingtalk_webhook_url=os.getenv("DINGTALK_WEBHOOK_URL", "").strip(),
        dingtalk_keyword=os.getenv("DINGTALK_KEYWORD", "钉钉测试").strip(),
    )


def ensure_data_dirs() -> None:
    settings = get_settings()
    for path in (settings.data_dir, settings.upload_dir, settings.artifact_dir):
        path.mkdir(parents=True, exist_ok=True)
