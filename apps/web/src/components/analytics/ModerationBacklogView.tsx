"use client"

import { AgingBucketChart } from "./AgingBucketChart"
import type { ModerationAnalyticsResponse } from "@/lib/types"

interface ModerationBacklogViewProps {
  moderation: ModerationAnalyticsResponse
}

export function ModerationBacklogView({ moderation }: ModerationBacklogViewProps) {
  const medianAgeDays = moderation.median_queue_age_hours
    ? (moderation.median_queue_age_hours / 24).toFixed(1)
    : null

  return (
    <div className="space-y-6">
      <div className="rounded-(--radius-xl) border border-(--color-line) bg-(--color-surface) p-5 space-y-4">
        <div>
          <h3 className="text-base font-bold text-(--color-ink)">Moderation & Verification Command Queue</h3>
          <p className="text-xs text-(--color-ink-muted)">
            Live triage velocity, queue backlog, and priority distributions for ground verifiers.
          </p>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface-raised) p-3 text-center">
            <span className="text-xs text-(--color-ink-muted)">Pending Verification</span>
            <p className="text-2xl font-extrabold text-amber-600 mt-1">
              {moderation.pending_verification_count}
            </p>
            <span className="text-[10px] text-(--color-ink-muted)">Awaiting reviewer action</span>
          </div>

          <div className="rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface-raised) p-3 text-center">
            <span className="text-xs text-(--color-ink-muted)">High Priority Queue</span>
            <p className="text-2xl font-extrabold text-red-600 mt-1">
              {moderation.high_priority_count}
            </p>
            <span className="text-[10px] text-(--color-ink-muted)">Critical severity / safety</span>
          </div>

          <div className="rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface-raised) p-3 text-center">
            <span className="text-xs text-(--color-ink-muted)">Duplicate Candidates</span>
            <p className="text-2xl font-extrabold text-blue-600 mt-1">
              {moderation.duplicate_candidates_count}
            </p>
            <span className="text-[10px] text-(--color-ink-muted)">Flagged for merge</span>
          </div>

          <div className="rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface-raised) p-3 text-center">
            <span className="text-xs text-(--color-ink-muted)">Median Queue Age</span>
            <p className="text-2xl font-extrabold text-(--color-ink) mt-1">
              {medianAgeDays ? `${medianAgeDays}d` : "0d"}
            </p>
            <span className="text-[10px] text-(--color-ink-muted)">
              {moderation.median_queue_age_hours ? `${moderation.median_queue_age_hours.toFixed(1)} hrs` : "Clean queue"}
            </span>
          </div>
        </div>
      </div>

      <AgingBucketChart
        buckets={moderation.aging_buckets}
        title="Moderation Queue Aging Distribution"
        description="Time pending in moderation before initial review."
      />
    </div>
  )
}
