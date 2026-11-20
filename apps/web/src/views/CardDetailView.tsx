import { useState, type FormEvent } from 'react'
import { api, errorMessage } from '../api'
import { ArtifactImage } from '../components/ArtifactImage'
import { Icon } from '../components/Icon'
import { Markdown } from '../components/Markdown'
import { Modal } from '../components/Modal'
import { useToast } from '../components/Toast'
import {
  EmptyState,
  ErrorBanner,
  MicroLabel,
  Skeleton,
  Tag,
  ViewHeader,
} from '../components/ui'
import { useAsyncData } from '../hooks/useAsyncData'
import type { Asset, DossierSummary, Draft, OpenView, RawContent } from '../types'
import { cx, formatDate, shortId } from '../utils'

type AssetDetail = Asset & { raw_content?: RawContent; draft?: Draft }

export function CardDetailView({
  assetId,
  openView,
}: {
  assetId: string
  openView: OpenView
}) {
  const { notify } = useToast()
  const { data: asset, loading, error, reload, setData } = useAsyncData<AssetDetail>(
    (signal) => api.asset(assetId, signal),
    [assetId],
  )
  const { data: dossiers } = useAsyncData<DossierSummary[]>(
    (signal) => api.dossiers(signal),
    [],
  )

  const [editOpen, setEditOpen] = useState(false)
  const [moveOpen, setMoveOpen] = useState(false)
  const [category, setCategory] = useState('')
  const [tags, setTags] = useState('')
  const [selectedDossier, setSelectedDossier] = useState('')
  const [saving, setSaving] = useState(false)
  const [moving, setMoving] = useState(false)
  const [modalError, setModalError] = useState<string | null>(null)
  const [actionBusy, setActionBusy] = useState<'archive' | 'artifact' | null>(null)

  const openEdit = () => {
    if (!asset) return
    setCategory(asset.category ?? '')
    setTags((asset.tags ?? []).join(', '))
    setModalError(null)
    setEditOpen(true)
  }

  const openMove = () => {
    if (!asset) return
    setSelectedDossier(asset.dossier_ids?.[0] ?? '')
    setModalError(null)
    setMoveOpen(true)
  }

  const saveEdit = async (event: FormEvent) => {
    event.preventDefault()
    if (!asset) return
    setSaving(true)
    setModalError(null)
    try {
      const updated = await api.patchAsset(asset.id, {
        category: category.trim(),
        tags: tags
          .split(',')
          .map((tag) => tag.trim())
          .filter(Boolean),
      })
      setData((previous) => (previous ? { ...previous, ...updated } : updated))
      setEditOpen(false)
      notify('Card metadata updated.', 'success')
    } catch (caught) {
      setModalError(errorMessage(caught))
    } finally {
      setSaving(false)
    }
  }

  const moveCard = async () => {
    if (!asset) return
    setMoving(true)
    setModalError(null)
    try {
      const updated = await api.patchAsset(asset.id, {
        dossier_id: selectedDossier || null,
      })
      setData((previous) => (previous ? { ...previous, ...updated } : updated))
      setMoveOpen(false)
      notify(selectedDossier ? 'Card moved to dossier.' : 'Card removed from dossiers.', 'success')
    } catch (caught) {
      setModalError(errorMessage(caught))
    } finally {
      setMoving(false)
    }
  }

  const toggleArchive = async () => {
    if (!asset) return
    setActionBusy('archive')
    try {
      const updated = await api.patchAsset(asset.id, { archived: !asset.archived })
      setData((previous) => (previous ? { ...previous, ...updated } : updated))
      notify(updated.archived ? 'Card archived.' : 'Card restored.', 'success')
    } catch (caught) {
      notify(errorMessage(caught), 'danger')
    } finally {
      setActionBusy(null)
    }
  }

  const regenerate = async () => {
    if (!asset?.artifact) return
    setActionBusy('artifact')
    try {
      await api.regenerateArtifact(asset.artifact.id)
      reload()
      notify('Artifact regeneration started.', 'success')
    } catch (caught) {
      notify(errorMessage(caught), 'danger')
    } finally {
      setActionBusy(null)
    }
  }

  if (loading && !asset) {
    return (
      <div className="view-scroll">
        <div className="view-inner">
          <Skeleton lines={2} />
          <div className="skeleton skeleton-hero" />
          <div className="detail-columns">
            <Skeleton lines={8} />
            <Skeleton lines={6} />
          </div>
        </div>
      </div>
    )
  }

  if (error && !asset) {
    return (
      <div className="view-scroll">
        <div className="view-inner">
          <ViewHeader
            eyebrow="Wiki / Cards / Detail"
            title="Card unavailable"
            back={{ label: 'Cards', onClick: () => openView('cards') }}
          />
          <ErrorBanner message={error} onRetry={reload} />
        </div>
      </div>
    )
  }

  if (!asset) return null

  const model = asset.model ?? asset.draft?.model ?? '—'
  const linkedDossiers = (dossiers ?? []).filter((dossier) =>
    (asset.dossier_ids ?? []).includes(dossier.id),
  )

  return (
    <div className="view-scroll">
      <div className="view-inner">
        <ViewHeader
          eyebrow="Wiki / Cards / Detail"
          title={asset.title}
          description={asset.summary || 'Published knowledge asset'}
          back={{ label: 'Card library', onClick: () => openView('cards') }}
          actions={
            <>
              <button type="button" className="button ghost" onClick={openEdit}>
                <Icon name="edit" size={13} /> Edit
              </button>
              <button type="button" className="button ghost" onClick={openMove}>
                <Icon name="folder" size={13} /> Move
              </button>
              <button
                type="button"
                className={cx('button', 'ghost', asset.archived && 'button-warning')}
                onClick={toggleArchive}
                disabled={actionBusy === 'archive'}
              >
                <Icon name="archive" size={13} />
                {asset.archived ? 'Restore' : 'Archive'}
              </button>
            </>
          }
        />

        {error && <ErrorBanner message={error} onRetry={reload} />}

        {asset.is_mock === true && (
          <div className="provenance-banner provenance-mock">
            <strong>MOCK · 规则模拟 · 未调用真实 LLM</strong>
            <span>
              本知识卡片由本地规则引擎生成，不代表真实 AI 语义分析结果。 · provider {asset.provider ?? 'unknown'} · model {model} · prompt {asset.prompt_version ?? 'unknown'}
            </span>
          </div>
        )}
        {asset.is_mock === null && (
          <div className="provenance-banner provenance-unknown">
            <strong>UNKNOWN · 历史来源未知</strong>
            <span>
              该记录缺少可验证的 Provider 信息，不能视为真实 LLM 分析。 · provider {asset.provider ?? 'unknown'} · model {model}
            </span>
          </div>
        )}
        {asset.is_mock === false && (
          <div className="provenance-banner provenance-real">
            <strong>REAL PROVIDER · {asset.provider ?? 'unknown'}</strong>
            <span>model {model} · prompt {asset.prompt_version ?? 'unknown'} · mode {asset.processing_mode ?? 'unknown'}</span>
          </div>
        )}

        <div className="card-detail">
          <div className="card-detail-main">
            <section className="detail-artifact">
              <div className="artifact-toolbar">
                <div className="artifact-toolbar-left">
                  <MicroLabel>Artifact</MicroLabel>
                  <span className="artifact-status">
                    <span className={cx('api-dot', asset.artifact ? 'api-dot-online' : 'api-dot-offline')} />
                    {asset.artifact?.status ?? 'not generated'}
                  </span>
                </div>
                <div className="artifact-toolbar-right">
                  {asset.artifact && (
                    <span className="artifact-dims">
                      {asset.artifact.width} × {asset.artifact.height}
                    </span>
                  )}
                  {asset.artifact && (
                    <button
                      type="button"
                      className="icon-button"
                      onClick={regenerate}
                      disabled={actionBusy === 'artifact'}
                      title="Regenerate artifact"
                      aria-label="Regenerate artifact"
                    >
                      <Icon name="refresh" size={12} />
                    </button>
                  )}
                </div>
              </div>
              <div className="card-artifact-large">
                <ArtifactImage asset={asset} />
              </div>
            </section>

            <section className="detail-section">
              <div className="section-head">
                <MicroLabel>Summary</MicroLabel>
                <span className="section-index">01</span>
              </div>
              <p className="detail-lead">{asset.summary || 'No summary recorded for this card.'}</p>
            </section>

            {asset.conclusion && (
              <section className="detail-section conclusion-block">
                <div className="section-head">
                  <MicroLabel>Conclusion</MicroLabel>
                  <span className="section-index">02</span>
                </div>
                <p>{asset.conclusion}</p>
              </section>
            )}

            <section className="detail-section">
              <div className="section-head">
                <MicroLabel>Body</MicroLabel>
                <span className="section-index">03</span>
              </div>
              <div className="prose-shell">
                <Markdown source={asset.body_markdown} />
              </div>
            </section>

            {asset.tags.length > 0 && (
              <section className="detail-section">
                <div className="section-head">
                  <MicroLabel>Tags</MicroLabel>
                </div>
                <div className="tag-row">
                  {asset.tags.map((tag) => (
                    <Tag key={tag}>{tag}</Tag>
                  ))}
                </div>
              </section>
            )}
          </div>

          <aside className="card-detail-side">
            <div className="side-panel">
              <div className="side-panel-head">
                <MicroLabel>Asset record</MicroLabel>
                {asset.archived ? <Tag tone="muted">archived</Tag> : <Tag tone="success">active</Tag>}
              </div>
              <dl className="meta-list">
                <div>
                  <dt>asset</dt>
                  <dd title={asset.id}>{shortId(asset.id, 14)}</dd>
                </div>
                <div>
                  <dt>draft</dt>
                  <dd title={asset.draft_id}>{shortId(asset.draft_id, 14)}</dd>
                </div>
                <div>
                  <dt>raw content</dt>
                  <dd title={asset.raw_content_id}>{shortId(asset.raw_content_id, 14)}</dd>
                </div>
                <div>
                  <dt>category</dt>
                  <dd>
                    <Tag tone="accent">{asset.category || 'uncategorized'}</Tag>
                  </dd>
                </div>
                <div>
                  <dt>provider</dt>
                  <dd>{asset.provider ?? asset.draft?.provider ?? 'unknown'}</dd>
                </div>
                <div>
                  <dt>model</dt>
                  <dd>{model}</dd>
                </div>
                <div>
                  <dt>prompt</dt>
                  <dd>{asset.prompt_version ?? asset.draft?.prompt_version ?? 'unknown'}</dd>
                </div>
                <div>
                  <dt>mode</dt>
                  <dd>{asset.processing_mode ?? asset.draft?.processing_mode ?? 'unknown'}</dd>
                </div>
                <div>
                  <dt>source</dt>
                  <dd>
                    <Tag tone={asset.is_mock ? 'accent' : 'muted'}>
                      {asset.is_mock === true ? 'MOCK' : asset.is_mock === false ? 'REAL' : 'UNKNOWN'}
                    </Tag>
                  </dd>
                </div>
                <div>
                  <dt>version</dt>
                  <dd>v{asset.version}</dd>
                </div>
                <div>
                  <dt>status</dt>
                  <dd>{asset.status}</dd>
                </div>
                <div>
                  <dt>published</dt>
                  <dd>{formatDate(asset.published_at)}</dd>
                </div>
              </dl>
            </div>

            <div className="side-panel">
              <div className="side-panel-head">
                <MicroLabel>Dossiers</MicroLabel>
                <span className="side-count">{String(linkedDossiers.length).padStart(2, '0')}</span>
              </div>
              {linkedDossiers.length === 0 ? (
                <p className="side-muted">This card is not filed in a dossier.</p>
              ) : (
                <div className="side-links">
                  {linkedDossiers.map((dossier) => (
                    <button
                      key={dossier.id}
                      type="button"
                      className="side-link"
                      onClick={() =>
                        openView('dossier', { id: dossier.id }, dossier.name)
                      }
                    >
                      <Icon name="folder" size={12} />
                      <span>{dossier.name}</span>
                      <Icon name="chevron-right" size={11} />
                    </button>
                  ))}
                </div>
              )}
              <button type="button" className="button ghost full small" onClick={openMove}>
                <Icon name="folder" size={12} /> Manage dossier
              </button>
            </div>

            <div className="side-panel side-panel-actions">
              <MicroLabel>Actions</MicroLabel>
              <button type="button" className="button ghost full" onClick={openEdit}>
                <Icon name="edit" size={13} /> Edit metadata
              </button>
              <button type="button" className="button ghost full" onClick={toggleArchive}>
                <Icon name="archive" size={13} /> {asset.archived ? 'Restore card' : 'Archive card'}
              </button>
            </div>
          </aside>
        </div>
      </div>

      {editOpen && (
        <Modal
          title="Edit card metadata"
          eyebrow="Asset / Metadata"
          onClose={() => setEditOpen(false)}
          footer={
            <>
              <button type="button" className="button ghost" onClick={() => setEditOpen(false)}>
                Cancel
              </button>
              <button type="submit" form="edit-card-form" className="button primary" disabled={saving}>
                {saving ? 'Saving…' : 'Save changes'}
              </button>
            </>
          }
        >
          <form id="edit-card-form" className="modal-form" onSubmit={saveEdit}>
            <div className="field">
              <label className="field-label" htmlFor="edit-category">
                Category
              </label>
              <input
                id="edit-category"
                className="input"
                value={category}
                onChange={(event) => setCategory(event.target.value)}
                placeholder="uncategorized"
                autoFocus
              />
            </div>
            <div className="field">
              <label className="field-label" htmlFor="edit-tags">
                Tags
              </label>
              <input
                id="edit-tags"
                className="input"
                value={tags}
                onChange={(event) => setTags(event.target.value)}
                placeholder="systems, note, research"
              />
              <span className="field-hint">Comma-separated. Empty values are discarded.</span>
            </div>
            {modalError && <ErrorBanner message={modalError} />}
          </form>
        </Modal>
      )}

      {moveOpen && (
        <Modal
          title="Move card"
          eyebrow="Asset / Dossier"
          onClose={() => setMoveOpen(false)}
          footer={
            <>
              <button type="button" className="button ghost" onClick={() => setMoveOpen(false)}>
                Cancel
              </button>
              <button
                type="button"
                className="button primary"
                onClick={moveCard}
                disabled={moving}
              >
                {moving ? 'Moving…' : 'Apply move'}
              </button>
            </>
          }
        >
          <p className="modal-copy">
            Filing a card updates its dossier assignment. Existing dossier visualizations will
            refresh when reopened.
          </p>
          {(dossiers ?? []).length === 0 ? (
            <EmptyState
              icon="folder"
              title="No dossiers"
              description="Create a dossier first, then return to file this card."
              compact
              action={
                <button
                  type="button"
                  className="button small"
                  onClick={() => {
                    setMoveOpen(false)
                    openView('dossiers')
                  }}
                >
                  Open dossiers
                </button>
              }
            />
          ) : (
            <div className="option-list" role="radiogroup" aria-label="Destination dossier">
              {(dossiers ?? []).map((dossier) => (
                <label
                  key={dossier.id}
                  className={cx(
                    'option-row',
                    selectedDossier === dossier.id && 'option-row-selected',
                  )}
                >
                  <input
                    type="radio"
                    name="dossier"
                    value={dossier.id}
                    checked={selectedDossier === dossier.id}
                    onChange={() => setSelectedDossier(dossier.id)}
                  />
                  <span className="option-icon">
                    <Icon name="folder" size={14} />
                  </span>
                  <span className="option-copy">
                    <strong>{dossier.name}</strong>
                    <span>{dossier.description || `${dossier.card_count} cards`}</span>
                  </span>
                </label>
              ))}
              <label
                className={cx('option-row', selectedDossier === '' && 'option-row-selected')}
              >
                <input
                  type="radio"
                  name="dossier"
                  value=""
                  checked={selectedDossier === ''}
                  onChange={() => setSelectedDossier('')}
                />
                <span className="option-icon">
                  <Icon name="x" size={14} />
                </span>
                <span className="option-copy">
                  <strong>Unfile card</strong>
                  <span>Remove this card from all dossier assignments.</span>
                </span>
              </label>
            </div>
          )}
          {modalError && <ErrorBanner message={modalError} />}
        </Modal>
      )}
    </div>
  )
}
