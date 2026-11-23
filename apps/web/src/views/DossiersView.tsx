import { useState, type FormEvent } from 'react'
import { api, errorMessage } from '../api'
import { Icon } from '../components/Icon'
import { Modal } from '../components/Modal'
import { useToast } from '../components/Toast'
import {
  EmptyState,
  ErrorBanner,
  MicroLabel,
  Skeleton,
  ViewHeader,
} from '../components/ui'
import { useAsyncData } from '../hooks/useAsyncData'
import type { DossierSummary, OpenView } from '../types'
import { formatDate, relativeTime } from '../utils'
import { useI18n } from '../i18n'

export function DossiersView({ openView }: { openView: OpenView }) {
  const { notify } = useToast()
  const { t } = useI18n()
  const { data, loading, error, reload } = useAsyncData<DossierSummary[]>(
    (signal) => api.dossiers(signal),
    [],
  )
  const [createOpen, setCreateOpen] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  const dossiers = data ?? []

  const create = async (event: FormEvent) => {
    event.preventDefault()
    if (!name.trim()) return
    setCreating(true)
    setCreateError(null)
    try {
      const dossier = await api.createDossier(name.trim(), description.trim() || undefined)
      setCreateOpen(false)
      setName('')
      setDescription('')
      reload()
      notify(t('dossiers.toastCreated'), 'success')
      openView('dossier', { id: dossier.id }, dossier.name)
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
          eyebrow={t('dossiers.eyebrow')}
          title={t('dossiers.title')}
          description={t('dossiers.description')}
          actions={
            <>
              <button type="button" className="button ghost" onClick={reload}>
                <Icon name="refresh" size={13} /> {t('common.refresh')}
              </button>
              <button type="button" className="button primary" onClick={() => setCreateOpen(true)}>
                <Icon name="plus" size={13} /> {t('dossiers.new')}
              </button>
            </>
          }
        />

        {error && <ErrorBanner message={error} onRetry={reload} />}

        {loading && !data && (
          <div className="dossier-grid">
            {Array.from({ length: 4 }, (_, index) => (
              <div key={index} className="dossier-tile">
                <Skeleton lines={4} />
              </div>
            ))}
          </div>
        )}

        {!loading && dossiers.length === 0 && (
          <EmptyState
            icon="folder"
            title={t('dossiers.empty')}
            description={t('dossiers.emptyBody')}
            action={
              <button type="button" className="button primary" onClick={() => setCreateOpen(true)}>
                <Icon name="plus" size={13} /> {t('dossiers.create')}
              </button>
            }
          />
        )}

        {dossiers.length > 0 && (
          <div className="dossier-grid">
            {dossiers.map((dossier, index) => (
              <button
                key={dossier.id}
                type="button"
                className="dossier-tile"
                onClick={() => openView('dossier', { id: dossier.id }, dossier.name)}
              >
                <div className="dossier-tile-top">
                  <span className="dossier-glyph">
                    <Icon name="folder" size={18} />
                  </span>
                  <span className="dossier-index">
                    {String(index + 1).padStart(2, '0')}
                  </span>
                </div>
                <h3>{dossier.name}</h3>
                <p>{dossier.description || t('common.noDescription')}</p>
                <div className="dossier-tile-foot">
                  <span>
                    <Icon name="layers" size={11} />
                    {t('dossiers.cardsCount', { count: dossier.card_count })}
                  </span>
                  <span title={formatDate(dossier.updated_at)}>
                    {relativeTime(dossier.updated_at)}
                  </span>
                </div>
                <div className="dossier-tile-bar">
                  <span style={{ width: `${Math.min(100, dossier.card_count * 9 + 8)}%` }} />
                </div>
                <span className="dossier-open">
                  {t('dossiers.openGraph')} <Icon name="arrow-up-right" size={11} />
                </span>
              </button>
            ))}
          </div>
        )}

        <div className="page-footnote">
          <MicroLabel>{t('dossiers.noteTitle')}</MicroLabel>
          <p>{t('dossiers.note')}</p>
        </div>
      </div>

      {createOpen && (
        <Modal
          title={t('dossiers.new')}
          eyebrow={t('dossiers.eyebrow')}
          onClose={() => {
            setCreateOpen(false)
            setCreateError(null)
          }}
          footer={
            <>
              <button
                type="button"
                className="button ghost"
                onClick={() => setCreateOpen(false)}
              >
                {t('common.cancel')}
              </button>
              <button
                type="submit"
                form="create-dossier-form"
                className="button primary"
                disabled={creating || !name.trim()}
              >
                {creating ? t('common.creating') : t('dossiers.create')}
              </button>
            </>
          }
        >
          <form id="create-dossier-form" className="modal-form" onSubmit={create}>
            <div className="field">
              <label className="field-label" htmlFor="dossier-name">
                {t('dossiers.name')}
              </label>
              <input
                id="dossier-name"
                className="input"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder={t('dossiers.namePlaceholder')}
                autoFocus
              />
            </div>
            <div className="field">
              <label className="field-label" htmlFor="dossier-description">
                {t('dossiers.descriptionField')}
              </label>
              <textarea
                id="dossier-description"
                className="textarea"
                rows={3}
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder={t('dossiers.descriptionPlaceholder')}
              />
            </div>
            {createError && <ErrorBanner message={createError} />}
          </form>
        </Modal>
      )}
    </div>
  )
}
