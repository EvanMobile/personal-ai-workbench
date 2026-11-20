import { Icon } from '../components/Icon'
import { EmptyState, MicroLabel, ViewHeader } from '../components/ui'
import type { OpenView } from '../types'

const content = {
  'project-replay': {
    eyebrow: 'Products / Project Replay',
    title: 'Project Replay',
    description: 'A timeline of decisions, context, and playable project histories.',
    emptyTitle: 'No projects yet',
    emptyDescription:
      'Project Replay has no projects in this workspace. Capture project context to begin building a replay.',
    action: 'Capture project context',
    module: 'PRJ_REPLAY',
    capabilities: ['Timeline reconstruction', 'Decision ledger', 'Context snapshots'],
  },
  arsenal: {
    eyebrow: 'Products / Personal Arsenal',
    title: 'Personal Arsenal',
    description: 'A working catalogue of tools, methods, and reusable operating knowledge.',
    emptyTitle: 'No tools catalogued yet',
    emptyDescription:
      'Personal Arsenal is waiting for its first entry. Capture a tool, method, or practice to seed the catalogue.',
    action: 'Capture an entry',
    module: 'ARSENAL',
    capabilities: ['Tool registry', 'Method cards', 'Reuse notes'],
  },
} as const

export function PlaceholderView({
  kind,
  openView,
}: {
  kind: 'project-replay' | 'arsenal'
  openView: OpenView
}) {
  const model = content[kind]

  return (
    <div className="view-scroll">
      <div className="view-inner">
        <ViewHeader eyebrow={model.eyebrow} title={model.title} description={model.description} />

        <div className="product-empty-layout">
          <div className="product-empty-main">
            <div className="blueprint-grid" aria-hidden="true">
              <span className="blueprint-cross">+</span>
              <span className="blueprint-cross blueprint-cross-br">+</span>
              <div className="blueprint-tag">MODULE // {model.module}</div>
            </div>
            <EmptyState
              icon={kind === 'project-replay' ? 'terminal' : 'layers'}
              title={model.emptyTitle}
              description={model.emptyDescription}
              action={
                <button
                  type="button"
                  className="button primary"
                  onClick={() => openView('capture')}
                >
                  <Icon name="bolt" size={13} /> {model.action}
                </button>
              }
            />
          </div>

          <aside className="product-spec">
            <div className="spec-head">
              <MicroLabel>Module spec</MicroLabel>
              <span className="spec-status">EMPTY</span>
            </div>
            <dl className="meta-list">
              <div>
                <dt>module</dt>
                <dd>{model.module}</dd>
              </div>
              <div>
                <dt>state</dt>
                <dd>Not configured</dd>
              </div>
              <div>
                <dt>phase</dt>
                <dd>P1.M1</dd>
              </div>
            </dl>
            <div className="spec-capabilities">
              <MicroLabel>Capabilities</MicroLabel>
              {model.capabilities.map((capability, index) => (
                <div className="spec-capability" key={capability}>
                  <span>{String(index + 1).padStart(2, '0')}</span>
                  <span>{capability}</span>
                  <span className="spec-pending">pending</span>
                </div>
              ))}
            </div>
          </aside>
        </div>
      </div>
    </div>
  )
}
