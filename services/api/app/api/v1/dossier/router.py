"""Dossier API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.modules.dossier import service

router = APIRouter(prefix="/api/v1/knowledge/dossiers", tags=["dossier"])


class DossierCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)


class DossierAssets(BaseModel):
    asset_ids: list[str] = Field(default_factory=list)


@router.get("")
def list_dossiers(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return service.list_dossiers(session)


@router.post("")
def create_dossier(payload: DossierCreate, session: Session = Depends(get_session)) -> dict[str, Any]:
    dossier = service.create_dossier(session, payload.name, payload.description)
    return {
        "id": dossier.id,
        "name": dossier.name,
        "description": dossier.description,
        "updated_at": dossier.updated_at.isoformat(),
    }


@router.get("/{dossier_id}")
def get_dossier(dossier_id: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    try:
        return service.dossier_detail(session, dossier_id)
    except service.DossierNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{dossier_id}/assets")
def add_assets(
    dossier_id: str, payload: DossierAssets, session: Session = Depends(get_session)
) -> dict[str, Any]:
    try:
        service.add_assets(session, dossier_id, payload.asset_ids)
        return service.dossier_detail(session, dossier_id)
    except service.DossierNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{dossier_id}/assets/{asset_id}", status_code=204)
def remove_asset(dossier_id: str, asset_id: str, session: Session = Depends(get_session)) -> None:
    try:
        service.remove_asset(session, dossier_id, asset_id)
    except service.DossierNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
