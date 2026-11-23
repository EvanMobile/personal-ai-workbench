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
import { useI18n } from '../i18n'

export function DraftView({
  draftId,
  openView,
}: {
  draftId: string
  openView: OpenView
}) {
  const { notify } = useToast()
  const { t } = useI18n()
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
      notify(t('draft.toastRevised', { version: response.draft.version }), 'success')
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
      notify(t('draft.toastPublished'), 'success')
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
            eyebrow={t('draft.eyebrow')}
            title={t('draft.unavailable')}
            back={{ label: t('draft.capture'), onClick: () => openView('capture') }}
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
          eyebrow={t('draft.eyebrow')}
          title={draft.title}
          description={draft.summary || t('draft.awaiting')}
          back={{ label: t('draft.capture'), onClick: () => openView('capture') }}
          actions={
            <>
              <Tag tone={draft.status === 'published' ? 'success' : 'accent'}>{draft.status === 'published' ? t('common.published') : t('common.draft')}</Tag>
              <button type="button" className="button ghost" onClick={reload}>
                <Icon name="refresh" size={13} /> {t('draft.reload')}
              </button>
            </>
          }
        />

        {error && <ErrorBanner message={error} onRetry={reload} />}

        {draft.is_mock === true && (
          <div className="provenance-banner provenance-mock">
            <strong>{t('draft.mockTitle')}</strong>
            <span>{t('common.provider')} {draft.provider} · {t('common.model')} {draft.model} · {t('common.prompt')} {draft.prompt_version} · {t('common.mode')} {draft.processing_mode}</span>
          </div>
        )}
        {draft.is_mock === null && (
          <div className="provenance-banner provenance-unknown">
            <strong>{t('draft.unknownTitle')}</strong>
            <span>{t('common.provider')} {draft.provider} · {t('common.model')} {draft.model} · {t('common.prompt')} {draft.prompt_version} · {t('draft.unknownBody')}</span>
          </div>
        )}
        {draft.is_mock === false && (
          <div className="provenance-banner provenance-real">
            <strong>{t('card.realProvider')} · {draft.provider}</strong>
            <span>{t('common.model')} {draft.model} · {t('common.prompt')} {draft.prompt_version} · {t('common.mode')} {draft.processing_mode}</span>
          </div>
        )}

        <div className="meta-strip">
          <div>
            <span>{t('common.provider')}</span>
            <strong>{draft.provider || t('common.unknown')}</strong>
          </div>
          <div>
            <span>{t('common.mode')}</span>
            <strong>{draft.processing_mode || t('common.unknown')}</strong>
          </div>
          <div>
            <span>{t('common.model')}</span>
            <strong>{draft.model}</strong>
          </div>
          <div>
            <span>{t('common.prompt')}</span>
            <strong>{draft.prompt_version}</strong>
          </div>
          <div>
            <span>{t('common.version')}</span>
            <strong>v{draft.version}</strong>
          </div>
          <div>
            <span>{t('common.category')}</span>
            <strong>{draft.category || '—'}</strong>
          </div>
          <div>
            <span>{t('common.updated')}</span>
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
                <strong>{t('draft.publishedAsCard')}</strong>
              </div>
              <p>
                {published.asset.title} · {published.artifact ? t('draft.artifactGenerated') : t('draft.noArtifact')}
              </p>
              <button
                type="button"
                className="button small primary"
                onClick={() =>
                  openView('card', { id: published.asset.id }, published.asset.title)
                }
              >
                {t('draft.openCard')} <Icon name="arrow-up-right" size={11} />
              </button>
            </div>
          </div>
        )}

        <div className="draft-layout">
          <div className="draft-main">
            <section className="detail-section">
              <div className="section-head">
                <MicroLabel>{t('draft.summary')}</MicroLabel>
                <span className="section-index">01</span>
              </div>
              <p className="detail-lead">{draft.summary || t('draft.noSummary')}</p>
            </section>

            <section className="detail-section">
              <div className="section-head">
                <MicroLabel>{t('draft.conclusion')}</MicroLabel>
                <span className="section-index">02</span>
              </div>
              <p>{draft.conclusion || t('draft.noConclusion')}</p>
            </section>

            <section className="detail-section">
              <div className="section-head">
                <MicroLabel>{t('draft.body')}</MicroLabel>
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
                <MicroLabel>{t('draft.revision')}</MicroLabel>
                <Icon name="sparkles" size={13} />
              </div>
              <p className="side-muted">{t('draft.revisionHint')}</p>
              <textarea
                className="textarea"
                value={instruction}
                onChange={(event) => setInstruction(event.target.value)}
                rows={4}
                placeholder={t('draft.revisionPlaceholder')}
              />
              {revisionError && <ErrorBanner message={revisionError} />}
              <button
                type="button"
                className="button full"
                disabled={revising || !instruction.trim()}
                onClick={revise}
              >
                {revising ? t('common.revising') : t('draft.applyRevision')}
              </button>
            </div>

            <div className="side-panel">
              <div className="side-panel-head">
                <MicroLabel>{t('draft.publish')}</MicroLabel>
              </div>
              <p className="side-muted">{t('draft.publishHint')}</p>
              <input
                className="input"
                value={note}
                onChange={(event) => setNote(event.target.value)}
                placeholder={t('draft.publishNote')}
              />
              {publishError && <ErrorBanner message={publishError} />}
              <button
                type="button"
                className="button primary full"
                onClick={publish}
                disabled={publishing || draft.status === 'published' || Boolean(published)}
              >
                <Icon name="arrow-up-right" size={13} />
                {publishing ? t('common.publishing') : t('draft.publishDraft')}
              </button>
            </div>

            <div className="side-panel">
              <MicroLabel>{t('common.record')}</MicroLabel>
              <dl className="meta-list">
                <div>
                  <dt>{t('common.draft')}</dt>
                  <dd title={draft.id}>{shortId(draft.id, 14)}</dd>
                </div>
                <div>
                  <dt>{t('common.rawContent')}</dt>
                  <dd title={draft.raw_content_id}>{shortId(draft.raw_content_id, 14)}</dd>
                </div>
                <div>
                  <dt>{t('common.created')}</dt>
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
