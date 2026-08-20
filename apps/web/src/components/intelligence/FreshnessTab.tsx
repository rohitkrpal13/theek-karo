"use client"

import { useCallback, useEffect, useState } from "react"

import { SectionCard, fmtDate } from "@/components/intelligence/shared"
import { Badge, ErrorState, Skeleton } from "@/components/ui/primitives"
import { intelligenceApi } from "@/lib/api"
import type { DataGapItem, FreshnessItem } from "@/lib/api"
import { useT } from "@/lib/i18n-client"

function isStale(item: FreshnessItem): boolean {
  if (!item.last_updated_at) return false
  const updated = new Date(item.last_updated_at).getTime()
  if (Number.isNaN(updated)) return false
  const match = item.expected_frequency?.match(/(\d+)\s*(day|week|month)/i)
  if (!match) return false
  const multiplier = match[2].toLowerCase() === "day" ? 1 : match[2].toLowerCase() === "week" ? 7 : 30
  const hours = Number(match[1]) * multiplier * 24
  return Date.now() - updated > hours * 3600 * 1000
}

export function FreshnessTab() {
  const t = useT()
  const [freshness, setFreshness] = useState<FreshnessItem[] | null>(null)
  const [gaps, setGaps] = useState<DataGapItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const [freshRes, gapRes] = await Promise.all([
        intelligenceApi.freshness(),
        intelligenceApi.dataGaps(),
      ])
      setFreshness(freshRes.items)
      setGaps(gapRes.items)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0)
    return () => window.clearTimeout(timer)
  }, [load])

  if (error) return <ErrorState title={t("intelligence.error")} detail={error} onRetry={load} />
  if (!freshness || !gaps)
    return (
      <div className="space-y-3">
        {[0, 1].map((i) => (
          <Skeleton key={i} height={120} />
        ))}
      </div>
    )

  return (
    <div className="space-y-5">
      <SectionCard title={t("intelligence.overview.freshness")}>
        {freshness.length === 0 ? (
          <p className="text-sm text-(--color-ink-muted)">{t("intelligence.freshness.healthy")}</p>
        ) : (
          <ul className="space-y-2">
            {freshness.map((item, index) => (
              <li key={index} className="flex flex-wrap items-center justify-between gap-3 rounded-(--radius-lg) border border-(--color-line) p-3 text-sm">
                <div>
                  <span className="font-medium text-(--color-ink)">{item.label}</span>
                  {item.detail && <p className="text-xs text-(--color-ink-muted)">{item.detail}</p>}
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-(--color-ink-muted)">
                    {t("intelligence.freshness.lastUpdated")}: {fmtDate(item.last_updated_at, "en")}
                  </span>
                  {item.expected_frequency && (
                    <Badge tone={isStale(item) ? "error" : "success"}>
                      {t("intelligence.freshness.expected")}: {item.expected_frequency}
                    </Badge>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>
      <SectionCard title={t("intelligence.gaps.scope")}>
        {gaps.length === 0 ? (
          <p className="text-sm text-(--color-ink-muted)">{t("intelligence.empty")}</p>
        ) : (
          <ul className="space-y-2">
            {gaps.map((gap, index) => (
              <li key={index} className="flex flex-wrap items-center justify-between gap-3 rounded-(--radius-lg) border border-(--color-line) p-3 text-sm">
                <div>
                  <span className="font-medium text-(--color-ink)">{gap.scope}</span>
                  {gap.note && <p className="text-xs text-(--color-ink-muted)">{gap.note}</p>}
                </div>
                <span className="text-(--color-ink-muted)">
                  {gap.with_data} {t("intelligence.gaps.withData")} · {gap.without_data}{" "}
                  {t("intelligence.gaps.withoutData")} · {t("intelligence.gaps.coverage")}{" "}
                  {gap.coverage_pct !== null && gap.coverage_pct !== undefined ? `${gap.coverage_pct.toFixed(1)}%` : "—"}
                </span>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>
    </div>
  )
}
