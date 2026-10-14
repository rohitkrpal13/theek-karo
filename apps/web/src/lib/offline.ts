"use client"

import { useEffect, useState } from "react"

export function useOnline(): boolean {
  const [online, setOnline] = useState(() =>
    typeof navigator !== "undefined" ? navigator.onLine : true,
  )
  useEffect(() => {
    const on = (): void => setOnline(true)
    const off = (): void => setOnline(false)
    window.addEventListener("online", on)
    window.addEventListener("offline", off)
    return () => {
      window.removeEventListener("online", on)
      window.removeEventListener("offline", off)
    }
  }, [])
  return online
}

// draft persistence as offline queue fallback
const DRAFT_KEY = "tk_report_draft_v1"
const QUEUE_KEY = "tk_offline_queue_v1"

export interface QueuedAction {
  id: string
  url: string
  method: string
  body?: unknown
  ts: number
}

export function enqueueOffline(action: Omit<QueuedAction, "id" | "ts">): void {
  try {
    const raw = localStorage.getItem(QUEUE_KEY)
    const arr: QueuedAction[] = raw ? (JSON.parse(raw) as QueuedAction[]) : []
    arr.push({ ...action, id: crypto.randomUUID(), ts: Date.now() })
    localStorage.setItem(QUEUE_KEY, JSON.stringify(arr.slice(-20)))
  } catch {}
}

export function peekQueue(): QueuedAction[] {
  try {
    const raw = localStorage.getItem(QUEUE_KEY)
    return raw ? (JSON.parse(raw) as QueuedAction[]) : []
  } catch {
    return []
  }
}

export function clearQueue(ids: string[]): void {
  try {
    const q = peekQueue().filter((x) => !ids.includes(x.id))
    localStorage.setItem(QUEUE_KEY, JSON.stringify(q))
  } catch {}
}

export function saveDraft(draft: unknown): void {
  try {
    localStorage.setItem(DRAFT_KEY, JSON.stringify({ draft, ts: Date.now() }))
  } catch {}
}
export function loadDraft<T>(): T | null {
  try {
    const raw = localStorage.getItem(DRAFT_KEY)
    if (!raw) return null
    return (JSON.parse(raw) as { draft: T }).draft ?? null
  } catch {
    return null
  }
}
export function clearDraft(): void {
  try {
    localStorage.removeItem(DRAFT_KEY)
  } catch {}
}
