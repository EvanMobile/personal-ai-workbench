import { api } from '../api'
import { ArtifactImage } from '../components/ArtifactImage'
import { Icon } from '../components/Icon'
import {
  EmptyState,
  ErrorBanner,
  MicroLabel,
  Skeleton,
  ViewHeader,
} from '../components/ui'
import { useAsyncData } from '../hooks/useAsyncData'
import type { Asset, KnowledgeStats, OpenView } from '../types'
import { relativeTime, sortAssetsNewest } from '../utils'

interface HomeData {
  stats: KnowledgeStats
  assets: Asset[]
}

const statLabels: Array<{ key: keyof KnowledgeStats; label: string; accent?: boolean }> = [
  { key: 'raw_contents', label: 'Raw inputs' },
  { key: 'drafts', label: 'Drafts' },
  { key: 'assets', label: 'Cards', accent: true },
  { key: 'dossiers', label: 'Dossiers' },
  { key: 'pages', label: 'Pages' },
  { key: 'artifacts', label: 'Artifacts' },
]

export function HomeView({ openView }: { openView: OpenView }) {
  const { data, loading, error, reload } = useAsyncData<HomeData>(async (signal) => {
    const [stats, assets] = await Promise.all([api.stats(signal), api.assets(signal)])
    return { stats, assets: sortAssetsNewest(assets) }
  }, [])

  return (
    <div className="view-scroll">
      <div className="view-inner">
        <ViewHeader
          eyebrow="Workbench / Overview"
          title="Personal AI Workbench"
          description="A local workspace for capturing context, distilling knowledge, and composing artifacts."
          actions={
            <>
              <button type="button" className="button ghost" onClick={reload}>
                <Icon name="refresh" size={13} />
                Refresh
              </button>
              <button type="button" className="button primary" onClick={() => openView('capture')}>
                <Icon name="bolt" size={13} />
                New capture
              </button>
            </>
          }
        />

        {error && <ErrorBanner message={error} onRetry={reload} />}

        <section className="home-stats" aria-label="Knowledge statistics">
          {loading && !data
            ? Array.from({ length: 6 }, (_, index) => (
                <div className="stat-tile" key={index}>
                  <Skeleton lines={2} />
                </div>
              ))
            : data &&
              statLabels.map(({ key, label, accent }) => (
                <div key={key} className={`stat-tile ${accent ? 'stat-tile-accent' : ''}`}>
                  <MicroLabel>{label}</MicroLabel>
                  <strong>{String(data.stats[key] ?? 0).padStart(2, '0')}</strong>
                  <span className="stat-tile-rule" />
                  <span className="stat-tile-key">{key}</span>
                </div>
              ))}
        </section>

        <div className="home-grid">
          <section className="panel-section home-actions">
            <div className="section-head">
              <MicroLabel>Quick actions</MicroLabel>
              <span className="section-index">01</span>
            </div>
            <div className="quick-actions">
              <QuickAction
                icon="bolt"
                title="New capture"
                description="Ingest text or a file"
                onClick={() => openView('capture')}
              />
              <QuickAction
                icon="layers"
                title="Cards"
                description="Browse published assets"
                onClick={() => openView('cards')}
              />
              <QuickAction
                icon="folder"
                title="Dossiers"
                description="Curate connected cards"
                onClick={() => openView('dossiers')}
              />
              <QuickAction
                icon="page"
                title="Pages"
                description="Read composed artifacts"
                onClick={() => openView('pages')}
              />
            </div>
          </section>

          <section className="panel-section home-recent">
            <div className="section-head">
              <MicroLabel>Recent assets</MicroLabel>
              <button
                type="button"
                className="text-button"
                onClick={() => openView('cards')}
              >
                View all <Icon name="arrow-up-right" size={11} />
              </button>
            </div>
            {loading && !data && (
              <div className="recent-list">
                {Array.from({ length: 3 }, (_, index) => (
                  <div className="recent-row" key={index}>
                    <div className="skeleton skeleton-thumb" />
                    <div className="recent-copy">
                      <Skeleton lines={2} />
                    </div>
                  </div>
                ))}
              </div>
            )}
            {!loading && data && data.assets.length === 0 && (
              <EmptyState
                icon="layers"
                title="No assets yet"
                description="Capture an input and publish a card. Recent assets appear here."
                action={
                  <button type="button" className="button small primary" onClick={() => openView('capture')}>
                    Start a capture
                  </button>
                }
                compact
              />
            )}
            {data && data.assets.length > 0 && (
              <div className="recent-list">
                {data.assets.slice(0, 5).map((asset) => (
                  <button
                    type="button"
                    className="recent-row"
                    key={asset.id}
                    onClick={() => openView('card', { id: asset.id }, asset.title)}
                  >
                    <div className="recent-thumb">
                      <ArtifactImage asset={asset} compact />
                    </div>
                    <div className="recent-copy">
                      <span className="recent-title">{asset.title}</span>
                      <span className="recent-meta">
                        {asset.category || 'uncategorized'} · {relativeTime(asset.published_at)}
                      </span>
                    </div>
                    <Icon name="chevron-right" size={12} className="recent-arrow" />
                  </button>
                ))}
              </div>
            )}
          </section>
        </div>

        <section className="system-strip">
          <MicroLabel>Pipeline</MicroLabel>
          <div className="pipeline-step">
            <span className="pipeline-dot" /> Raw content
          </div>
          <span className="pipeline-link">→</span>
          <div className="pipeline-step">
            <span className="pipeline-dot" /> Draft
          </div>
          <span className="pipeline-link">→</span>
          <div className="pipeline-step">
            <span className="pipeline-dot accent" /> Card
          </div>
          <span className="pipeline-link">→</span>
          <div className="pipeline-step">
            <span className="pipeline-dot" /> Dossier / Page
          </div>
        </section>
      </div>
    </div>
  )
}

function QuickAction({
  icon,
  title,
  description,
  onClick,
}: {
  icon: 'bolt' | 'layers' | 'folder' | 'page'
  title: string
  description: string
  onClick: () => void
}) {
  return (
    <button type="button" className="quick-action" onClick={onClick}>
      <span className="quick-icon">
        <Icon name={icon} size={16} />
      </span>
      <span className="quick-copy">
        <strong>{title}</strong>
        <span>{description}</span>
      </span>
      <Icon name="arrow-up-right" size={12} className="quick-arrow" />
    </button>
  )
}
