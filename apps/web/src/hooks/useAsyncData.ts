import { useCallback, useEffect, useState, type Dispatch, type SetStateAction } from 'react'
import { errorMessage } from '../api'

interface AsyncState<T> {
  data: T | null
  loading: boolean
  error: string | null
  reload: () => void
  setData: Dispatch<SetStateAction<T | null>>
}

/**
 * Small fetch lifecycle helper. `key` should contain every value that changes
 * the request (for example, a record id).
 */
export function useAsyncData<T>(
  load: (signal: AbortSignal) => Promise<T>,
  key: readonly unknown[] = [],
): AsyncState<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [revision, setRevision] = useState(0)

  const reload = useCallback(() => setRevision((value) => value + 1), [])

  useEffect(() => {
    const controller = new AbortController()
    let active = true
    setLoading(true)
    setError(null)

    load(controller.signal)
      .then((payload) => {
        if (!active) return
        setData(payload)
        setLoading(false)
      })
      .catch((caught: unknown) => {
        if (!active) return
        if (caught instanceof DOMException && caught.name === 'AbortError') return
        setError(errorMessage(caught))
        setLoading(false)
      })

    return () => {
      active = false
      controller.abort()
    }
    // The caller supplies the request identity through `key`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [revision, ...key])

  return { data, loading, error, reload, setData }
}
