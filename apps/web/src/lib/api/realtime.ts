import { api } from "@/lib/api"

export interface LiveActivityItem {
  id: string
  ticket_no: string
  title: string
  status: string
  severity: string
  created_at: string | null
}

export interface LiveActivityResponse {
  items: LiveActivityItem[]
  has_more: boolean
  next_cursor: string | null
  generated_at: number
}

export interface LiveStatsResponse {
  reports_24h: number
  open_reports: number
  resolved_24h: number
  velocity_rate: number
  generated_at: number
}

export interface PublicAlertItem {
  id: string
  title: string
  summary: string
  severity: "info" | "warning" | "critical" | "emergency"
  status: "published"
  verified: boolean
  category?: string
  geography_id?: string
  expires_at?: string | null
  created_at: string
}

export interface LiveActivityParams {
  limit?: number
  cursor?: string | null
  severity?: string
  status?: string
}

export const realtimeApi = {
  liveActivity: (params?: LiveActivityParams) =>
    api.get<LiveActivityResponse>("/live/activity", {
      params: params as Record<string, string | number | null | undefined>,
    }),

  liveStats: () => api.get<LiveStatsResponse>("/live/stats"),

  publicAlerts: () =>
    api.get<{ items: PublicAlertItem[] }>("/communication/public-alerts", {
      params: { limit: 5 },
    }),

  bulkCreate: (items: Array<Record<string, unknown>>, idempotencyKey?: string) =>
    api.post<{ created: Array<{ id: string; ticket_no: string; title: string }>; count: number }>(
      "/reports/bulk",
      { items },
      { idempotencyKey },
    ),

  streamUrl: (base = "") => `${base}/api/v1/live/stream`,
}

export function openLiveStream(
  onEvent: (event: string, data: unknown) => void,
  url = "/api/v1/live/stream",
): () => void {
  if (typeof window === "undefined" || typeof EventSource === "undefined") return () => undefined
  const es = new EventSource(url)
  const handler = (e: MessageEvent<string>): void => {
    try {
      const parsed = JSON.parse(e.data) as unknown
      onEvent((e as unknown as { type?: string }).type ?? "message", parsed)
    } catch {
      onEvent("message", e.data)
    }
  }

  const events = [
    "report.created",
    "report.updated",
    "case.created",
    "case.assigned",
    "case.transitioned",
    "case.responded",
    "case.escalated",
    "alert.issued",
    "alert.resolved",
    "heartbeat",
  ]
  for (const ev of events) {
    es.addEventListener(ev, handler as EventListener)
  }
  es.onmessage = handler
  return () => es.close()
}
