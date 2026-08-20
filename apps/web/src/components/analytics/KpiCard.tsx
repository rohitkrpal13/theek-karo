"use client"

import { useState } from "react"
import { Icon as IconCmp } from "@/components/ui/icons"
import { Badge } from "@/components/ui/primitives"
import type { KpiItem } from "@/lib/types"

interface KpiCardProps {
  kpi: KpiItem
}

export function KpiCard({ kpi }: KpiCardProps) {
  const [showDefinition, setShowDefinition] = useState(false)

  const formattedValue =
    kpi.unit === "percentage"
      ? `${kpi.value.toFixed(1)}%`
      : kpi.unit === "hours"
      ? `${kpi.value.toFixed(1)}h`
      : kpi.unit === "currency_usd"
      ? `$${kpi.value.toFixed(4)}`
      : kpi.unit === "currency_inr"
      ? `₹${kpi.value.toLocaleString()}`
      : kpi.value.toLocaleString()

  return (
    <article
      className="relative flex flex-col justify-between rounded-(--radius-xl) border border-(--color-line) bg-(--color-surface) p-5 shadow-xs transition hover:border-(--color-primary) hover:shadow-md"
      aria-labelledby={`kpi-title-${kpi.metric_id}`}
    >
      <div className="flex items-start justify-between gap-2">
        <h3
          id={`kpi-title-${kpi.metric_id}`}
          className="text-sm font-semibold text-(--color-ink-muted)"
        >
          {kpi.name}
        </h3>
        <button
          type="button"
          onClick={() => setShowDefinition(!showDefinition)}
          aria-label={`Definition for ${kpi.name}`}
          className="text-(--color-ink-muted) hover:text-(--color-primary) p-0.5 rounded focus:outline-none focus:ring-1 focus:ring-(--color-primary)"
        >
          <IconCmp name="info" size={14} />
        </button>
      </div>

      <div className="my-3 flex items-baseline gap-2">
        <span className="text-3xl font-extrabold tracking-tight text-(--color-ink)">
          {formattedValue}
        </span>
        {kpi.denominator_label ? (
          <span className="text-xs text-(--color-ink-muted)">
            ({kpi.denominator_label})
          </span>
        ) : null}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-(--color-line) text-xs text-(--color-ink-muted)">
        <span className="inline-flex items-center gap-1">
          <IconCmp name="clock" size={12} />
          {kpi.period_label}
        </span>
        <Badge tone="default" className="text-[10px] px-1.5 py-0.5">
          {kpi.source}
        </Badge>
      </div>

      {showDefinition ? (
        <div className="mt-3 rounded-(--radius-md) bg-(--color-surface-raised) p-3 text-xs text-(--color-ink) border border-(--color-line)">
          <p className="font-medium text-(--color-primary-strong)">Methodology & Formula:</p>
          <p className="mt-1 text-(--color-ink-muted)">{kpi.definition}</p>
        </div>
      ) : null}
    </article>
  )
}
