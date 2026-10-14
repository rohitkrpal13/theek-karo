"use client"

import { useEffect, useRef, useState, useCallback } from "react"

export type SSEEvent = {
  id?: string
  event?: string
  data: string
  retry?: number
}

export function useSSE(
  url: string | null,
  opts: { enabled?: boolean; withCredentials?: boolean } = {},
): { connected: boolean; lastEvent: SSEEvent | null; error: string | null; reconnect: () => void } {
  const [connected, setConnected] = useState(false)
  const [lastEvent, setLastEvent] = useState<SSEEvent | null>(null)
  const [error, setError] = useState<string | null>(null)
  const esRef = useRef<EventSource | null>(null)
  const retryRef = useRef<number>(0)

  const connect = useCallback(() => {
    if (!url || opts.enabled === false) return
    // EventSource not available in some test envs
    if (typeof window === "undefined" || typeof EventSource === "undefined") return

    const es = new EventSource(url, { withCredentials: !!opts.withCredentials })
    esRef.current = es

    es.onopen = (): void => {
      setConnected(true)
      setError(null)
      retryRef.current = 0
    }

    es.onmessage = (ev: MessageEvent<string>): void => {
      setLastEvent({ data: ev.data, event: "message", id: (ev as MessageEvent & { lastEventId?: string }).lastEventId })
    }

    es.onerror = (): void => {
      setConnected(false)
      setError("SSE disconnected")
      es.close()
      // exponential reconnect
      const delay = Math.min(1000 * 2 ** retryRef.current, 15000)
      retryRef.current += 1
      // eslint-disable-next-line react-hooks/immutability -- intentional recursive reconnect
      setTimeout(() => connect(), delay)
    }

    const onCustom = (e: MessageEvent<string>): void => {
      setLastEvent({ data: e.data, event: (e as unknown as { type: string }).type })
    }
    // listen to common civic events
    es.addEventListener("report.created", onCustom as EventListener)
    es.addEventListener("report.updated", onCustom as EventListener)
    es.addEventListener("case.assigned", onCustom as EventListener)
  }, [url, opts.enabled, opts.withCredentials])

  useEffect(() => {
    connect()
    return () => {
      esRef.current?.close()
      esRef.current = null
    }
  }, [connect])

  const reconnect = useCallback(() => {
    esRef.current?.close()
    retryRef.current = 0
    connect()
  }, [connect])

  return { connected, lastEvent, error, reconnect }
}

// Polling fallback when SSE not available (e.g., behind proxy)
export function useLivePoll<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  intervalMs = 8000,
  enabled = true,
): { data: T | null; updatedAt: number | null; error: unknown } {
  const [data, setData] = useState<T | null>(null)
  const [updatedAt, setUpdatedAt] = useState<number | null>(null)
  const [error, setError] = useState<unknown>(null)

  useEffect(() => {
    if (!enabled) return
    let cancelled = false
    let timer: number | undefined

    const tick = async (): Promise<void> => {
      const ctrl = new AbortController()
      try {
        const v = await fetcher(ctrl.signal)
        if (!cancelled) {
          setData(v)
          setUpdatedAt(Date.now())
          setError(null)
        }
      } catch (e) {
        if ((e as DOMException)?.name === "AbortError") return
        if (!cancelled) setError(e)
      }
      if (!cancelled) timer = window.setTimeout(tick, intervalMs)
    }

    void tick()
    const onVis = (): void => {
      if (document.visibilityState === "visible") void tick()
    }
    document.addEventListener("visibilitychange", onVis)
    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
      document.removeEventListener("visibilitychange", onVis)
    }
  }, [fetcher, intervalMs, enabled])

  return { data, updatedAt, error }
}
