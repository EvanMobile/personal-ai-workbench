/* Domain types for the Personal AI Workbench API (P1.M1 contract). */

export interface HealthResponse {
  status: string
  database: string
}

export interface KnowledgeStats {
  raw_contents: number
  drafts: number
  assets: number
  dossiers: number
  pages: number
  artifacts: number
}

export interface CapturePayload {
  input_type: 'text'
  content: string
  intent: string
  metadata?: Record<string, unknown>
}

export interface CaptureResponse {
  capture_id: string
  raw_content_id: string
  status: string
  message: string
  source_type: string
}

export interface RawContent {
  id: string
  source_type: string
  title: string
  preview: string
  created_at: string
}

export interface Draft {
  id: string
  raw_content_id: string
  title: string
  summary: string
  conclusion: string
  body_markdown: string
  category: string
  tags: string[]
  provider: string
  model: string
  prompt_version: string
  processing_mode: string
  is_mock: boolean | null
  status: 'draft' | string
  version: number
  created_at: string
  updated_at: string
}

export interface ArtifactRef {
  id: string
  status: string
  url: string
  width: number
  height: number
  provider?: string
  processing_mode?: string
  is_mock?: boolean | null
}

export interface Asset {
  id: string
  draft_id: string
  raw_content_id: string
  title: string
  summary: string
  conclusion: string
  body_markdown: string
  category: string
  tags: string[]
  status: string
  version: number
  published_at: string
  archived: boolean
  artifact: ArtifactRef | null
  dossier_ids: string[]
  /* Not guaranteed by the P1.M1 list contract, but exposed by some detail payloads. */
  provider?: string
  model?: string
  prompt_version?: string
  processing_mode?: string
  is_mock?: boolean | null
  created_at?: string
  updated_at?: string
}

export interface PublishResponse {
  asset: Asset
  artifact: ArtifactRef | null
  publish_record: Record<string, unknown>
}

export interface DossierSummary {
  id: string
  name: string
  description: string
  card_count: number
  page_id: string | null
  updated_at: string
  created_at?: string
}

export interface DossierEdge {
  source: string
  target: string
  reason: string
}

export interface DossierDetailData {
  dossier: DossierSummary
  cards: Asset[]
  edges: DossierEdge[]
}

export interface DossierAssetResponse {
  dossier: DossierSummary
  cards: Asset[]
  edges: DossierEdge[]
}

export interface PageSummary {
  id: string
  dossier_id: string
  title: string
  version: number
  updated_at: string
  cover_asset_id: string | null
}

export interface PageSection {
  heading: string
  body: string
  cards?: Asset[]
}

export interface PageContent {
  title?: string
  subtitle?: string
  sections?: PageSection[]
}

export interface PageVersion {
  id: string
  version: number
  content_json: PageContent | string
  source_asset_ids: string[]
  renderer: string
  model: string
  created_at: string
}

export interface PageDetailData {
  page: PageSummary
  current: PageVersion
  versions: PageVersion[]
}

export interface ConversationSummary {
  id: string
  title: string
  updated_at: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | string
  content: string
  created_at: string
}

export interface ConversationDetail {
  conversation: ConversationSummary
  messages: ChatMessage[]
}

export interface MessageExchange {
  user: ChatMessage
  reply: ChatMessage
}

export interface SuggestionAction {
  type: string
  payload?: Record<string, unknown>
}

export interface ChatSuggestion {
  id: string
  kind: string
  title: string
  description: string
  action: SuggestionAction
  related_id: string | null
}

export interface AssetPatch {
  category?: string
  tags?: string[]
  archived?: boolean
  dossier_id?: string | null
}

/* UI routing types */

export type ViewKind =
  | 'home'
  | 'capture'
  | 'cards'
  | 'card'
  | 'dossiers'
  | 'dossier'
  | 'pages'
  | 'page'
  | 'draft'
  | 'rag-dossiers'
  | 'rag-dossier'
  | 'rag-run'
  | 'project-replay'
  | 'arsenal'

export interface ViewParams {
  id?: string
  title?: string
}

export interface WorkspaceTab {
  id: string
  kind: ViewKind
  title: string
  params?: ViewParams
  closable: boolean
}

export type OpenView = (kind: ViewKind, params?: ViewParams, title?: string) => void

export interface ToastMessage {
  id: number
  tone: 'info' | 'success' | 'danger'
  text: string
}
