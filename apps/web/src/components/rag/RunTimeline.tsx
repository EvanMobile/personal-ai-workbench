import { useI18n } from '../../i18n'
import type { OpenView } from '../../types'
import type { RagRunSummary } from '../../rag/types'
import { formatDateTime, relativeTime, shortId } from '../../utils'
import { EmptyState, MicroLabel } from '../ui'
import { Icon } from '../Icon'
import { RagStatusBadge } from './RagStatusBadge'

export function RunTimeline({
  runs,
  openView,
  title,
}: {
  runs: RagRunSummary[]
  openView: OpenView
  title?: string
}) {
  const { t } = useI18n()
  return (
    <section className="rag-section rag-timeline-section">
      <div className="section-head">
        <MicroLabel>{title ?? t('rag.run.timeline')}</MicroLabel>
        <span className="section-index">{runs.length.toString().padStart(2, '0')}</span>
      </div>
      {runs.length === 0 ? (
        <EmptyState
          compact
          icon="activity"
          title={t('rag.run.noRuns')}
          description={t('rag.run.noRunsBody')}
        />
      ) : (
        <div className="rag-run-timeline">
          {runs.map((run) => (
            <button
              key={run.id}
              type="button"
              className="rag-run-row"
              onClick={() => openView('rag-run', { id: run.id }, t('tabs.ragRun'))}
            >
              <span className="rag-run-line" aria-hidden="true" />
              <span className="rag-run-main">
                <span className="rag-run-id">{shortId(run.id, 10)}</span>
                <span className="rag-run-stage">{run.stage}</span>
                <span className="rag-run-time" title={formatDateTime(run.updated_at)}>
                  {relativeTime(run.updated_at)}
                </span>
              </span>
              <RagStatusBadge status={run.status} />
              <Icon name="chevron-right" size={12} className="rag-run-chevron" />
            </button>
          ))}
        </div>
      )}
    </section>
  )
}
