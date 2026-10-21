"use client"

import { useCallback, useEffect, useRef, useState } from "react"

import { ApiError } from "@/lib/api"

export interface AsyncState<T> {
  data: T | null
  error: unknown
  loading: boolean
  retry: () => void
}

export function useAsync<T>(
  fn: (signal: AbortSignal) => Promise<T>,
  deps: unknown[] = [],
): AsyncState<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [loading, setLoading] = useState(true)
  const [tick, setTick] = useState(0)
  const abortRef = useRef<AbortController | null>(null)

  const retry = useCallback(() => setTick((t) => t + 1), [])

  useEffect(() => {
    const ctrl = new AbortController()
    abortRef.current = ctrl
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reset for new deps
    setLoading(true)
    setError(null)
    fn(ctrl.signal)
      .then((v) => {
        if (!ctrl.signal.aborted) setData(v)
      })
      .catch((e) => {
        if (ctrl.signal.aborted) return
        // don't treat abort as error
        if (e instanceof DOMException && e.name === "AbortError") return
        setError(e)
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setLoading(false)
      })
    return () => ctrl.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick])

  return { data, error, loading, retry }
}

export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.toUserMessage()
  if (error instanceof Error) return error.message
  return String(error)
}

export function useCountdown(targetIso: string | null): string | null {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!targetIso) return
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [targetIso])
  if (!targetIso) return null
  const diff = new Date(targetIso).getTime() - now
  if (diff <= 0) return "due"
  const h = Math.floor(diff / 3600000)
  const m = Math.floor((diff % 3600000) / 60000)
  if (h > 24) return `${Math.floor(h / 24)}d ${h % 24}h`
  return `${h}h ${m}m`
}
