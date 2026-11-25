/** RAG Lab M1-A API DTOs. Mirrors the frozen OpenAPI contract. */

export type RagRunStatus =
  | 'queued'
  | 'running'
  | 'succeeded'
  | 'partial'
  | 'failed'
  | 'cancelled'
  | 'skipped'

export type RagStageStatus =
  | 'not_started'
  | 'active'
  | 'queued'
  | 'running'
  | 'succeeded'
  | 'partial'
  | 'failed'
  | 'cancelled'
  | 'skipped'

export type RagJobStatus = RagRunStatus
export type RagStepStatus =
  | 'pending'
  | 'running'
  | 'succeeded'
  | 'partial'
  | 'failed'
  | 'cancelled'
  | 'skipped'
export type RagAttemptStatus = 'running' | 'succeeded' | 'failed' | 'abandoned' | 'cancelled'

export interface RagRunSummary {
  id: string
  scope_type: string
  scope_id: string
  pipeline: string
  stage: string
  status: RagRunStatus
  created_at: string
  updated_at: string
  cancel_requested_at: string | null
  error_code: string | null
}

export interface RagDossierSummary {
  id: string
  title: string
  description: string
  status: 'active' | 'archived'
  created_at: string
  updated_at: string
  last_run: RagRunSummary | null
  run_count: number
  active_run_count: number
}

export interface RagDossierList {
  items: RagDossierSummary[]
  total: number
  limit: number
  offset: number
}

export interface RagExecutionStats {
  run_count: number
  active_run_count: number
  failed_run_count: number
  latest_run_at: string | null
  latest_success_at: string | null
}

export interface RagLastError {
  code: string
  detail: string | null
}

export interface RagStageSummary {
  stage_key: string
  status: RagStageStatus
  active_run_count: number
  latest_run: RagRunSummary | null
  latest_terminal_run: RagRunSummary | null
  run_count: number
  failed_run_count: number
  last_activity_at: string | null
  latest_result: Record<string, unknown> | null
  last_error: RagLastError | null
  next_actions: string[]
}

export interface RagEvidenceCapabilities {
  generated: boolean
  db_persisted: boolean
  artifact_persisted: string
  verified: string
}

export interface RagEvidenceObjectState {
  exists: boolean | null
  read_back: boolean
}

export interface RagEvidenceState {
  readback_session: string
  run: RagEvidenceObjectState
  steps: RagEvidenceObjectState
  jobs: RagEvidenceObjectState
  attempts: RagEvidenceObjectState
  events: RagEvidenceObjectState
}

export interface RagWorkerSnapshot {
  available: boolean
  heartbeat_at: string | null
  expired: boolean
  pid: number | null
  worker_id: string | null
  current_job_id: string | null
  state: string | null
  age_seconds: number | null
  stale_after_seconds: number
  reason_code: string | null
}

export interface RagDossierDetail {
  dossier: RagDossierSummary
  stages: RagStageSummary[]
  execution: RagExecutionStats
  recent_runs: RagRunSummary[]
  worker: RagWorkerSnapshot
  evidence_capabilities: RagEvidenceCapabilities
  blocking: string[]
  next_actions: string[]
}

export interface RagAttempt {
  id: string
  job_id: string
  attempt_no: number
  status: RagAttemptStatus
  worker_id: string
  started_at: string
  finished_at: string | null
  error_code: string | null
  error_detail: string | null
  metrics: Record<string, unknown>
}

export interface RagJob {
  id: string
  run_id: string
  step_id: string
  job_key: string
  kind: string
  status: RagJobStatus
  attempts: number
  max_attempts: number
  available_at: string
  locked_by: string | null
  cancel_requested_at: string | null
  processed_count: number
  failed_count: number
  error_code: string | null
  error_detail: string | null
  created_at: string
  updated_at: string
  attempts_history: RagAttempt[]
}

export interface RagStep {
  id: string
  run_id: string
  step_key: string
  ordinal: number
  status: RagStepStatus
  progress: number
  processed_count: number
  failed_count: number
  error_code: string | null
  error_detail: string | null
  created_at: string
  updated_at: string
  jobs: RagJob[]
}

export interface RagRunDetail {
  run: RagRunSummary
  config_snapshot: Record<string, unknown>
  config_hash: string
  fingerprint: string
  parent_run_id: string | null
  app_git_sha: string | null
  result: Record<string, unknown> | null
  error_detail: string | null
  steps: RagStep[]
  evidence_capabilities: RagEvidenceCapabilities
  evidence_state: RagEvidenceState
}

export interface RagStartRunResponse {
  run: RagRunSummary
  reused: boolean
  worker_available: boolean
  warnings: string[]
}

export interface RagEvent {
  id: number
  run_id: string
  step_id: string | null
  job_id: string | null
  type: string
  level: string
  message: string
  payload: Record<string, unknown>
  created_at: string
}

export interface RagEventPage {
  items: RagEvent[]
  next_after_id: number
  has_more: boolean
}
