"""Evidence-state contract: object-level new-Session readback for Run Detail."""

from __future__ import annotations

from sqlalchemy import select

from app.core.db import SessionLocal
from app.modules.evaluation.facades.dossiers import DossierFacade
from app.modules.evaluation.facades.execution import ExecutionFacade
from app.modules.execution import service as execution_service
from app.modules.execution.models import (
    ExecutionEvent,
    ExecutionJob,
    ExecutionJobAttempt,
    ExecutionStep,
)
from app.modules.execution.results import StepResult
from app.modules.execution.service import (
    claim_job,
    create_job,
    create_run,
    create_step,
    finish_job,
    get_run_evidence_presence,
    payload_hash,
)


def _dossier() -> str:
    with SessionLocal() as session:
        return DossierFacade.create(session, title="Evidence State Dossier").id


def _start(dossier_id: str, key: str):
    with SessionLocal() as session:
        return ExecutionFacade.start_dossier_rollup(
            session, dossier_id=dossier_id, idempotency_key=key
        )


def _claim_and_finish() -> None:
    with SessionLocal() as session:
        claimed = claim_job(session, worker_id="evidence-worker", lease_seconds=60)
        assert claimed is not None
        finish_job(
            session,
            job_id=claimed.job_id,
            lease_token=claimed.lease_token,
            attempt_id=claimed.attempt_id,
            result=StepResult(status="succeeded", processed_count=1),
        )


def _get_detail(run_id: str):
    with SessionLocal() as session:
        return ExecutionFacade.get_run(session, run_id=run_id)


def test_evidence_state_success_all_objects_and_new_session() -> None:
    dossier_id = _dossier()
    run = _start(dossier_id, "evidence-all")
    _claim_and_finish()
    detail = _get_detail(run.run.id)
    state = detail.evidence_state
    assert state.readback_session == "new"
    for item in (state.run, state.steps, state.jobs, state.attempts, state.events):
        assert item.exists is True
        assert item.read_back is True
    assert not hasattr(state, "artifact_persisted")
    assert not hasattr(state, "verified")


def test_evidence_state_no_child_objects() -> None:
    dossier_id = _dossier()
    with SessionLocal() as session:
        run, _ = create_run(
            session,
            scope_type="rag_dossier",
            scope_id=dossier_id,
            pipeline="dossier",
            stage="dossier_rollup",
            config_snapshot={"kind": "evidence-empty"},
            config_hash="a" * 64,
            fingerprint="b" * 64,
        )
    detail = _get_detail(run.id)
    state = detail.evidence_state
    assert state.run.exists is True and state.run.read_back is True
    for item in (state.steps, state.jobs, state.attempts, state.events):
        assert item.exists is False
        assert item.read_back is True


def test_evidence_state_multiple_children_and_events_not_first_page() -> None:
    dossier_id = _dossier()
    with SessionLocal() as session:
        created = execution_service.create_run_with_step_job(
            session,
            scope_type="rag_dossier",
            scope_id=dossier_id,
            pipeline="dossier",
            stage="dossier_rollup",
            config_snapshot={"kind": "evidence-many"},
            config_hash="a" * 64,
            fingerprint="b" * 64,
            step_key="first",
            ordinal=1,
            job_key="first",
            kind="dossier_rollup",
            payload={},
            idempotency_key="evidence-many",
            idempotency_payload_hash=payload_hash({"kind": "evidence-many"}),
        )
        step2 = create_step(session, run_id=created.run_id, step_key="second", ordinal=2)
        create_job(
            session,
            run_id=created.run_id,
            step_id=step2.id,
            job_key="second",
            kind="dossier_rollup",
            payload={},
        )
    _claim_and_finish()
    _claim_and_finish()

    with SessionLocal() as session:
        for index in range(60):
            session.add(
                ExecutionEvent(
                    run_id=created.run_id,
                    type="test.many",
                    message=f"event {index}",
                    payload={"index": index},
                )
            )
        session.commit()
        counts = (
            len(session.scalars(select(ExecutionStep).where(ExecutionStep.run_id == created.run_id)).all()),
            len(session.scalars(select(ExecutionJob).where(ExecutionJob.run_id == created.run_id)).all()),
            len(session.scalars(select(ExecutionJobAttempt).join(ExecutionJob, ExecutionJobAttempt.job_id == ExecutionJob.id).where(ExecutionJob.run_id == created.run_id)).all()),
            len(session.scalars(select(ExecutionEvent).where(ExecutionEvent.run_id == created.run_id)).all()),
        )
        presence = get_run_evidence_presence(session, run_id=created.run_id)
    assert counts[0] >= 2 and counts[1] >= 2 and counts[2] >= 2 and counts[3] >= 60
    assert presence.run_exists is True
    assert presence.steps_exists is True
    assert presence.jobs_exists is True
    assert presence.attempts_exists is True
    assert presence.events_exists is True

    detail = _get_detail(created.run_id)
    state = detail.evidence_state
    assert all(
        item.exists is True and item.read_back is True
        for item in (state.run, state.steps, state.jobs, state.attempts, state.events)
    )


def test_evidence_state_uses_distinct_new_session(monkeypatch) -> None:
    dossier_id = _dossier()
    run = _start(dossier_id, "evidence-session")
    captured = []
    real = execution_service.get_run_evidence_presence

    def wrapper(session, *, run_id):
        captured.append(session)
        return real(session, run_id=run_id)

    monkeypatch.setattr(execution_service, "get_run_evidence_presence", wrapper)
    with SessionLocal() as request_session:
        detail = ExecutionFacade.get_run(request_session, run_id=run.run.id)
        assert captured
        assert captured[0] is not request_session
    assert detail.evidence_state.readback_session == "new"


def test_evidence_state_read_failure_is_not_false_absence(monkeypatch) -> None:
    dossier_id = _dossier()
    run = _start(dossier_id, "evidence-failure")

    def boom(*_args, **_kwargs):
        raise RuntimeError("readback unavailable")

    monkeypatch.setattr(execution_service, "get_run_evidence_presence", boom)
    detail = _get_detail(run.run.id)
    state = detail.evidence_state
    assert state.readback_session == "new"
    for item in (state.run, state.steps, state.jobs, state.attempts, state.events):
        assert item.exists is None
        assert item.read_back is False


def test_evidence_presence_missing_run() -> None:
    with SessionLocal() as session:
        presence = get_run_evidence_presence(session, run_id="missing")
    assert presence.run_exists is False
    assert presence.steps_exists is False
    assert presence.jobs_exists is False
    assert presence.attempts_exists is False
    assert presence.events_exists is False


def test_dossier_detail_keeps_fixed_capabilities_only() -> None:
    dossier_id = _dossier()
    with SessionLocal() as session:
        detail = DossierFacade.detail(session, dossier_id=dossier_id)
    assert detail.evidence_capabilities.generated is True
    assert detail.evidence_capabilities.db_persisted is True
    assert detail.evidence_capabilities.artifact_persisted == "not_available"
    assert detail.evidence_capabilities.verified == "not_implemented"
    assert not hasattr(detail, "evidence_state")
