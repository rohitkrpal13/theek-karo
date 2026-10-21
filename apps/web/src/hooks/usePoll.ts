"use client"

import { useCallback, useEffect, useRef, useState } from "react"

export function usePoll<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  intervalMs = 15000,
  enabled = true,
): { data: T | null; error: unknown; loading: boolean; refresh: () => void; lastUpdated: Date | null } {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [loading, setLoading] = useState(true)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const tick = useCallback(async () => {
    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl
    try {
      const v = await fetcher(ctrl.signal)
      if (!ctrl.signal.aborted) {
        setData(v)
        setError(null)
        setLastUpdated(new Date())
      }
    } catch (e) {
      if ((e as DOMException)?.name === "AbortError") return
      setError(e)
    } finally {
      if (!ctrl.signal.aborted) setLoading(false)
    }
  }, [fetcher])

  const refresh = useCallback(() => {
    setLoading(true)
    void tick()
  }, [tick])

  useEffect(() => {
    if (!enabled) return
    // eslint-disable-next-line react-hooks/set-state-in-effect -- polling initial fetch
    void tick()
    const id = setInterval(() => void tick(), intervalMs)
    const onVis = (): void => {
      if (document.visibilityState === "visible") void tick()
    }
    document.addEventListener("visibilitychange", onVis)
    return () => {
      clearInterval(id)
      document.removeEventListener("visibilitychange", onVis)
      abortRef.current?.abort()
    }
  }, [enabled, intervalMs, tick])

  return { data, error, loading, refresh, lastUpdated }
}
