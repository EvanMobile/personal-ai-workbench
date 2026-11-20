import { useState, type FormEvent } from 'react'
import { api, errorMessage } from '../api'
import { ArtifactImage } from '../components/ArtifactImage'
import { Icon } from '../components/Icon'
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
import type { Asset, DossierSummary, OpenView, PageSummary } from '../types'
import { formatDate, relativeTime } from '../utils'

interface PagesData {
  pages: PageSummary[]
  assets: Asset[]
  dossiers: DossierSummary[]
}

export function PagesView({ openView }: { openView: OpenView }) {
  const { notify } = useToast()
  const { data, loading, error, reload } = useAsyncData<PagesData>(async (signal) => {
    const [pages, assets, dossiers] = await Promise.all([
      api.pages(signal),
      api.assets(signal),
      api.dossiers(signal),
    ])
    return { pages, assets, dossiers }
  }, [])
  const [createOpen, setCreateOpen] = useState(false)
  const [dossierId, setDossierId] = useState('')
  const [title, setTitle] = useState('')
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  const pages = [...(data?.pages ?? [])].sort(
    (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
  )
  const assets = data?.assets ?? []
  const dossiers = data?.dossiers ?? []

  const openCreate = () => {
    setDossierId(dossiers[0]?.id ?? '')
    setTitle('')
    setCreateError(null)
    setCreateOpen(true)
  }

  const create = async (event: FormEvent) => {
    event.preventDefault()
    if (!dossierId) return
    setCreating(true)
    setCreateError(null)
    try {
      const created = await api.createPage(dossierId, title.trim() || undefined)
      setCreateOpen(false)
      notify('Page created.', 'success')
      reload()
      openView('page', { id: created.page.id }, created.page.title)
    } catch (caught) {
      setCreateError(errorMessage(caught))
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="view-scroll">
      <div className="view-inner">
        <ViewHeader
          eyebrow="Wiki / Pages"
          title="Page archive"
          description="Composed, versioned snapshots of a dossier — built to be read, not edited in place."
          actions={
            <>
              <button type="button" className="button ghost" onClick={reload}>
                <Icon name="refresh" size={13} /> Refresh
              </button>
              <button
                type="button"
                className="button primary"
                onClick={openCreate}
                disabled={dossiers.length === 0}
                title={dossiers.length === 0 ? 'Create a dossier first' : 'Create a page'}
              >
                <Icon name="plus" size={13} /> New page
              </button>
            </>
          }
        />

        {error && <ErrorBanner message={error} onRetry={reload} />}

        {loading && !data && (
          <div className="page-grid">
            {Array.from({ length: 4 }, (_, index) => (
              <div className="page-tile" key={index}>
                <div className="skeleton skeleton-image" />
                <Skeleton lines={3} />
              </div>
            ))}
          </div>
        )}

        {!loading && pages.length === 0 && (
          <EmptyState
            icon="page"
            title="No pages composed"
            description={
              dossiers.length === 0
                ? 'Create a dossier and add cards. Pages are composed from a dossier graph.'
                : 'Open a dossier and create a page from its cards.'
            }
            action={
              dossiers.length === 0 ? (
                <button type="button" className="button primary" onClick={() => openView('dossiers')}>
                  <Icon name="folder" size={13} /> Open dossiers
                </button>
              ) : (
                <button type="button" className="button primary" onClick={openCreate}>
                  <Icon name="plus" size={13} /> Compose page
                </button>
              )
            }
          />
        )}

        {pages.length > 0 && (
          <div className="page-grid">
            {pages.map((page, index) => {
              const cover = assets.find((asset) => asset.id === page.cover_asset_id) ?? null
              return (
                <button
                  key={page.id}
                  type="button"
                  className="page-tile"
                  onClick={() => openView('page', { id: page.id }, page.title)}
                >
                  <div className="page-cover">
                    {cover ? (
                      <ArtifactImage asset={cover} />
                    ) : (
                      <div className="page-cover-placeholder">
                        <span className="page-cover-glyph">
                          <Icon name="page" size={22} />
                        </span>
                        <span>no cover artifact</span>
                      </div>
                    )}
                    <span className="page-number">P.{String(index + 1).padStart(2, '0')}</span>
                  </div>
                  <div className="page-tile-body">
                    <div className="page-tile-top">
                      <Tag>v{page.version}</Tag>
                      <span>{relativeTime(page.updated_at)}</span>
                    </div>
                    <h3>{page.title}</h3>
                    <div className="page-tile-foot">
                      <span>
                        <Icon name="folder" size={11} />
                        dossier {page.dossier_id.slice(0, 8)}
                      </span>
                      <span>{formatDate(page.updated_at)}</span>
                    </div>
                  </div>
                </button>
              )
            })}
          </div>
        )}

        <div className="page-footnote">
          <MicroLabel>Archive</MicroLabel>
          <p>
            Pages preserve their source card IDs and content snapshot. Use the dossier graph to
            compose a new version.
          </p>
        </div>
      </div>

      {createOpen && (
        <Modal
          title="Compose a page"
          eyebrow="Wiki / Pages"
          onClose={() => setCreateOpen(false)}
          footer={
            <>
              <button type="button" className="button ghost" onClick={() => setCreateOpen(false)}>
                Cancel
              </button>
              <button
                type="submit"
                form="create-page-form"
                className="button primary"
                disabled={creating || !dossierId}
              >
                {creating ? 'Composing…' : 'Create page'}
              </button>
            </>
          }
        >
          <form id="create-page-form" className="modal-form" onSubmit={create}>
            <div className="field">
              <label className="field-label" htmlFor="page-dossier">
                Source dossier
              </label>
              <select
                id="page-dossier"
                className="select"
                value={dossierId}
                onChange={(event) => setDossierId(event.target.value)}
                autoFocus
              >
                {dossiers.map((dossier) => (
                  <option key={dossier.id} value={dossier.id}>
                    {dossier.name} · {dossier.card_count} cards
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label className="field-label" htmlFor="page-title">
                Title <span className="field-optional">optional</span>
              </label>
              <input
                id="page-title"
                className="input"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="Model composes a title when empty"
              />
            </div>
            {createError && <ErrorBanner message={createError} />}
          </form>
        </Modal>
      )}
    </div>
  )
}
