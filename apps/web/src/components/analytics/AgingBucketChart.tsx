"use client"

import type { AgingBucket } from "@/lib/types"

interface AgingBucketChartProps {
  buckets: AgingBucket[]
  title?: string
  description?: string
}

export function AgingBucketChart({
  buckets,
  title = "Open Backlog Aging",
  description = "Distribution of active issues by time since submission.",
}: AgingBucketChartProps) {
  if (!buckets || buckets.length === 0) {
    return null
  }

  const bucketColors: Record<string, string> = {
    "0-7 days": "bg-emerald-500",
    "8-30 days": "bg-amber-500",
    "31-90 days": "bg-orange-500",
    "90+ days": "bg-red-500",
  }

  return (
    <div className="rounded-(--radius-xl) border border-(--color-line) bg-(--color-surface) p-5 space-y-4">
      <div>
        <h3 className="text-base font-bold text-(--color-ink)">{title}</h3>
        <p className="text-xs text-(--color-ink-muted)">{description}</p>
      </div>

      <div className="space-y-3">
        {buckets.map((b) => {
          const colorClass = bucketColors[b.bucket_label] || "bg-(--color-primary)"

          return (
            <div key={b.bucket_label} className="space-y-1">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-(--color-ink)">{b.bucket_label}</span>
                <span className="font-mono text-(--color-ink-muted)">
                  {b.count} reports ({b.pct}%)
                </span>
              </div>
              <div className="h-2.5 w-full rounded-full bg-(--color-line) overflow-hidden">
                <div
                  className={`h-full ${colorClass} rounded-full transition-all duration-300`}
                  style={{ width: `${Math.min(100, Math.max(b.count > 0 ? 3 : 0, b.pct))}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
