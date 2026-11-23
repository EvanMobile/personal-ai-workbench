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
import { useI18n } from '../i18n'
import type { MessageKey } from '../i18n/messages'

interface HomeData {
  stats: KnowledgeStats
  assets: Asset[]
}

const statLabels: Array<{ key: keyof KnowledgeStats; labelKey: MessageKey; accent?: boolean }> = [
  { key: 'raw_contents', labelKey: 'home.rawInputs' },
  { key: 'drafts', labelKey: 'home.drafts' },
  { key: 'assets', labelKey: 'home.cards', accent: true },
  { key: 'dossiers', labelKey: 'home.dossiers' },
  { key: 'pages', labelKey: 'home.pages' },
  { key: 'artifacts', labelKey: 'home.artifacts' },
]

export function HomeView({ openView }: { openView: OpenView }) {
  const { t } = useI18n()
  const { data, loading, error, reload } = useAsyncData<HomeData>(async (signal) => {
    const [stats, assets] = await Promise.all([api.stats(signal), api.assets(signal)])
    return { stats, assets: sortAssetsNewest(assets) }
  }, [])

  return (
    <div className="view-scroll">
      <div className="view-inner">
        <ViewHeader
          eyebrow={t('home.eyebrow')}
          title={t('home.title')}
          description={t('home.description')}
          actions={
            <>
              <button type="button" className="button ghost" onClick={reload}>
                <Icon name="refresh" size={13} />
                {t('common.refresh')}
              </button>
              <button type="button" className="button primary" onClick={() => openView('capture')}>
                <Icon name="bolt" size={13} />
                {t('home.newCapture')}
              </button>
            </>
          }
        />

        {error && <ErrorBanner message={error} onRetry={reload} />}

        <section className="home-stats" aria-label={t('home.statsAria')}>
          {loading && !data
            ? Array.from({ length: 6 }, (_, index) => (
                <div className="stat-tile" key={index}>
                  <Skeleton lines={2} />
                </div>
              ))
            : data &&
              statLabels.map(({ key, labelKey, accent }) => (
                <div key={key} className={`stat-tile ${accent ? 'stat-tile-accent' : ''}`}>
                  <MicroLabel>{t(labelKey)}</MicroLabel>
                  <strong>{String(data.stats[key] ?? 0).padStart(2, '0')}</strong>
                  <span className="stat-tile-rule" />
                  <span className="stat-tile-key">{key}</span>
                </div>
              ))}
        </section>

        <div className="home-grid">
          <section className="panel-section home-actions">
            <div className="section-head">
              <MicroLabel>{t('home.quickActions')}</MicroLabel>
              <span className="section-index">01</span>
            </div>
            <div className="quick-actions">
              <QuickAction
                icon="bolt"
                title={t('home.newCapture')}
                description={t('home.ingest')}
                onClick={() => openView('capture')}
              />
              <QuickAction
                icon="layers"
                title={t('home.cards')}
                description={t('home.browseAssets')}
                onClick={() => openView('cards')}
              />
              <QuickAction
                icon="folder"
                title={t('home.dossiers')}
                description={t('home.curate')}
                onClick={() => openView('dossiers')}
              />
              <QuickAction
                icon="page"
                title={t('home.pages')}
                description={t('home.readPages')}
                onClick={() => openView('pages')}
              />
            </div>
          </section>

          <section className="panel-section home-recent">
            <div className="section-head">
              <MicroLabel>{t('home.recentAssets')}</MicroLabel>
              <button
                type="button"
                className="text-button"
                onClick={() => openView('cards')}
              >
                {t('common.viewAll')} <Icon name="arrow-up-right" size={11} />
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
                title={t('home.noAssets')}
                description={t('home.noAssetsBody')}
                action={
                  <button type="button" className="button small primary" onClick={() => openView('capture')}>
                    {t('home.startCapture')}
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
                        {asset.category || t('home.uncategorized')} · {relativeTime(asset.published_at)}
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
          <MicroLabel>{t('home.pipeline')}</MicroLabel>
          <div className="pipeline-step">
            <span className="pipeline-dot" /> {t('home.pipelineRaw')}
          </div>
          <span className="pipeline-link">→</span>
          <div className="pipeline-step">
            <span className="pipeline-dot" /> {t('home.pipelineDraft')}
          </div>
          <span className="pipeline-link">→</span>
          <div className="pipeline-step">
            <span className="pipeline-dot accent" /> {t('home.pipelineCard')}
          </div>
          <span className="pipeline-link">→</span>
          <div className="pipeline-step">
            <span className="pipeline-dot" /> {t('home.pipelinePage')}
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
