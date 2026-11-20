import { useState } from 'react'
import { api } from '../api'
import { ArtifactImage } from '../components/ArtifactImage'
import { Icon } from '../components/Icon'
import {
  EmptyState,
  ErrorBanner,
  Skeleton,
  Tag,
  ViewHeader,
} from '../components/ui'
import { useAsyncData } from '../hooks/useAsyncData'
import type { Asset, Draft, OpenView } from '../types'
import { relativeTime, sortAssetsNewest } from '../utils'

interface CardsData {
  assets: Asset[]
  models: Record<string, string>
}

type CardFilter = 'all' | 'unarchived' | 'archived'

const filters: Array<{ id: CardFilter; label: string }> = [
  { id: 'all', label: 'All' },
  { id: 'unarchived', label: 'Unarchived' },
  { id: 'archived', label: 'Archived' },
]

export function CardsView({ openView }: { openView: OpenView }) {
  const { data, loading, error, reload } = useAsyncData<CardsData>(async (signal) => {
    // Assets are the primary data. Draft metadata only enriches the model label,
    // so a drafts failure must not blank the whole library.
    const [assets, drafts] = await Promise.all([
      api.assets(signal),
      api.drafts(signal).catch((): Draft[] => []),
    ])
    const models: Record<string, string> = {}
    for (const draft of drafts) {
      if (draft.model) models[draft.id] = draft.model
    }
    return { assets, models }
  }, [])
  const [filter, setFilter] = useState<CardFilter>('unarchived')

  const assets = sortAssetsNewest(data?.assets ?? [])
  const archivedCount = assets.filter((asset) => asset.archived).length
  const visible = assets.filter((asset) => {
    if (filter === 'archived') return asset.archived
    if (filter === 'unarchived') return !asset.archived
    return true
  })

  const counts: Record<CardFilter, number> = {
    all: assets.length,
    unarchived: assets.length - archivedCount,
    archived: archivedCount,
  }

  return (
    <div className="view-scroll">
      <div className="view-inner">
        <ViewHeader
          eyebrow="Wiki / Cards"
          title="Card library"
          description="Published knowledge assets, each backed by a draft and generated artifact."
          actions={
            <>
              <button type="button" className="button ghost" onClick={reload}>
                <Icon name="refresh" size={13} /> Refresh
              </button>
              <button type="button" className="button primary" onClick={() => openView('capture')}>
                <Icon name="bolt" size={13} /> Capture
              </button>
            </>
          }
        />

        <div className="filter-bar" role="tablist" aria-label="Card filters">
          {filters.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={filter === item.id}
              className={`filter-tab ${filter === item.id ? 'filter-tab-active' : ''}`}
              onClick={() => setFilter(item.id)}
            >
              {item.label}
              <span className="filter-count">{String(counts[item.id]).padStart(2, '0')}</span>
            </button>
          ))}
          <span className="filter-spacer" />
          <span className="filter-meta">
            SORT <strong>CREATED ↓</strong>
          </span>
        </div>

        {error && <ErrorBanner message={error} onRetry={reload} />}

        {loading && !data && (
          <div className="masonry">
            {Array.from({ length: 6 }, (_, index) => (
              <Skeleton key={index} variant="card" />
            ))}
          </div>
        )}

        {!loading && data && visible.length === 0 && (
          <EmptyState
            icon={filter === 'archived' ? 'archive' : 'layers'}
            title={
              filter === 'archived'
                ? 'No archived cards'
                : filter === 'unarchived'
                  ? 'No active cards'
                  : 'No cards yet'
            }
            description={
              filter === 'archived'
                ? 'Cards you archive will be collected here.'
                : 'Publish a draft to add the first card to the library.'
            }
            action={
              filter !== 'archived' ? (
                <button type="button" className="button primary" onClick={() => openView('capture')}>
                  <Icon name="bolt" size={13} /> Start a capture
                </button>
              ) : undefined
            }
          />
        )}

        {visible.length > 0 && (
          <div className="masonry">
            {visible.map((asset) => (
              <CardTile
                key={asset.id}
                asset={asset}
                model={data?.models[asset.draft_id]}
                onClick={() => openView('card', { id: asset.id }, asset.title)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function CardTile({
  asset,
  model,
  onClick,
}: {
  asset: Asset
  model?: string
  onClick: () => void
}) {
  return (
    <button type="button" className="card-tile" onClick={onClick}>
      <div className="card-tile-artifact">
        <ArtifactImage asset={asset} />
        <span className="card-tile-open">
          <Icon name="arrow-up-right" size={11} /> inspect
        </span>
      </div>
      <div className="card-tile-body">
        <div className="card-tile-tags">
          <Tag tone="accent">{asset.category || 'uncategorized'}</Tag>
          {asset.archived && <Tag tone="muted">archived</Tag>}
        </div>
        <h3>{asset.title}</h3>
        {asset.summary && <p>{asset.summary}</p>}
        <div className="card-tile-foot">
          <span>
            <Icon name="database" size={10} />
            {asset.model || model || 'model n/a'}
          </span>
          <span>{relativeTime(asset.created_at ?? asset.published_at)}</span>
        </div>
      </div>
    </button>
  )
}
