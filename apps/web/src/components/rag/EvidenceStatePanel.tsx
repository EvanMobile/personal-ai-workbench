import { useI18n } from '../../i18n'
import type { MessageKey } from '../../i18n/messages'
import type { RagEvidenceObjectState, RagEvidenceState } from '../../rag/types'
import { cx } from '../../utils'
import { MicroLabel } from '../ui'

const OBJECTS: Array<{
  key: keyof Omit<RagEvidenceState, 'readback_session'>
  label: MessageKey
}> = [
  { key: 'run', label: 'rag.evidence.run' },
  { key: 'steps', label: 'rag.evidence.steps' },
  { key: 'jobs', label: 'rag.evidence.jobs' },
  { key: 'attempts', label: 'rag.evidence.attempts' },
  { key: 'events', label: 'rag.evidence.events' },
]

function stateModel(state: RagEvidenceObjectState): {
  label: MessageKey
  tone: 'ok' | 'empty' | 'failed'
} {
  if (state.read_back === false || state.exists === null) {
    return { label: 'rag.evidence.failed', tone: 'failed' }
  }
  return state.exists
    ? { label: 'rag.evidence.exists', tone: 'ok' }
    : { label: 'rag.evidence.empty', tone: 'empty' }
}

export function EvidenceStatePanel({ state }: { state: RagEvidenceState }) {
  const { t } = useI18n()
  return (
    <section className="rag-section rag-evidence-section">
      <div className="section-head">
        <MicroLabel>{t('rag.evidence.title')}</MicroLabel>
        <span className="rag-readback-session">
          {t('rag.evidence.readbackSession')}: <code>{state.readback_session}</code>
        </span>
      </div>
      <p className="rag-section-note">{t('rag.evidence.note')}</p>
      <div className="rag-evidence-grid">
        {OBJECTS.map(({ key, label }) => {
          const model = stateModel(state[key])
          return (
            <div key={key} className={cx('rag-evidence-cell', `rag-evidence-${model.tone}`)}>
              <span className="rag-evidence-label">{t(label)}</span>
              <span className="rag-evidence-state">{t(model.label)}</span>
              <span className="rag-evidence-readback">
                {t('rag.evidence.readBack')}:{' '}
                {state[key].read_back ? t('rag.evidence.yes') : t('rag.evidence.no')}
              </span>
            </div>
          )
        })}
      </div>
    </section>
  )
}
