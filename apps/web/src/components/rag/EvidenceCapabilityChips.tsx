import { useI18n } from '../../i18n'
import type { MessageKey } from '../../i18n/messages'
import type { RagEvidenceCapabilities } from '../../rag/types'
import { cx } from '../../utils'

function booleanValue(value: boolean): { key: MessageKey; tone: 'on' | 'off' } {
  return value
    ? { key: 'rag.capability.available', tone: 'on' }
    : { key: 'rag.capability.unavailable', tone: 'off' }
}

function stringValue(value: string): { key: MessageKey; tone: 'on' | 'off' | 'na' } {
  if (value === 'available') return { key: 'rag.capability.available', tone: 'on' }
  if (value === 'not_implemented') return { key: 'rag.capability.notImplemented', tone: 'na' }
  return { key: 'rag.capability.notAvailable', tone: 'na' }
}

function CapabilityChip({
  label,
  value,
  tone,
}: {
  label: string
  value: string
  tone: 'on' | 'off' | 'na'
}) {
  return (
    <span className={cx('rag-capability-chip', `rag-capability-${tone}`)}>
      <span className="rag-capability-label">{label}</span>
      <span className="rag-capability-value">{value}</span>
    </span>
  )
}

export function EvidenceCapabilityChips({
  capabilities,
}: {
  capabilities: RagEvidenceCapabilities
}) {
  const { t } = useI18n()
  const generated = booleanValue(capabilities.generated)
  const persisted = booleanValue(capabilities.db_persisted)
  const artifact = stringValue(capabilities.artifact_persisted)
  const verified = stringValue(capabilities.verified)

  return (
    <div className="rag-capability-chips" aria-label={t('rag.capability.label')}>
      <CapabilityChip
        label={t('rag.capability.generated')}
        value={t(generated.key)}
        tone={generated.tone}
      />
      <CapabilityChip
        label={t('rag.capability.dbPersisted')}
        value={t(persisted.key)}
        tone={persisted.tone}
      />
      <CapabilityChip
        label={t('rag.capability.artifactPersisted')}
        value={t(artifact.key)}
        tone={artifact.tone}
      />
      <CapabilityChip
        label={t('rag.capability.verified')}
        value={t(verified.key)}
        tone={verified.tone}
      />
    </div>
  )
}
