"""Capture business service: persist Raw Content for text, URL and file input."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.utils import new_id
from app.modules.capture.models import Capture, RawContent
from app.modules.capture.parsing import (
    decode_upload,
    derive_title,
    sha256_text,
    store_upload,
)
from app.schemas.capture import CaptureResponse


def _persist(
    session: Session,
    *,
    input_type: str,
    intent: str,
    text: str,
    source_type: str,
    source_uri: str | None,
    metadata: dict[str, Any] | None,
    status: str,
) -> CaptureResponse:
    content_hash = sha256_text(text)
    existing = session.scalar(
        select(RawContent).where(
            RawContent.content_hash == content_hash,
            RawContent.source_type == source_type,
        )
    )
    capture = Capture(
        id=new_id("cap"),
        input_type=input_type,
        intent=intent,
        status="duplicate" if existing else "stored",
    )
    session.add(capture)
    session.flush()

    if existing is not None:
        capture.raw_content_id = existing.id
        session.commit()
        return CaptureResponse(
            capture_id=capture.id,
            raw_content_id=existing.id,
            status="received",
            storage_status="duplicate",
            source_type=source_type,
            duplicate=True,
            message="Capture received; identical Raw Content already stored",
        )

    raw = RawContent(
        id=new_id("raw"),
        capture_id=capture.id,
        source_type=source_type,
        source_uri=source_uri,
        title=derive_title(text),
        text=text,
        meta=metadata or {},
        status=status,
        content_hash=content_hash,
    )
    session.add(raw)
    session.flush()
    capture.raw_content_id = raw.id
    session.commit()
    return CaptureResponse(
        capture_id=capture.id,
        raw_content_id=raw.id,
        status="received",
        storage_status="stored" if status == "stored" else status,
        source_type=source_type,
        duplicate=False,
        message="Capture received successfully",
    )


def create_text_or_url_capture(
    session: Session,
    *,
    input_type: str,
    content: str,
    intent: str,
    metadata: dict[str, Any] | None,
) -> CaptureResponse:
    if input_type == "url":
        # No external fetch is performed in P1.M1; the URL is stored verbatim
        # and flagged so downstream processing can explain the limitation.
        return _persist(
            session,
            input_type="url",
            intent=intent,
            text=content,
            source_type="url",
            source_uri=content,
            metadata=metadata,
            status="needs_fetch",
        )
    return _persist(
        session,
        input_type="text",
        intent=intent,
        text=content,
        source_type="text",
        source_uri=None,
        metadata=metadata,
        status="stored",
    )


def create_file_capture(
    session: Session,
    *,
    filename: str,
    payload: bytes,
    intent: str,
    metadata: dict[str, Any] | None,
) -> CaptureResponse:
    text, suffix = decode_upload(filename, payload)
    content_hash = sha256_text(text)
    existing = session.scalar(
        select(RawContent).where(
            RawContent.content_hash == content_hash,
            RawContent.source_type == "file",
        )
    )
    capture = Capture(
        id=new_id("cap"),
        input_type="file",
        intent=intent,
        status="duplicate" if existing else "stored",
    )
    session.add(capture)
    session.flush()
    if existing is not None:
        capture.raw_content_id = existing.id
        session.commit()
        return CaptureResponse(
            capture_id=capture.id,
            raw_content_id=existing.id,
            status="received",
            storage_status="duplicate",
            source_type="file",
            duplicate=True,
            message="Capture received; identical Raw Content already stored",
        )

    raw_id = new_id("raw")
    path = store_upload(raw_id, suffix, payload)
    meta = dict(metadata or {})
    meta.update({"filename": filename, "content_type": suffix})
    raw = RawContent(
        id=raw_id,
        capture_id=capture.id,
        source_type="file",
        source_uri=str(path),
        title=derive_title(text, fallback=filename or "Uploaded file"),
        text=text,
        meta=meta,
        status="stored",
        content_hash=content_hash,
    )
    session.add(raw)
    session.flush()
    capture.raw_content_id = raw.id
    session.commit()
    return CaptureResponse(
        capture_id=capture.id,
        raw_content_id=raw.id,
        status="received",
        storage_status="stored",
        source_type="file",
        duplicate=False,
        message="Capture received successfully",
    )


def get_capture(session: Session, capture_id: str) -> Capture | None:
    return session.get(Capture, capture_id)


def list_raw_contents(session: Session) -> list[RawContent]:
    return list(
        session.scalars(select(RawContent).order_by(RawContent.created_at.desc())).all()
    )
