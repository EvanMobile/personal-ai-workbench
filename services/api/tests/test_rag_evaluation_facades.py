"""R3.2: M06 DossierFacade / ExecutionFacade with real PostgreSQL + M05."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest
from sqlalchemy import event, func, select

from app.core.db import SessionLocal, engine
from app.core.utils import utcnow
from app.modules.evaluation.errors import (
    DossierArchived,
    DossierNotFound,
    InvalidDossierRunParams,
    RunNotFound,
    UnsupportedDossierRunKind,
)
from app.modules.evaluation.facades.dossiers import DossierFacade
from app.modules.evaluation.facades.execution import (
    DOSSIER_ROLLUP_STAGE,
    ExecutionFacade,
)
from app.modules.evaluation.models import RagDossier
from app.modules.execution.models import ExecutionJob, ExecutionRun
from app.modules.execution.results import StepResult
from app.modules.execution.service import (
    claim_job,
    create_run_with_step_job,
    finish_job,
    payload_hash,
)


@pytest.fixture(autouse=True)
def no_worker(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "RAG_WORKER_HEARTBEAT_FILE", str(tmp_path / "missing.worker.heartbeat")
    )


def _create_dossier(title: str = "Facade Dossier") -> str:
    with SessionLocal() as session:
        return DossierFacade.create(session, title=title).id


def _start(dossier_id: str, key: str):
    with SessionLocal() as session:
        return ExecutionFacade.start_dossier_rollup(
            session, dossier_id=dossier_id, idempotency_key=key
        )


def _claim():
    with SessionLocal() as session:
        claimed = claim_job(session, worker_id="facade-worker", lease_seconds=60)
        assert claimed is not None
        return claimed


def _finish(claimed, status: str = "succeeded", *, result=None):
    with SessionLocal() as session:
        return finish_job(
            session,
            job_id=claimed.job_id,
            lease_token=claimed.lease_token,
            attempt_id=claimed.attempt_id,
            result=StepResult(
                status=status,
                processed_count=1 if status in {"succeeded", "partial"} else 0,
                failed_count=1 if status in {"failed", "partial"} else 0,
                result=result,
                error_code="SYNTHETIC" if status == "failed" else None,
            ),
        )


def _seed_stage_run(dossier_id: str, stage: str, key: str):
    with SessionLocal() as session:
        return create_run_with_step_job(
            session,
            scope_type="rag_dossier",
            scope_id=dossier_id,
            pipeline="dataset" if stage == "dataset" else "dossier",
            stage=stage,
            config_snapshot={"kind": stage},
            config_hash="a" * 64,
            fingerprint="b" * 64,
            step_key=stage,
            ordinal=1,
            job_key=stage,
            kind=stage,
            payload={},
            idempotency_key=key,
            idempotency_payload_hash=payload_hash({"stage": stage, "key": key}),
        )


def _write_worker_heartbeat(path: Path, worker_id: str = "facade-worker") -> None:
    path.write_text(
        json.dumps(
            {
                "status": "running",
                "pid": 1234,
                "worker_id": worker_id,
                "last_seen": utcnow().isoformat(),
                "current_job_id": None,
            }
        ),
        encoding="utf-8",
    )


def test_dossier_create_list_and_detail_without_runs(tmp_path, monkeypatch) -> None:
    dossier_id = _create_dossier()
    with SessionLocal() as session:
        listed = DossierFacade.list(session)
        detail = DossierFacade.detail(session, dossier_id=dossier_id)

    assert listed.total == 1
    assert listed.items[0].id == dossier_id
    assert listed.items[0].run_count == 0
    assert listed.items[0].last_run is None
    assert detail.dossier.id == dossier_id
    assert len(detail.stages) == 1
    stage = detail.stages[0]
    assert stage.stage_key == DOSSIER_ROLLUP_STAGE
    assert stage.status == "not_started"
    assert stage.active_run_count == 0
    assert stage.latest_run is None
    assert stage.latest_terminal_run is None
    assert detail.execution.run_count == 0
    assert detail.recent_runs == ()
    assert detail.worker.available is False
    assert detail.worker.reason_code == "HEARTBEAT_MISSING"
    assert "NO_RUN" in detail.blocking
    assert "WORKER_UNAVAILABLE" in detail.blocking
    assert detail.next_actions == ("RUN_DOSSIER_ROLLUP",)
    assert detail.evidence_capabilities.artifact_persisted == "not_available"
    assert detail.evidence_capabilities.verified == "not_implemented"


def test_dossier_not_found() -> None:
    with SessionLocal() as session:
        with pytest.raises(DossierNotFound):
            DossierFacade.detail(session, dossier_id="missing-dossier")


def test_execution_start_is_idempotent_and_returns_worker_warning() -> None:
    dossier_id = _create_dossier()
    first = _start(dossier_id, "facade-key-1")
    second = _start(dossier_id, "facade-key-1")
    assert first.reused is False
    assert second.reused is True
    assert first.run.id == second.run.id
    assert first.worker_available is False
    assert first.warnings == ("WORKER_UNAVAILABLE",)

    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(ExecutionRun)) == 1
        assert session.scalar(select(func.count()).select_from(ExecutionJob)) == 1


def test_execution_start_validates_dossier_and_params() -> None:
    dossier_id = _create_dossier()
    with SessionLocal() as session:
        with pytest.raises(InvalidDossierRunParams):
            ExecutionFacade.start_dossier_rollup(
                session, dossier_id=dossier_id, idempotency_key="x", params={"bad": 1}
            )
        with pytest.raises(UnsupportedDossierRunKind):
            ExecutionFacade.start_dossier_rollup(
                session, dossier_id=dossier_id, idempotency_key="x", kind="other"
            )
        with pytest.raises(DossierNotFound):
            ExecutionFacade.start_dossier_rollup(
                session, dossier_id="missing", idempotency_key="x"
            )

    with SessionLocal() as session:
        dossier = session.get(RagDossier, dossier_id)
        assert dossier is not None
        dossier.status = "archived"
        session.commit()
    with SessionLocal() as session:
        with pytest.raises(DossierArchived):
            ExecutionFacade.start_dossier_rollup(
                session, dossier_id=dossier_id, idempotency_key="archived"
            )


def test_stage_active_wins_over_latest_terminal_success() -> None:
    dossier_id = _create_dossier()
    first = _start(dossier_id, "active-1")
    _finish(_claim(), "succeeded", result={"count": 1})
    second = _start(dossier_id, "active-2")
    claimed = _claim()

    with SessionLocal() as session:
        detail = DossierFacade.detail(session, dossier_id=dossier_id)

    stage = detail.stages[0]
    assert stage.stage_key == DOSSIER_ROLLUP_STAGE
    assert stage.status == "active"
    assert stage.active_run_count == 1
    assert stage.latest_terminal_run is not None
    assert stage.latest_terminal_run.status == "succeeded"
    assert stage.latest_run is not None and stage.latest_run.id == second.run.id
    assert stage.latest_result == {"count": 1}
    assert detail.execution.active_run_count == 1
    assert "ACTIVE_RUN" in detail.blocking
    assert "CANCEL_RUN" in detail.next_actions
    assert "WAIT" in detail.next_actions
    # The claim is intentionally left running for the next test cleanup.
    assert claimed.run_id == second.run.id


def test_multiple_stages_aggregate_independently() -> None:
    dossier_id = _create_dossier()
    rollup = _start(dossier_id, "multi-rollup")
    _finish(_claim(), "succeeded", result={"count": 2})
    _seed_stage_run(dossier_id, "dataset", "multi-dataset")
    dataset_job = _claim()

    with SessionLocal() as session:
        detail = DossierFacade.detail(session, dossier_id=dossier_id)

    stages = {stage.stage_key: stage for stage in detail.stages}
    assert set(stages) == {"dossier_rollup", "dataset"}
    assert stages["dossier_rollup"].status == "succeeded"
    assert stages["dossier_rollup"].active_run_count == 0
    assert stages["dataset"].status == "active"
    assert stages["dataset"].active_run_count == 1
    assert detail.execution.run_count == 2
    assert detail.execution.active_run_count == 1
    assert "ACTIVE_RUN" in detail.blocking
    assert "CANCEL_RUN" in detail.next_actions
    assert dataset_job.run_id


def test_recent_runs_are_limited_and_statistics_are_real() -> None:
    dossier_id = _create_dossier()
    for index in range(7):
        _start(dossier_id, f"recent-{index}")

    with SessionLocal() as session:
        detail = DossierFacade.detail(session, dossier_id=dossier_id)
        listed = DossierFacade.list(session)

    assert detail.execution.run_count == 7
    assert detail.execution.active_run_count == 7
    assert len(detail.recent_runs) == 5
    assert all(
        detail.recent_runs[index].created_at >= detail.recent_runs[index + 1].created_at
        for index in range(len(detail.recent_runs) - 1)
    )
    assert listed.items[0].run_count == 7
    assert listed.items[0].active_run_count == 7
    assert listed.items[0].last_run is not None
    assert listed.items[0].last_run.id == detail.recent_runs[0].id


def test_dossier_detail_success_normal_combination(tmp_path, monkeypatch) -> None:
    path = tmp_path / "worker.heartbeat"
    _write_worker_heartbeat(path)
    monkeypatch.setenv("RAG_WORKER_HEARTBEAT_FILE", str(path))
    dossier_id = _create_dossier()
    run = _start(dossier_id, "success-normal")
    _finish(_claim(), "succeeded", result={"dossier_count": 1})

    with SessionLocal() as session:
        detail = DossierFacade.detail(session, dossier_id=dossier_id)

    stage = detail.stages[0]
    assert stage.status == "succeeded"
    assert stage.latest_result == {"dossier_count": 1}
    assert stage.last_error is None
    assert detail.dossier.last_run is not None
    assert detail.dossier.last_run.id == run.run.id
    assert detail.worker.available is True
    assert detail.blocking == ()
    assert detail.next_actions == ("RUN_DOSSIER_ROLLUP", "VIEW_RUN")
    assert detail.evidence_capabilities.generated is True
    assert detail.evidence_capabilities.db_persisted is True
    assert detail.evidence_capabilities.artifact_persisted == "not_available"
    assert detail.evidence_capabilities.verified == "not_implemented"


def test_failed_stage_exposes_safe_error_and_retry_action() -> None:
    dossier_id = _create_dossier()
    run = _start(dossier_id, "failed-key")
    _finish(_claim(), "failed")

    with SessionLocal() as session:
        detail = DossierFacade.detail(session, dossier_id=dossier_id)

    stage = detail.stages[0]
    assert stage.status == "failed"
    assert stage.last_error is not None
    assert stage.last_error.code == "SYNTHETIC"
    assert "LAST_RUN_FAILED" in detail.blocking
    assert "RETRY_DOSSIER_ROLLUP" in detail.next_actions


def test_dataset_failure_does_not_trigger_rollup_retry_action() -> None:
    dossier_id = _create_dossier()
    rollup = _start(dossier_id, "rollup-success-dataset-fail")
    _finish(_claim(), "succeeded", result={"count": 1})
    _seed_stage_run(dossier_id, "dataset", "dataset-fail")
    _finish(_claim(), "failed")

    with SessionLocal() as session:
        detail = DossierFacade.detail(session, dossier_id=dossier_id)

    stages = {stage.stage_key: stage for stage in detail.stages}
    assert stages["dossier_rollup"].status == "succeeded"
    assert stages["dataset"].status == "failed"
    # Global last_run includes the failed Dataset Run, but Dossier Cover actions
    # must still be driven by the Rollup Stage.
    assert detail.dossier.last_run is not None
    assert detail.dossier.last_run.stage == "dataset"
    assert "LAST_RUN_FAILED" not in detail.blocking
    assert "RETRY_DOSSIER_ROLLUP" not in detail.next_actions
    assert detail.next_actions == ("RUN_DOSSIER_ROLLUP", "VIEW_RUN")


def test_rollup_failure_survives_later_dataset_success() -> None:
    dossier_id = _create_dossier()
    rollup = _start(dossier_id, "rollup-fail-dataset-success")
    _finish(_claim(), "failed")
    _seed_stage_run(dossier_id, "dataset", "dataset-success")
    _finish(_claim(), "succeeded", result={"documents": 3})

    with SessionLocal() as session:
        detail = DossierFacade.detail(session, dossier_id=dossier_id)

    stages = {stage.stage_key: stage for stage in detail.stages}
    assert stages["dossier_rollup"].status == "failed"
    assert stages["dataset"].status == "succeeded"
    assert detail.dossier.last_run is not None
    assert detail.dossier.last_run.stage == "dataset"
    assert "LAST_RUN_FAILED" in detail.blocking
    assert "RETRY_DOSSIER_ROLLUP" in detail.next_actions
    assert rollup.run.id


def test_worker_snapshot_available_removes_worker_blocking(tmp_path, monkeypatch) -> None:
    path = tmp_path / "worker.heartbeat"
    _write_worker_heartbeat(path)
    monkeypatch.setenv("RAG_WORKER_HEARTBEAT_FILE", str(path))
    dossier_id = _create_dossier()

    with SessionLocal() as session:
        detail = DossierFacade.detail(session, dossier_id=dossier_id)

    assert detail.worker.available is True
    assert "WORKER_UNAVAILABLE" not in detail.blocking
    assert detail.worker.state == "idle"


def test_execution_facade_run_events_cancel_and_not_found() -> None:
    dossier_id = _create_dossier()
    run = _start(dossier_id, "facade-run")
    with SessionLocal() as session:
        detail = ExecutionFacade.get_run(session, run_id=run.run.id)
        page = ExecutionFacade.list_events(session, run_id=run.run.id)
        assert detail.evidence_state.readback_session == "new"
        assert detail.evidence_state.run.exists is True
        assert detail.evidence_state.steps.exists is True
        assert detail.evidence_state.jobs.exists is True
        assert detail.evidence_state.attempts.exists is False
        assert detail.evidence_state.events.exists is False
        assert detail.evidence_state.run.read_back is True
        assert page.items == ()

        with pytest.raises(RunNotFound):
            ExecutionFacade.get_run(session, run_id="missing")
        with pytest.raises(RunNotFound):
            ExecutionFacade.list_events(session, run_id="missing")
        with pytest.raises(RunNotFound):
            ExecutionFacade.cancel_run(session, run_id="missing")

        # Keep the Run non-terminal so repeated Cancel exercises the
        # already_requested path rather than terminal-run rejection.
        _claim()
        cancelled = ExecutionFacade.cancel_run(session, run_id=run.run.id)
        assert cancelled.already_requested is False
        cancelled_again = ExecutionFacade.cancel_run(session, run_id=run.run.id)
        assert cancelled_again.already_requested is True


def test_dossier_list_uses_batch_reads_not_per_dossier_queries() -> None:
    for index in range(12):
        _create_dossier(f"Dossier {index}")

    select_count = 0

    def count_selects(*_args) -> None:
        nonlocal select_count
        select_count += 1

    event.listen(engine, "before_cursor_execute", count_selects)
    try:
        with SessionLocal() as session:
            listed = DossierFacade.list(session, limit=100)
    finally:
        event.remove(engine, "before_cursor_execute", count_selects)

    assert listed.total == 12
    assert len(listed.items) == 12
    assert select_count <= 4, f"dossier list issued {select_count} SELECTs"


def test_m06_facades_do_not_import_m05_orm_or_m03() -> None:
    facade_dir = Path(__file__).resolve().parents[1] / "app/modules/evaluation/facades"
    sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(facade_dir.glob("*.py"))
    )
    assert "app.modules.execution.models" not in sources
    assert "app.modules.knowledge" not in sources
    assert "app.modules.dossier" not in sources
