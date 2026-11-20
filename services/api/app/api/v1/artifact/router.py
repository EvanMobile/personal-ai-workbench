"""Visual Artifact API (cross-business shared service)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.modules.artifact.models import Artifact
from app.modules.artifact.service import (
    SUPPORTED_TARGETS,
    ArtifactError,
    artifact_payload,
    generate_for_asset,
    get_artifact,
    regenerate,
    validate,
)
from app.modules.knowledge.models import KnowledgeAsset

router = APIRouter(prefix="/api/v1/artifacts", tags=["artifact"])


class ArtifactCreate(BaseModel):
    target_type: str
    target_id: str
    purpose: str = "knowledge_card"


@router.get("")
def list_artifacts(
    target_type: str | None = None,
    target_id: str | None = None,
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    stmt = select(Artifact).order_by(Artifact.updated_at.desc())
    if target_type:
        stmt = stmt.where(Artifact.target_type == target_type)
    if target_id:
        stmt = stmt.where(Artifact.target_id == target_id)
    return [artifact_payload(item) for item in session.scalars(stmt).all()]


@router.post("")
def create_artifact(payload: ArtifactCreate, session: Session = Depends(get_session)) -> dict[str, Any]:
    if payload.target_type not in SUPPORTED_TARGETS:
        raise HTTPException(status_code=422, detail="当前仅支持 knowledge_asset")
    asset = session.get(KnowledgeAsset, payload.target_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="目标对象不存在")
    artifact = generate_for_asset(session, asset, force=True, purpose=payload.purpose)
    return artifact_payload(artifact)


@router.get("/{artifact_id}")
def read_artifact(artifact_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    try:
        return artifact_payload(get_artifact(session, artifact_id))
    except ArtifactError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{artifact_id}/regenerate")
def regenerate_artifact(
    artifact_id: str, session: Session = Depends(get_session)
) -> dict[str, Any]:
    try:
        return artifact_payload(regenerate(session, artifact_id))
    except ArtifactError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{artifact_id}/validate")
def validate_artifact(artifact_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    try:
        return validate(session, artifact_id)
    except ArtifactError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{artifact_id}/file")
def artifact_file(artifact_id: str, session: Session = Depends(get_session)) -> FileResponse:
    try:
        artifact = get_artifact(session, artifact_id)
    except ArtifactError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if artifact.status != "ready" or not artifact.file_path:
        raise HTTPException(status_code=404, detail="Artifact 尚未生成成功")
    path = Path(artifact.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Artifact 文件缺失")
    return FileResponse(path, media_type="image/png", filename=path.name)
