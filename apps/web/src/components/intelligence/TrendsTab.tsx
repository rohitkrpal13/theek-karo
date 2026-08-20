"use client"

import { useCallback, useEffect, useState } from "react"

import { SectionCard, directionLabel, directionTone, fmtDate, fmtNumber } from "@/components/intelligence/shared"
import { ChartBars } from "@/components/ui/data"
import { Badge, EmptyState, ErrorState, Skeleton } from "@/components/ui/primitives"
import { intelligenceApi } from "@/lib/api"
import type { AnomalyItem, TrendAnalysisResponse } from "@/lib/api"
import { useT } from "@/lib/i18n-client"

export function TrendsTab() {
  const t = useT()
  const [trends, setTrends] = useState<TrendAnalysisResponse | null>(null)
  const [anomalies, setAnomalies] = useState<AnomalyItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const [trendRes, anomalyRes] = await Promise.all([
        intelligenceApi.trends(),
        intelligenceApi.anomalies(),
      ])
      setTrends(trendRes)
      setAnomalies(anomalyRes.anomalies)
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
  if (!trends || !anomalies)
    return (
      <div className="space-y-3">
        {[0, 1].map((i) => (
          <Skeleton key={i} height={160} />
        ))}
      </div>
    )

  return (
    <div className="space-y-5">
      {trends.items.length === 0 ? (
        <EmptyState icon="info" title={t("intelligence.empty")}>
          {t("intelligence.insufficientData")}
        </EmptyState>
      ) : (
        trends.items.map((item) => (
          <SectionCard key={`${item.metric}-${item.interval}`} title={item.metric} limitations={item.limitations}>
            <div className="flex flex-wrap items-center gap-3">
              <Badge tone={directionTone(item.comparison.direction)}>{directionLabel(t, item.comparison.direction)}</Badge>
              <span className="text-sm text-(--color-ink-muted)">
                {t("intelligence.trend.period")}: {item.comparison.period_label}
              </span>
              <span className="text-sm text-(--color-ink-muted)">
                {t("intelligence.overview.count")}: {item.comparison.count}
              </span>
              {item.comparison.change_pct !== null && item.comparison.change_pct !== undefined && (
                <span className="text-sm text-(--color-ink-muted)">
                  {item.comparison.change_pct > 0 ? "+" : ""}
                  {item.comparison.change_pct.toFixed(1)}% · {t("intelligence.overview.changes")}
                </span>
              )}
            </div>
            {item.series.length > 0 && (
              <div className="mt-4">
                <ChartBars
                  series={item.series.map((point) => ({ label: fmtDate(point.timestamp, "en"), value: point.value }))}
                  summary={`${item.metric} · ${t("intelligence.trend.series")}`}
                />
              </div>
            )}
            {item.seasonality.length > 0 && (
              <div className="mt-4">
                <h4 className="text-sm font-semibold text-(--color-ink)">{t("intelligence.trend.seasonality")}</h4>
                <ul className="mt-2 space-y-1 text-sm text-(--color-ink-muted)">
                  {item.seasonality.map((entry, index) => (
                    <li key={index} className="flex justify-between gap-3">
                      <span>{String(entry.month ?? entry.label ?? index)}</span>
                      <span>{fmtNumber(Number(entry.proportion ?? entry.value))}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </SectionCard>
        ))
      )}
      <SectionCard title={t("intelligence.overview.anomalies")}>
        {anomalies.length === 0 ? (
          <p className="text-sm text-(--color-ink-muted)">{t("intelligence.empty")}</p>
        ) : (
          <ul className="space-y-3">
            {anomalies.map((anomaly, index) => (
              <li key={index} className="rounded-(--radius-lg) border border-(--color-line) p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-medium text-(--color-ink)">{anomaly.metric}</span>
                  <Badge tone={directionTone("increasing")}>{anomaly.status}</Badge>
                </div>
                <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-sm text-(--color-ink-muted)">
                  <span>
                    {t("intelligence.anomaly.observed")}: {fmtNumber(anomaly.observed_value)}
                  </span>
                  {anomaly.expected_low !== null && anomaly.expected_high !== null && (
                    <span>
                      {t("intelligence.anomaly.expected")}: {fmtNumber(anomaly.expected_low)}–{fmtNumber(anomaly.expected_high)}
                    </span>
                  )}
                  {anomaly.deviation_pct !== null && anomaly.deviation_pct !== undefined && (
                    <span>
                      {t("intelligence.anomaly.deviation")}: +{anomaly.deviation_pct.toFixed(0)}%
                    </span>
                  )}
                </div>
                {anomaly.explanation && <p className="mt-2 text-xs text-(--color-ink-muted)">{anomaly.explanation}</p>}
              </li>
            ))}
          </ul>
        )}
      </SectionCard>
    </div>
  )
}
