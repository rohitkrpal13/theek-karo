"use client"

import { Icon as IconCmp } from "@/components/ui/icons"
import { Badge } from "@/components/ui/primitives"
import type { ResolutionAnalyticsResponse } from "@/lib/types"

interface ResolutionMatrixProps {
  resolution: ResolutionAnalyticsResponse
}

export function ResolutionMatrix({ resolution }: ResolutionMatrixProps) {
  const medianDays = resolution.median_resolution_hours
    ? (resolution.median_resolution_hours / 24).toFixed(1)
    : null

  const p90Days = resolution.p90_resolution_hours
    ? (resolution.p90_resolution_hours / 24).toFixed(1)
    : null

  return (
    <div className="rounded-(--radius-xl) border border-(--color-line) bg-(--color-surface) p-5 space-y-4">
      <div>
        <h3 className="text-base font-bold text-(--color-ink)">Resolution Velocity & Integrity</h3>
        <p className="text-xs text-(--color-ink-muted)">
          Formal tracking from submission to ground resolution. Distinguishes authority claims from community-verified outcomes.
        </p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface-raised) p-3 text-center">
          <span className="text-xs text-(--color-ink-muted)">Resolution Rate</span>
          <p className="text-2xl font-extrabold text-blue-600 mt-1">
            {resolution.resolution_rate.toFixed(1)}%
          </p>
          <span className="text-[10px] text-(--color-ink-muted)">
            {resolution.total_resolved} total resolved
          </span>
        </div>

        <div className="rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface-raised) p-3 text-center">
          <span className="text-xs text-(--color-ink-muted)">Median Time</span>
          <p className="text-2xl font-extrabold text-(--color-ink) mt-1">
            {medianDays ? `${medianDays}d` : "N/A"}
          </p>
          <span className="text-[10px] text-(--color-ink-muted)">
            {resolution.median_resolution_hours ? `${resolution.median_resolution_hours.toFixed(1)} hrs` : "No resolved data"}
          </span>
        </div>

        <div className="rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface-raised) p-3 text-center">
          <span className="text-xs text-(--color-ink-muted)">P90 Time</span>
          <p className="text-2xl font-extrabold text-(--color-ink) mt-1">
            {p90Days ? `${p90Days}d` : "N/A"}
          </p>
          <span className="text-[10px] text-(--color-ink-muted)">90th percentile</span>
        </div>

        <div className="rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface-raised) p-3 text-center">
          <span className="text-xs text-(--color-ink-muted)">Verified Ground Fixes</span>
          <p className="text-2xl font-extrabold text-emerald-600 mt-1">
            {resolution.verified_resolution_count}
          </p>
          <span className="text-[10px] text-(--color-ink-muted)">Confirmed by citizens</span>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 pt-3 border-t border-(--color-line) text-xs text-(--color-ink-muted)">
        <div className="flex items-center gap-2">
          <IconCmp name="refresh" size={14} className="text-amber-500" />
          <span>Reopened Reports: <strong className="text-(--color-ink)">{resolution.reopened_count}</strong></span>
        </div>
        <Badge tone="success" className="text-[10px]">
          Official & Community Verified
        </Badge>
      </div>
    </div>
  )
}
