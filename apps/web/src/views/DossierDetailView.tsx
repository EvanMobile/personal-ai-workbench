import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
} from 'react'
import { api, errorMessage } from '../api'
import { ArtifactImage } from '../components/ArtifactImage'
import { Icon } from '../components/Icon'
import { Modal } from '../components/Modal'
import { useToast } from '../components/Toast'
import {
  EmptyState,
  ErrorBanner,
  MicroLabel,
  Skeleton,
  Tag,
  ViewHeader,
} from '../components/ui'
import { useAsyncData } from '../hooks/useAsyncData'
import type {
  Asset,
  DossierAssetResponse,
  DossierDetailData,
  OpenView,
} from '../types'
import { cx, shortId, sortAssetsNewest } from '../utils'

const NODE_WIDTH = 184
const NODE_HEIGHT = 138
const GAP_X = 62
const GAP_Y = 72
const PAD = 64
const MIN_WIDTH = 960
const MIN_HEIGHT = 520

interface NodePosition {
  x: number
  y: number
}

interface CanvasLayout {
  positions: Record<string, NodePosition>
  width: number
  height: number
}

const emptyCanvas: CanvasLayout = {
  positions: {},
  width: MIN_WIDTH,
  height: MIN_HEIGHT,
}

function layoutCanvas(
  cards: Asset[],
  widthHint = 0,
  heightHint = 0,
): CanvasLayout {
  const count = cards.length
  if (count === 0) return emptyCanvas

  const columns = count === 1 ? 1 : Math.max(2, Math.ceil(Math.sqrt(count * 1.35)))
  const rows = Math.ceil(count / columns)
  const contentWidth = columns * NODE_WIDTH + (columns - 1) * GAP_X
  const contentHeight = rows * NODE_HEIGHT + (rows - 1) * GAP_Y
  const width = Math.max(MIN_WIDTH, widthHint, contentWidth + PAD * 2)
  const height = Math.max(MIN_HEIGHT, heightHint, contentHeight + PAD * 2)
  const originX = (width - contentWidth) / 2
  const originY = Math.max(PAD, (height - contentHeight) / 2)
  const positions: Record<string, NodePosition> = {}

  cards.forEach((card, index) => {
    const column = index % columns
    const row = Math.floor(index / columns)
    const jitterX = count === 1 ? 0 : ((index * 37) % 29) - 14
    const jitterY = count === 1 ? 0 : ((index * 53) % 23) - 11
    positions[card.id] = {
      x: Math.round(originX + column * (NODE_WIDTH + GAP_X) + jitterX),
      y: Math.round(originY + row * (NODE_HEIGHT + GAP_Y) + jitterY),
    }
  })

  return { positions, width, height }
}

export function DossierDetailView({
  dossierId,
  immersive,
  onEnterImmersive,
  onExitImmersive,
  openView,
}: {
  dossierId: string
  immersive: boolean
  onEnterImmersive: () => void
  onExitImmersive: () => void
  openView: OpenView
}) {
  const { notify } = useToast()
  const { data, loading, error, reload, setData } = useAsyncData<DossierDetailData>(
    (signal) => api.dossier(dossierId, signal),
    [dossierId],
  )
  const [canvas, setCanvas] = useState<CanvasLayout>(emptyCanvas)
  const [draggingId, setDraggingId] = useState<string | null>(null)
  const [addOpen, setAddOpen] = useState(false)
  const [removeTarget, setRemoveTarget] = useState<Asset | null>(null)
  const [creatingPage, setCreatingPage] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const drag = useRef<{
    id: string
    startX: number
    startY: number
    originX: number
    originY: number
  } | null>(null)

  useEffect(() => {
    if (!data) return
    // Immersive mode gets a larger, centered working surface. Exiting focus
    // restores the regular view and the persisted shell columns.
    if (immersive) {
      setCanvas(
        layoutCanvas(
          data.cards,
          Math.max(MIN_WIDTH, window.innerWidth - 8),
          Math.max(MIN_HEIGHT, window.innerHeight - 150),
        ),
      )
    } else {
      setCanvas(layoutCanvas(data.cards))
    }
  }, [data, immersive])

  const markerId = useMemo(
    () => `dossier-arrow-${dossierId.replace(/[^a-zA-Z0-9_-]/g, '')}`,
    [dossierId],
  )

  const edges = useMemo(() => {
    if (!data) return []
    return data.edges
      .map((edge) => {
        const source = canvas.positions[edge.source]
        const target = canvas.positions[edge.target]
        if (!source || !target) return null
        const sx = source.x + NODE_WIDTH
        const sy = source.y + NODE_HEIGHT / 2
        const tx = target.x
        const ty = target.y + NODE_HEIGHT / 2
        const bend = Math.max(48, Math.abs(tx - sx) * 0.38)
        const direction = tx >= sx ? 1 : -1
        const path = `M ${sx} ${sy} C ${sx + bend * direction} ${sy}, ${tx - bend * direction} ${ty}, ${tx} ${ty}`
        return { ...edge, path }
      })
      .filter((edge): edge is NonNullable<typeof edge> => Boolean(edge))
  }, [canvas.positions, data])

  const handlePointerDown = (event: ReactPointerEvent<HTMLElement>, cardId: string) => {
    if ((event.target as HTMLElement).closest('button')) return
    const position = canvas.positions[cardId]
    if (!position) return
    event.preventDefault()
    event.currentTarget.setPointerCapture(event.pointerId)
    drag.current = {
      id: cardId,
      startX: event.clientX,
      startY: event.clientY,
      originX: position.x,
      originY: position.y,
    }
    setDraggingId(cardId)
  }

  const handlePointerMove = (event: ReactPointerEvent<HTMLElement>) => {
    const current = drag.current
    if (!current) return
    const nextX = Math.max(12, current.originX + event.clientX - current.startX)
    const nextY = Math.max(12, current.originY + event.clientY - current.startY)
    setCanvas((previous) => ({
      ...previous,
      positions: {
        ...previous.positions,
        [current.id]: { x: nextX, y: nextY },
      },
    }))
  }

  const endDrag = (event: ReactPointerEvent<HTMLElement>) => {
    if (drag.current) {
      if (event.currentTarget.hasPointerCapture(event.pointerId)) {
        event.currentTarget.releasePointerCapture(event.pointerId)
      }
      drag.current = null
      setDraggingId(null)
    }
  }

  const createPage = async () => {
    if (!data) return
    setCreatingPage(true)
    setActionError(null)
    try {
      const page = await api.createPage(data.dossier.id)
      notify('Page created from dossier.', 'success')
      openView('page', { id: page.id }, page.title)
    } catch (caught) {
      setActionError(errorMessage(caught))
      notify(errorMessage(caught), 'danger')
    } finally {
      setCreatingPage(false)
    }
  }

  const handleAdded = (response: DossierAssetResponse) => {
    setData(response)
    setAddOpen(false)
    notify(`${response.cards.length} cards in dossier.`, 'success')
  }

  if (loading && !data) {
    return (
      <div className="view-scroll">
        <div className="view-inner">
          <Skeleton lines={2} />
          <div className="skeleton skeleton-block canvas-skeleton" />
        </div>
      </div>
    )
  }

  if (error && !data) {
    return (
      <div className="view-scroll">
        <div className="view-inner">
          <ViewHeader
            eyebrow="Wiki / Dossiers / Graph"
            title="Dossier unavailable"
            back={{ label: 'Dossiers', onClick: () => openView('dossiers') }}
          />
          <ErrorBanner message={error} onRetry={reload} />
        </div>
      </div>
    )
  }

  if (!data) return null

  const dossier = data.dossier

  return (
    <div className={cx('dossier-view', immersive && 'dossier-view-immersive')}>
      {!immersive && (
        <div className="view-scroll dossier-head-scroll">
          <div className="view-inner dossier-head-inner">
            <ViewHeader
              eyebrow="Wiki / Dossiers / Graph"
              title={dossier.name}
              description={dossier.description || 'No description.'}
              back={{ label: 'Dossiers', onClick: () => openView('dossiers') }}
            />
            {error && <ErrorBanner message={error} onRetry={reload} />}
            {actionError && (
              <ErrorBanner message={actionError} onDismiss={() => setActionError(null)} />
            )}
          </div>
        </div>
      )}

      <div className={cx('canvas-shell', immersive && 'canvas-shell-immersive')}>
        <div className="canvas-toolbar">
          <div className="canvas-toolbar-info">
            {immersive && (
              <span className="immersive-mark">
                <Icon name="maximize" size={13} /> Focus
              </span>
            )}
            <MicroLabel>{immersive ? dossier.name : 'Dossier graph'}</MicroLabel>
            <span className="canvas-stat">
              {String(data.cards.length).padStart(2, '0')} nodes
              <span className="canvas-stat-divider">/</span>
              {String(data.edges.length).padStart(2, '0')} edges
            </span>
            {dossier.page_id && (
              <button
                type="button"
                className="canvas-inline-link"
                onClick={() => openView('page', { id: dossier.page_id as string }, 'Page')}
              >
                <Icon name="page" size={11} /> Has page
              </button>
            )}
          </div>
          <div className="canvas-toolbar-actions">
            <button type="button" className="button ghost small" onClick={() => setAddOpen(true)}>
              <Icon name="plus" size={12} /> Add cards
            </button>
            <button
              type="button"
              className="button ghost small"
              onClick={createPage}
              disabled={creatingPage || data.cards.length === 0}
            >
              <Icon name="page" size={12} />
              {creatingPage ? 'Composing…' : 'Create Page'}
            </button>
            {immersive ? (
              <button type="button" className="button small primary" onClick={onExitImmersive}>
                <Icon name="minimize" size={12} /> Exit focus
              </button>
            ) : (
              <button type="button" className="button small" onClick={onEnterImmersive}>
                <span className="focus-glyph">⏏</span> Focus
              </button>
            )}
          </div>
        </div>

        {data.cards.length === 0 ? (
          <div className="graph-empty">
            <EmptyState
              icon="layers"
              title="This dossier has no cards"
              description="Add cards to build the shared-tag graph. Edges appear automatically."
              action={
                <button type="button" className="button primary" onClick={() => setAddOpen(true)}>
                  <Icon name="plus" size={13} /> Add cards
                </button>
              }
            />
          </div>
        ) : (
          <div className="graph-scroll">
            <div
              className="graph-canvas"
              style={{ width: canvas.width, height: canvas.height }}
            >
              <svg
                className="graph-edges"
                width={canvas.width}
                height={canvas.height}
                viewBox={`0 0 ${canvas.width} ${canvas.height}`}
                aria-hidden="true"
              >
                <defs>
                  <marker
                    id={markerId}
                    viewBox="0 0 10 10"
                    refX="8"
                    refY="5"
                    markerWidth="5"
                    markerHeight="5"
                    orient="auto-start-reverse"
                  >
                    <path d="M 0 0 L 10 5 L 0 10 z" className="edge-arrowhead" />
                  </marker>
                </defs>
                {edges.map((edge, index) => (
                  <path
                    key={`${edge.source}-${edge.target}-${index}`}
                    d={edge.path}
                    className="graph-edge"
                    markerEnd={`url(#${markerId})`}
                  >
                    <title>{edge.reason}</title>
                  </path>
                ))}
              </svg>

              {data.cards.map((card) => {
                const position = canvas.positions[card.id]
                if (!position) return null
                return (
                  <article
                    key={card.id}
                    className={cx(
                      'graph-node',
                      draggingId === card.id && 'graph-node-dragging',
                    )}
                    style={{
                      width: NODE_WIDTH,
                      height: NODE_HEIGHT,
                      transform: `translate(${position.x}px, ${position.y}px)`,
                    }}
                    onPointerDown={(event) => handlePointerDown(event, card.id)}
                    onPointerMove={handlePointerMove}
                    onPointerUp={endDrag}
                    onPointerCancel={endDrag}
                    onDoubleClick={() =>
                      openView('card', { id: card.id }, card.title)
                    }
                    title="Drag to arrange · Double-click to open card"
                  >
                    <div className="graph-node-image">
                      <ArtifactImage asset={card} compact />
                      <span className="graph-node-index">{shortId(card.id, 4).toUpperCase()}</span>
                      <button
                        type="button"
                        className="graph-node-remove"
                        title="Remove card from dossier"
                        aria-label={`Remove ${card.title} from dossier`}
                        onPointerDown={(event) => event.stopPropagation()}
                        onClick={(event) => {
                          event.stopPropagation()
                          setRemoveTarget(card)
                        }}
                      >
                        <Icon name="x" size={10} />
                      </button>
                    </div>
                    <div className="graph-node-body">
                      <h3>{card.title}</h3>
                      <span className="graph-node-meta">
                        {card.category || 'uncategorized'}
                      </span>
                    </div>
                  </article>
                )
              })}
            </div>
          </div>
        )}

        <div className="canvas-legend">
          <span className="legend-item">
            <span className="legend-line" /> shared tags
          </span>
          <span className="legend-item">
            <span className="legend-node" /> card
          </span>
          <span className="legend-item legend-hint">drag nodes · double-click to inspect</span>
        </div>
      </div>

      {addOpen && (
        <AddCardsModal
          dossierId={dossierId}
          existingIds={data.cards.map((card) => card.id)}
          onClose={() => setAddOpen(false)}
          onAdded={handleAdded}
        />
      )}

      {removeTarget && (
        <RemoveCardModal
          dossierId={dossierId}
          asset={removeTarget}
          onClose={() => setRemoveTarget(null)}
          onRemoved={() => {
            setRemoveTarget(null)
            reload()
          }}
        />
      )}
    </div>
  )
}

function AddCardsModal({
  dossierId,
  existingIds,
  onClose,
  onAdded,
}: {
  dossierId: string
  existingIds: string[]
  onClose: () => void
  onAdded: (response: DossierAssetResponse) => void
}) {
  const { notify } = useToast()
  const { data, loading, error, reload } = useAsyncData<Asset[]>(
    (signal) => api.assets(signal),
    [],
  )
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const existing = useMemo(() => new Set(existingIds), [existingIds])
  const assets = sortAssetsNewest(data ?? [])

  const toggle = (id: string) => {
    setSelected((previous) => {
      const next = new Set(previous)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const submit = async () => {
    if (selected.size === 0) return
    setSubmitting(true)
    setSubmitError(null)
    try {
      const response = await api.addDossierAssets(dossierId, [...selected])
      notify('Cards added to dossier.', 'success')
      onAdded(response)
    } catch (caught) {
      setSubmitError(errorMessage(caught))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      title="Add cards to dossier"
      eyebrow="Dossier / Compose"
      width="lg"
      onClose={onClose}
      footer={
        <>
          <span className="modal-selection-count">
            {selected.size} selected
          </span>
          <button type="button" className="button ghost" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="button primary"
            disabled={submitting || selected.size === 0}
            onClick={submit}
          >
            {submitting ? 'Adding…' : `Add ${selected.size || ''} cards`.trim()}
          </button>
        </>
      }
    >
      {error && <ErrorBanner message={error} onRetry={reload} />}
      {submitError && <ErrorBanner message={submitError} />}
      {loading && !data && (
        <div className="asset-pick-list">
          {Array.from({ length: 4 }, (_, index) => (
            <div className="asset-pick-row" key={index}>
              <Skeleton lines={2} />
            </div>
          ))}
        </div>
      )}
      {!loading && assets.length === 0 && (
        <EmptyState
          icon="layers"
          title="No cards available"
          description="Publish a draft to create a card, then add it to this dossier."
          compact
        />
      )}
      {assets.length > 0 && (
        <div className="asset-pick-list">
          {assets.map((asset) => {
            const already = existing.has(asset.id)
            return (
              <label
                key={asset.id}
                className={cx(
                  'asset-pick-row',
                  selected.has(asset.id) && 'asset-pick-row-selected',
                  already && 'asset-pick-row-disabled',
                )}
              >
                <input
                  type="checkbox"
                  checked={already || selected.has(asset.id)}
                  disabled={already}
                  onChange={() => toggle(asset.id)}
                />
                <span className="asset-pick-thumb">
                  <ArtifactImage asset={asset} compact />
                </span>
                <span className="asset-pick-copy">
                  <strong>{asset.title}</strong>
                  <span>
                    {asset.category || 'uncategorized'} · {asset.tags.slice(0, 3).join(', ') || 'no tags'}
                  </span>
                </span>
                {already && <Tag tone="muted">in dossier</Tag>}
                {asset.archived && !already && <Tag tone="muted">archived</Tag>}
              </label>
            )
          })}
        </div>
      )}
    </Modal>
  )
}

function RemoveCardModal({
  dossierId,
  asset,
  onClose,
  onRemoved,
}: {
  dossierId: string
  asset: Asset
  onClose: () => void
  onRemoved: () => void
}) {
  const { notify } = useToast()
  const [removing, setRemoving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const remove = async () => {
    setRemoving(true)
    setError(null)
    try {
      await api.removeDossierAsset(dossierId, asset.id)
      notify('Card removed from dossier.', 'success')
      onRemoved()
    } catch (caught) {
      setError(errorMessage(caught))
    } finally {
      setRemoving(false)
    }
  }

  return (
    <Modal
      title="Remove card"
      eyebrow="Dossier / Detach"
      width="sm"
      onClose={onClose}
      footer={
        <>
          <button type="button" className="button ghost" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="button danger"
            disabled={removing}
            onClick={remove}
          >
            {removing ? 'Removing…' : 'Remove from dossier'}
          </button>
        </>
      }
    >
      <p className="modal-copy">
        Remove <strong>{asset.title}</strong> from this dossier? The underlying card and its
        artifact will not be deleted.
      </p>
      {error && <ErrorBanner message={error} />}
    </Modal>
  )
}
