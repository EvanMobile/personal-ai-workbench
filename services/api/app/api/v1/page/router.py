"""Page API: versioned documents generated from Dossiers."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.modules.dossier.service import DossierNotFound
from app.modules.page import service

router = APIRouter(prefix="/api/v1/knowledge/pages", tags=["page"])


class PageCreate(BaseModel):
    dossier_id: str
    title: str | None = None


@router.get("")
def list_pages(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return service.list_pages(session)


@router.post("")
def create_page(payload: PageCreate, session: Session = Depends(get_session)) -> dict[str, Any]:
    try:
        page = service.create_or_regenerate_page(session, payload.dossier_id, payload.title)
    except DossierNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return service.page_detail(session, page.id)


@router.get("/{page_id}")
def get_page(page_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    try:
        return service.page_detail(session, page_id)
    except service.PageNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{page_id}/regenerate")
def regenerate_page(page_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    try:
        detail = service.page_detail(session, page_id)
    except service.PageNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    page = service.create_or_regenerate_page(
        session, detail["page"]["dossier_id"], detail["page"]["title"]
    )
    return service.page_detail(session, page.id)
