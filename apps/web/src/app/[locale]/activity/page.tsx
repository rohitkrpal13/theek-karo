"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { useParams } from "next/navigation"
import { Badge, Button, EmptyState, Input, Skeleton } from "@/components/ui/primitives"
import { Icon } from "@/components/ui/icons"
import { realtimeApi, type LiveActivityItem, type LiveStatsResponse } from "@/lib/api/realtime"
import { reportsApi } from "@/lib/api"
import { useRealtimeEvents } from "@/hooks/useRealtimeEvents"

// Web Audio synthesizer for unobtrusive civic alert sound cue
function playChime(kind: "critical" | "normal" = "normal") {
  if (typeof window === "undefined") return
  try {
    const ctx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)()
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()

    osc.type = "sine"
    osc.frequency.setValueAtTime(kind === "critical" ? 587.33 : 440, ctx.currentTime) // D5 or A4
    if (kind === "critical") {
      osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.15)
    } else {
      osc.frequency.exponentialRampToValueAtTime(659.25, ctx.currentTime + 0.12)
    }

    gain.gain.setValueAtTime(0.04, ctx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3)

    osc.connect(gain)
    gain.connect(ctx.destination)

    osc.start()
    osc.stop(ctx.currentTime + 0.3)
  } catch {
    // AudioContext blocked or unsupported
  }
}

export default function ActivityPage() {
  const params = useParams<{ locale?: string }>()
  const locale = params.locale ?? "en"

  const [items, setItems] = useState<LiveActivityItem[]>([])
  const [stats, setStats] = useState<LiveStatsResponse | null>(null)
  const [initialLoading, setInitialLoading] = useState(true)
  const [soundEnabled, setSoundEnabled] = useState(false)
  const [isPaused, setIsPaused] = useState(false)
  const [selectedSeverity, setSelectedSeverity] = useState<string>("all")
  const [selectedStatus, setSelectedStatus] = useState<string>("all")
  const [searchQuery, setSearchQuery] = useState("")
  const [inspectItem, setInspectItem] = useState<LiveActivityItem | null>(null)
  const [newlyAddedId, setNewlyAddedId] = useState<string | null>(null)

  // Fetch initial batch and pulse stats
  const fetchPulse = useCallback(async () => {
    try {
      const [activity, statData] = await Promise.all([
        realtimeApi.liveActivity({ limit: 30 }),
        realtimeApi.liveStats().catch(() => null),
      ])
      setItems(activity.items)
      if (statData) setStats(statData)
    } catch {
      // Fallback to reportsApi
      try {
        const rep = await reportsApi.list({ limit: 20 })
        setItems(
          rep.items.map((r) => ({
            id: r.id,
            ticket_no: r.ticket_no,
            title: r.title,
            status: r.status,
            severity: r.severity || "medium",
            created_at: r.created_at,
          }))
        )
      } catch {
        setItems([])
      }
    } finally {
      setInitialLoading(false)
    }
  }, [])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- initial pulse fetch
    void fetchPulse()
  }, [fetchPulse])

  // Handle incoming real-time events
  const onRealtimeEvent = useCallback(
    (event: string, data: unknown) => {
      if (isPaused) return

      if (event === "report.created" && data && typeof data === "object") {
        const item = data as LiveActivityItem
        if (item.id && item.ticket_no) {
          setNewlyAddedId(item.id)
          setItems((prev) => [item, ...prev.filter((p) => p.id !== item.id).slice(0, 99)])

          if (soundEnabled) {
            playChime(item.severity === "critical" ? "critical" : "normal")
          }

          // Update stats count optimistically
          setStats((prev) =>
            prev
              ? {
                  ...prev,
                  reports_24h: prev.reports_24h + 1,
                  open_reports: prev.open_reports + 1,
                }
              : null
          )

          setTimeout(() => setNewlyAddedId(null), 3000)
        }
      } else if (event === "report.updated" && data && typeof data === "object") {
        const item = data as Partial<LiveActivityItem> & { id: string }
        if (item.id) {
          setItems((prev) =>
            prev.map((p) => (p.id === item.id ? { ...p, ...item } : p))
          )
        }
      }
    },
    [isPaused, soundEnabled]
  )

  const { status, lastPing, reconnect } = useRealtimeEvents({
    enabled: !isPaused,
    onEvent: onRealtimeEvent,
  })

  // Filtered items
  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      if (selectedSeverity !== "all" && item.severity !== selectedSeverity) return false
      if (selectedStatus !== "all" && item.status !== selectedStatus) return false
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase()
        const matchTitle = item.title.toLowerCase().includes(q)
        const matchTicket = item.ticket_no.toLowerCase().includes(q)
        if (!matchTitle && !matchTicket) return false
      }
      return true
    })
  }, [items, selectedSeverity, selectedStatus, searchQuery])

  return (
    <div className="space-y-6 pb-12">
      {/* Header and Live Status Bar */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-(--color-line) pb-4">
        <div>
          <div className="flex items-center gap-2.5">
            <span className="relative flex h-3 w-3">
              <span
                className={`absolute inline-flex h-full w-full rounded-full opacity-75 ${
                  status === "connected"
                    ? "animate-ping bg-emerald-400"
                    : status === "polling"
                    ? "bg-amber-400 animate-pulse"
                    : "bg-stone-400"
                }`}
              />
              <span
                className={`relative inline-flex h-3 w-3 rounded-full ${
                  status === "connected"
                    ? "bg-emerald-500"
                    : status === "polling"
                    ? "bg-amber-500"
                    : "bg-stone-500"
                }`}
              />
            </span>
            <h1 className="text-2xl font-black tracking-tight text-(--color-ink)">
              Civic Activity Stream
            </h1>
          </div>
          <p className="text-xs text-(--color-ink-muted) mt-1">
            Real-time verified intake, department updates, and resolution telemetry across India.
          </p>
        </div>

        {/* Live Controls */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Connection status badge */}
          <div className="flex items-center gap-1.5 rounded-full border border-(--color-line) bg-(--color-surface-raised) px-3 py-1 text-xs font-semibold">
            <span
              className={`h-2 w-2 rounded-full ${
                status === "connected"
                  ? "bg-emerald-500"
                  : status === "polling"
                  ? "bg-amber-500"
                  : "bg-red-500"
              }`}
            />
            <span className="uppercase tracking-wider">
              {status === "connected"
                ? "Live Stream"
                : status === "polling"
                ? "Live Polling"
                : "Disconnected"}
            </span>
            {lastPing && (
              <span className="text-[10px] text-(--color-ink-muted) border-l border-(--color-line) pl-1.5 ml-1">
                {lastPing.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
              </span>
            )}
          </div>

          {/* Sound alert toggle */}
          <Button
            variant={soundEnabled ? "secondary" : "ghost"}
            size="sm"
            onClick={() => {
              setSoundEnabled(!soundEnabled)
              if (!soundEnabled) playChime("normal")
            }}
            title={soundEnabled ? "Mute audio cues" : "Enable sound on new reports"}
            icon={soundEnabled ? "check" : "bell"}
          >
            <span className="hidden md:inline">{soundEnabled ? "Sound ON" : "Sound OFF"}</span>
          </Button>

          {/* Pause / Resume stream */}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsPaused(!isPaused)}
            icon={isPaused ? "activity" : "clock"}
          >
            {isPaused ? "Resume" : "Pause"}
          </Button>

          {/* Reconnect button */}
          <Button variant="ghost" size="sm" onClick={reconnect} icon="refresh" title="Reconnect stream">
            <span className="sr-only">Reconnect</span>
          </Button>
        </div>
      </div>

      {/* Real-Time Pulse Metric Cards */}
      {stats && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="rounded-xl border border-(--color-line) bg-(--color-surface-raised) p-3 shadow-xs">
            <div className="text-[11px] font-semibold text-(--color-ink-muted) uppercase tracking-wider">
              24h Intake
            </div>
            <div className="mt-1 flex items-baseline gap-2">
              <span className="text-2xl font-black text-(--color-ink)">{stats.reports_24h}</span>
              <span className="text-xs text-emerald-600 font-semibold">Live incoming</span>
            </div>
          </div>

          <div className="rounded-xl border border-(--color-line) bg-(--color-surface-raised) p-3 shadow-xs">
            <div className="text-[11px] font-semibold text-(--color-ink-muted) uppercase tracking-wider">
              Active Cases
            </div>
            <div className="mt-1 flex items-baseline gap-2">
              <span className="text-2xl font-black text-(--color-ink)">{stats.open_reports}</span>
              <span className="text-xs text-amber-600 font-semibold">Under action</span>
            </div>
          </div>

          <div className="rounded-xl border border-(--color-line) bg-(--color-surface-raised) p-3 shadow-xs">
            <div className="text-[11px] font-semibold text-(--color-ink-muted) uppercase tracking-wider">
              Resolved (24h)
            </div>
            <div className="mt-1 flex items-baseline gap-2">
              <span className="text-2xl font-black text-emerald-600">{stats.resolved_24h}</span>
              <span className="text-xs text-(--color-ink-muted)">Verified</span>
            </div>
          </div>

          <div className="rounded-xl border border-(--color-line) bg-(--color-surface-raised) p-3 shadow-xs">
            <div className="text-[11px] font-semibold text-(--color-ink-muted) uppercase tracking-wider">
              Resolution Velocity
            </div>
            <div className="mt-1 flex items-baseline gap-2">
              <span className="text-2xl font-black text-(--color-primary-strong)">
                {stats.velocity_rate}%
              </span>
              <span className="text-xs text-(--color-ink-muted)">Turnaround</span>
            </div>
          </div>
        </div>
      )}

      {/* Filter and Search Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 bg-(--color-surface-raised) p-3 rounded-xl border border-(--color-line)">
        {/* Severity filter pills */}
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-xs font-bold text-(--color-ink-muted) mr-1">Severity:</span>
          {(["all", "critical", "high", "medium", "low"] as const).map((sev) => (
            <button
              key={sev}
              type="button"
              onClick={() => setSelectedSeverity(sev)}
              className={`rounded-lg px-2.5 py-1 text-xs font-semibold capitalize transition-colors ${
                selectedSeverity === sev
                  ? "bg-(--color-primary) text-white shadow-xs"
                  : "bg-(--color-surface) text-(--color-ink-muted) hover:text-(--color-ink) border border-(--color-line)"
              }`}
            >
              {sev}
            </button>
          ))}
        </div>

        {/* Status filter pills */}
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-xs font-bold text-(--color-ink-muted) mr-1">Status:</span>
          {(["all", "submitted", "in_progress", "resolved"] as const).map((st) => (
            <button
              key={st}
              type="button"
              onClick={() => setSelectedStatus(st)}
              className={`rounded-lg px-2.5 py-1 text-xs font-semibold capitalize transition-colors ${
                selectedStatus === st
                  ? "bg-(--color-primary) text-white shadow-xs"
                  : "bg-(--color-surface) text-(--color-ink-muted) hover:text-(--color-ink) border border-(--color-line)"
              }`}
            >
              {st === "all" ? "All" : st.replace("_", " ")}
            </button>
          ))}
        </div>

        {/* Search input */}
        <div className="w-full md:w-64">
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search ticket or keyword..."
            aria-label="Filter activity"
          />
        </div>
      </div>

      {/* Stream List */}
      {initialLoading ? (
        <div className="space-y-3">
          <Skeleton height={80} />
          <Skeleton height={80} />
          <Skeleton height={80} />
        </div>
      ) : filteredItems.length === 0 ? (
        <EmptyState
          icon="activity"
          title="No reports match your filters"
        >
          Listening to live stream for incoming civic updates...
        </EmptyState>
      ) : (
        <div className="divide-y divide-(--color-line) rounded-xl border border-(--color-line) bg-(--color-surface-raised) shadow-xs overflow-hidden">
          {filteredItems.map((item) => {
            const isFresh = item.id === newlyAddedId
            const isCritical = item.severity === "critical"
            return (
              <div
                key={item.id}
                className={`flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 transition-all duration-500 hover:bg-(--color-surface) ${
                  isFresh
                    ? "bg-emerald-50 dark:bg-emerald-950/30 scale-[1.005]"
                    : isCritical
                    ? "bg-red-50/40 dark:bg-red-950/20"
                    : ""
                }`}
              >
                <div className="space-y-1.5 flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-xs font-bold text-(--color-primary-strong) bg-(--color-primary-soft) px-2 py-0.5 rounded">
                      {item.ticket_no}
                    </span>
                    <Badge
                      tone={
                        item.severity === "critical"
                          ? "danger"
                          : item.severity === "high"
                          ? "warning"
                          : "default"
                      }
                    >
                      {item.severity}
                    </Badge>
                    <Badge
                      tone={
                        item.status === "resolved" || item.status === "closed"
                          ? "success"
                          : item.status === "in_progress"
                          ? "info"
                          : "default"
                      }
                    >
                      {item.status.replace("_", " ")}
                    </Badge>
                    {isFresh && (
                      <span className="text-[10px] font-extrabold uppercase tracking-wider text-emerald-600 bg-emerald-100 dark:bg-emerald-900/50 px-1.5 py-0.5 rounded animate-bounce">
                        NEW
                      </span>
                    )}
                  </div>

                  <div className="font-semibold text-sm text-(--color-ink) truncate">
                    {item.title}
                  </div>

                  <div className="text-xs text-(--color-ink-muted)">
                    {item.created_at
                      ? new Date(item.created_at).toLocaleString()
                      : "Recently reported"}
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setInspectItem(item)}
                    icon="info"
                  >
                    Quick View
                  </Button>
                  <Link
                    href={`/${locale}/reports/${item.id}`}
                    className="rounded-lg bg-(--color-primary) px-3 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-(--color-primary-strong) transition-colors"
                  >
                    Open
                  </Link>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Quick View Modal */}
      {inspectItem && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4"
        >
          <div className="w-full max-w-lg rounded-2xl border border-(--color-line) bg-(--color-surface-raised) p-6 shadow-2xl space-y-4 animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between border-b border-(--color-line) pb-3">
              <div>
                <span className="font-mono text-xs font-bold text-(--color-primary-strong)">
                  {inspectItem.ticket_no}
                </span>
                <h3 className="text-lg font-bold text-(--color-ink) mt-0.5">
                  {inspectItem.title}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setInspectItem(null)}
                className="rounded-lg p-1 text-(--color-ink-muted) hover:text-(--color-ink) transition-colors"
                aria-label="Close dialog"
              >
                <Icon name="close" size={18} />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-lg bg-(--color-surface) p-2.5 border border-(--color-line)">
                <span className="text-xs text-(--color-ink-muted) block">Severity</span>
                <span className="font-semibold capitalize text-(--color-ink)">{inspectItem.severity}</span>
              </div>
              <div className="rounded-lg bg-(--color-surface) p-2.5 border border-(--color-line)">
                <span className="text-xs text-(--color-ink-muted) block">Current Status</span>
                <span className="font-semibold capitalize text-(--color-ink)">
                  {inspectItem.status.replace("_", " ")}
                </span>
              </div>
            </div>

            <div className="text-xs text-(--color-ink-muted)">
              Reported on {inspectItem.created_at ? new Date(inspectItem.created_at).toLocaleString() : "N/A"}.
              This data is verified and protected under India-first provenance integrity rules.
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <Button variant="ghost" size="sm" onClick={() => setInspectItem(null)}>
                Dismiss
              </Button>
              <Link
                href={`/${locale}/reports/${inspectItem.id}`}
                className="rounded-lg bg-(--color-primary) px-4 py-2 text-xs font-bold text-white shadow-xs hover:bg-(--color-primary-strong) transition-colors"
              >
                View Full Report Lifecycle →
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}