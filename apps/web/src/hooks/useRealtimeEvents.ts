"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { openLiveStream, realtimeApi, type LiveActivityItem } from "@/lib/api/realtime"

export interface RealtimeEventPayload {
  id?: string
  event: string
  data: Record<string, unknown> | LiveActivityItem | unknown
  timestamp?: number
}

export type ConnectionStatus = "connected" | "connecting" | "polling" | "disconnected"

export interface UseRealtimeEventsOptions {
  enabled?: boolean
  pollIntervalMs?: number
  onEvent?: (event: string, data: unknown) => void
}

export function useRealtimeEvents(options: UseRealtimeEventsOptions = {}) {
  const { enabled = true, pollIntervalMs = 12000, onEvent } = options

  const [status, setStatus] = useState<ConnectionStatus>("connecting")
  const [lastPing, setLastPing] = useState<Date | null>(null)
  const [recentEvents, setRecentEvents] = useState<RealtimeEventPayload[]>([])
  const [liveItems, setLiveItems] = useState<LiveActivityItem[]>([])
  const [error, setError] = useState<string | null>(null)

  const onEventRef = useRef(onEvent)
  useEffect(() => {
    onEventRef.current = onEvent
  }, [onEvent])

  const closeStreamRef = useRef<(() => void) | null>(null)
  const retryCountRef = useRef(0)
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null)

  const handleIncomingEvent = useCallback((event: string, data: unknown) => {
    setLastPing(new Date())
    setStatus("connected")
    setError(null)
    retryCountRef.current = 0

    const payload: RealtimeEventPayload = {
      event,
      data,
      timestamp: Date.now(),
    }

    setRecentEvents((prev) => [payload, ...prev.slice(0, 49)])

    // If report.created or live activity item
    if (event === "report.created" && data && typeof data === "object") {
      const item = data as LiveActivityItem
      if (item.id && item.ticket_no) {
        setLiveItems((prev) => [item, ...prev.filter((p) => p.id !== item.id).slice(0, 49)])
      }
    }

    if (onEventRef.current) {
      onEventRef.current(event, data)
    }
  }, [])

  // Polling fallback
  const pollFallback = useCallback(async () => {
    try {
      const res = await realtimeApi.liveActivity({ limit: 15 })
      setLiveItems(res.items)
      setLastPing(new Date())
      setStatus("polling")
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Polling error")
    }
  }, [])

  const startPolling = useCallback(() => {
    if (pollTimerRef.current) clearInterval(pollTimerRef.current)
    void pollFallback()
    pollTimerRef.current = setInterval(() => {
      void pollFallback()
    }, pollIntervalMs)
  }, [pollFallback, pollIntervalMs])

  const connectStream = useCallback(() => {
    if (!enabled || typeof window === "undefined") return

    // Close any previous stream
    if (closeStreamRef.current) {
      closeStreamRef.current()
      closeStreamRef.current = null
    }

    setStatus("connecting")

    try {
      const close = openLiveStream((event, data) => {
        handleIncomingEvent(event, data)
      })

      if (!close) {
        // SSE not supported
        startPolling()
        return
      }

      closeStreamRef.current = close
    } catch {
      // Fallback to polling
      startPolling()
    }
  }, [enabled, handleIncomingEvent, startPolling])

  useEffect(() => {
    if (!enabled) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- sync disabled state
      setStatus("disconnected")
      return
    }

    connectStream()

    return () => {
      if (closeStreamRef.current) {
        closeStreamRef.current()
        closeStreamRef.current = null
      }
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current)
        pollTimerRef.current = null
      }
    }
  }, [enabled, connectStream])

  const reconnect = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current)
      pollTimerRef.current = null
    }
    connectStream()
  }, [connectStream])

  return {
    status,
    isConnected: status === "connected",
    isPolling: status === "polling",
    lastPing,
    recentEvents,
    liveItems,
    error,
    reconnect,
  }
}
