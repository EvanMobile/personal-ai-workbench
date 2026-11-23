import { useEffect, useState } from 'react'
import type { Asset } from '../types'
import { cx } from '../utils'
import { Icon } from './Icon'
import { useI18n } from '../i18n'

interface ArtifactImageProps {
  asset: Asset | null | undefined
  alt?: string
  className?: string
  compact?: boolean
}

export function ArtifactImage({ asset, alt, className, compact = false }: ArtifactImageProps) {
  const { t } = useI18n()
  const url = asset?.artifact?.url ?? null
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    setFailed(false)
  }, [url])

  if (!url || failed) {
    return (
      <div className={cx('artifact-placeholder', compact && 'artifact-placeholder-compact', className)}>
        <Icon name={asset?.artifact ? 'alert' : 'image'} size={compact ? 16 : 24} />
        <span>{asset?.artifact ? t('component.artifactUnavailable') : t('component.noArtifact')}</span>
        {asset?.artifact && <code>{asset.artifact.status === 'ready' ? t('common.ready') : asset.artifact.status === 'failed' ? t('status.failed') : asset.artifact.status}</code>}
      </div>
    )
  }

  return (
    <img
      className={cx('artifact-image', className)}
      src={url}
      alt={alt ?? t('component.artifactAlt', { title: asset?.title ?? t('tabs.card') })}
      loading="lazy"
      onError={() => setFailed(true)}
    />
  )
}
