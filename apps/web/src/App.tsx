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
import { LanguageSwitcher } from './components/LanguageSwitcher'
import { TabStrip } from './components/TabStrip'
import { useToast } from './components/Toast'
import { useI18n } from './i18n'
import type { MessageKey } from './i18n/messages'
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
import { RagDossiersView } from './views/rag/RagDossiersView'
import { RagDossierView } from './views/rag/RagDossierView'
import { RagRunView } from './views/rag/RagRunView'

const TAB_STORAGE_KEY = 'paw.workspace.tabs.v1'
const LAYOUT_STORAGE_KEY = 'paw.workspace.layout.v1'
const ACTIVE_STORAGE_KEY = 'paw.workspace.active.v1'

const HOME_TAB: WorkspaceTab = {
  id: 'home',
  kind: 'home',
  title: '',
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
  'rag-dossiers',
  'rag-dossier',
  'rag-run',
  'project-replay',
  'arsenal',
])

const SINGLETON_VIEWS = new Set<ViewKind>([
  'home',
  'capture',
  'cards',
  'dossiers',
  'pages',
  'rag-dossiers',
  'project-replay',
  'arsenal',
])

function defaultTitle(
  kind: ViewKind,
  params: ViewParams | undefined,
  t: (key: MessageKey) => string,
): string {
  if (params?.title) return params.title
  switch (kind) {
    case 'home':
      return t('tabs.workbench')
    case 'capture':
      return t('tabs.capture')
    case 'cards':
      return t('tabs.cards')
    case 'card':
      return t('tabs.card')
    case 'dossiers':
      return t('tabs.dossiers')
    case 'dossier':
      return t('tabs.dossier')
    case 'pages':
      return t('tabs.pages')
    case 'page':
      return params?.title ? `${t('tabs.page')} · ${params.title}` : t('tabs.page')
    case 'draft':
      return t('tabs.draft')
    case 'rag-dossiers':
      return t('tabs.ragDossiers')
    case 'rag-dossier':
      return t('tabs.ragDossier')
    case 'rag-run':
      return t('tabs.ragRun')
    case 'project-replay':
      return t('tabs.projectReplay')
    case 'arsenal':
      return t('tabs.arsenal')
    default:
      return t('tabs.untitled')
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
  const { locale, t } = useI18n()
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

  const tabTitle = (tab: WorkspaceTab): string => {
    switch (tab.kind) {
      case 'home':
        return t('tabs.workbench')
      case 'capture':
        return t('tabs.capture')
      case 'cards':
        return t('tabs.cards')
      case 'dossiers':
        return t('tabs.dossiers')
      case 'pages':
        return t('tabs.pages')
      case 'draft':
        return t('tabs.draft')
      case 'rag-dossiers':
        return t('tabs.ragDossiers')
      case 'rag-dossier':
        return tab.title || t('tabs.ragDossier')
      case 'rag-run':
        return t('tabs.ragRun')
      case 'project-replay':
        return t('tabs.projectReplay')
      case 'arsenal':
        return t('tabs.arsenal')
      case 'card':
        return tab.title || t('tabs.card')
      case 'dossier':
        return tab.title || t('tabs.dossier')
      case 'page':
        return tab.title || t('tabs.page')
      default:
        return tab.title || t('tabs.untitled')
    }
  }
  const displayTabs = tabs.map((tab) => ({ ...tab, title: tabTitle(tab) }))

  useEffect(() => {
    document.title = activeTab ? `${tabTitle(activeTab)} · Personal AI Workbench` : 'Personal AI Workbench'
    // tabTitle is derived from the active tab and current locale.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, locale])

  const checkApi = useCallback(async (quiet = false) => {
    if (!quiet) setApiStatus('checking')
    try {
      const health = await api.health()
      if (health.status !== 'ok') throw new Error(t('app.healthError'))
      setApiStatus('online')
    } catch {
      setApiStatus('offline')
    }
  }, [t])

  useEffect(() => {
    void checkApi()
    const timer = window.setInterval(() => void checkApi(true), 30000)
    return () => window.clearInterval(timer)
  }, [checkApi])

  const openView = useCallback<OpenView>((kind, params, title) => {
    const id = viewTabId(kind, params)
    const resolvedTitle = title?.trim() || defaultTitle(kind, params, t)
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
  }, [t])

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
              title: t('tabs.pages'),
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
    [activeId, tabs, t],
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
      notify(t('app.sessionRestored'), 'info')
    }
  }, [boot.tabs.length, notify, t])

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
              <span>{t('app.tagline')}</span>
            </div>
          </div>
          <div className="brand-center" aria-hidden="true">
            <span className="brand-rule" />
            <span className="brand-env">{t('app.workspaceActive')}</span>
            <span className="brand-rule" />
          </div>
          <div className="brand-actions">
            <LanguageSwitcher />
            <button
              type="button"
              className={cx('api-pill', `api-pill-${apiStatus}`)}
              onClick={() => void checkApi()}
              title={t('app.checkApi')}
            >
              <span className={cx('api-dot', `api-dot-${apiStatus}`)} />
              {apiStatus === 'online'
                ? t('app.apiOnline')
                : apiStatus === 'offline'
                  ? t('app.apiOffline')
                  : t('app.apiChecking')}
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
              title={layout.rightCollapsed ? t('app.openChat') : t('app.collapseChat')}
              aria-label={layout.rightCollapsed ? t('app.openChat') : t('app.collapseChat')}
              aria-pressed={!layout.rightCollapsed}
            >
              <Icon name="panel-right" size={14} />
            </button>
          </div>
        </div>

        <div className="editor-bar">
          <TabStrip
            tabs={displayTabs}
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
                <Icon name="maximize" size={10} /> {t('app.focusMode')}
              </span>
            )}
            <span className="editor-hint">
              <span className="kbd">⌘</span>{t('app.captureShortcut')}
            </span>
            <span className="editor-hint">
              <span className="kbd">⌘</span>{t('app.chatShortcut')}
            </span>
          </div>
        </div>
      </header>

      {apiStatus === 'offline' && (
        <div className="offline-banner" role="alert">
          <div className="offline-left">
            <Icon name="alert" size={14} />
            <span>
              {t('app.offlineBody', { url: '127.0.0.1:8000' })}
            </span>
          </div>
          <button type="button" className="button small ghost" onClick={() => void checkApi()}>
            <Icon name="refresh" size={12} /> {t('common.retry')}
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
              label={t('app.resizeContext')}
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
              label={t('app.resizeChat')}
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
        <MissingTarget openView={openView} kind="card" />
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
        <MissingTarget openView={openView} kind="dossier" />
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
        <MissingTarget openView={openView} kind="page" />
      )
    case 'draft':
      return id ? (
        <DraftView draftId={id} openView={openView} />
      ) : (
        <MissingTarget openView={openView} kind="draft" />
      )
    case 'rag-dossiers':
      return <RagDossiersView openView={openView} />
    case 'rag-dossier':
      return id ? (
        <RagDossierView dossierId={id} openView={openView} />
      ) : (
        <MissingTarget openView={openView} kind="rag-dossier" />
      )
    case 'rag-run':
      return id ? (
        <RagRunView runId={id} openView={openView} />
      ) : (
        <MissingTarget openView={openView} kind="rag-run" />
      )
    case 'project-replay':
      return <PlaceholderView kind="project-replay" openView={openView} />
    case 'arsenal':
      return <PlaceholderView kind="arsenal" openView={openView} />
    default:
      return <HomeView openView={openView} />
  }
}

function MissingTarget({
  kind,
  openView,
}: {
  kind: 'card' | 'dossier' | 'page' | 'draft' | 'rag-dossier' | 'rag-run'
  openView: OpenView
}) {
  const { t } = useI18n()
  const labelKeys = {
    card: 'tabs.card',
    dossier: 'tabs.dossier',
    page: 'tabs.page',
    draft: 'tabs.draft',
    'rag-dossier': 'tabs.ragDossier',
    'rag-run': 'tabs.ragRun',
  } as const
  return (
    <div className="view-scroll">
      <div className="view-inner">
        <div className="missing-target">
          <Icon name="alert" size={20} />
          <h1>{t('app.missingTarget', { label: t(labelKeys[kind]) })}</h1>
          <p>{t('app.pageMissingBody')}</p>
          <button type="button" className="button primary" onClick={() => openView('home')}>
            {t('app.returnWorkbench')}
          </button>
        </div>
      </div>
    </div>
  )
}
