import assert from 'node:assert/strict'
import test from 'node:test'
import {
  isTerminalRun,
  pollingBackoff,
  runPollingDelay,
} from '../src/rag/polling.ts'

test('terminal run statuses stop polling', () => {
  for (const status of ['succeeded', 'partial', 'failed', 'cancelled', 'skipped']) {
    assert.equal(isTerminalRun(status), true, status)
  }
  for (const status of ['queued', 'running']) {
    assert.equal(isTerminalRun(status), false, status)
  }
})

test('polling cadence is active 1s and idle 5s', () => {
  assert.equal(runPollingDelay('running'), 1000)
  assert.equal(runPollingDelay('queued'), 5000)
})

test('polling errors use bounded exponential backoff', () => {
  assert.equal(pollingBackoff(1), 2000)
  assert.equal(pollingBackoff(2), 4000)
  assert.equal(pollingBackoff(3), 8000)
  assert.equal(pollingBackoff(10), 30000)
})
