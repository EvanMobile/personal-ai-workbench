"""Cross-business Visual Artifact service (filesystem cache + metadata)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.utils import utcnow
from app.modules.artifact.models import Artifact
from app.modules.artifact.renderer import render_knowledge_card
from app.modules.knowledge.models import KnowledgeAsset

SUPPORTED_TARGETS = {"knowledge_asset"}


class ArtifactError(RuntimeError):
    pass


def source_hash(asset: KnowledgeAsset) -> str:
    payload = {
        "title": asset.title,
        "summary": asset.summary,
        "conclusion": asset.conclusion,
        "body": asset.body_markdown,
        "category": asset.category,
        "tags": list(asset.tags or []),
        "version": asset.version,
        "provider": asset.provider,
        "model": asset.model,
        "prompt_version": asset.prompt_version,
        "processing_mode": asset.processing_mode,
        "is_mock": asset.is_mock,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _find(session: Session, target_type: str, target_id: str, purpose: str) -> Artifact | None:
    return session.scalar(
        select(Artifact).where(
            Artifact.target_type == target_type,
            Artifact.target_id == target_id,
            Artifact.purpose == purpose,
        )
    )


def generate_for_asset(
    session: Session, asset: KnowledgeAsset, *, force: bool = False, purpose: str = "knowledge_card"
) -> Artifact:
    settings = get_settings()
    digest = source_hash(asset)
    artifact = _find(session, "knowledge_asset", asset.id, purpose)
    if artifact is not None and not force:
        if (
            artifact.status == "ready"
            and artifact.content_hash == digest
            and artifact.file_path
            and Path(artifact.file_path).exists()
        ):
            return artifact

    if artifact is None:
        artifact = Artifact(
            target_type="knowledge_asset",
            target_id=asset.id,
            purpose=purpose,
            status="pending",
            config={"renderer": "knowledge-card-v1", "width": 1200, "height": 1600},
        )
        session.add(artifact)
        session.flush()

    artifact.source_version = asset.version
    artifact.content_hash = digest
    artifact.provider = asset.provider or "unknown"
    artifact.processing_mode = asset.processing_mode or "unknown"
    artifact.is_mock = asset.is_mock
    artifact.config = {
        **(artifact.config or {}),
        "renderer": "knowledge-card-v1",
        "width": 1200,
        "height": 1600,
        "provider": asset.provider,
        "model": asset.model,
        "prompt_version": asset.prompt_version,
        "processing_mode": asset.processing_mode,
        "is_mock": asset.is_mock,
    }
    artifact.updated_at = utcnow()
    artifact.error = None
    try:
        target = settings.artifact_dir / f"{artifact.id}.png"
        render_knowledge_card(
            target,
            title=asset.title,
            summary=asset.summary,
            conclusion=asset.conclusion,
            body_markdown=asset.body_markdown,
            category=asset.category,
            tags=list(asset.tags or []),
            provider=asset.provider or "unknown",
            model=asset.model,
            version=asset.version,
            processing_mode=asset.processing_mode or "unknown",
            is_mock=asset.is_mock,
            footer_note="SOURCE: RAW CONTENT → DRAFT → HUMAN PUBLISH",
        )
        artifact.file_path = str(target)
        artifact.status = "ready"
        artifact.width = 1200
        artifact.height = 1600
    except Exception as exc:  # noqa: BLE001 - never fake success
        artifact.status = "failed"
        artifact.error = f"{type(exc).__name__}: {exc}"
        artifact.file_path = None
    session.commit()
    session.refresh(artifact)
    return artifact


def get_artifact(session: Session, artifact_id: str) -> Artifact:
    artifact = session.get(Artifact, artifact_id)
    if artifact is None:
        raise ArtifactError("Artifact 不存在")
    return artifact


def regenerate(session: Session, artifact_id: str) -> Artifact:
    artifact = get_artifact(session, artifact_id)
    if artifact.target_type != "knowledge_asset":
        raise ArtifactError("当前仅支持 knowledge_asset 目标")
    asset = session.get(KnowledgeAsset, artifact.target_id)
    if asset is None:
        raise ArtifactError("来源对象已不存在")
    return generate_for_asset(session, asset, force=True, purpose=artifact.purpose)


def validate(session: Session, artifact_id: str) -> dict[str, Any]:
    artifact = get_artifact(session, artifact_id)
    exists = bool(artifact.file_path and Path(artifact.file_path).exists())
    expected = None
    asset = None
    if artifact.target_type == "knowledge_asset":
        asset = session.get(KnowledgeAsset, artifact.target_id)
        if asset is not None:
            expected = source_hash(asset)
    return {
        "artifact_id": artifact.id,
        "file_exists": exists,
        "hash_matches": expected == artifact.content_hash if expected else False,
        "version_matches": (
            artifact.source_version == asset.version if expected and asset else False
        ),
        "status": artifact.status,
    }


def artifact_payload(artifact: Artifact) -> dict[str, Any]:
    return {
        "id": artifact.id,
        "target_type": artifact.target_type,
        "target_id": artifact.target_id,
        "purpose": artifact.purpose,
        "status": artifact.status,
        "provider": artifact.provider or "unknown",
        "processing_mode": artifact.processing_mode or "unknown",
        "is_mock": artifact.is_mock,
        "url": f"/api/v1/artifacts/{artifact.id}/file" if artifact.status == "ready" else None,
        "content_hash": artifact.content_hash,
        "source_version": artifact.source_version,
        "width": artifact.width,
        "height": artifact.height,
        "error": artifact.error,
        "created_at": artifact.created_at.isoformat(),
        "updated_at": artifact.updated_at.isoformat(),
    }
