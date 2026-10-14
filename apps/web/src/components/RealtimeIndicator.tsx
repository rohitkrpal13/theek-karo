"use client"

import { useOnline } from "@/lib/offline"

export function RealtimeIndicator({
  lastUpdated,
  loading,
  error,
  onRefresh,
}: {
  lastUpdated: Date | null
  loading: boolean
  error: unknown
  onRefresh: () => void
}): React.ReactNode {
  const online = useOnline()
  return (
    <div className="flex items-center gap-2 text-xs text-(--color-ink-muted)">
      <span className={["h-2 w-2 rounded-full", online && !error ? "bg-emerald-500 animate-pulse" : "bg-amber-500"].join(" ")} aria-hidden />
      <span>
        {loading ? "Syncing…" : error ? "Sync failed" : online ? "Live" : "Offline"}
        {lastUpdated && !loading && ` • ${lastUpdated.toLocaleTimeString()}`}
      </span>
      <button
        type="button"
        onClick={onRefresh}
        disabled={loading}
        className="rounded px-1.5 py-0.5 text-(--color-primary) hover:bg-(--color-primary-soft) disabled:opacity-50"
      >
        Refresh
      </button>
    </div>
  )
}
