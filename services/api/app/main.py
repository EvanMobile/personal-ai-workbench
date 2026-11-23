"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

import app.models_registry  # noqa: F401  (registers ORM models)
from app.api.v1.artifact.router import router as artifact_router
from app.api.v1.chat.router import router as chat_router
from app.api.v1.client.ingestion.captures import router as capture_router
from app.api.v1.dossier.router import router as dossier_router
from app.api.v1.dingtalk.router import router as dingtalk_router
from app.api.v1.knowledge.router import router as knowledge_router
from app.api.v1.page.router import router as page_router
from app.core.config import ensure_data_dirs, get_settings
from app.core.db import SessionLocal


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_data_dirs()
    yield


settings = get_settings()

app = FastAPI(
    title="Personal AI Workbench API",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(capture_router)
app.include_router(knowledge_router)
app.include_router(dossier_router)
app.include_router(page_router)
app.include_router(artifact_router)
app.include_router(chat_router)
app.include_router(dingtalk_router)


def _database_ok() -> bool:
    try:
        with SessionLocal() as session:
            session.execute(text("select 1"))
        return True
    except Exception:  # noqa: BLE001 - health endpoint must not crash
        return False


@app.get("/health", tags=["health"])
@app.get("/api/v1/health", tags=["health"], include_in_schema=False)
def health_check() -> dict[str, str]:
    database = "ok" if _database_ok() else "error"
    return {"status": "ok" if database == "ok" else "degraded", "database": database}


@app.get("/health/ready", tags=["health"])
def readiness() -> dict[str, str]:
    database = "ok" if _database_ok() else "error"
    return {"status": "ready" if database == "ok" else "not_ready", "database": database}
