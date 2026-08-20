"use client"

import { Button } from "@/components/ui/primitives"
import { Icon as IconCmp } from "@/components/ui/icons"
import type { AnalyticsFilterParams } from "@/lib/types"

interface AnalyticsFilterBarProps {
  filters: AnalyticsFilterParams
  onFilterChange: (updated: AnalyticsFilterParams) => void
  onExport: (format: "csv" | "json") => void
  isExporting?: boolean
}

export function AnalyticsFilterBar({
  filters,
  onFilterChange,
  onExport,
  isExporting = false,
}: AnalyticsFilterBarProps) {
  const datePresets = [
    { label: "Today", value: "today" },
    { label: "7 Days", value: "7d" },
    { label: "30 Days", value: "30d" },
    { label: "90 Days", value: "90d" },
    { label: "This Year", value: "year" },
    { label: "All Time", value: "all" },
  ] as const

  return (
    <section
      aria-label="Analytics Filters"
      className="flex flex-wrap items-center justify-between gap-3 rounded-(--radius-xl) border border-(--color-line) bg-(--color-surface) p-4"
    >
      {/* Date Presets */}
      <div className="flex items-center gap-1.5 flex-wrap">
        <span className="text-xs font-semibold text-(--color-ink-muted) mr-1 flex items-center gap-1">
          <IconCmp name="clock" size={14} />
          Period:
        </span>
        {datePresets.map((preset) => {
          const isActive = (filters.date_preset || "30d") === preset.value
          return (
            <button
              key={preset.value}
              type="button"
              onClick={() => onFilterChange({ ...filters, date_preset: preset.value })}
              aria-pressed={isActive}
              className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                isActive
                  ? "bg-(--color-primary) text-white shadow-xs"
                  : "border border-(--color-line) bg-(--color-surface-raised) text-(--color-ink-muted) hover:text-(--color-ink)"
              }`}
            >
              {preset.label}
            </button>
          )
        })}
      </div>

      {/* Interval & Export Actions */}
      <div className="flex items-center gap-2">
        <div className="flex items-center rounded-(--radius-md) border border-(--color-line) bg-(--color-surface-raised) p-0.5">
          {(["day", "week", "month"] as const).map((inv) => (
            <button
              key={inv}
              type="button"
              onClick={() => onFilterChange({ ...filters, interval: inv })}
              className={`px-2 py-0.5 text-xs font-semibold rounded ${
                (filters.interval || "day") === inv
                  ? "bg-(--color-primary) text-white"
                  : "text-(--color-ink-muted) hover:text-(--color-ink)"
              }`}
            >
              {inv.charAt(0).toUpperCase() + inv.slice(1)}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-1">
          <Button
            size="sm"
            variant="outline"
            disabled={isExporting}
            onClick={() => onExport("csv")}
            className="text-xs"
          >
            Export CSV
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={isExporting}
            onClick={() => onExport("json")}
            className="text-xs"
          >
            JSON
          </Button>
        </div>
      </div>
    </section>
  )
}
