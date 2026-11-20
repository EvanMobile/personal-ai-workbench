"""Capture input parsing and file storage helpers."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from app.core.config import get_settings

TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".csv", ".json", ".log", ".yaml", ".yml"}
MAX_TITLE = 120


class UnsupportedFileType(ValueError):
    """Raised when an uploaded file cannot be parsed as readable text."""


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def derive_title(text: str, fallback: str = "Untitled capture") -> str:
    for line in text.splitlines():
        stripped = line.strip(" #\t")
        if stripped:
            return re.sub(r"\s+", " ", stripped)[:MAX_TITLE]
    return fallback


def decode_upload(filename: str, payload: bytes) -> tuple[str, str]:
    settings = get_settings()
    if len(payload) > settings.max_upload_bytes:
        raise UnsupportedFileType(
            f"文件超过大小限制（{settings.max_upload_bytes // 1024} KB）"
        )
    suffix = Path(filename or "").suffix.lower()
    if suffix not in TEXT_EXTENSIONS:
        allowed = ", ".join(sorted(TEXT_EXTENSIONS))
        raise UnsupportedFileType(f"暂不支持 {suffix or '未知'} 格式；当前支持：{allowed}")
    if not payload:
        raise UnsupportedFileType("文件为空")
    try:
        return payload.decode("utf-8"), suffix
    except UnicodeDecodeError as exc:
        raise UnsupportedFileType("文件不是有效的 UTF-8 文本") from exc


def store_upload(raw_id: str, suffix: str, payload: bytes) -> Path:
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    target = settings.upload_dir / f"{raw_id}{suffix}"
    target.write_bytes(payload)
    return target
