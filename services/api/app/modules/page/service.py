"""Page service: versioned rich documents generated from a Dossier."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.utils import utcnow
from app.modules.dossier.models import DossierAsset
from app.modules.dossier.service import get_dossier
from app.modules.knowledge.models import KnowledgeAsset
from app.modules.knowledge.service import asset_payload
from app.modules.page.models import Page, PageVersion


class PageNotFound(LookupError):
    pass


def _dossier_assets(session: Session, dossier_id: str) -> list[KnowledgeAsset]:
    ids = list(
        session.scalars(
            select(DossierAsset.asset_id).where(DossierAsset.dossier_id == dossier_id)
        ).all()
    )
    cards = [session.get(KnowledgeAsset, asset_id) for asset_id in ids]
    return [card for card in cards if card is not None]


def _content(session: Session, dossier_id: str, title: str) -> tuple[dict[str, Any], list[str]]:
    cards = _dossier_assets(session, dossier_id)
    grouped: dict[str, list[KnowledgeAsset]] = {}
    for card in cards:
        grouped.setdefault(card.category, []).append(card)
    sections = []
    for heading, group in grouped.items():
        sections.append(
            {
                "heading": heading,
                "body": f"{len(group)} 张已发布 Card",
                "cards": [asset_payload(session, card) for card in group],
            }
        )
    content = {
        "title": title,
        "subtitle": f"由 Dossier 生成 · {len(cards)} 张 Card",
        "sections": sections,
    }
    return content, [card.id for card in cards]


def _page_summary(page: Page) -> dict[str, Any]:
    return {
        "id": page.id,
        "dossier_id": page.dossier_id,
        "title": page.title,
        "version": page.current_version,
        "status": page.status,
        "updated_at": page.updated_at.isoformat(),
    }


def list_pages(session: Session) -> list[dict[str, Any]]:
    pages = session.scalars(select(Page).order_by(Page.updated_at.desc())).all()
    result = []
    for page in pages:
        version = session.scalar(
            select(PageVersion).where(
                PageVersion.page_id == page.id, PageVersion.version == page.current_version
            )
        )
        cover = None
        if version and version.source_asset_ids:
            cover = version.source_asset_ids[0]
        item = _page_summary(page)
        item["cover_asset_id"] = cover
        result.append(item)
    return result


def create_or_regenerate_page(session: Session, dossier_id: str, title: str | None) -> Page:
    dossier = get_dossier(session, dossier_id)
    page = session.scalar(select(Page).where(Page.dossier_id == dossier.id))
    page_title = (title or dossier.name)[:200]
    if page is None:
        page = Page(dossier_id=dossier.id, title=page_title, current_version=1)
        session.add(page)
        session.flush()
        version_number = 1
    else:
        page.title = page_title
        page.current_version += 1
        page.updated_at = utcnow()
        version_number = page.current_version

    content, source_ids = _content(session, dossier.id, page_title)
    session.add(
        PageVersion(
            page_id=page.id,
            version=version_number,
            content=content,
            source_asset_ids=source_ids,
        )
    )
    session.commit()
    session.refresh(page)
    return page


def page_detail(session: Session, page_id: str) -> dict[str, Any]:
    page = session.get(Page, page_id)
    if page is None:
        raise PageNotFound("Page 不存在")
    versions = session.scalars(
        select(PageVersion)
        .where(PageVersion.page_id == page.id)
        .order_by(PageVersion.version.desc())
    ).all()
    current = versions[0] if versions else None
    stale = False
    if current and current.source_asset_ids:
        cards = [session.get(KnowledgeAsset, asset_id) for asset_id in current.source_asset_ids]
        stale = any(card and card.updated_at > current.created_at for card in cards)
    item = _page_summary(page)
    item["stale"] = stale
    return {
        "page": item,
        "current": _version_payload(current) if current else None,
        "versions": [_version_payload(version) for version in versions],
    }


def _version_payload(version: PageVersion) -> dict[str, Any]:
    return {
        "id": version.id,
        "version": version.version,
        "content_json": version.content,
        "source_asset_ids": list(version.source_asset_ids or []),
        "renderer": version.renderer,
        "model": version.model,
        "created_at": version.created_at.isoformat(),
    }
