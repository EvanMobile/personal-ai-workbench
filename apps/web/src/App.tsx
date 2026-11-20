import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent as ReactKeyboardEvent,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from 'react'
import { api } from './api'
import { ChatPanel } from './components/ChatPanel'
import { ContextTree } from './components/ContextTree'
import { Icon } from './components/Icon'
import { TabStrip } from './components/TabStrip'
import { useToast } from './components/Toast'
import type { OpenView, ViewKind, ViewParams, WorkspaceTab } from './types'
import { clamp, cx } from './utils'
import { CardDetailView } from './views/CardDetailView'
import { CardsView } from './views/CardsView'
import { CaptureView } from './views/CaptureView'
import { DossierDetailView } from './views/DossierDetailView'
import { DossiersView } from './views/DossiersView'
import { DraftView } from './views/DraftView'
import { HomeView } from './views/HomeView'
import { PageReaderView } from './views/PageReaderView'
import { PagesView } from './views/PagesView'
import { PlaceholderView } from './views/PlaceholderView'

const TAB_STORAGE_KEY = 'paw.workspace.tabs.v1'
const LAYOUT_STORAGE_KEY = 'paw.workspace.layout.v1'
const ACTIVE_STORAGE_KEY = 'paw.workspace.active.v1'

const HOME_TAB: WorkspaceTab = {
  id: 'home',
  kind: 'home',
  title: 'Workbench',
  closable: false,
}

type ApiStatus = 'checking' | 'online' | 'offline'

interface LayoutState {
  leftWidth: number
  rightWidth: number
  rightCollapsed: boolean
}

const DEFAULT_LAYOUT: LayoutState = {
  leftWidth: 272,
  rightWidth: 360,
  rightCollapsed: false,
}

const VIEW_KINDS = new Set<ViewKind>([
  'home',
  'capture',
  'cards',
  'card',
  'dossiers',
  'dossier',
  'pages',
  'page',
  'draft',
  'project-replay',
  'arsenal',
])

const SINGLETON_VIEWS = new Set<ViewKind>([
  'home',
  'capture',
  'cards',
  'dossiers',
  'pages',
  'project-replay',
  'arsenal',
])

function defaultTitle(kind: ViewKind, params?: ViewParams): string {
  if (params?.title) return params.title
  switch (kind) {
    case 'home':
      return 'Workbench'
    case 'capture':
      return 'Capture'
    case 'cards':
      return 'Cards'
    case 'card':
      return 'Card'
    case 'dossiers':
      return 'Dossiers'
    case 'dossier':
      return 'Dossier'
    case 'pages':
      return 'Pages'
    case 'page':
      return params?.title ? `Page · ${params.title}` : 'Page'
    case 'draft':
      return 'Draft'
    case 'project-replay':
      return 'Project Replay'
    case 'arsenal':
      return 'Personal Arsenal'
    default:
      return 'Untitled'
  }
}

function viewTabId(kind: ViewKind, params?: ViewParams): string {
  if (SINGLETON_VIEWS.has(kind)) return kind
  return params?.id ? `${kind}:${params.id}` : `${kind}:unknown`
}

function readJson<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : null
  } catch {
    return null
  }
}

function writeJson(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // Storage may be unavailable (private mode); the workspace still works in memory.
  }
}

function readWorkspace(): { tabs: WorkspaceTab[]; activeId: string } {
  const stored = readJson<WorkspaceTab[]>(TAB_STORAGE_KEY)
  if (!Array.isArray(stored) || stored.length === 0) {
    return { tabs: [HOME_TAB], activeId: HOME_TAB.id }
  }

  const seen = new Set<string>()
  const tabs = stored.filter((tab): tab is WorkspaceTab => {
    if (
      !tab ||
      typeof tab.id !== 'string' ||
      typeof tab.title !== 'string' ||
      !VIEW_KINDS.has(tab.kind) ||
      seen.has(tab.id)
    ) {
      return false
    }
    seen.add(tab.id)
    return true
  })

  if (!tabs.some((tab) => tab.id === HOME_TAB.id)) {
    tabs.unshift(HOME_TAB)
  }
  if (tabs.length === 0) tabs.push(HOME_TAB)
  tabs[0] = { ...tabs[0], closable: tabs[0].id === HOME_TAB.id ? false : tabs[0].closable }

  const storedActive = (() => {
    try {
      return localStorage.getItem(ACTIVE_STORAGE_KEY)
    } catch {
      return null
    }
  })()

  const activeId = tabs.some((tab) => tab.id === storedActive)
    ? (storedActive as string)
    : tabs[0].id

  return { tabs, activeId }
}

function readLayout(): LayoutState {
  const stored = readJson<Partial<LayoutState>>(LAYOUT_STORAGE_KEY)
  if (!stored) return DEFAULT_LAYOUT
  return {
    leftWidth: clamp(Number(stored.leftWidth) || DEFAULT_LAYOUT.leftWidth, 228, 380),
    rightWidth: clamp(Number(stored.rightWidth) || DEFAULT_LAYOUT.rightWidth, 312, 500),
    rightCollapsed: Boolean(stored.rightCollapsed),
  }
}

export default function App() {
  const { notify } = useToast()
  const [boot] = useState(readWorkspace)
  const [layout, setLayout] = useState<LayoutState>(readLayout)
  const [tabs, setTabs] = useState<WorkspaceTab[]>(boot.tabs)
  const [activeId, setActiveId] = useState(boot.activeId)
  const [immersive, setImmersive] = useState(false)
  const [apiStatus, setApiStatus] = useState<ApiStatus>('checking')
  const activeTab = tabs.find((tab) => tab.id === activeId) ?? tabs[0] ?? HOME_TAB

  useEffect(() => {
    writeJson(TAB_STORAGE_KEY, tabs)
    writeJson(ACTIVE_STORAGE_KEY, activeId)
  }, [tabs, activeId])

  useEffect(() => {
    writeJson(LAYOUT_STORAGE_KEY, layout)
  }, [layout])

  useEffect(() => {
    document.title = activeTab ? `${activeTab.title} · Personal AI Workbench` : 'Personal AI Workbench'
  }, [activeTab])

  const checkApi = useCallback(async (quiet = false) => {
    if (!quiet) setApiStatus('checking')
    try {
      const health = await api.health()
      if (health.status !== 'ok') throw new Error('Health check reported an unhealthy status.')
      setApiStatus('online')
    } catch {
      setApiStatus('offline')
    }
  }, [])

  useEffect(() => {
    void checkApi()
    const timer = window.setInterval(() => void checkApi(true), 30000)
    return () => window.clearInterval(timer)
  }, [checkApi])

  const openView = useCallback<OpenView>((kind, params, title) => {
    const id = viewTabId(kind, params)
    const resolvedTitle = title?.trim() || defaultTitle(kind, params)
    setTabs((previous) => {
      const existing = previous.find((tab) => tab.id === id)
      if (existing) {
        if (existing.title === resolvedTitle && existing.params?.id === params?.id) return previous
        return previous.map((tab) =>
          tab.id === id
            ? {
                ...tab,
                ...(title ? { title: resolvedTitle } : {}),
                ...(params ? { params: { ...tab.params, ...params } } : {}),
              }
            : tab,
        )
      }
      return [
        ...previous,
        {
          id,
          kind,
          title: resolvedTitle,
          params,
          closable: kind !== 'home',
        },
      ]
    })
    setActiveId(id)
    setImmersive(false)
  }, [])

  const closeTab = useCallback(
    (id: string) => {
      const tab = tabs.find((item) => item.id === id)
      if (!tab || !tab.closable) return
      let remaining = tabs.filter((item) => item.id !== id)
      if (remaining.length === 0) remaining = [HOME_TAB]

      if (activeId === id) {
        if (tab.kind === 'page') {
          const pagesTab = remaining.find((item) => item.kind === 'pages')
          if (pagesTab) {
            setActiveId(pagesTab.id)
          } else {
            const newPagesTab: WorkspaceTab = {
              id: 'pages',
              kind: 'pages',
              title: 'Pages',
              closable: true,
            }
            remaining = [...remaining, newPagesTab]
            setActiveId(newPagesTab.id)
          }
        } else {
          const index = tabs.findIndex((item) => item.id === id)
          const fallback = remaining[Math.max(0, index - 1)] ?? remaining[0]
          setActiveId(fallback.id)
        }
      }

      setTabs(remaining)
      setImmersive(false)
    },
    [activeId, tabs],
  )

  const startResize = (
    side: 'left' | 'right',
    event: ReactPointerEvent<HTMLDivElement>,
  ) => {
    if (immersive) return
    event.preventDefault()
    const startX = event.clientX
    const startWidth = side === 'left' ? layout.leftWidth : layout.rightWidth
    document.body.classList.add('is-resizing')

    const onMove = (move: PointerEvent) => {
      const delta = move.clientX - startX
      if (side === 'left') {
        setLayout((previous) => ({
          ...previous,
          leftWidth: clamp(startWidth + delta, 228, 380),
        }))
      } else {
        setLayout((previous) => ({
          ...previous,
          rightWidth: clamp(startWidth - delta, 312, 500),
        }))
      }
    }

    const stop = () => {
      document.body.classList.remove('is-resizing')
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', stop)
      window.removeEventListener('pointercancel', stop)
    }

    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', stop)
    window.addEventListener('pointercancel', stop)
  }

  const nudgeWidth = (
    side: 'left' | 'right',
    event: ReactKeyboardEvent<HTMLDivElement>,
  ) => {
    const step = event.shiftKey ? 32 : 8
    if (side === 'left' && (event.key === 'ArrowLeft' || event.key === 'ArrowRight')) {
      event.preventDefault()
      setLayout((previous) => ({
        ...previous,
        leftWidth: clamp(previous.leftWidth + (event.key === 'ArrowRight' ? step : -step), 228, 380),
      }))
    }
    if (side === 'right' && (event.key === 'ArrowLeft' || event.key === 'ArrowRight')) {
      event.preventDefault()
      setLayout((previous) => ({
        ...previous,
        rightWidth: clamp(
          previous.rightWidth + (event.key === 'ArrowLeft' ? step : -step),
          312,
          500,
        ),
      }))
    }
  }

  useEffect(() => {
    const handleKey = (event: globalThis.KeyboardEvent) => {
      const mod = event.metaKey || event.ctrlKey
      if (mod && event.key.toLowerCase() === 'n') {
        event.preventDefault()
        openView('capture')
      }
      if (mod && event.key === '\\') {
        event.preventDefault()
        setLayout((previous) => ({
          ...previous,
          rightCollapsed: !previous.rightCollapsed,
        }))
      }
      if (event.key === 'Escape' && immersive) {
        event.preventDefault()
        setImmersive(false)
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [immersive, openView])

  const showToastForRestore = useRef(false)
  useEffect(() => {
    if (showToastForRestore.current) return
    showToastForRestore.current = true
    if (boot.tabs.length > 1) {
      notify('Last workspace session restored.', 'info')
    }
  }, [boot.tabs.length, notify])

  const style = {
    '--left-width': `${layout.leftWidth}px`,
    '--right-width': `${layout.rightWidth}px`,
  } as CSSProperties

  return (
    <div className={cx('app-shell', immersive && 'app-shell-immersive')} style={style}>
      <header className="app-chrome">
        <div className="brand-bar">
          <div className="brand">
            <span className="brand-glyph">
              <Icon name="workbench" size={17} />
            </span>
            <div className="brand-copy">
              <strong>Personal AI Workbench</strong>
              <span>LOCAL KNOWLEDGE OS · P1.M1</span>
            </div>
          </div>
          <div className="brand-center" aria-hidden="true">
            <span className="brand-rule" />
            <span className="brand-env">WORKSPACE // ACTIVE</span>
            <span className="brand-rule" />
          </div>
          <div className="brand-actions">
            <button
              type="button"
              className={cx('api-pill', `api-pill-${apiStatus}`)}
              onClick={() => void checkApi()}
              title="Check API connection"
            >
              <span className={cx('api-dot', `api-dot-${apiStatus}`)} />
              {apiStatus === 'online' ? 'API ONLINE' : apiStatus === 'offline' ? 'API OFFLINE' : 'CHECKING'}
            </button>
            <button
              type="button"
              className={cx('icon-button topbar-icon', !layout.rightCollapsed && 'icon-button-active')}
              onClick={() =>
                setLayout((previous) => ({
                  ...previous,
                  rightCollapsed: !previous.rightCollapsed,
                }))
              }
              title={layout.rightCollapsed ? 'Open AI chat panel' : 'Collapse AI chat panel'}
              aria-label={layout.rightCollapsed ? 'Open AI chat panel' : 'Collapse AI chat panel'}
              aria-pressed={!layout.rightCollapsed}
            >
              <Icon name="panel-right" size={14} />
            </button>
          </div>
        </div>

        <div className="editor-bar">
          <TabStrip
            tabs={tabs}
            activeId={activeTab.id}
            onSelect={(id) => {
              setActiveId(id)
              setImmersive(false)
            }}
            onClose={closeTab}
            onNewCapture={() => openView('capture')}
          />
          <div className="editor-bar-right">
            {immersive && (
              <span className="immersive-chip">
                <Icon name="maximize" size={10} /> Focus mode
              </span>
            )}
            <span className="editor-hint">
              <span className="kbd">⌘</span>N capture
            </span>
            <span className="editor-hint">
              <span className="kbd">⌘</span>\ chat
            </span>
          </div>
        </div>
      </header>

      {apiStatus === 'offline' && (
        <div className="offline-banner" role="alert">
          <div className="offline-left">
            <Icon name="alert" size={14} />
            <span>
              <strong>API offline</strong> — cannot reach the workbench service at{' '}
              <code>127.0.0.1:8000</code>. Start the backend, then retry.
            </span>
          </div>
          <button type="button" className="button small ghost" onClick={() => void checkApi()}>
            <Icon name="refresh" size={12} /> Retry
          </button>
        </div>
      )}

      <div
        className={cx(
          'workspace',
          layout.rightCollapsed && 'workspace-chat-collapsed',
          immersive && 'workspace-immersive',
        )}
      >
        {!immersive && (
          <>
            <ContextTree activeTab={activeTab} openView={openView} apiStatus={apiStatus} />
            <ResizeHandle
              side="left"
              label="Resize context directory"
              onPointerDown={(event) => startResize('left', event)}
              onKeyDown={(event) => nudgeWidth('left', event)}
            />
          </>
        )}

        <main className="workspace-main">
          <div className="tab-content" key={activeTab.id}>
            {renderTab(activeTab, {
              openView,
              closeTab,
              setImmersive,
              immersive,
            })}
          </div>
        </main>

        {!immersive && !layout.rightCollapsed && (
          <>
            <ResizeHandle
              side="right"
              label="Resize AI chat panel"
              onPointerDown={(event) => startResize('right', event)}
              onKeyDown={(event) => nudgeWidth('right', event)}
            />
            <ChatPanel
              openView={openView}
              onCollapse={() =>
                setLayout((previous) => ({ ...previous, rightCollapsed: true }))
              }
            />
          </>
        )}
      </div>
    </div>
  )
}

function ResizeHandle({
  side,
  label,
  onPointerDown,
  onKeyDown,
}: {
  side: 'left' | 'right'
  label: string
  onPointerDown: (event: ReactPointerEvent<HTMLDivElement>) => void
  onKeyDown: (event: ReactKeyboardEvent<HTMLDivElement>) => void
}) {
  return (
    <div
      className={cx('resize-divider', `resize-divider-${side}`)}
      role="separator"
      aria-label={label}
      aria-orientation="vertical"
      tabIndex={0}
      onPointerDown={onPointerDown}
      onKeyDown={onKeyDown}
    >
      <span className="resize-line" />
    </div>
  )
}

function renderTab(
  tab: WorkspaceTab,
  context: {
    openView: OpenView
    closeTab: (id: string) => void
    setImmersive: (value: boolean) => void
    immersive: boolean
  },
): ReactNode {
  const { openView, closeTab, setImmersive, immersive } = context
  const id = tab.params?.id

  switch (tab.kind) {
    case 'home':
      return <HomeView openView={openView} />
    case 'capture':
      return <CaptureView openView={openView} />
    case 'cards':
      return <CardsView openView={openView} />
    case 'card':
      return id ? (
        <CardDetailView assetId={id} openView={openView} />
      ) : (
        <MissingTarget openView={openView} label="Card" />
      )
    case 'dossiers':
      return <DossiersView openView={openView} />
    case 'dossier':
      return id ? (
        <DossierDetailView
          dossierId={id}
          immersive={immersive}
          onEnterImmersive={() => setImmersive(true)}
          onExitImmersive={() => setImmersive(false)}
          openView={openView}
        />
      ) : (
        <MissingTarget openView={openView} label="Dossier" />
      )
    case 'pages':
      return <PagesView openView={openView} />
    case 'page':
      return id ? (
        <PageReaderView
          pageId={id}
          openView={openView}
          onClose={() => closeTab(tab.id)}
        />
      ) : (
        <MissingTarget openView={openView} label="Page" />
      )
    case 'draft':
      return id ? (
        <DraftView draftId={id} openView={openView} />
      ) : (
        <MissingTarget openView={openView} label="Draft" />
      )
    case 'project-replay':
      return <PlaceholderView kind="project-replay" openView={openView} />
    case 'arsenal':
      return <PlaceholderView kind="arsenal" openView={openView} />
    default:
      return <HomeView openView={openView} />
  }
}

function MissingTarget({ label, openView }: { label: string; openView: OpenView }) {
  return (
    <div className="view-scroll">
      <div className="view-inner">
        <div className="missing-target">
          <Icon name="alert" size={20} />
          <h1>{label} reference missing</h1>
          <p>This tab was restored without a record identifier.</p>
          <button type="button" className="button primary" onClick={() => openView('home')}>
            Return to workbench
          </button>
        </div>
      </div>
    </div>
  )
}
