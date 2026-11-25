import { useState, type FormEvent } from 'react'
import { useI18n } from '../../i18n'
import type { OpenView } from '../../types'
import { useAsyncData } from '../../hooks/useAsyncData'
import { ragApi, ragErrorMessage } from '../../rag/api'
import type { RagDossierList } from '../../rag/types'
import { Icon } from '../../components/Icon'
import { Modal } from '../../components/Modal'
import { useToast } from '../../components/Toast'
import {
  EmptyState,
  ErrorBanner,
  MicroLabel,
  Skeleton,
  ViewHeader,
} from '../../components/ui'
import { formatDate, relativeTime } from '../../utils'

export function RagDossiersView({ openView }: { openView: OpenView }) {
  const { t } = useI18n()
  const { notify } = useToast()
  const { data, loading, error, reload } = useAsyncData<RagDossierList>(
    (signal) => ragApi.dossiers(signal),
    [],
    (caught) => ragErrorMessage(caught, t),
  )
  const [createOpen, setCreateOpen] = useState(false)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  const dossiers = data?.items ?? []

  const create = async (event: FormEvent) => {
    event.preventDefault()
    if (!title.trim() || creating) return
    setCreating(true)
    setCreateError(null)
    try {
      const created = await ragApi.createDossier(title.trim(), description.trim())
      setCreateOpen(false)
      setTitle('')
      setDescription('')
      notify(t('rag.dossier.created'), 'success')
      reload()
      openView('rag-dossier', { id: created.id }, created.title)
    } catch (caught) {
      setCreateError(ragErrorMessage(caught, t))
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="view-scroll">
      <div className="view-inner">
        <ViewHeader
          eyebrow={t('rag.library.eyebrow')}
          title={t('rag.library.title')}
          description={t('rag.library.description')}
          actions={
            <>
              <button type="button" className="button ghost" onClick={reload}>
                <Icon name="refresh" size={13} /> {t('common.refresh')}
              </button>
              <button
                type="button"
                className="button primary"
                onClick={() => setCreateOpen(true)}
              >
                <Icon name="plus" size={13} /> {t('rag.library.new')}
              </button>
            </>
          }
        />

        {error && <ErrorBanner message={error} onRetry={reload} />}

        {loading && !data && (
          <div className="rag-dossier-grid">
            {Array.from({ length: 3 }, (_, index) => (
              <div key={index} className="rag-dossier-card">
                <Skeleton lines={3} />
              </div>
            ))}
          </div>
        )}

        {!loading && dossiers.length === 0 && !error && (
          <EmptyState
            icon="database"
            title={t('rag.library.empty')}
            description={t('rag.library.emptyBody')}
            action={
              <button
                type="button"
                className="button primary"
                onClick={() => setCreateOpen(true)}
              >
                <Icon name="plus" size={13} /> {t('rag.library.createAction')}
              </button>
            }
          />
        )}

        {dossiers.length > 0 && (
          <>
            <div className="rag-list-meta">
              <MicroLabel>{t('rag.library.total', { count: data?.total ?? dossiers.length })}</MicroLabel>
              <span className="rag-list-note">{t('rag.library.scope')}</span>
            </div>
            <div className="rag-dossier-grid">
              {dossiers.map((dossier) => (
                <button
                  key={dossier.id}
                  type="button"
                  className="rag-dossier-card"
                  onClick={() =>
                    openView('rag-dossier', { id: dossier.id }, dossier.title)
                  }
                >
                  <div className="rag-dossier-card-top">
                    <span className="rag-dossier-glyph">
                      <Icon name="database" size={18} />
                    </span>
                    <span className={`tag tag-${dossier.status === 'active' ? 'success' : 'muted'}`}>
                      {t(dossier.status === 'active' ? 'rag.library.active' : 'rag.library.archived')}
                    </span>
                  </div>
                  <h3>{dossier.title}</h3>
                  <p>{dossier.description || t('common.noDescription')}</p>
                  <div className="rag-dossier-stats">
                    <span>
                      <Icon name="activity" size={11} />
                      {t('rag.library.runsCount', { count: dossier.run_count })}
                    </span>
                    <span>
                      <Icon name="bolt" size={11} />
                      {t('rag.library.activeRuns', { count: dossier.active_run_count })}
                    </span>
                  </div>
                  <div className="rag-dossier-card-foot">
                    <span title={formatDate(dossier.updated_at)}>
                      {relativeTime(dossier.updated_at)}
                    </span>
                    <span className="rag-open-link">
                      {t('rag.library.open')} <Icon name="arrow-up-right" size={11} />
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </>
        )}

        <div className="page-footnote">
          <MicroLabel>{t('rag.library.noteTitle')}</MicroLabel>
          <p>{t('rag.library.note')}</p>
        </div>
      </div>

      {createOpen && (
        <Modal
          title={t('rag.library.createTitle')}
          eyebrow={t('rag.library.eyebrow')}
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
                form="create-rag-dossier-form"
                className="button primary"
                disabled={creating || !title.trim()}
              >
                {creating ? t('common.creating') : t('rag.library.createAction')}
              </button>
            </>
          }
        >
          <form id="create-rag-dossier-form" className="modal-form" onSubmit={create}>
            <div className="field">
              <label className="field-label" htmlFor="rag-dossier-title">
                {t('rag.dossier.titleField')}
              </label>
              <input
                id="rag-dossier-title"
                className="input"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder={t('rag.dossier.titlePlaceholder')}
                autoFocus
              />
            </div>
            <div className="field">
              <label className="field-label" htmlFor="rag-dossier-description">
                {t('rag.dossier.descriptionField')}
              </label>
              <textarea
                id="rag-dossier-description"
                className="textarea"
                rows={3}
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder={t('rag.dossier.descriptionPlaceholder')}
              />
            </div>
            {createError && <ErrorBanner message={createError} />}
          </form>
        </Modal>
      )}
    </div>
  )
}
