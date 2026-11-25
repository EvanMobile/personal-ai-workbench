import { useI18n } from '../../i18n'
import { Tag } from '../ui'
import { ragStatusKey, ragStatusTone } from '../../rag/status'
import type {
  RagAttemptStatus,
  RagJobStatus,
  RagRunStatus,
  RagStageStatus,
  RagStepStatus,
} from '../../rag/types'

export function RagStatusBadge({
  status,
}: {
  status: RagRunStatus | RagStageStatus | RagJobStatus | RagStepStatus | RagAttemptStatus
}) {
  const { t } = useI18n()
  return (
    <Tag tone={ragStatusTone(status)}>
      <span className="rag-status-badge">{t(ragStatusKey(status))}</span>
    </Tag>
  )
}
