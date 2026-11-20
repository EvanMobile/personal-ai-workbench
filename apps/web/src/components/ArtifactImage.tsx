import { useEffect, useState } from 'react'
import type { Asset } from '../types'
import { cx } from '../utils'
import { Icon } from './Icon'

interface ArtifactImageProps {
  asset: Asset | null | undefined
  alt?: string
  className?: string
  compact?: boolean
}

export function ArtifactImage({ asset, alt, className, compact = false }: ArtifactImageProps) {
  const url = asset?.artifact?.url ?? null
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    setFailed(false)
  }, [url])

  if (!url || failed) {
    return (
      <div className={cx('artifact-placeholder', compact && 'artifact-placeholder-compact', className)}>
        <Icon name={asset?.artifact ? 'alert' : 'image'} size={compact ? 16 : 24} />
        <span>{asset?.artifact ? 'Artifact unavailable' : 'No artifact'}</span>
        {asset?.artifact && <code>{asset.artifact.status}</code>}
      </div>
    )
  }

  return (
    <img
      className={cx('artifact-image', className)}
      src={url}
      alt={alt ?? `Artifact for ${asset?.title ?? 'card'}`}
      loading="lazy"
      onError={() => setFailed(true)}
    />
  )
}
