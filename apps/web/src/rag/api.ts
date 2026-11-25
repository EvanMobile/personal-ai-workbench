import { ApiError, errorMessage, request } from '../api'
import type { MessageKey } from '../i18n/messages'
import type {
  RagDossierDetail,
  RagDossierList,
  RagDossierSummary,
  RagEventPage,
  RagRunDetail,
  RagStartRunResponse,
} from './types'

export const RAG_LIMIT = 100

export const ragApi = {
  dossiers: (signal?: AbortSignal) =>
    request<RagDossierList>(`/rag/dossiers?limit=${RAG_LIMIT}&offset=0`, { signal }),

  createDossier: (title: string, description: string, signal?: AbortSignal) =>
    request<RagDossierSummary>('/rag/dossiers', {
      method: 'POST',
      body: { title, description },
      signal,
    }),

  dossier: (id: string, signal?: AbortSignal) =>
    request<RagDossierDetail>(`/rag/dossiers/${encodeURIComponent(id)}`, { signal }),

  startDossierRollup: (
    dossierId: string,
    idempotencyKey: string,
    signal?: AbortSignal,
  ) =>
    request<RagStartRunResponse>(
      `/rag/dossiers/${encodeURIComponent(dossierId)}/runs`,
      {
        method: 'POST',
        body: { kind: 'dossier_rollup', params: {} },
        headers: { 'Idempotency-Key': idempotencyKey },
        signal,
      },
    ),

  run: (runId: string, signal?: AbortSignal) =>
    request<RagRunDetail>(`/rag/runs/${encodeURIComponent(runId)}`, { signal }),

  runEvents: (runId: string, afterId = 0, signal?: AbortSignal) =>
    request<RagEventPage>(
      `/rag/runs/${encodeURIComponent(runId)}/events?after_id=${afterId}&limit=200`,
      { signal },
    ),
}

const ERROR_KEYS: Record<string, MessageKey> = {
  RAG_DOSSIER_NOT_FOUND: 'rag.error.RAG_DOSSIER_NOT_FOUND',
  RAG_RUN_NOT_FOUND: 'rag.error.RAG_RUN_NOT_FOUND',
  RAG_DOSSIER_ARCHIVED: 'rag.error.RAG_DOSSIER_ARCHIVED',
  RAG_IDEMPOTENCY_CONFLICT: 'rag.error.RAG_IDEMPOTENCY_CONFLICT',
  RAG_RUN_INCOMPLETE: 'rag.error.RAG_RUN_INCOMPLETE',
  RAG_RUN_NOT_CANCELLABLE: 'rag.error.RAG_RUN_NOT_CANCELLABLE',
  RAG_UNSUPPORTED_RUN_KIND: 'rag.error.RAG_UNSUPPORTED_RUN_KIND',
  RAG_INVALID_RUN_PARAMS: 'rag.error.RAG_INVALID_RUN_PARAMS',
  RAG_IDEMPOTENCY_KEY_REQUIRED: 'rag.error.RAG_IDEMPOTENCY_KEY_REQUIRED',
  RAG_INVALID_IDEMPOTENCY_KEY: 'rag.error.RAG_INVALID_IDEMPOTENCY_KEY',
  RAG_VALIDATION_ERROR: 'rag.error.RAG_VALIDATION_ERROR',
  RAG_INTERNAL_ERROR: 'rag.error.RAG_INTERNAL_ERROR',
  RAG_EXECUTION_CONFLICT: 'rag.error.RAG_EXECUTION_CONFLICT',
}

function errorCode(error: ApiError): string | null {
  if (!error.detail || typeof error.detail !== 'object') return null
  const code = (error.detail as { code?: unknown }).code
  return typeof code === 'string' ? code : null
}

export function ragErrorMessage(
  error: unknown,
  t: (key: MessageKey) => string,
): string {
  if (error instanceof ApiError) {
    const code = errorCode(error)
    if (code) {
      const key = ERROR_KEYS[code]
      return key ? `${code} · ${t(key)}` : `${code} · ${error.message}`
    }
  }
  return errorMessage(error)
}
