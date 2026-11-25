import type { RagRunStatus } from './types'

export const RUN_TERMINAL_STATUSES: ReadonlySet<RagRunStatus> = new Set([
  'succeeded',
  'partial',
  'failed',
  'cancelled',
  'skipped',
])

export function isTerminalRun(status: RagRunStatus): boolean {
  return RUN_TERMINAL_STATUSES.has(status)
}

/** Running jobs poll quickly; queued/idle runs poll conservatively. */
export function runPollingDelay(status: RagRunStatus): number {
  return status === 'running' ? 1000 : 5000
}

export function pollingBackoff(consecutiveFailures: number): number {
  return Math.min(30_000, 2000 * 2 ** Math.max(0, consecutiveFailures - 1))
}
