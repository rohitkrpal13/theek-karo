"use client"

/**
 * Modern SWR-like cache: stale-while-revalidate, deduplication, persistence.
 * Zero deps, works with the modern fetch client (ApiError, abort).
 */
import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react"

type CacheEntry<T> = {
  data: T | null
  error: unknown
  timestamp: number
  promise?: Promise<T>
}

const memory = new Map<string, CacheEntry<unknown>>()
const listeners = new Map<string, Set<() => void>>()
const PERSIST_PREFIX = "tk_cache_v2:"
const TTL_MS = 5 * 60 * 1000 // 5min default
const STALE_MS = 30 * 1000 // revalidate after 30s

function persistKey(key: string): string {
  return PERSIST_PREFIX + key
}

function loadPersisted<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(persistKey(key))
    if (!raw) return null
    const parsed = JSON.parse(raw) as { data: T; ts: number }
    if (Date.now() - parsed.ts > TTL_MS) {
      localStorage.removeItem(persistKey(key))
      return null
    }
    return parsed.data
  } catch {
    return null
  }
}

function savePersisted<T>(key: string, data: T): void {
  try {
    localStorage.setItem(persistKey(key), JSON.stringify({ data, ts: Date.now() }))
  } catch {}
}

function notify(key: string): void {
  listeners.get(key)?.forEach((fn) => fn())
}

export interface SWROptions {
  ttlMs?: number
  staleMs?: number
  persist?: boolean
  dedupe?: boolean
  revalidateOnFocus?: boolean
}

export function getCache<T>(key: string): T | null {
  const entry = memory.get(key) as CacheEntry<T> | undefined
  if (entry?.data) return entry.data
  return null
}

export function setCache<T>(key: string, data: T, opts: SWROptions = {}): void {
  memory.set(key, { data, error: null, timestamp: Date.now() })
  if (opts.persist) savePersisted(key, data)
  notify(key)
}

export function mutate<T>(key: string, data: T | null, opts: SWROptions = {}): void {
  if (data === null) {
    memory.delete(key)
    try {
      localStorage.removeItem(persistKey(key))
    } catch {}
  } else {
    setCache(key, data, opts)
  }
}

export async function fetchWithCache<T>(
  key: string,
  fetcher: (signal: AbortSignal) => Promise<T>,
  opts: SWROptions = {},
): Promise<T> {
  const ttlMs = opts.ttlMs ?? TTL_MS
  const staleMs = opts.staleMs ?? STALE_MS
  const now = Date.now()
  const existing = memory.get(key) as CacheEntry<T> | undefined

  // dedupe in-flight
  if (opts.dedupe !== false && existing?.promise) {
    return existing.promise
  }

  const shouldRevalidate = !existing || now - existing.timestamp > staleMs
  const isExpired = !existing || now - existing.timestamp > ttlMs

  // try persisted hydration
  if (!existing && opts.persist) {
    const persisted = loadPersisted<T>(key)
    if (persisted) {
      memory.set(key, { data: persisted, error: null, timestamp: now - staleMs + 2000 })
    }
  }

  // if we have fresh data and not stale, return it without revalidation
  if (existing?.data && !shouldRevalidate && !isExpired) {
    return existing.data
  }

  // stale-while-revalidate: return stale immediately, revalidate in background if stale
  if (existing?.data && !isExpired && !shouldRevalidate) {
    return existing.data
  }

  // need fetch
  const controller = new AbortController()
  const promise = fetcher(controller.signal)
    .then((data) => {
      memory.set(key, { data, error: null, timestamp: Date.now() })
      if (opts.persist) savePersisted(key, data)
      notify(key)
      return data
    })
    .catch((err) => {
      // keep stale on error
      const prev = memory.get(key) as CacheEntry<T> | undefined
      memory.set(key, { data: prev?.data ?? null, error: err, timestamp: prev?.timestamp ?? now })
      notify(key)
      throw err
    })
    .finally(() => {
      const e = memory.get(key) as CacheEntry<T> | undefined
      if (e) delete e.promise
    })

  // store promise for dedupe
  const entry: CacheEntry<T> = {
    data: existing?.data ?? null,
    error: existing?.error ?? null,
    timestamp: existing?.timestamp ?? now,
    promise,
  }
  memory.set(key, entry as CacheEntry<unknown>)

  // if we have stale data, don't await revalidation — caller gets stale via hook
  if (existing?.data && !isExpired) {
    // fire and forget revalidation
    void promise.catch(() => {})
    return existing.data
  }

  return promise
}

/**
 * React hook: useSWR-like
 * - returns data/error/loading + mutate + revalidate
 * - subscribes to global cache updates
 * - revalidates on mount, on focus (optional), and when key changes
 */
export function useCache<T>(
  key: string | null,
  fetcher: ((signal: AbortSignal) => Promise<T>) | null,
  opts: SWROptions = {},
): {
  data: T | null
  error: unknown
  loading: boolean
  mutate: (data: T | null) => void
  revalidate: () => Promise<void>
} {
  const subscribe = useCallback(
    (cb: () => void) => {
      if (!key) return (): void => undefined
      let set = listeners.get(key)
      if (!set) {
        set = new Set()
        listeners.set(key, set)
      }
      set.add(cb)
      return () => {
        set!.delete(cb)
        if (set!.size === 0) listeners.delete(key)
      }
    },
    [key],
  )

  const getSnapshot = useCallback((): CacheEntry<T> | null => {
    if (!key) return null
    // hydrate from persisted on first read
    if (!memory.has(key) && opts.persist) {
      const persisted = loadPersisted<T>(key)
      if (persisted) {
        memory.set(key, { data: persisted, error: null, timestamp: Date.now() - (opts.staleMs ?? STALE_MS) + 1000 })
      }
    }
    return (memory.get(key) as CacheEntry<T> | undefined) ?? null
  }, [key, opts.persist, opts.staleMs])

  const entry = useSyncExternalStore(subscribe, getSnapshot, getSnapshot)
  const [loading, setLoading] = useState(() => !entry?.data && !!fetcher && !!key)

  const revalidate = useCallback(async () => {
    if (!key || !fetcher) return
    setLoading(true)
    try {
      await fetchWithCache(key, fetcher, opts)
    } finally {
      setLoading(false)
    }
  }, [key, fetcher, opts])

  // initial fetch — keep ref in sync without render-phase assignment
  const fetcherRef = useRef(fetcher)
  useEffect(() => {
    fetcherRef.current = fetcher
  }, [fetcher])

  useEffect(() => {
    if (!key || !fetcherRef.current) return
    const current = memory.get(key) as CacheEntry<T> | undefined
    const now = Date.now()
    const staleMs = opts.staleMs ?? STALE_MS
    const shouldFetch = !current?.data || now - (current.timestamp ?? 0) > staleMs
    if (shouldFetch) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- SWR cache sync
      setLoading(true)
      void fetchWithCache(key, fetcherRef.current, opts)
        .catch(() => {})
        .finally(() => setLoading(false))
    } else {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])

  // revalidate on focus
  useEffect(() => {
    if (!opts.revalidateOnFocus || !key || !fetcher) return
    const onFocus = (): void => {
      void fetchWithCache(key, fetcher, opts).catch(() => {})
    }
    const onVisible = (): void => {
      if (document.visibilityState === "visible") onFocus()
    }
    window.addEventListener("focus", onFocus)
    document.addEventListener("visibilitychange", onVisible)
    return () => {
      window.removeEventListener("focus", onFocus)
      document.removeEventListener("visibilitychange", onVisible)
    }
  }, [key, fetcher, opts])

  const mutateCb = useCallback(
    (data: T | null) => {
      if (!key) return
      mutate(key, data, opts)
    },
    [key, opts],
  )

  return {
    data: entry?.data ?? null,
    error: entry?.error ?? null,
    loading: loading && !entry?.data,
    mutate: mutateCb,
    revalidate,
  }
}
