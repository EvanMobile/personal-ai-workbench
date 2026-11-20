import type {
  Asset,
  AssetPatch,
  CapturePayload,
  CaptureResponse,
  ChatSuggestion,
  ConversationDetail,
  ConversationSummary,
  DossierAssetResponse,
  DossierDetailData,
  DossierSummary,
  Draft,
  HealthResponse,
  KnowledgeStats,
  MessageExchange,
  PageDetailData,
  PageSummary,
  PublishResponse,
  RawContent,
} from './types'

const API_ROOT = '/api/v1'

export class ApiError extends Error {
  readonly status: number
  readonly detail: unknown

  constructor(message: string, status: number, detail?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

/** Network-level failures (as opposed to an HTTP error response). */
export class ApiOfflineError extends Error {
  constructor(message = 'API offline — cannot reach the workbench service.') {
    super(message)
    this.name = 'ApiOfflineError'
  }
}

function extractMessage(body: unknown, fallback: string): string {
  if (!body) return fallback
  if (typeof body === 'string') return body
  if (typeof body === 'object') {
    const record = body as Record<string, unknown>
    const detail = record.detail ?? record.message ?? record.error
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      const parts = detail
        .map((item) => {
          if (typeof item === 'string') return item
          if (item && typeof item === 'object' && 'msg' in item) {
            return String((item as { msg: unknown }).msg)
          }
          return ''
        })
        .filter(Boolean)
      if (parts.length > 0) return parts.join('; ')
    }
  }
  return fallback
}

interface RequestOptions {
  method?: string
  body?: unknown
  signal?: AbortSignal
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, signal } = options
  let response: Response

  try {
    response = await fetch(`${API_ROOT}${path}`, {
      method,
      headers:
        body instanceof FormData
          ? undefined
          : body !== undefined
            ? { 'Content-Type': 'application/json' }
            : undefined,
      body:
        body === undefined
          ? undefined
          : body instanceof FormData
            ? body
            : JSON.stringify(body),
      signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiOfflineError()
  }

  if (!response.ok) {
    let parsed: unknown
    try {
      parsed = await response.json()
    } catch {
      try {
        parsed = await response.text()
      } catch {
        parsed = undefined
      }
    }
    const message = extractMessage(parsed, `Request failed (${response.status})`)
    throw new ApiError(message, response.status, parsed)
  }

  if (response.status === 204) return undefined as T
  const contentType = response.headers.get('content-type') ?? ''
  if (!contentType.includes('application/json')) {
    return (await response.text()) as T
  }
  return (await response.json()) as T
}

function q(value: string): string {
  return encodeURIComponent(value)
}

export const api = {
  health: (signal?: AbortSignal) => request<HealthResponse>('/health', { signal }),

  stats: (signal?: AbortSignal) => request<KnowledgeStats>('/knowledge/stats', { signal }),

  captureText: (payload: CapturePayload, signal?: AbortSignal) =>
    request<CaptureResponse>('/ingestion/captures', {
      method: 'POST',
      body: payload,
      signal,
    }),

  captureFile: (file: File, intent: string, signal?: AbortSignal) => {
    const form = new FormData()
    form.append('file', file)
    form.append('intent', intent)
    return request<CaptureResponse>('/ingestion/captures/files', {
      method: 'POST',
      body: form,
      signal,
    })
  },

  rawContents: (signal?: AbortSignal) =>
    request<RawContent[]>('/ingestion/raw-contents', { signal }),

  digest: (rawContentId: string, signal?: AbortSignal) =>
    request<{ draft: Draft }>(`/knowledge/raw-contents/${q(rawContentId)}/digest`, {
      method: 'POST',
      body: {},
      signal,
    }),

  drafts: (signal?: AbortSignal) => request<Draft[]>('/knowledge/drafts', { signal }),

  draft: (id: string, signal?: AbortSignal) =>
    request<Draft>(`/knowledge/drafts/${q(id)}`, { signal }),

  reviseDraft: (id: string, instruction: string, signal?: AbortSignal) =>
    request<{ draft: Draft }>(`/knowledge/drafts/${q(id)}/revisions`, {
      method: 'POST',
      body: { instruction },
      signal,
    }),

  publishDraft: (id: string, note?: string, signal?: AbortSignal) =>
    request<PublishResponse>(`/knowledge/drafts/${q(id)}/publish`, {
      method: 'POST',
      body: note ? { note } : {},
      signal,
    }),

  assets: (signal?: AbortSignal) => request<Asset[]>('/knowledge/assets', { signal }),

  asset: (id: string, signal?: AbortSignal) =>
    request<Asset & { raw_content?: RawContent; draft?: Draft }>(
      `/knowledge/assets/${q(id)}`,
      { signal },
    ),

  patchAsset: (id: string, patch: AssetPatch, signal?: AbortSignal) =>
    request<Asset>(`/knowledge/assets/${q(id)}`, {
      method: 'PATCH',
      body: patch,
      signal,
    }),

  dossiers: (signal?: AbortSignal) =>
    request<DossierSummary[]>('/knowledge/dossiers', { signal }),

  createDossier: (name: string, description?: string, signal?: AbortSignal) =>
    request<DossierSummary>('/knowledge/dossiers', {
      method: 'POST',
      body: description ? { name, description } : { name },
      signal,
    }),

  dossier: (id: string, signal?: AbortSignal) =>
    request<DossierDetailData>(`/knowledge/dossiers/${q(id)}`, { signal }),

  addDossierAssets: (id: string, assetIds: string[], signal?: AbortSignal) =>
    request<DossierAssetResponse>(`/knowledge/dossiers/${q(id)}/assets`, {
      method: 'POST',
      body: { asset_ids: assetIds },
      signal,
    }),

  removeDossierAsset: (dossierId: string, assetId: string, signal?: AbortSignal) =>
    request<void>(
      `/knowledge/dossiers/${q(dossierId)}/assets/${q(assetId)}`,
      { method: 'DELETE', signal },
    ),

  pages: (signal?: AbortSignal) => request<PageSummary[]>('/knowledge/pages', { signal }),

  createPage: (dossierId: string, title?: string, signal?: AbortSignal) =>
    request<PageDetailData>('/knowledge/pages', {
      method: 'POST',
      body: title ? { dossier_id: dossierId, title } : { dossier_id: dossierId },
      signal,
    }),

  page: (id: string, signal?: AbortSignal) =>
    request<PageDetailData>(`/knowledge/pages/${q(id)}`, { signal }),

  regenerateArtifact: (id: string, signal?: AbortSignal) =>
    request<unknown>(`/artifacts/${q(id)}/regenerate`, {
      method: 'POST',
      body: {},
      signal,
    }),

  conversations: (signal?: AbortSignal) =>
    request<ConversationSummary[]>('/chat/conversations', { signal }),

  createConversation: (title?: string, signal?: AbortSignal) =>
    request<ConversationSummary>('/chat/conversations', {
      method: 'POST',
      body: title ? { title } : {},
      signal,
    }),

  conversation: (id: string, signal?: AbortSignal) =>
    request<ConversationDetail>(`/chat/conversations/${q(id)}`, { signal }),

  sendMessage: (id: string, content: string, signal?: AbortSignal) =>
    request<MessageExchange>(`/chat/conversations/${q(id)}/messages`, {
      method: 'POST',
      body: { content },
      signal,
    }),

  suggestions: (signal?: AbortSignal) =>
    request<ChatSuggestion[]>('/chat/suggestions', { signal }),
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiOfflineError) return error.message
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return 'Something went wrong.'
}

export function isOfflineError(error: unknown): boolean {
  return error instanceof ApiOfflineError
}
