import { useState } from 'react'
import type { OpenView, ViewKind, WorkspaceTab } from '../types'
import { cx } from '../utils'
import { Icon, type IconName } from './Icon'
import { MicroLabel } from './ui'
import { useI18n } from '../i18n'

interface ContextTreeProps {
  activeTab: WorkspaceTab | null
  openView: OpenView
  apiStatus: 'checking' | 'online' | 'offline'
}

function activeClass(activeTab: WorkspaceTab | null, kind: ViewKind): string {
  return activeTab?.kind === kind ? 'tree-row tree-row-active' : 'tree-row'
}

export function ContextTree({ activeTab, openView, apiStatus }: ContextTreeProps) {
  const { t } = useI18n()
  const [replayOpen, setReplayOpen] = useState(false)
  const [arsenalOpen, setArsenalOpen] = useState(false)
  const [wikiOpen, setWikiOpen] = useState(true)

  const openProduct = (kind: 'project-replay' | 'arsenal', title: string) => {
    openView(kind, undefined, title)
  }

  const openWikiRoot = () => {
    setWikiOpen(true)
    openView('dossiers', undefined, t('nav.dossiers'))
  }

  return (
    <aside className="context-panel" aria-label={t('nav.contextDirectory')}>
      <div className="panel-head">
        <MicroLabel>{t('nav.contextDirectory')}</MicroLabel>
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
          <span className="tree-label">{t('nav.workbench')}</span>
          <span className="tree-root-badge">{t('nav.root')}</span>
        </button>

        <div className="tree-children">
          <button type="button" className="tree-row tree-row-sub" onClick={() => openView('home')}>
            <span className="tree-indent" />
            <span className="tree-icon">
              <Icon name="grid" size={13} />
            </span>
            <span className="tree-label">{t('nav.overview')}</span>
          </button>

          <div className="tree-group">
            <div className="tree-row tree-row-product">
              <button
                type="button"
                className="tree-chevron-button"
                aria-label={replayOpen ? t('nav.collapseReplay') : t('nav.expandReplay')}
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
                  openProduct('project-replay', t('nav.projectReplay'))
                }}
              >
                <span className="tree-icon">
                  <Icon name="terminal" size={13} />
                </span>
                <span className="tree-label">{t('nav.projectReplay')}</span>
                <span className="tree-count">0</span>
              </button>
            </div>
            {replayOpen && (
              <div className="tree-empty-row">
                <span className="tree-branch">└</span>
                <span>{t('nav.noProjects')}</span>
              </div>
            )}
          </div>

          <div className="tree-group">
            <div className="tree-row tree-row-product">
              <button
                type="button"
                className="tree-chevron-button"
                aria-label={arsenalOpen ? t('nav.collapseArsenal') : t('nav.expandArsenal')}
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
                  openProduct('arsenal', t('nav.personalArsenal'))
                }}
              >
                <span className="tree-icon">
                  <Icon name="layers" size={13} />
                </span>
                <span className="tree-label">{t('nav.personalArsenal')}</span>
                <span className="tree-count">0</span>
              </button>
            </div>
            {arsenalOpen && (
              <div className="tree-empty-row">
                <span className="tree-branch">└</span>
                <span>{t('nav.noTools')}</span>
              </div>
            )}
          </div>

          <div className="tree-group">
            <div className="tree-row tree-row-product">
              <button
                type="button"
                className="tree-chevron-button"
                aria-label={wikiOpen ? t('nav.collapseWiki') : t('nav.expandWiki')}
                aria-expanded={wikiOpen}
                onClick={() => setWikiOpen((value) => !value)}
              >
                <Icon name={wikiOpen ? 'chevron-down' : 'chevron-right'} size={11} />
              </button>
              <button
                type="button"
                className="tree-product-label"
                onClick={openWikiRoot}
                title={t('nav.openWiki')}
              >
                <span className="tree-icon">
                  <Icon name="book" size={13} />
                </span>
                <span className="tree-label">{t('nav.personalWiki')}</span>
              </button>
            </div>

            {wikiOpen && (
              <div className="tree-subtree">
                <TreeLeaf
                  icon="folder"
                  label={t('nav.dossiers')}
                  active={activeTab?.kind === 'dossiers' || activeTab?.kind === 'dossier'}
                  onClick={() => openView('dossiers')}
                />
                <TreeLeaf
                  icon="layers"
                  label={t('nav.cards')}
                  active={activeTab?.kind === 'cards' || activeTab?.kind === 'card'}
                  onClick={() => openView('cards')}
                />
                <TreeLeaf
                  icon="page"
                  label={t('nav.pages')}
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
            <span className="tree-label">{t('nav.capture')}</span>
            <span className="shortcut-hint">⌘N</span>
          </button>
        </div>
      </div>

      <div className="context-footer">
        <div className="context-footer-row">
          <span className="micro-label">{t('nav.session')}</span>
          <span className="session-id">{t('nav.local')}</span>
        </div>
        <div className="context-footer-row">
          <span className={cx('api-dot', `api-dot-${apiStatus}`)} />
          <span className="context-status">
            {apiStatus === 'online' ? t('nav.apiConnected') : apiStatus === 'offline' ? t('nav.apiOffline') : t('nav.apiChecking')}
          </span>
          <Icon name="database" size={12} className="context-db-icon" />
        </div>
        <div className="context-footer-meta">{t('nav.phase')}</div>
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
