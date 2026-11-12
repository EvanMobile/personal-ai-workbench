"""FastAPI application entry point."""

from fastapi import FastAPI

from app.api.v1.client.ingestion.captures import router as capture_router

app = FastAPI(
    title="Personal AI Workbench API",
    version="0.1.0",
)

app.include_router(capture_router)


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Report that the API process is responding."""
    return {"status": "ok"}
