"""Pytest fixtures: isolated PostgreSQL test database, migrations, clean state."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

TEST_DATABASE_URL = os.environ.setdefault(
    "WORKBENCH_TEST_DATABASE_URL",
    "postgresql+psycopg://127.0.0.1:5432/workbench_test",
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("ALLOW_REAL_LLM", "false")
os.environ["WORKBENCH_DATA_DIR"] = str(Path(__file__).parent / ".test-data")

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.db import Base, SessionLocal, engine  # noqa: E402
import app.models_registry  # noqa: E402,F401
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    with engine.connect() as connection:
        connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
        connection.commit()
    alembic_cfg = Config(str(Path(__file__).parent.parent / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(Path(__file__).parent.parent / "migrations"))
    command.upgrade(alembic_cfg, "head")
    yield


@pytest.fixture(autouse=True)
def clean_tables():
    yield
    tables = ", ".join(table.name for table in reversed(Base.metadata.sorted_tables))
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
