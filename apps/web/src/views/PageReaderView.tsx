import { api } from '../api'
import { ArtifactImage } from '../components/ArtifactImage'
import { Icon } from '../components/Icon'
import { Markdown } from '../components/Markdown'
import {
  EmptyState,
  ErrorBanner,
  MicroLabel,
  Skeleton,
  Tag,
} from '../components/ui'
import { useAsyncData } from '../hooks/useAsyncData'
import type { OpenView, PageContent, PageDetailData, PageSection } from '../types'
import { formatDate } from '../utils'

function parseContent(value: PageDetailData['current']['content_json'] | undefined): {
  content: PageContent | null
  malformed: boolean
} {
  if (!value) return { content: null, malformed: false }
  if (typeof value === 'object') return { content: value, malformed: false }
  try {
    const parsed: unknown = JSON.parse(value)
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      return { content: parsed as PageContent, malformed: false }
    }
    return { content: null, malformed: true }
  } catch {
    return { content: null, malformed: true }
  }
}

export function PageReaderView({
  pageId,
  onClose,
  openView,
}: {
  pageId: string
  onClose: () => void
  openView: OpenView
}) {
  const { data, loading, error, reload } = useAsyncData<PageDetailData>(
    (signal) => api.page(pageId, signal),
    [pageId],
  )

  if (loading && !data) {
    return (
      <div className="view-scroll reader-scroll">
        <div className="reader-inner">
          <Skeleton lines={2} />
          <div className="skeleton skeleton-hero reader-skeleton" />
          <Skeleton lines={8} />
        </div>
      </div>
    )
  }

  if (error && !data) {
    return (
      <div className="view-scroll reader-scroll">
        <div className="reader-inner">
          <div className="reader-error-head">
            <MicroLabel>Wiki / Pages / Reader</MicroLabel>
            <h1>Page unavailable</h1>
          </div>
          <ErrorBanner message={error} onRetry={reload} />
          <button type="button" className="button ghost" onClick={onClose}>
            <Icon name="arrow-left" size={12} /> Back to pages
          </button>
        </div>
      </div>
    )
  }

  if (!data) return null

  const parsed = parseContent(data.current?.content_json)
  const content = parsed.content
  const sections = Array.isArray(content?.sections) ? content.sections : []
  const title = content?.title || data.page.title

  return (
    <div className="view-scroll reader-scroll">
      <div className="reader-inner">
        <div className="reader-toolbar">
          <button type="button" className="back-link" onClick={onClose}>
            <Icon name="arrow-left" size={12} /> Close reader
          </button>
          <div className="reader-toolbar-right">
            <span className="reader-toolbar-meta">
              version {data.current?.version ?? data.page.version}
            </span>
            <button type="button" className="icon-button" onClick={onClose} aria-label="Close reader">
              <Icon name="x" size={14} />
            </button>
          </div>
        </div>

        <article className="reader-sheet">
          <header className="reader-head">
            <MicroLabel>Knowledge page</MicroLabel>
            <h1>{title}</h1>
            {content?.subtitle && <p className="reader-subtitle">{content.subtitle}</p>}
            <div className="reader-meta-row">
              <span>
                <Icon name="page" size={11} /> PAGE {data.current?.id.slice(0, 8) ?? data.page.id.slice(0, 8)}
              </span>
              <span>
                <Icon name="database" size={11} /> {data.current?.model || 'model n/a'}
              </span>
              <span>{data.current?.renderer || 'renderer n/a'}</span>
              <span>{formatDate(data.current?.created_at ?? data.page.updated_at)}</span>
              <Tag>v{data.current?.version ?? data.page.version}</Tag>
            </div>
          </header>

          {parsed.malformed && (
            <ErrorBanner message="Page content_json could not be parsed. Showing available metadata only." />
          )}

          {sections.length === 0 && !parsed.malformed && (
            <EmptyState
              icon="page"
              title="No sections in this page"
              description="The composed snapshot has no sections yet."
              compact
            />
          )}

          <div className="reader-sections">
            {sections.map((section: PageSection, index) => (
              <section className="reader-section" key={`${section.heading}-${index}`}>
                <div className="reader-section-head">
                  <span className="reader-section-index">
                    {String(index + 1).padStart(2, '0')}
                  </span>
                  <h2>{section.heading || 'Untitled section'}</h2>
                </div>
                <div className="reader-section-body">
                  <Markdown source={section.body} />
                </div>
                {Array.isArray(section.cards) && section.cards.length > 0 && (
                  <div className="reader-figures">
                    {section.cards.map((card) => (
                      <figure className="reader-figure" key={card.id}>
                        <button
                          type="button"
                          className="reader-figure-image"
                          onClick={() => openView('card', { id: card.id }, card.title)}
                          title={`Open ${card.title}`}
                        >
                          <ArtifactImage asset={card} />
                        </button>
                        <figcaption>
                          <div className="reader-figure-copy">
                            <strong>{card.title}</strong>
                            <span>{card.summary || 'Card artifact'}</span>
                          </div>
                          <Tag tone="accent">{card.category || 'uncategorized'}</Tag>
                        </figcaption>
                      </figure>
                    ))}
                  </div>
                )}
              </section>
            ))}
          </div>

          <footer className="reader-foot">
            <div>
              <MicroLabel>Source cards</MicroLabel>
              <span>
                {data.current?.source_asset_ids?.length ?? 0} assets linked to this snapshot
              </span>
            </div>
            <button type="button" className="button ghost small" onClick={onClose}>
              Close reader <Icon name="x" size={11} />
            </button>
          </footer>
        </article>
      </div>
    </div>
  )
}
