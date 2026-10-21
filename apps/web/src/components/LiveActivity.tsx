"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { reportsApi } from "@/lib/api/reports"
import { realtimeApi, type LiveActivityItem } from "@/lib/api/realtime"
import { useLivePoll } from "@/lib/sse"
import { useRealtimeEvents } from "@/hooks/useRealtimeEvents"
import { PulseDot } from "@/components/ui/Motion"
import { RealtimeIndicator } from "@/components/RealtimeIndicator"
import { DataGrid, type Column } from "@/components/ui/DataGrid"
import { Badge } from "@/components/ui/primitives"
import { FormattedDate } from "@/components/FormattedDate"

interface LiveReport {
  id: string
  ticket_no: string
  title: string
  status: string
  severity: string
  created_at: string
}

export function LiveActivityFeed(): React.ReactNode {
  const [items, setItems] = useState<LiveReport[]>([])
  const [loading, setLoading] = useState(true)

  const loadInitial = useCallback(async () => {
    try {
      const res = await realtimeApi.liveActivity({ limit: 10 })
      setItems(
        res.items.map((r: LiveActivityItem) => ({
          id: r.id,
          ticket_no: r.ticket_no,
          title: r.title,
          status: r.status,
          severity: r.severity,
          created_at: r.created_at || "",
        })),
      )
    } catch {
      try {
        const res = await reportsApi.list({ limit: 10 })
        setItems(
          res.items.map((r) => ({
            id: r.id,
            ticket_no: r.ticket_no,
            title: r.title,
            status: r.status,
            severity: r.severity || "medium",
            created_at: r.created_at || "",
          })),
        )
      } catch {
        setItems([])
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- initial load
    void loadInitial()
  }, [loadInitial])

  const { isConnected, lastPing, error, reconnect } = useRealtimeEvents({
    onEvent: (event, data) => {
      if (event === "report.created" && data && typeof data === "object") {
        const item = data as LiveReport
        if (item.id && item.ticket_no) {
          setItems((prev) => [item, ...prev.filter((p) => p.id !== item.id).slice(0, 19)])
        }
      } else if (event === "report.updated" && data && typeof data === "object") {
        const item = data as Partial<LiveReport> & { id: string }
        if (item.id) {
          setItems((prev) => prev.map((p) => (p.id === item.id ? { ...p, ...item } : p)))
        }
      }
    },
  })

  const columns: Column<LiveReport>[] = useMemo(
    () => [
      {
        key: "ticket_no",
        header: "Ticket",
        width: "140px",
        sortable: true,
        accessor: (r) => r.ticket_no,
        render: (r) => <span className="font-mono text-xs font-semibold">{r.ticket_no}</span>,
      },
      {
        key: "title",
        header: "Title",
        render: (r) => <span className="line-clamp-1 font-medium">{r.title}</span>,
      },
      {
        key: "status",
        header: "Status",
        width: "130px",
        render: (r) => (
          <Badge
            tone={
              r.status === "resolved" || r.status === "closed"
                ? "success"
                : r.status === "rejected"
                ? "error"
                : "info"
            }
          >
            {r.status}
          </Badge>
        ),
      },
      {
        key: "severity",
        header: "Severity",
        width: "100px",
        render: (r) => (
          <span
            className={`text-xs font-semibold capitalize ${
              r.severity === "critical"
                ? "text-(--color-error)"
                : r.severity === "high"
                ? "text-orange-600"
                : "text-(--color-ink-muted)"
            }`}
          >
            {r.severity}
          </span>
        ),
      },
      {
        key: "created_at",
        header: "Created",
        width: "140px",
        sortable: true,
        accessor: (r) => r.created_at ?? "",
        render: (r) => (r.created_at ? <FormattedDate iso={r.created_at} /> : <span>—</span>),
      },
    ],
    [],
  )

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-sm font-bold">
          <PulseDot active={isConnected} /> Live reports stream
        </h3>
        <RealtimeIndicator
          lastUpdated={lastPing}
          loading={loading}
          error={error}
          onRefresh={reconnect}
        />
      </div>
      <DataGrid
        data={items}
        columns={columns}
        loading={loading}
        error={error}
        onRetry={reconnect}
        emptyTitle="No live reports yet"
      />
      <p className="text-xs text-(--color-ink-muted)">
        Connected to live SSE stream • Auto-updates when community reports arrive
      </p>
    </div>
  )
}

// Lightweight hook variant for any dashboard
export function useLiveReports(enabled = true): ReturnType<typeof useLivePoll> {
  const fetcher = useCallback(
    (signal: AbortSignal) =>
      reportsApi.list({ limit: 5 }, { signal } as unknown as { signal: AbortSignal }),
    [],
  )
  return useLivePoll(fetcher as unknown as (s: AbortSignal) => Promise<unknown>, 10000, enabled)
}
