import { useState } from 'react'
import type { OpenView, ViewKind, WorkspaceTab } from '../types'
import { cx } from '../utils'
import { Icon, type IconName } from './Icon'
import { MicroLabel } from './ui'

interface ContextTreeProps {
  activeTab: WorkspaceTab | null
  openView: OpenView
  apiStatus: 'checking' | 'online' | 'offline'
}

function activeClass(activeTab: WorkspaceTab | null, kind: ViewKind): string {
  return activeTab?.kind === kind ? 'tree-row tree-row-active' : 'tree-row'
}

export function ContextTree({ activeTab, openView, apiStatus }: ContextTreeProps) {
  const [replayOpen, setReplayOpen] = useState(false)
  const [arsenalOpen, setArsenalOpen] = useState(false)
  const [wikiOpen, setWikiOpen] = useState(true)

  const openProduct = (kind: 'project-replay' | 'arsenal', title: string) => {
    openView(kind, undefined, title)
  }

  const openWikiRoot = () => {
    setWikiOpen(true)
    openView('dossiers', undefined, 'Dossiers')
  }

  return (
    <aside className="context-panel" aria-label="Context directory">
      <div className="panel-head">
        <MicroLabel>Context directory</MicroLabel>
        <span className="panel-head-mark">CTX</span>
      </div>

      <div className="tree-root">
        <button
          type="button"
          className={cx('tree-row', 'tree-row-root', activeTab?.kind === 'home' && 'tree-row-active')}
          onClick={() => openView('home')}
        >
          <span className="tree-chevron">
            <Icon name="chevron-down" size={11} />
          </span>
          <span className="tree-icon tree-icon-accent">
            <Icon name="workbench" size={15} />
          </span>
          <span className="tree-label">Workbench</span>
          <span className="tree-root-badge">ROOT</span>
        </button>

        <div className="tree-children">
          <button type="button" className="tree-row tree-row-sub" onClick={() => openView('home')}>
            <span className="tree-indent" />
            <span className="tree-icon">
              <Icon name="grid" size={13} />
            </span>
            <span className="tree-label">Overview</span>
          </button>

          <div className="tree-group">
            <div className="tree-row tree-row-product">
              <button
                type="button"
                className="tree-chevron-button"
                aria-label={replayOpen ? 'Collapse Project Replay' : 'Expand Project Replay'}
                aria-expanded={replayOpen}
                onClick={() => setReplayOpen((value) => !value)}
              >
                <Icon name={replayOpen ? 'chevron-down' : 'chevron-right'} size={11} />
              </button>
              <button
                type="button"
                className={cx('tree-product-label', activeTab?.kind === 'project-replay' && 'active')}
                onClick={() => {
                  setReplayOpen(true)
                  openProduct('project-replay', 'Project Replay')
                }}
              >
                <span className="tree-icon">
                  <Icon name="terminal" size={13} />
                </span>
                <span className="tree-label">Project Replay</span>
                <span className="tree-count">0</span>
              </button>
            </div>
            {replayOpen && (
              <div className="tree-empty-row">
                <span className="tree-branch">└</span>
                <span>No projects yet</span>
              </div>
            )}
          </div>

          <div className="tree-group">
            <div className="tree-row tree-row-product">
              <button
                type="button"
                className="tree-chevron-button"
                aria-label={arsenalOpen ? 'Collapse Personal Arsenal' : 'Expand Personal Arsenal'}
                aria-expanded={arsenalOpen}
                onClick={() => setArsenalOpen((value) => !value)}
              >
                <Icon name={arsenalOpen ? 'chevron-down' : 'chevron-right'} size={11} />
              </button>
              <button
                type="button"
                className={cx('tree-product-label', activeTab?.kind === 'arsenal' && 'active')}
                onClick={() => {
                  setArsenalOpen(true)
                  openProduct('arsenal', 'Personal Arsenal')
                }}
              >
                <span className="tree-icon">
                  <Icon name="layers" size={13} />
                </span>
                <span className="tree-label">Personal Arsenal</span>
                <span className="tree-count">0</span>
              </button>
            </div>
            {arsenalOpen && (
              <div className="tree-empty-row">
                <span className="tree-branch">└</span>
                <span>No tools catalogued yet</span>
              </div>
            )}
          </div>

          <div className="tree-group">
            <div className="tree-row tree-row-product">
              <button
                type="button"
                className="tree-chevron-button"
                aria-label={wikiOpen ? 'Collapse Personal LLM Wiki' : 'Expand Personal LLM Wiki'}
                aria-expanded={wikiOpen}
                onClick={() => setWikiOpen((value) => !value)}
              >
                <Icon name={wikiOpen ? 'chevron-down' : 'chevron-right'} size={11} />
              </button>
              <button
                type="button"
                className="tree-product-label"
                onClick={openWikiRoot}
                title="Open knowledge base"
              >
                <span className="tree-icon">
                  <Icon name="book" size={13} />
                </span>
                <span className="tree-label">Personal LLM Wiki</span>
              </button>
            </div>

            {wikiOpen && (
              <div className="tree-subtree">
                <TreeLeaf
                  icon="folder"
                  label="Dossiers"
                  active={activeTab?.kind === 'dossiers' || activeTab?.kind === 'dossier'}
                  onClick={() => openView('dossiers')}
                />
                <TreeLeaf
                  icon="layers"
                  label="Cards"
                  active={activeTab?.kind === 'cards' || activeTab?.kind === 'card'}
                  onClick={() => openView('cards')}
                />
                <TreeLeaf
                  icon="page"
                  label="Pages"
                  active={activeTab?.kind === 'pages' || activeTab?.kind === 'page'}
                  onClick={() => openView('pages')}
                />
              </div>
            )}
          </div>

          <div className="tree-divider" />

          <button
            type="button"
            className={cx(activeClass(activeTab, 'capture'), 'tree-capture')}
            onClick={() => openView('capture')}
          >
            <span className="tree-indent" />
            <span className="tree-icon tree-icon-capture">
              <Icon name="bolt" size={13} />
            </span>
            <span className="tree-label">Capture</span>
            <span className="shortcut-hint">⌘N</span>
          </button>
        </div>
      </div>

      <div className="context-footer">
        <div className="context-footer-row">
          <span className="micro-label">Session</span>
          <span className="session-id">LOCAL</span>
        </div>
        <div className="context-footer-row">
          <span className={cx('api-dot', `api-dot-${apiStatus}`)} />
          <span className="context-status">
            {apiStatus === 'online' ? 'API connected' : apiStatus === 'offline' ? 'API offline' : 'Checking API…'}
          </span>
          <Icon name="database" size={12} className="context-db-icon" />
        </div>
        <div className="context-footer-meta">P1.M1 · CONTEXT ENGINE</div>
      </div>
    </aside>
  )
}

function TreeLeaf({
  icon,
  label,
  active,
  onClick,
}: {
  icon: IconName
  label: string
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      className={cx('tree-row', 'tree-row-leaf', active && 'tree-row-active')}
      onClick={onClick}
    >
      <span className="tree-branch">├</span>
      <span className="tree-icon">
        <Icon name={icon} size={12} />
      </span>
      <span className="tree-label">{label}</span>
    </button>
  )
}
