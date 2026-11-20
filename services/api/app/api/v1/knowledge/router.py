"""Knowledge API: digest, draft review, publish, cards and stats."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai.provider import ProviderNotAuthorized
from app.core.db import get_session
from app.modules.artifact.models import Artifact
from app.modules.artifact.service import artifact_payload
from app.modules.capture.models import RawContent
from app.modules.dossier.models import Dossier, DossierAsset
from app.modules.knowledge import service
from app.modules.page.models import Page

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


class DigestRequest(BaseModel):
    instruction: str | None = None


class RevisionRequest(BaseModel):
    instruction: str = Field(min_length=1, max_length=2000)


class PublishRequest(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


class AssetPatch(BaseModel):
    category: str | None = Field(default=None, max_length=80)
    tags: list[str] | None = None
    archived: bool | None = None
    dossier_id: str | None = None


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, service.NotFound):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, service.InvalidState):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, ProviderNotAuthorized):
        return HTTPException(status_code=503, detail=str(exc))
    return HTTPException(status_code=500, detail="内部错误")


@router.post("/raw-contents/{raw_id}/digest")
def run_digest(
    raw_id: str, payload: DigestRequest | None = None, session: Session = Depends(get_session)
) -> dict[str, Any]:
    try:
        draft = service.digest_raw_content(session, raw_id)
    except Exception as exc:  # noqa: BLE001
        raise _error(exc) from exc
    return {"draft": service.draft_payload(draft)}


@router.get("/raw-contents/{raw_id}")
def read_raw(raw_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    raw = session.get(RawContent, raw_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="Raw Content 不存在")
    return {
        "id": raw.id,
        "source_type": raw.source_type,
        "title": raw.title,
        "text": raw.text,
        "metadata": raw.meta,
        "status": raw.status,
        "created_at": raw.created_at.isoformat(),
    }


@router.get("/drafts")
def read_drafts(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return [service.draft_payload(draft) for draft in service.list_drafts(session)]


@router.get("/drafts/{draft_id}")
def read_draft(draft_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    try:
        return service.draft_payload(service.get_draft(session, draft_id))
    except Exception as exc:  # noqa: BLE001
        raise _error(exc) from exc


@router.post("/drafts/{draft_id}/revisions")
def revise(
    draft_id: str, payload: RevisionRequest, session: Session = Depends(get_session)
) -> dict[str, Any]:
    try:
        draft, revision = service.revise_draft(session, draft_id, payload.instruction)
    except Exception as exc:  # noqa: BLE001
        raise _error(exc) from exc
    return {
        "draft": service.draft_payload(draft),
        "revision": {"id": revision.id, "created_at": revision.created_at.isoformat()},
    }


@router.post("/drafts/{draft_id}/publish")
def publish(
    draft_id: str,
    payload: PublishRequest | None = None,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        asset, artifact, record = service.publish_draft(
            session, draft_id, payload.note if payload else None
        )
    except Exception as exc:  # noqa: BLE001
        raise _error(exc) from exc
    return {
        "asset": service.asset_payload(session, asset),
        "artifact": artifact_payload(artifact) if artifact else None,
        "publish_record": {
            "id": record.id,
            "asset_version": record.asset_version,
            "created_at": record.created_at.isoformat(),
        },
    }


@router.get("/assets")
def read_assets(
    archived: bool | None = Query(default=None), session: Session = Depends(get_session)
) -> list[dict[str, Any]]:
    return [service.asset_payload(session, asset) for asset in service.list_assets(session, archived)]


@router.get("/assets/{asset_id}")
def read_asset(asset_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    try:
        asset = service.get_asset(session, asset_id)
        payload = service.asset_payload(session, asset)
        raw = session.get(RawContent, asset.raw_content_id) if asset.raw_content_id else None
        payload["raw_content"] = (
            {
                "id": raw.id,
                "source_type": raw.source_type,
                "title": raw.title,
                "text": raw.text,
                "created_at": raw.created_at.isoformat(),
            }
            if raw
            else None
        )
        return payload
    except Exception as exc:  # noqa: BLE001
        raise _error(exc) from exc


@router.patch("/assets/{asset_id}")
def patch_asset(
    asset_id: str, payload: AssetPatch, session: Session = Depends(get_session)
) -> dict[str, Any]:
    try:
        if "dossier_id" in payload.model_fields_set and payload.dossier_id is None:
            from app.modules.dossier.models import DossierAsset

            for link in session.query(DossierAsset).filter(DossierAsset.asset_id == asset_id):
                session.delete(link)
            session.commit()
        asset = service.patch_asset(
            session,
            asset_id,
            category=payload.category,
            tags=payload.tags,
            archived=payload.archived,
            dossier_id=payload.dossier_id,
        )
        return service.asset_payload(session, asset)
    except Exception as exc:  # noqa: BLE001
        raise _error(exc) from exc


@router.get("/stats")
def read_stats(session: Session = Depends(get_session)) -> dict[str, int]:
    return service.stats(session)


@router.get("/dossiers/{dossier_id}/cards")
def dossier_cards(dossier_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    from app.modules.dossier import service as dossier_service

    try:
        return dossier_service.dossier_detail(session, dossier_id)
    except Exception as exc:  # noqa: BLE001
        if isinstance(exc, dossier_service.DossierNotFound):
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise
