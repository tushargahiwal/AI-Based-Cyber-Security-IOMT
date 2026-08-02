import { useEffect, useState, useCallback } from 'react'

/**
 * Runs an async fetcher on mount (and whenever deps change), exposing
 * { data, loading, error, reload }. Designed to fail soft: if the backend
 * endpoint isn't wired up yet, `error` is set instead of throwing.
 */
export default function useApi(fetcher, deps = [], initialData = null) {
  const [data, setData] = useState(initialData)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)

  const reload = useCallback(() => setReloadKey((k) => k + 1), [])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    fetcher()
      .then((res) => {
        if (!cancelled) setData(res?.data ?? res)
      })
      .catch((err) => {
        if (!cancelled) setError(err)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, reloadKey])

  return { data, loading, error, reload }
}
