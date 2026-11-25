"""RAG Lab M1-A API router composition."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.rag.dossiers import router as dossiers_router
from app.api.v1.rag.runs import router as runs_router
from app.api.v1.rag.runtime import router as runtime_router

router = APIRouter(prefix="/api/v1/rag")
router.include_router(dossiers_router)
router.include_router(runs_router)
router.include_router(runtime_router)
