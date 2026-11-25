import { useI18n } from '../../i18n'
import type { OpenView } from '../../types'
import { useRunPolling } from '../../rag/useRunPolling'
import { RagStatusBadge } from '../../components/rag/RagStatusBadge'
import { ragStatusKey } from '../../rag/status'
import { EvidenceCapabilityChips } from '../../components/rag/EvidenceCapabilityChips'
import { EvidenceStatePanel } from '../../components/rag/EvidenceStatePanel'
import { Icon } from '../../components/Icon'
import {
  EmptyState,
  ErrorBanner,
  MicroLabel,
  Skeleton,
  Tag,
  ViewHeader,
} from '../../components/ui'
import { formatDateTime, relativeTime, shortId } from '../../utils'
import type { RagAttempt, RagEvent, RagJob, RagStep } from '../../rag/types'

export function RagRunView({ runId, openView }: { runId: string; openView: OpenView }) {
  const { t } = useI18n()
  const { data, events, loading, error, polling, reload } = useRunPolling(runId)

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
            eyebrow={t('rag.run.eyebrow')}
            title={t('rag.run.unavailable')}
            back={{ label: t('rag.library.back'), onClick: () => openView('rag-dossiers') }}
          />
          <ErrorBanner message={error} onRetry={reload} />
        </div>
      </div>
    )
  }

  if (!data) return null
  const { run } = data

  return (
    <div className="view-scroll">
      <div className="view-inner">
        <ViewHeader
          eyebrow={t('rag.run.eyebrow')}
          title={`${t('rag.run.title')} · ${shortId(run.id, 10)}`}
          description={`${run.stage} · ${run.pipeline}`}
          back={{
            label: t('rag.run.backToDossier'),
            onClick: () => openView('rag-dossier', { id: run.scope_id }, t('tabs.ragDossier')),
          }}
          actions={
            <>
              <button type="button" className="button ghost" onClick={reload}>
                <Icon name="refresh" size={13} /> {t('common.refresh')}
              </button>
              <RagStatusBadge status={run.status} />
            </>
          }
        />

        {error && <ErrorBanner message={error} onRetry={reload} />}

        <div className="rag-summary-grid">
          <div className="rag-summary-card">
            <MicroLabel>{t('rag.run.status')}</MicroLabel>
            <strong>{t(ragStatusKey(run.status))}</strong>
            <span>
              {polling ? t('rag.run.polling') : t('rag.run.pollingStopped')}
            </span>
          </div>
          <div className="rag-summary-card">
            <MicroLabel>{t('rag.run.created')}</MicroLabel>
            <strong>{formatDateTime(run.created_at)}</strong>
            <span>{relativeTime(run.created_at)}</span>
          </div>
          <div className="rag-summary-card">
            <MicroLabel>{t('rag.run.updated')}</MicroLabel>
            <strong>{formatDateTime(run.updated_at)}</strong>
            <span>{relativeTime(run.updated_at)}</span>
          </div>
        </div>

        <section className="rag-section">
          <div className="section-head">
            <MicroLabel>{t('rag.dossier.capabilities')}</MicroLabel>
          </div>
          <EvidenceCapabilityChips capabilities={data.evidence_capabilities} />
        </section>

        <EvidenceStatePanel state={data.evidence_state} />

        <section className="rag-section">
          <div className="section-head">
            <MicroLabel>{t('rag.run.result')}</MicroLabel>
          </div>
          {data.result ? (
            <pre className="rag-code-block">{JSON.stringify(data.result, null, 2)}</pre>
          ) : (
            <p className="rag-section-note">{t('rag.run.noResult')}</p>
          )}
          {data.error_detail && (
            <div className="rag-error-detail">
              <MicroLabel>{t('rag.run.errorDetail')}</MicroLabel>
              <p>{data.error_detail}</p>
            </div>
          )}
          <dl className="meta-list rag-run-meta">
            <div>
              <dt>{t('rag.run.configHash')}</dt>
              <dd>{shortId(data.config_hash, 16)}</dd>
            </div>
            <div>
              <dt>{t('rag.run.fingerprint')}</dt>
              <dd>{shortId(data.fingerprint, 16)}</dd>
            </div>
            <div>
              <dt>{t('rag.run.parent')}</dt>
              <dd>{data.parent_run_id ? shortId(data.parent_run_id, 16) : t('rag.common.na')}</dd>
            </div>
          </dl>
        </section>

        <section className="rag-section">
          <div className="section-head">
            <MicroLabel>{t('rag.run.steps')}</MicroLabel>
            <span className="section-index">{data.steps.length.toString().padStart(2, '0')}</span>
          </div>
          {data.steps.length === 0 ? (
            <EmptyState compact icon="layers" title={t('rag.run.noSteps')} />
          ) : (
            <div className="rag-step-list">
              {data.steps.map((step) => (
                <StepBlock key={step.id} step={step} />
              ))}
            </div>
          )}
        </section>

        <section className="rag-section">
          <div className="section-head">
            <MicroLabel>{t('rag.run.events')}</MicroLabel>
            <span className="section-index">{events.length.toString().padStart(2, '0')}</span>
          </div>
          {events.length === 0 ? (
            <EmptyState compact icon="activity" title={t('rag.run.noEvents')} />
          ) : (
            <EventList events={events} />
          )}
        </section>

        <div className="page-footnote">
          <MicroLabel>{t('rag.run.noteTitle')}</MicroLabel>
          <p>{t('rag.run.note')}</p>
        </div>
      </div>
    </div>
  )
}

function StepBlock({ step }: { step: RagStep }) {
  const { t } = useI18n()
  return (
    <div className="rag-step">
      <div className="rag-step-head">
        <span className="rag-step-ordinal">{String(step.ordinal).padStart(2, '0')}</span>
        <span className="rag-step-name">{step.step_key}</span>
        <RagStatusBadge status={step.status} />
        <span className="rag-step-progress">
          {t('rag.run.processed', { processed: step.processed_count, failed: step.failed_count })}
        </span>
      </div>
      <div className="rag-progress" aria-hidden="true">
        <span style={{ width: `${Math.min(100, Math.max(0, step.progress))}%` }} />
      </div>
      <div className="rag-job-list">
        {step.jobs.length === 0 && <p className="rag-section-note">{t('rag.run.noJobs')}</p>}
        {step.jobs.map((job) => (
          <JobBlock key={job.id} job={job} />
        ))}
      </div>
    </div>
  )
}

function JobBlock({ job }: { job: RagJob }) {
  const { t } = useI18n()
  return (
    <div className="rag-job">
      <div className="rag-job-head">
        <span className="rag-job-name">{job.job_key}</span>
        <span className="rag-job-kind">{job.kind}</span>
        <RagStatusBadge status={job.status} />
        <span className="rag-job-attempts">
          {t('rag.run.attemptsCount', { used: job.attempts, max: job.max_attempts })}
        </span>
      </div>
      {job.attempts_history.length === 0 ? (
        <p className="rag-section-note">{t('rag.run.noAttempts')}</p>
      ) : (
        <div className="rag-attempt-list">
          {job.attempts_history.map((attempt) => (
            <AttemptRow key={attempt.id} attempt={attempt} />
          ))}
        </div>
      )}
    </div>
  )
}

function AttemptRow({ attempt }: { attempt: RagAttempt }) {
  const { t } = useI18n()
  return (
    <div className="rag-attempt-row">
      <span className="rag-attempt-no">
        {t('rag.run.attemptNo', { count: attempt.attempt_no })}
      </span>
      <RagStatusBadge status={attempt.status} />
      <span className="rag-attempt-worker">{attempt.worker_id}</span>
      <span className="rag-attempt-time">
        {attempt.finished_at ? relativeTime(attempt.finished_at) : t('rag.run.running')}
      </span>
      {attempt.error_code && <Tag tone="danger">{attempt.error_code}</Tag>}
    </div>
  )
}

function EventList({ events }: { events: RagEvent[] }) {
  return (
    <ol className="rag-event-list">
      {events.map((event) => (
        <li key={event.id} className="rag-event-row">
          <span className="rag-event-index">#{event.id}</span>
          <span className={`rag-event-level rag-event-${event.level}`}>{event.level}</span>
          <span className="rag-event-main">
            <span className="rag-event-type">{event.type}</span>
            <span className="rag-event-message">{event.message}</span>
          </span>
          <time className="rag-event-time" title={formatDateTime(event.created_at)}>
            {relativeTime(event.created_at)}
          </time>
        </li>
      ))}
    </ol>
  )
}
