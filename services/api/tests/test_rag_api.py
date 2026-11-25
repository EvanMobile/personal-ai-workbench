"""R3.3: M01 RAG API contract and integration tests (real PostgreSQL)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi import Request
from fastapi.exceptions import RequestValidationError

from app.api.v1.rag.errors import rag_request_validation_handler
from app.core.db import SessionLocal
from app.core.utils import utcnow
from app.modules.evaluation.facades.dossiers import DossierFacade
from app.modules.evaluation.models import RagDossier
from app.modules.execution.results import StepResult
from app.modules.execution.service import (
    claim_job,
    create_run_with_step_job,
    finish_job,
    payload_hash,
)

RAG = "/api/v1/rag"


@pytest.fixture(autouse=True)
def no_worker(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "RAG_WORKER_HEARTBEAT_FILE", str(tmp_path / "missing.worker.heartbeat")
    )


def _create(client, title: str = "API Dossier") -> dict[str, Any]:
    response = client.post(
        f"{RAG}/dossiers",
        json={"title": title, "description": "API test"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _start(client, dossier_id: str, key: str = "api-key") -> Any:
    return client.post(
        f"{RAG}/dossiers/{dossier_id}/runs",
        headers={"Idempotency-Key": key},
        json={"kind": "dossier_rollup", "params": {}},
    )


def _assert_no_internal_tokens(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            assert key not in {"lease_token", "fencing_token"}
            _assert_no_internal_tokens(item)
    elif isinstance(value, list):
        for item in value:
            _assert_no_internal_tokens(item)


def test_dossier_list_create_and_detail(client) -> None:
    empty = client.get(f"{RAG}/dossiers")
    assert empty.status_code == 200
    assert empty.json() == {"items": [], "total": 0, "limit": 50, "offset": 0}

    created = _create(client)
    assert created["title"] == "API Dossier"
    assert created["status"] == "active"
    assert created["last_run"] is None
    assert created["run_count"] == 0

    listed = client.get(f"{RAG}/dossiers")
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == created["id"]

    detail_response = client.get(f"{RAG}/dossiers/{created['id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert set(detail) == {
        "dossier",
        "stages",
        "execution",
        "recent_runs",
        "worker",
        "evidence_capabilities",
        "blocking",
        "next_actions",
    }
    assert detail["stages"][0]["stage_key"] == "dossier_rollup"
    assert detail["stages"][0]["status"] == "not_started"
    assert detail["worker"]["available"] is False
    assert "NO_RUN" in detail["blocking"]
    assert "WORKER_UNAVAILABLE" in detail["blocking"]
    assert detail["next_actions"] == ["RUN_DOSSIER_ROLLUP"]
    assert detail["evidence_capabilities"]["artifact_persisted"] == "not_available"


def test_start_run_idempotency_worker_warning_and_run_detail(client) -> None:
    dossier = _create(client)
    first = _start(client, dossier["id"], "dedupe-1")
    assert first.status_code == 202, first.text
    first_body = first.json()
    assert first_body["reused"] is False
    assert first_body["worker_available"] is False
    assert first_body["warnings"] == ["WORKER_UNAVAILABLE"]

    second = _start(client, dossier["id"], "dedupe-1")
    assert second.status_code == 200, second.text
    assert second.json()["reused"] is True
    assert second.json()["run"]["id"] == first_body["run"]["id"]

    run_id = first_body["run"]["id"]
    detail = client.get(f"{RAG}/runs/{run_id}")
    assert detail.status_code == 200
    body = detail.json()
    _assert_no_internal_tokens(body)
    assert body["run"]["id"] == run_id
    assert body["run"]["pipeline"] == "dossier"
    assert body["run"]["stage"] == "dossier_rollup"
    job = body["steps"][0]["jobs"][0]
    assert job["kind"] == "dossier_rollup"
    assert "locked_by" in job
    assert "last_heartbeat_at" not in job
    assert "lease_expires_at" not in job
    evidence = body["evidence_state"]
    assert evidence["readback_session"] == "new"
    assert evidence["run"] == {"exists": True, "read_back": True}
    assert evidence["steps"] == {"exists": True, "read_back": True}
    assert evidence["jobs"] == {"exists": True, "read_back": True}
    assert evidence["attempts"] == {"exists": False, "read_back": True}
    assert evidence["events"] == {"exists": False, "read_back": True}
    assert "artifact_persisted" not in evidence
    assert "verified" not in evidence
    assert body["evidence_capabilities"]["verified"] == "not_implemented"

    events = client.get(f"{RAG}/runs/{run_id}/events")
    assert events.status_code == 200
    assert events.json() == {"items": [], "next_after_id": 0, "has_more": False}


def test_http_errors_and_validation(client) -> None:
    missing_dossier = client.get(f"{RAG}/dossiers/missing")
    assert missing_dossier.status_code == 404
    assert missing_dossier.json()["code"] == "RAG_DOSSIER_NOT_FOUND"

    missing_run = client.get(f"{RAG}/runs/missing")
    assert missing_run.status_code == 404
    assert missing_run.json()["code"] == "RAG_RUN_NOT_FOUND"

    missing_key = client.post(
        f"{RAG}/dossiers/missing/runs", json={"kind": "dossier_rollup"}
    )
    assert missing_key.status_code == 422
    assert missing_key.json()["code"] == "RAG_IDEMPOTENCY_KEY_REQUIRED"

    dossier = _create(client)
    unsupported = client.post(
        f"{RAG}/dossiers/{dossier['id']}/runs",
        headers={"Idempotency-Key": "unsupported"},
        json={"kind": "other"},
    )
    assert unsupported.status_code == 422
    assert unsupported.json()["code"] == "RAG_UNSUPPORTED_RUN_KIND"

    invalid_params = client.post(
        f"{RAG}/dossiers/{dossier['id']}/runs",
        headers={"Idempotency-Key": "bad-params"},
        json={"kind": "dossier_rollup", "params": {"x": 1}},
    )
    assert invalid_params.status_code == 422
    assert invalid_params.json()["code"] == "RAG_INVALID_RUN_PARAMS"

    invalid_page = client.get(f"{RAG}/dossiers?limit=0")
    assert invalid_page.status_code == 422
    assert invalid_page.json()["code"] == "RAG_VALIDATION_ERROR"

    blank_title = client.post(f"{RAG}/dossiers", json={"title": "   "})
    assert blank_title.status_code == 422
    assert blank_title.json()["code"] == "RAG_VALIDATION_ERROR"


def test_missing_idempotency_key_has_stable_code(client) -> None:
    dossier = _create(client)
    response = client.post(
        f"{RAG}/dossiers/{dossier['id']}/runs",
        json={"kind": "dossier_rollup"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "RAG_IDEMPOTENCY_KEY_REQUIRED"


def test_idempotency_conflict_maps_to_409(client) -> None:
    dossier = _create(client)
    with SessionLocal() as session:
        create_run_with_step_job(
            session,
            scope_type="rag_dossier",
            scope_id=dossier["id"],
            pipeline="dossier",
            stage="dossier_rollup",
            config_snapshot={"kind": "dossier_rollup"},
            config_hash="a" * 64,
            fingerprint="b" * 64,
            step_key="dossier_rollup",
            ordinal=1,
            job_key="dossier_rollup",
            kind="dossier_rollup",
            payload={},
            idempotency_key="conflict-key",
            idempotency_payload_hash=payload_hash({"different": True}),
        )

    response = _start(client, dossier["id"], "conflict-key")
    assert response.status_code == 409
    assert response.json()["code"] == "RAG_IDEMPOTENCY_CONFLICT"


def test_idempotency_key_whitespace_and_length(client) -> None:
    dossier = _create(client)
    blank = client.post(
        f"{RAG}/dossiers/{dossier['id']}/runs",
        headers={"Idempotency-Key": "   "},
        json={"kind": "dossier_rollup"},
    )
    assert blank.status_code == 422
    assert blank.json()["code"] == "RAG_IDEMPOTENCY_KEY_REQUIRED"

    too_long = client.post(
        f"{RAG}/dossiers/{dossier['id']}/runs",
        headers={"Idempotency-Key": "x" * 129},
        json={"kind": "dossier_rollup"},
    )
    assert too_long.status_code == 422
    assert too_long.json()["code"] == "RAG_INVALID_IDEMPOTENCY_KEY"


def test_unknown_value_error_is_safe_500(client, monkeypatch) -> None:
    def boom(*_args, **_kwargs):
        raise ValueError("internal-secret-should-not-leak")

    monkeypatch.setattr(DossierFacade, "create", staticmethod(boom))
    response = client.post(f"{RAG}/dossiers", json={"title": "boom"})
    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "RAG_INTERNAL_ERROR"
    assert "internal-secret-should-not-leak" not in response.text
    assert "Traceback" not in response.text


def test_rag_validation_handler_path_boundary() -> None:
    error = RequestValidationError(
        [{"type": "missing", "loc": ("query", "x"), "msg": "Field required", "input": None}]
    )

    def request(path: str) -> Request:
        return Request(
            {
                "type": "http",
                "method": "GET",
                "path": path,
                "raw_path": path.encode(),
                "query_string": b"",
                "headers": [],
                "client": ("test", 1),
                "server": ("test", 80),
                "scheme": "http",
                "root_path": "",
            }
        )

    rag_response = asyncio.run(rag_request_validation_handler(request("/api/v1/rag/x"), error))
    assert json.loads(rag_response.body)["code"] == "RAG_VALIDATION_ERROR"

    default_response = asyncio.run(
        rag_request_validation_handler(request("/api/v1/ragX/x"), error)
    )
    default_body = json.loads(default_response.body)
    assert "detail" in default_body
    assert "code" not in default_body


def test_archived_dossier_conflict(client) -> None:
    dossier = _create(client)
    with SessionLocal() as session:
        row = session.get(RagDossier, dossier["id"])
        assert row is not None
        row.status = "archived"
        session.commit()

    response = _start(client, dossier["id"], "archived")
    assert response.status_code == 409
    assert response.json()["code"] == "RAG_DOSSIER_ARCHIVED"


def test_cancel_and_terminal_conflict(client) -> None:
    dossier = _create(client)
    run = _start(client, dossier["id"], "cancel-1").json()["run"]

    # Keep the job running so the first cancel request is not terminal.
    with SessionLocal() as session:
        claimed = claim_job(session, worker_id="api-worker", lease_seconds=60)
        assert claimed is not None

    first = client.post(f"{RAG}/runs/{run['id']}/cancel")
    assert first.status_code == 200
    assert first.json()["already_requested"] is False
    second = client.post(f"{RAG}/runs/{run['id']}/cancel")
    assert second.status_code == 200
    assert second.json()["already_requested"] is True

    # Finish the running job after cancellation: M05 must return cancelled.
    with SessionLocal() as session:
        finish_job(
            session,
            job_id=claimed.job_id,
            lease_token=claimed.lease_token,
            attempt_id=claimed.attempt_id,
            result=StepResult(status="succeeded", processed_count=1),
        )
    terminal = client.post(f"{RAG}/runs/{run['id']}/cancel")
    assert terminal.status_code == 409
    assert terminal.json()["code"] == "RAG_RUN_NOT_CANCELLABLE"


def test_events_pagination_contract(client) -> None:
    dossier = _create(client)
    run = _start(client, dossier["id"], "events-1").json()["run"]
    with SessionLocal() as session:
        claimed = claim_job(session, worker_id="api-events", lease_seconds=60)
        assert claimed is not None
        finish_job(
            session,
            job_id=claimed.job_id,
            lease_token=claimed.lease_token,
            attempt_id=claimed.attempt_id,
            result=StepResult(status="succeeded", processed_count=1),
        )

    first = client.get(f"{RAG}/runs/{run['id']}/events?limit=1")
    assert first.status_code == 200
    page = first.json()
    assert len(page["items"]) == 1
    assert page["has_more"] is True
    second = client.get(
        f"{RAG}/runs/{run['id']}/events?after_id={page['next_after_id']}&limit=10"
    )
    assert second.status_code == 200
    assert second.json()["items"]
    ids = [item["id"] for item in page["items"] + second.json()["items"]]
    assert ids == sorted(ids)
    assert len(ids) == len(set(ids))


def test_worker_runtime_endpoint_without_and_with_heartbeat(client, tmp_path, monkeypatch) -> None:
    missing = client.get(f"{RAG}/runtime/worker")
    assert missing.status_code == 200
    assert missing.json()["available"] is False
    assert missing.json()["reason_code"] == "HEARTBEAT_MISSING"

    path = tmp_path / "worker.heartbeat"
    path.write_text(
        json.dumps(
            {
                "status": "running",
                "pid": 1234,
                "worker_id": "api-worker",
                "last_seen": utcnow().isoformat(),
                "current_job_id": None,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("RAG_WORKER_HEARTBEAT_FILE", str(path))
    available = client.get(f"{RAG}/runtime/worker")
    assert available.status_code == 200
    assert available.json()["available"] is True
    assert available.json()["worker_id"] == "api-worker"


def test_openapi_contains_frozen_api_inventory_and_no_internal_tokens(client) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    paths = spec["paths"]
    expected = {
        ("get", "/api/v1/rag/dossiers"),
        ("post", "/api/v1/rag/dossiers"),
        ("get", "/api/v1/rag/dossiers/{dossier_id}"),
        ("post", "/api/v1/rag/dossiers/{dossier_id}/runs"),
        ("get", "/api/v1/rag/runs/{run_id}"),
        ("get", "/api/v1/rag/runs/{run_id}/events"),
        ("post", "/api/v1/rag/runs/{run_id}/cancel"),
        ("get", "/api/v1/rag/runtime/worker"),
    }
    present = {
        (method, path)
        for path, item in paths.items()
        for method in item
        if path.startswith("/api/v1/rag")
    }
    assert expected.issubset(present)
    start = paths["/api/v1/rag/dossiers/{dossier_id}/runs"]["post"]
    assert any(
        parameter.get("in") == "header"
        and parameter.get("name") == "Idempotency-Key"
        and parameter.get("required") is True
        for parameter in start.get("parameters", [])
    )
    evidence_state = spec["components"]["schemas"]["EvidenceStateSchema"]["properties"]
    assert set(evidence_state) == {
        "readback_session",
        "run",
        "steps",
        "jobs",
        "attempts",
        "events",
    }
    assert "artifact_persisted" not in evidence_state
    assert "verified" not in evidence_state
    serialized = json.dumps(spec)
    assert "lease_token" not in serialized
    assert "fencing_token" not in serialized


def test_rag_router_has_no_m05_service_or_m03_import() -> None:
    root = Path(__file__).resolve().parents[1] / "app/api/v1/rag"
    sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(root.glob("*.py"))
        if path.name != "errors.py"
    )
    assert "app.modules.execution.service" not in sources
    assert "app.modules.execution.models" not in sources
    assert "app.modules.knowledge" not in sources
    assert "app.modules.dossier" not in sources
