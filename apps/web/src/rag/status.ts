import type { MessageKey } from '../i18n/messages'
import type {
  RagAttemptStatus,
  RagJobStatus,
  RagRunStatus,
  RagStageStatus,
  RagStepStatus,
} from './types'

type AnyStatus = RagRunStatus | RagStageStatus | RagJobStatus | RagStepStatus | RagAttemptStatus

const STATUS_KEYS: Record<AnyStatus, MessageKey> = {
  not_started: 'rag.status.not_started',
  active: 'rag.status.active',
  pending: 'rag.status.pending',
  queued: 'rag.status.queued',
  running: 'rag.status.running',
  succeeded: 'rag.status.succeeded',
  partial: 'rag.status.partial',
  failed: 'rag.status.failed',
  cancelled: 'rag.status.cancelled',
  skipped: 'rag.status.skipped',
  abandoned: 'rag.status.abandoned',
}

export type RagStatusTone = 'default' | 'accent' | 'success' | 'danger' | 'muted'

export function ragStatusKey(status: AnyStatus): MessageKey {
  return STATUS_KEYS[status]
}

export function ragStatusTone(status: AnyStatus): RagStatusTone {
  if (status === 'succeeded') return 'success'
  if (status === 'failed' || status === 'abandoned') return 'danger'
  if (status === 'running' || status === 'active') return 'accent'
  if (status === 'partial') return 'accent'
  return 'muted'
}
