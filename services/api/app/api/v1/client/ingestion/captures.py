"""Capture API routes for client-submitted knowledge sources."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.modules.capture.parsing import UnsupportedFileType
from app.modules.capture.service import (
    create_file_capture,
    create_text_or_url_capture,
    get_capture,
    list_raw_contents,
)
from app.schemas.capture import (
    CaptureDetail,
    CaptureResponse,
    CreateCaptureRequest,
    RawContentSummary,
)

router = APIRouter(prefix="/api/v1/ingestion", tags=["CLIENT", "ingestion"])


@router.post(
    "/captures",
    response_model=CaptureResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit a knowledge source for capture",
    description=(
        "Accepts a text or URL source, persists it as Raw Content, and confirms receipt. "
        "URL sources are stored verbatim and are not fetched in P1.M1. No Digest is triggered."
    ),
    openapi_extra={"x-audience": "CLIENT"},
)
def submit_capture(
    request: CreateCaptureRequest,
    session: Session = Depends(get_session),
) -> CaptureResponse:
    return create_text_or_url_capture(
        session,
        input_type=request.input_type,
        content=request.content,
        intent=request.intent,
        metadata=request.metadata,
    )


@router.post(
    "/captures/files",
    response_model=CaptureResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit a readable text file for capture",
    description=(
        "Accepts UTF-8 text-like files (.txt/.md/.markdown/.csv/.json/.log/.yaml/.yml), "
        "stores the original file and persists its text as Raw Content."
    ),
)
async def submit_capture_file(
    file: UploadFile = File(...),
    intent: str = Form("knowledge_capture"),
    metadata: str | None = Form(default=None),
    session: Session = Depends(get_session),
) -> CaptureResponse:
    payload = await file.read()
    parsed_metadata = None
    if metadata:
        try:
            parsed_metadata = json.loads(metadata)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=422, detail="metadata 必须是合法 JSON") from exc
    try:
        return create_file_capture(
            session,
            filename=file.filename or "upload.txt",
            payload=payload,
            intent=intent,
            metadata=parsed_metadata,
        )
    except UnsupportedFileType as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)) from exc


@router.get(
    "/captures/{capture_id}",
    response_model=CaptureDetail,
    summary="Read a capture record",
)
def read_capture(capture_id: str, session: Session = Depends(get_session)) -> CaptureDetail:
    capture = get_capture(session, capture_id)
    if capture is None:
        raise HTTPException(status_code=404, detail="Capture not found")
    return CaptureDetail(
        id=capture.id,
        raw_content_id=capture.raw_content_id,
        input_type=capture.input_type,
        intent=capture.intent,
        status=capture.status,
        error=capture.error,
        created_at=capture.created_at.isoformat(),
    )


@router.get(
    "/raw-contents",
    response_model=list[RawContentSummary],
    summary="List captured Raw Content",
)
def read_raw_contents(session: Session = Depends(get_session)) -> list[RawContentSummary]:
    items = []
    for raw in list_raw_contents(session):
        preview = raw.text.strip().replace("\n", " ")[:160]
        items.append(
            RawContentSummary(
                id=raw.id,
                source_type=raw.source_type,
                title=raw.title,
                preview=preview,
                status=raw.status,
                created_at=raw.created_at.isoformat(),
            )
        )
    return items
