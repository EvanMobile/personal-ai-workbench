"""Knowledge business service: digest, draft revisions and human publish."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.provider import get_provider
from app.core.utils import utcnow
from app.modules.artifact.service import generate_for_asset
from app.modules.artifact.models import Artifact
from app.modules.capture.models import RawContent
from app.modules.dossier.models import Dossier, DossierAsset
from app.modules.page.models import Page
from app.modules.knowledge.models import (
    AssetVersion,
    Draft,
    DraftRevision,
    KnowledgeAsset,
    PublishRecord,
)


class NotFound(LookupError):
    pass


class InvalidState(RuntimeError):
    pass


def _raw_content(session: Session, raw_id: str) -> RawContent:
    raw = session.get(RawContent, raw_id)
    if raw is None:
        raise NotFound("Raw Content 不存在")
    return raw


def digest_raw_content(session: Session, raw_id: str) -> Draft:
    raw = _raw_content(session, raw_id)
    provider = get_provider()
    result = provider.digest(raw.text, raw.source_type, raw.title)
    draft = Draft(
        raw_content_id=raw.id,
        title=result.title,
        summary=result.summary,
        conclusion=result.conclusion,
        body_markdown=result.body_markdown,
        category=result.category,
        tags=result.tags,
        provider=provider.name,
        model=provider.model,
        prompt_version="digest-v0.1",
        processing_mode=provider.processing_mode,
        is_mock=provider.is_mock,
        status="draft",
    )
    session.add(draft)
    raw.status = "digested"
    session.commit()
    session.refresh(draft)
    return draft


def revise_draft(session: Session, draft_id: str, instruction: str) -> tuple[Draft, DraftRevision]:
    draft = session.get(Draft, draft_id)
    if draft is None:
        raise NotFound("Draft 不存在")
    if draft.status != "draft":
        raise InvalidState("只有 Draft 状态可修订；已发布内容不可直接覆盖")
    raw = _raw_content(session, draft.raw_content_id)
    provider = get_provider()
    body = provider.revise(raw.text, draft.title, instruction)
    draft.body_markdown = body
    draft.provider = provider.name
    draft.model = provider.model
    draft.processing_mode = provider.processing_mode
    draft.is_mock = provider.is_mock
    draft.version += 1
    draft.updated_at = utcnow()
    revision = DraftRevision(
        draft_id=draft.id,
        instruction=instruction,
        body_markdown=body,
        provider=provider.name,
        model=provider.model,
        prompt_version=draft.prompt_version,
        processing_mode=provider.processing_mode,
        is_mock=provider.is_mock,
    )
    session.add(revision)
    session.commit()
    session.refresh(draft)
    session.refresh(revision)
    return draft, revision


def publish_draft(
    session: Session, draft_id: str, note: str | None
) -> tuple[KnowledgeAsset, Any, PublishRecord]:
    draft = session.get(Draft, draft_id)
    if draft is None:
        raise NotFound("Draft 不存在")
    existing = session.scalar(select(KnowledgeAsset).where(KnowledgeAsset.draft_id == draft.id))
    if existing is None:
        asset = KnowledgeAsset(
            draft_id=draft.id,
            raw_content_id=draft.raw_content_id,
            title=draft.title,
            summary=draft.summary,
            conclusion=draft.conclusion,
            body_markdown=draft.body_markdown,
            category=draft.category,
            tags=list(draft.tags or []),
            provider=draft.provider,
            model=draft.model,
            prompt_version=draft.prompt_version,
            processing_mode=draft.processing_mode,
            is_mock=draft.is_mock,
            status="published",
            version=1,
            archived=False,
        )
        session.add(asset)
        session.flush()
    else:
        asset = existing
        asset.title = draft.title
        asset.summary = draft.summary
        asset.conclusion = draft.conclusion
        asset.body_markdown = draft.body_markdown
        asset.category = draft.category
        asset.tags = list(draft.tags or [])
        asset.provider = draft.provider
        asset.model = draft.model
        asset.prompt_version = draft.prompt_version
        asset.processing_mode = draft.processing_mode
        asset.is_mock = draft.is_mock
        asset.version += 1
        asset.updated_at = utcnow()
        session.flush()

    session.add(
        AssetVersion(
            asset_id=asset.id,
            version=asset.version,
            body_markdown=asset.body_markdown,
            snapshot={
                "title": asset.title,
                "summary": asset.summary,
                "conclusion": asset.conclusion,
                "category": asset.category,
                "tags": list(asset.tags or []),
                "provider": asset.provider,
                "model": asset.model,
                "prompt_version": asset.prompt_version,
                "processing_mode": asset.processing_mode,
                "is_mock": asset.is_mock,
            },
        )
    )
    draft.status = "published"
    draft.updated_at = utcnow()
    record = PublishRecord(
        draft_id=draft.id,
        asset_id=asset.id,
        asset_version=asset.version,
        note=note,
    )
    session.add(record)
    session.commit()
    session.refresh(asset)
    session.refresh(record)

    artifact = None
    try:
        artifact = generate_for_asset(session, asset)
    except Exception:  # noqa: BLE001 - artifact failure must not fail publish
        session.rollback()
        artifact = None
    return asset, artifact, record


def list_drafts(session: Session) -> list[Draft]:
    return list(session.scalars(select(Draft).order_by(Draft.updated_at.desc())).all())


def get_draft(session: Session, draft_id: str) -> Draft:
    draft = session.get(Draft, draft_id)
    if draft is None:
        raise NotFound("Draft 不存在")
    return draft


def list_assets(session: Session, archived: bool | None = None) -> list[KnowledgeAsset]:
    stmt = select(KnowledgeAsset).order_by(KnowledgeAsset.published_at.desc())
    if archived is not None:
        stmt = stmt.where(KnowledgeAsset.archived.is_(archived))
    return list(session.scalars(stmt).all())


def get_asset(session: Session, asset_id: str) -> KnowledgeAsset:
    asset = session.get(KnowledgeAsset, asset_id)
    if asset is None:
        raise NotFound("Card 不存在")
    return asset


def patch_asset(
    session: Session,
    asset_id: str,
    *,
    category: str | None = None,
    tags: list[str] | None = None,
    archived: bool | None = None,
    dossier_id: str | None = None,
) -> KnowledgeAsset:
    asset = get_asset(session, asset_id)
    if category is not None:
        asset.category = category[:80]
    if tags is not None:
        asset.tags = [tag[:40] for tag in tags][:12]
    if archived is not None:
        asset.archived = archived
    if dossier_id:
        exists = session.get(DossierAsset, {"dossier_id": dossier_id, "asset_id": asset.id})
        if exists is None:
            session.add(DossierAsset(dossier_id=dossier_id, asset_id=asset.id))
    asset.updated_at = utcnow()
    session.commit()
    session.refresh(asset)
    return asset


def stats(session: Session) -> dict[str, int]:
    def count(model: Any) -> int:
        return int(session.scalar(select(func.count()).select_from(model)) or 0)

    return {
        "raw_contents": count(RawContent),
        "drafts": count(Draft),
        "assets": count(KnowledgeAsset),
        "dossiers": count(Dossier),
        "pages": count(Page),
        "artifacts": count(Artifact),
    }


def draft_payload(draft: Draft) -> dict[str, Any]:
    return {
        "id": draft.id,
        "raw_content_id": draft.raw_content_id,
        "title": draft.title,
        "summary": draft.summary,
        "conclusion": draft.conclusion,
        "body_markdown": draft.body_markdown,
        "category": draft.category,
        "tags": list(draft.tags or []),
        "provider": draft.provider or "unknown",
        "model": draft.model or "unknown",
        "prompt_version": draft.prompt_version or "unknown",
        "processing_mode": draft.processing_mode or "unknown",
        "is_mock": draft.is_mock,
        "status": draft.status,
        "version": draft.version,
        "created_at": draft.created_at.isoformat(),
        "updated_at": draft.updated_at.isoformat(),
    }


def asset_payload(session: Session, asset: KnowledgeAsset) -> dict[str, Any]:
    from app.modules.artifact.service import artifact_payload

    artifact = session.scalar(
        select(Artifact)
        .where(Artifact.target_type == "knowledge_asset", Artifact.target_id == asset.id)
        .order_by(Artifact.updated_at.desc())
    )
    dossier_ids = list(
        session.scalars(
            select(DossierAsset.dossier_id).where(DossierAsset.asset_id == asset.id)
        ).all()
    )
    return {
        "id": asset.id,
        "draft_id": asset.draft_id,
        "raw_content_id": asset.raw_content_id,
        "title": asset.title,
        "summary": asset.summary,
        "conclusion": asset.conclusion,
        "body_markdown": asset.body_markdown,
        "category": asset.category,
        "tags": list(asset.tags or []),
        "provider": asset.provider or "unknown",
        "model": asset.model or "unknown",
        "prompt_version": asset.prompt_version or "unknown",
        "processing_mode": asset.processing_mode or "unknown",
        "is_mock": asset.is_mock,
        "status": asset.status,
        "version": asset.version,
        "archived": asset.archived,
        "published_at": asset.published_at.isoformat(),
        "created_at": asset.created_at.isoformat(),
        "updated_at": asset.updated_at.isoformat(),
        "artifact": artifact_payload(artifact) if artifact else None,
        "dossier_ids": dossier_ids,
    }
