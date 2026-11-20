import { useState } from 'react'
import { api, errorMessage } from '../api'
import { ArtifactImage } from '../components/ArtifactImage'
import { Icon } from '../components/Icon'
import { Markdown } from '../components/Markdown'
import { useToast } from '../components/Toast'
import {
  ErrorBanner,
  MicroLabel,
  Skeleton,
  Tag,
  ViewHeader,
} from '../components/ui'
import { useAsyncData } from '../hooks/useAsyncData'
import type { Draft, OpenView, PublishResponse } from '../types'
import { formatDate, shortId } from '../utils'

export function DraftView({
  draftId,
  openView,
}: {
  draftId: string
  openView: OpenView
}) {
  const { notify } = useToast()
  const { data: draft, loading, error, reload, setData } = useAsyncData<Draft>(
    (signal) => api.draft(draftId, signal),
    [draftId],
  )
  const [instruction, setInstruction] = useState('')
  const [revising, setRevising] = useState(false)
  const [revisionError, setRevisionError] = useState<string | null>(null)
  const [note, setNote] = useState('')
  const [publishing, setPublishing] = useState(false)
  const [publishError, setPublishError] = useState<string | null>(null)
  const [published, setPublished] = useState<PublishResponse | null>(null)

  const revise = async () => {
    if (!draft || !instruction.trim()) return
    setRevising(true)
    setRevisionError(null)
    try {
      const response = await api.reviseDraft(draft.id, instruction.trim())
      setData(response.draft)
      setInstruction('')
      notify(`Draft revised to v${response.draft.version}.`, 'success')
    } catch (caught) {
      setRevisionError(errorMessage(caught))
    } finally {
      setRevising(false)
    }
  }

  const publish = async () => {
    if (!draft) return
    setPublishing(true)
    setPublishError(null)
    try {
      const response = await api.publishDraft(draft.id, note.trim() || undefined)
      setPublished(response)
      setData({ ...draft, status: 'published' })
      notify('Draft published. Card asset created.', 'success')
    } catch (caught) {
      setPublishError(errorMessage(caught))
    } finally {
      setPublishing(false)
    }
  }

  if (loading && !draft) {
    return (
      <div className="view-scroll">
        <div className="view-inner">
          <Skeleton lines={3} />
          <div className="detail-columns">
            <Skeleton lines={10} />
            <Skeleton lines={6} />
          </div>
        </div>
      </div>
    )
  }

  if (error && !draft) {
    return (
      <div className="view-scroll">
        <div className="view-inner">
          <ViewHeader
            eyebrow="Ingestion / Draft"
            title="Draft unavailable"
            back={{ label: 'Capture', onClick: () => openView('capture') }}
          />
          <ErrorBanner message={error} onRetry={reload} />
        </div>
      </div>
    )
  }

  if (!draft) return null

  return (
    <div className="view-scroll">
      <div className="view-inner">
        <ViewHeader
          eyebrow="Ingestion / Draft"
          title={draft.title}
          description={draft.summary || 'Generated draft awaiting publication.'}
          back={{ label: 'Capture', onClick: () => openView('capture') }}
          actions={
            <>
              <Tag tone={draft.status === 'published' ? 'success' : 'accent'}>{draft.status}</Tag>
              <button type="button" className="button ghost" onClick={reload}>
                <Icon name="refresh" size={13} /> Reload
              </button>
            </>
          }
        />

        {error && <ErrorBanner message={error} onRetry={reload} />}

        {draft.is_mock === true && (
          <div className="provenance-banner provenance-mock">
            <strong>MOCK · 规则模拟 · 未调用真实 LLM</strong>
            <span>
              provider {draft.provider} · model {draft.model} · prompt {draft.prompt_version} · mode {draft.processing_mode}
            </span>
          </div>
        )}
        {draft.is_mock === null && (
          <div className="provenance-banner provenance-unknown">
            <strong>UNKNOWN · 历史来源未知</strong>
            <span>
              provider {draft.provider} · model {draft.model} · prompt {draft.prompt_version} · 不能视为真实 LLM 分析
            </span>
          </div>
        )}
        {draft.is_mock === false && (
          <div className="provenance-banner provenance-real">
            <strong>REAL PROVIDER · {draft.provider}</strong>
            <span>
              model {draft.model} · prompt {draft.prompt_version} · mode {draft.processing_mode}
            </span>
          </div>
        )}

        <div className="meta-strip">
          <div>
            <span>provider</span>
            <strong>{draft.provider || 'unknown'}</strong>
          </div>
          <div>
            <span>mode</span>
            <strong>{draft.processing_mode || 'unknown'}</strong>
          </div>
          <div>
            <span>model</span>
            <strong>{draft.model}</strong>
          </div>
          <div>
            <span>prompt</span>
            <strong>{draft.prompt_version}</strong>
          </div>
          <div>
            <span>version</span>
            <strong>v{draft.version}</strong>
          </div>
          <div>
            <span>category</span>
            <strong>{draft.category || '—'}</strong>
          </div>
          <div>
            <span>updated</span>
            <strong>{formatDate(draft.updated_at)}</strong>
          </div>
        </div>

        {published && (
          <div className="publish-success">
            <div className="publish-success-artifact">
              <ArtifactImage asset={published.asset} compact />
            </div>
            <div className="publish-success-copy">
              <div className="publish-success-title">
                <Icon name="check" size={14} />
                <strong>Published as card</strong>
              </div>
              <p>
                {published.asset.title} · {published.artifact ? 'artifact generated' : 'no artifact attached'}
              </p>
              <button
                type="button"
                className="button small primary"
                onClick={() =>
                  openView('card', { id: published.asset.id }, published.asset.title)
                }
              >
                Open card <Icon name="arrow-up-right" size={11} />
              </button>
            </div>
          </div>
        )}

        <div className="draft-layout">
          <div className="draft-main">
            <section className="detail-section">
              <div className="section-head">
                <MicroLabel>Summary</MicroLabel>
                <span className="section-index">01</span>
              </div>
              <p className="detail-lead">{draft.summary || 'No summary generated.'}</p>
            </section>

            <section className="detail-section">
              <div className="section-head">
                <MicroLabel>Conclusion</MicroLabel>
                <span className="section-index">02</span>
              </div>
              <p>{draft.conclusion || 'No conclusion generated.'}</p>
            </section>

            <section className="detail-section">
              <div className="section-head">
                <MicroLabel>Body</MicroLabel>
                <span className="section-index">03</span>
              </div>
              <div className="prose-shell">
                <Markdown source={draft.body_markdown} />
              </div>
            </section>

            {draft.tags.length > 0 && (
              <div className="tag-row">
                {draft.tags.map((tag) => (
                  <Tag key={tag}>{tag}</Tag>
                ))}
              </div>
            )}
          </div>

          <aside className="draft-side">
            <div className="side-panel">
              <div className="side-panel-head">
                <MicroLabel>Revision</MicroLabel>
                <Icon name="sparkles" size={13} />
              </div>
              <p className="side-muted">
                Guide the model with a revision instruction. This creates a new draft version.
              </p>
              <textarea
                className="textarea"
                value={instruction}
                onChange={(event) => setInstruction(event.target.value)}
                rows={4}
                placeholder="e.g. Tighten the conclusion and preserve the two main examples."
              />
              {revisionError && <ErrorBanner message={revisionError} />}
              <button
                type="button"
                className="button full"
                disabled={revising || !instruction.trim()}
                onClick={revise}
              >
                {revising ? 'Revising…' : 'Apply revision'}
              </button>
            </div>

            <div className="side-panel">
              <div className="side-panel-head">
                <MicroLabel>Publish</MicroLabel>
              </div>
              <p className="side-muted">
                Publishing creates a knowledge card and queues an artifact render.
              </p>
              <input
                className="input"
                value={note}
                onChange={(event) => setNote(event.target.value)}
                placeholder="Optional publish note"
              />
              {publishError && <ErrorBanner message={publishError} />}
              <button
                type="button"
                className="button primary full"
                onClick={publish}
                disabled={publishing || draft.status === 'published' || Boolean(published)}
              >
                <Icon name="arrow-up-right" size={13} />
                {publishing ? 'Publishing…' : 'Publish draft'}
              </button>
            </div>

            <div className="side-panel">
              <MicroLabel>Record</MicroLabel>
              <dl className="meta-list">
                <div>
                  <dt>draft</dt>
                  <dd title={draft.id}>{shortId(draft.id, 14)}</dd>
                </div>
                <div>
                  <dt>raw content</dt>
                  <dd title={draft.raw_content_id}>{shortId(draft.raw_content_id, 14)}</dd>
                </div>
                <div>
                  <dt>created</dt>
                  <dd>{formatDate(draft.created_at)}</dd>
                </div>
              </dl>
            </div>
          </aside>
        </div>
      </div>
    </div>
  )
}
