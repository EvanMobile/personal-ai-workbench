import type { ViewKind, WorkspaceTab } from '../types'
import { cx } from '../utils'
import { Icon, type IconName } from './Icon'
import { useI18n } from '../i18n'

const kindIcon: Record<ViewKind, IconName> = {
  home: 'grid',
  capture: 'bolt',
  cards: 'layers',
  card: 'image',
  dossiers: 'folder',
  dossier: 'folder-open',
  pages: 'book',
  page: 'page',
  draft: 'file',
  'project-replay': 'terminal',
  arsenal: 'layers',
}

interface TabStripProps {
  tabs: WorkspaceTab[]
  activeId: string
  onSelect: (id: string) => void
  onClose: (id: string) => void
  onNewCapture: () => void
}

export function TabStrip({ tabs, activeId, onSelect, onClose, onNewCapture }: TabStripProps) {
  const { t } = useI18n()
  return (
    <div className="tab-strip-wrap">
      <div className="tab-strip" role="tablist" aria-label={t('tabs.openTabs')}>
        {tabs.map((tab) => {
          const active = tab.id === activeId
          return (
            <div
              key={tab.id}
              className={cx('editor-tab', active && 'editor-tab-active')}
              role="presentation"
            >
              <button
                type="button"
                className="editor-tab-main"
                role="tab"
                aria-selected={active}
                title={tab.title}
                onClick={() => onSelect(tab.id)}
              >
                <Icon name={kindIcon[tab.kind]} size={12} className="tab-icon" />
                <span className="editor-tab-title">{tab.title}</span>
              </button>
              {tab.closable && (
                <button
                  type="button"
                  className="editor-tab-close"
                  aria-label={t('tabs.close', { title: tab.title })}
                  onClick={(event) => {
                    event.stopPropagation()
                    onClose(tab.id)
                  }}
                >
                  <Icon name="x" size={10} />
                </button>
              )}
            </div>
          )
        })}
      </div>
      <button
        type="button"
        className="tab-add"
        onClick={onNewCapture}
        title={t('tabs.newCapture')}
        aria-label={t('tabs.newCapture')}
      >
        <Icon name="plus" size={13} />
      </button>
    </div>
  )
}
