import { Icon } from '../components/Icon'
import { EmptyState, MicroLabel, ViewHeader } from '../components/ui'
import type { OpenView } from '../types'
import { useI18n } from '../i18n'
import type { MessageKey } from '../i18n/messages'

const content = {
  'project-replay': {
    eyebrowKey: 'placeholder.replayEyebrow',
    titleKey: 'placeholder.replayTitle',
    descriptionKey: 'placeholder.replayDescription',
    emptyTitleKey: 'placeholder.replayEmpty',
    emptyDescriptionKey: 'placeholder.noProjectsBody',
    actionKey: 'placeholder.captureProject',
    module: 'PRJ_REPLAY',
    capabilityKeys: [
      'placeholder.replayModule',
      'placeholder.decisionLedger',
      'placeholder.contextSnapshots',
    ],
  },
  arsenal: {
    eyebrowKey: 'placeholder.arsenalEyebrow',
    titleKey: 'placeholder.arsenalTitle',
    descriptionKey: 'placeholder.arsenalDescription',
    emptyTitleKey: 'placeholder.arsenalEmpty',
    emptyDescriptionKey: 'placeholder.arsenalBody',
    actionKey: 'placeholder.captureEntry',
    module: 'ARSENAL',
    capabilityKeys: [
      'placeholder.arsenalModule',
      'placeholder.methodCards',
      'placeholder.reuseNotes',
    ],
  },
} as const satisfies Record<
  'project-replay' | 'arsenal',
  {
    eyebrowKey: MessageKey
    titleKey: MessageKey
    descriptionKey: MessageKey
    emptyTitleKey: MessageKey
    emptyDescriptionKey: MessageKey
    actionKey: MessageKey
    module: string
    capabilityKeys: MessageKey[]
  }
>

export function PlaceholderView({
  kind,
  openView,
}: {
  kind: 'project-replay' | 'arsenal'
  openView: OpenView
}) {
  const { t } = useI18n()
  const model = content[kind]

  return (
    <div className="view-scroll">
      <div className="view-inner">
        <ViewHeader eyebrow={t(model.eyebrowKey)} title={t(model.titleKey)} description={t(model.descriptionKey)} />

        <div className="product-empty-layout">
          <div className="product-empty-main">
            <div className="blueprint-grid" aria-hidden="true">
              <span className="blueprint-cross">+</span>
              <span className="blueprint-cross blueprint-cross-br">+</span>
              <div className="blueprint-tag">{t('placeholder.module')} // {model.module}</div>
            </div>
            <EmptyState
              icon={kind === 'project-replay' ? 'terminal' : 'layers'}
              title={t(model.emptyTitleKey)}
              description={t(model.emptyDescriptionKey)}
              action={
                <button
                  type="button"
                  className="button primary"
                  onClick={() => openView('capture')}
                >
                  <Icon name="bolt" size={13} /> {t(model.actionKey)}
                </button>
              }
            />
          </div>

          <aside className="product-spec">
            <div className="spec-head">
              <MicroLabel>{t('placeholder.moduleSpec')}</MicroLabel>
              <span className="spec-status">{t('placeholder.empty')}</span>
            </div>
            <dl className="meta-list">
              <div>
                <dt>{t('placeholder.module')}</dt>
                <dd>{model.module}</dd>
              </div>
              <div>
                <dt>{t('placeholder.state')}</dt>
                <dd>{t('placeholder.notConfigured')}</dd>
              </div>
              <div>
                <dt>{t('placeholder.phase')}</dt>
                <dd>P1.M1</dd>
              </div>
            </dl>
            <div className="spec-capabilities">
              <MicroLabel>{t('placeholder.capabilities')}</MicroLabel>
              {model.capabilityKeys.map((capability, index) => (
                <div className="spec-capability" key={capability}>
                  <span>{String(index + 1).padStart(2, '0')}</span>
                  <span>{t(capability)}</span>
                  <span className="spec-pending">{t('common.pending')}</span>
                </div>
              ))}
            </div>
          </aside>
        </div>
      </div>
    </div>
  )
}
