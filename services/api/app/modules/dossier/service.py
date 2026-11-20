"""Dossier service: organize published cards into topic collections."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.utils import utcnow
from app.modules.dossier.models import Dossier, DossierAsset
from app.modules.knowledge.models import KnowledgeAsset
from app.modules.knowledge.service import asset_payload

class DossierNotFound(LookupError):
    pass


def list_dossiers(session: Session) -> list[dict[str, Any]]:
    rows = session.scalars(select(Dossier).order_by(Dossier.updated_at.desc())).all()
    result = []
    for dossier in rows:
        count = len(
            session.scalars(
                select(DossierAsset.asset_id).where(DossierAsset.dossier_id == dossier.id)
            ).all()
        )
        result.append(
            {
                "id": dossier.id,
                "name": dossier.name,
                "description": dossier.description,
                "card_count": count,
                "page_id": _page_id(session, dossier.id),
                "updated_at": dossier.updated_at.isoformat(),
            }
        )
    return result


def _page_id(session: Session, dossier_id: str) -> str | None:
    from app.modules.page.models import Page

    return session.scalar(select(Page.id).where(Page.dossier_id == dossier_id))


def create_dossier(session: Session, name: str, description: str = "") -> Dossier:
    dossier = Dossier(name=name.strip()[:160] or "Untitled dossier", description=description)
    session.add(dossier)
    session.commit()
    session.refresh(dossier)
    return dossier


def get_dossier(session: Session, dossier_id: str) -> Dossier:
    dossier = session.get(Dossier, dossier_id)
    if dossier is None:
        raise DossierNotFound("Dossier 不存在")
    return dossier


def dossier_detail(session: Session, dossier_id: str) -> dict[str, Any]:
    dossier = get_dossier(session, dossier_id)
    asset_ids = list(
        session.scalars(
            select(DossierAsset.asset_id).where(DossierAsset.dossier_id == dossier.id)
        ).all()
    )
    cards = [session.get(KnowledgeAsset, asset_id) for asset_id in asset_ids]
    cards = [card for card in cards if card is not None]
    edges = _edges(cards)
    return {
        "dossier": {
            "id": dossier.id,
            "name": dossier.name,
            "description": dossier.description,
            "updated_at": dossier.updated_at.isoformat(),
        },
        "cards": [asset_payload(session, card) for card in cards],
        "edges": edges,
    }


def _edges(cards: list[KnowledgeAsset]) -> list[dict[str, str]]:
    tag_map: dict[str, list[str]] = defaultdict(list)
    for card in cards:
        for tag in card.tags or []:
            tag_map[tag].append(card.id)
    edges: list[dict[str, str]] = []
    for tag, ids in tag_map.items():
        if len(ids) < 2:
            continue
        for index, source in enumerate(ids):
            for target in ids[index + 1 :]:
                edges.append({"source": source, "target": target, "reason": f"shared tag: {tag}"})
    return edges


def add_assets(session: Session, dossier_id: str, asset_ids: list[str]) -> None:
    dossier = get_dossier(session, dossier_id)
    for asset_id in asset_ids:
        asset = session.get(KnowledgeAsset, asset_id)
        if asset is None:
            continue
        existing = session.get(DossierAsset, {"dossier_id": dossier.id, "asset_id": asset.id})
        if existing is None:
            session.add(DossierAsset(dossier_id=dossier.id, asset_id=asset.id))
    dossier.updated_at = utcnow()
    session.commit()


def remove_asset(session: Session, dossier_id: str, asset_id: str) -> None:
    dossier = get_dossier(session, dossier_id)
    existing = session.get(DossierAsset, {"dossier_id": dossier.id, "asset_id": asset_id})
    if existing is not None:
        session.delete(existing)
        dossier.updated_at = utcnow()
        session.commit()
