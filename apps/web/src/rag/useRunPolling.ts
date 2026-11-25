import { useEffect, useRef, useState } from 'react'
import { useI18n } from '../i18n'
import { ragApi, ragErrorMessage } from './api'
import { isTerminalRun, pollingBackoff, runPollingDelay } from './polling'
import type { RagEvent, RagRunDetail } from './types'

interface RunPollingState {
  data: RagRunDetail | null
  events: RagEvent[]
  loading: boolean
  error: string | null
  polling: boolean
  reload: () => void
}

async function loadAllEvents(runId: string, signal: AbortSignal): Promise<RagEvent[]> {
  const collected: RagEvent[] = []
  let afterId = 0
  for (;;) {
    const page = await ragApi.runEvents(runId, afterId, signal)
    collected.push(...page.items)
    if (!page.has_more || page.next_after_id === afterId || collected.length >= 2000) {
      return collected
    }
    afterId = page.next_after_id
  }
}

export function useRunPolling(runId: string | undefined): RunPollingState {
  const { t } = useI18n()
  const [data, setData] = useState<RagRunDetail | null>(null)
  const [events, setEvents] = useState<RagEvent[]>([])
  const [loading, setLoading] = useState(Boolean(runId))
  const [error, setError] = useState<string | null>(null)
  const [polling, setPolling] = useState(false)
  const [revision, setRevision] = useState(0)
  const failures = useRef(0)

  useEffect(() => {
    if (!runId) {
      setLoading(false)
      setPolling(false)
      return
    }
    failures.current = 0
    let cancelled = false
    let timer: number | undefined
    let controller: AbortController | null = null

    const schedule = (delay: number) => {
      if (cancelled) return
      timer = window.setTimeout(() => void load(), delay)
    }

    const load = async () => {
      controller?.abort()
      controller = new AbortController()
      try {
        const [detail, eventItems] = await Promise.all([
          ragApi.run(runId, controller.signal),
          loadAllEvents(runId, controller.signal),
        ])
        if (cancelled) return
        setData(detail)
        setEvents(eventItems)
        setError(null)
        setLoading(false)
        failures.current = 0
        const terminal = isTerminalRun(detail.run.status)
        setPolling(!terminal)
        if (!terminal) schedule(runPollingDelay(detail.run.status))
      } catch (caught) {
        if (cancelled) return
        if (caught instanceof DOMException && caught.name === 'AbortError') return
        failures.current += 1
        setError(ragErrorMessage(caught, t))
        setLoading(false)
        setPolling(true)
        schedule(pollingBackoff(failures.current))
      }
    }

    setLoading(true)
    setError(null)
    setPolling(true)
    void load()

    return () => {
      cancelled = true
      if (timer) window.clearTimeout(timer)
      controller?.abort()
    }
  }, [runId, revision, t])

  return {
    data,
    events,
    loading,
    error,
    polling,
    reload: () => setRevision((value) => value + 1),
  }
}
