import { useState } from 'react'
import { useI18n } from '../../i18n'
import type { OpenView } from '../../types'
import { useAsyncData } from '../../hooks/useAsyncData'
import { ragApi, ragErrorMessage } from '../../rag/api'
import type { RagDossierDetail } from '../../rag/types'
import { Icon } from '../../components/Icon'
import { useToast } from '../../components/Toast'
import { EvidenceCapabilityChips } from '../../components/rag/EvidenceCapabilityChips'
import { RagStatusBadge } from '../../components/rag/RagStatusBadge'
import { ragStatusKey } from '../../rag/status'
import { RunTimeline } from '../../components/rag/RunTimeline'
import {
  EmptyState,
  ErrorBanner,
  MicroLabel,
  Skeleton,
  Tag,
  ViewHeader,
} from '../../components/ui'
import { formatDateTime, relativeTime } from '../../utils'

function newIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return `rag-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`
}

function stageLabelKey(stage: string): 'rag.stage.dataset' | 'rag.stage.dossierRollup' | null {
  if (stage === 'dataset') return 'rag.stage.dataset'
  if (stage === 'dossier_rollup') return 'rag.stage.dossierRollup'
  return null
}

export function RagDossierView({
  dossierId,
  openView,
}: {
  dossierId: string
  openView: OpenView
}) {
  const { t } = useI18n()
  const { notify } = useToast()
  const { data, loading, error, reload } = useAsyncData<RagDossierDetail>(
    (signal) => ragApi.dossier(dossierId, signal),
    [dossierId],
    (caught) => ragErrorMessage(caught, t),
  )
  const [starting, setStarting] = useState(false)
  const [startError, setStartError] = useState<string | null>(null)

  const startRollup = async () => {
    if (!data || starting || data.dossier.status !== 'active') return
    setStarting(true)
    setStartError(null)
    try {
      const started = await ragApi.startDossierRollup(data.dossier.id, newIdempotencyKey())
      notify(t('rag.dossier.started'), 'success')
      if (!started.worker_available) notify(t('rag.dossier.workerUnavailable'), 'info')
      reload()
      openView('rag-run', { id: started.run.id }, t('tabs.ragRun'))
    } catch (caught) {
      const message = ragErrorMessage(caught, t)
      setStartError(message)
      notify(message, 'danger')
    } finally {
      setStarting(false)
    }
  }

  if (loading && !data) {
    return (
      <div className="view-scroll">
        <div className="view-inner">
          <Skeleton lines={2} />
          <div className="rag-summary-grid">
            {Array.from({ length: 3 }, (_, index) => (
              <div key={index} className="rag-summary-card">
                <Skeleton lines={2} />
              </div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  if (error && !data) {
    return (
      <div className="view-scroll">
        <div className="view-inner">
          <ViewHeader
            eyebrow={t('rag.dossier.eyebrow')}
            title={t('rag.dossier.unavailable')}
            back={{ label: t('rag.library.back'), onClick: () => openView('rag-dossiers') }}
          />
          <ErrorBanner message={error} onRetry={reload} />
        </div>
      </div>
    )
  }

  if (!data) return null
  const { dossier, execution, worker } = data

  return (
    <div className="view-scroll">
      <div className="view-inner">
        <ViewHeader
          eyebrow={t('rag.dossier.eyebrow')}
          title={dossier.title}
          description={dossier.description || t('common.noDescription')}
          back={{ label: t('rag.library.back'), onClick: () => openView('rag-dossiers') }}
          actions={
            <>
              <button type="button" className="button ghost" onClick={reload}>
                <Icon name="refresh" size={13} /> {t('common.refresh')}
              </button>
              <button
                type="button"
                className="button primary"
                onClick={() => void startRollup()}
                disabled={starting || dossier.status !== 'active'}
              >
                <Icon name={starting ? 'refresh' : 'bolt'} size={13} />
                {starting ? t('rag.dossier.starting') : t('rag.dossier.start')}
              </button>
            </>
          }
        />

        {startError && <ErrorBanner message={startError} />}

        <div className="rag-dossier-cover">
          <div className="rag-cover-main">
            <div className="rag-cover-topline">
              <Tag tone={dossier.status === 'active' ? 'success' : 'muted'}>
                {t(dossier.status === 'active' ? 'rag.library.active' : 'rag.library.archived')}
              </Tag>
              <span className="rag-cover-id">{dossier.id}</span>
            </div>
            <div className="rag-summary-grid">
              <div className="rag-summary-card">
                <MicroLabel>{t('rag.dossier.execution')}</MicroLabel>
                <strong>{t('rag.dossier.runsCount', { count: execution.run_count })}</strong>
                <span>{t('rag.dossier.latest', { value: execution.latest_run_at ? relativeTime(execution.latest_run_at) : t('rag.common.never') })}</span>
              </div>
              <div className="rag-summary-card">
                <MicroLabel>{t('rag.dossier.activeRuns')}</MicroLabel>
                <strong>{execution.active_run_count}</strong>
                <span>{t('rag.dossier.failedRuns', { count: execution.failed_run_count })}</span>
              </div>
              <div className="rag-summary-card">
                <MicroLabel>{t('rag.dossier.worker')}</MicroLabel>
                <strong className={worker.available ? 'rag-positive' : 'rag-negative'}>
                  {t(worker.available ? 'rag.worker.available' : 'rag.worker.unavailable')}
                </strong>
                <span>
                  {worker.heartbeat_at
                    ? t('rag.worker.heartbeat', { value: relativeTime(worker.heartbeat_at) })
                    : t('rag.worker.noHeartbeat')}
                </span>
              </div>
            </div>

            <section className="rag-section">
              <div className="section-head">
                <MicroLabel>{t('rag.dossier.capabilities')}</MicroLabel>
              </div>
              <EvidenceCapabilityChips capabilities={data.evidence_capabilities} />
            </section>

            <RagStages data={data} openView={openView} />

            <RunTimeline runs={data.recent_runs} openView={openView} />

            {(data.blocking.length > 0 || data.next_actions.length > 0) && (
              <section className="rag-section rag-actions-section">
                {data.blocking.length > 0 && (
                  <div className="rag-action-column">
                    <MicroLabel>{t('rag.dossier.blocking')}</MicroLabel>
                    <div className="tag-row">
                      {data.blocking.map((item) => (
                        <Tag key={item} tone="danger">{item}</Tag>
                      ))}
                    </div>
                  </div>
                )}
                {data.next_actions.length > 0 && (
                  <div className="rag-action-column">
                    <MicroLabel>{t('rag.dossier.nextActions')}</MicroLabel>
                    <div className="tag-row">
                      {data.next_actions.map((item) => (
                        <Tag key={item} tone="muted">{item}</Tag>
                      ))}
                    </div>
                  </div>
                )}
              </section>
            )}
          </div>

          <aside className="rag-cover-side">
            <div className="panel-section">
              <MicroLabel>{t('rag.dossier.details')}</MicroLabel>
              <dl className="meta-list">
                <div>
                  <dt>{t('rag.common.created')}</dt>
                  <dd>{formatDateTime(dossier.created_at)}</dd>
                </div>
                <div>
                  <dt>{t('rag.common.updated')}</dt>
                  <dd>{formatDateTime(dossier.updated_at)}</dd>
                </div>
                <div>
                  <dt>{t('rag.dossier.lastRun')}</dt>
                  <dd>{dossier.last_run ? `${dossier.last_run.stage} · ${t(ragStatusKey(dossier.last_run.status))}` : t('rag.common.never')}</dd>
                </div>
                <div>
                  <dt>{t('rag.dossier.workerAge')}</dt>
                  <dd>{worker.age_seconds === null ? t('rag.common.na') : t('rag.dossier.secondsAgo', { count: Math.round(worker.age_seconds) })}</dd>
                </div>
              </dl>
            </div>
            <div className="panel-section">
              <MicroLabel>{t('rag.dossier.worker')}</MicroLabel>
              <dl className="meta-list">
                <div>
                  <dt>{t('rag.dossier.workerId')}</dt>
                  <dd>{worker.worker_id ?? t('rag.common.na')}</dd>
                </div>
                <div>
                  <dt>{t('rag.dossier.workerState')}</dt>
                  <dd>{worker.state ?? t('rag.common.unknown')}</dd>
                </div>
                <div>
                  <dt>{t('rag.dossier.workerJob')}</dt>
                  <dd>{worker.current_job_id ?? t('rag.common.na')}</dd>
                </div>
              </dl>
            </div>
          </aside>
        </div>

        <div className="page-footnote">
          <MicroLabel>{t('rag.dossier.noteTitle')}</MicroLabel>
          <p>{t('rag.dossier.note')}</p>
        </div>
      </div>
    </div>
  )
}

function RagStages({
  data,
  openView,
}: {
  data: RagDossierDetail
  openView: OpenView
}) {
  const { t } = useI18n()
  if (data.stages.length === 0) {
    return (
      <section className="rag-section">
        <EmptyState compact icon="layers" title={t('rag.dossier.noStages')} />
      </section>
    )
  }
  return (
    <section className="rag-section">
      <div className="section-head">
        <MicroLabel>{t('rag.dossier.stages')}</MicroLabel>
        <span className="section-index">{data.stages.length.toString().padStart(2, '0')}</span>
      </div>
      <div className="rag-stage-grid">
        {data.stages.map((stage) => {
          const labelKey = stageLabelKey(stage.stage_key)
          return (
            <div key={stage.stage_key} className="rag-stage-card">
              <div className="rag-stage-head">
                <span className="rag-stage-name">
                  {labelKey ? t(labelKey) : stage.stage_key}
                </span>
                <RagStatusBadge status={stage.status} />
              </div>
              <div className="rag-stage-meta">
                <span>{t('rag.dossier.runCount', { count: stage.run_count })}</span>
                <span>{t('rag.dossier.activeCount', { count: stage.active_run_count })}</span>
              </div>
              {stage.latest_run && (
                <button
                  type="button"
                  className="rag-stage-run"
                  onClick={() => openView('rag-run', { id: stage.latest_run!.id }, t('tabs.ragRun'))}
                >
                  {t('rag.dossier.latestRun')} {stage.latest_run.stage}
                  <Icon name="arrow-up-right" size={11} />
                </button>
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}
