"use client"

import { useCallback, useEffect, useState } from "react"

import { SectionCard, directionLabel, directionTone, fmtDate } from "@/components/intelligence/shared"
import { ChartBars } from "@/components/ui/data"
import { Badge, ErrorState, Skeleton } from "@/components/ui/primitives"
import { intelligenceApi } from "@/lib/api"
import type { AnomalyItem, ClusterItem, IntelligenceDashboardResponse } from "@/lib/api"
import { useT } from "@/lib/i18n-client"

export function OverviewTab() {
  const t = useT()
  const [data, setData] = useState<IntelligenceDashboardResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const res = await intelligenceApi.overview()
      setData(res)
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
  if (!data)
    return (
      <div className="space-y-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} height={120} />
        ))}
      </div>
    )

  const byKey = new Map(data.sections.map((section) => [section.key, section]))

  const trends = byKey.get("trends")
  const anomalies = byKey.get("anomalies")
  const clusters = byKey.get("clusters")
  const recurring = byKey.get("recurring_issues")
  const freshness = byKey.get("data_freshness")

  const direction = trends?.data.direction as string | null | undefined
  const changePct = trends?.data.change_pct as number | null | undefined
  const series = (trends?.data.series as Array<{ timestamp: string; value: number }> | undefined) ?? []
  const anomalyItems = (anomalies?.data.anomalies as AnomalyItem[] | undefined) ?? []
  const clusterItems = (clusters?.data.clusters as ClusterItem[] | undefined) ?? []
  const recurringItems =
    (recurring?.data.items as Array<{ institution_name: string | null; geography_name: string | null; distinct_months: number; total_reports: number }> | undefined) ?? []
  const freshnessItems =
    (freshness?.data.items as Array<{ label: string; last_updated_at: string | null; expected_frequency: string | null }> | undefined) ?? []

  return (
    <div className="space-y-5">
      <p className="text-xs text-(--color-ink-muted)">{t("intelligence.readonly.note")}</p>
      {trends && (
        <SectionCard title={t("intelligence.overview.trends")} limitations={trends.limitations}>
          {direction ? (
            <div className="flex flex-wrap items-center gap-3">
              <Badge tone={directionTone(direction)}>{directionLabel(t, direction)}</Badge>
              {changePct !== null && changePct !== undefined && (
                <span className="text-sm text-(--color-ink-muted)">
                  {changePct > 0 ? "+" : ""}
                  {changePct.toFixed(1)}% · {t("intelligence.overview.changes")}
                </span>
              )}
              <span className="text-sm text-(--color-ink-muted)">
                {t("intelligence.overview.count")}: {series.reduce((sum, point) => sum + point.value, 0)}
              </span>
            </div>
          ) : (
            <p className="text-sm text-(--color-ink-muted)">{t("intelligence.insufficientData")}</p>
          )}
          {series.length > 0 && (
            <div className="mt-4">
              <ChartBars
                series={series.map((point) => ({ label: fmtDate(point.timestamp, "en"), value: point.value }))}
                summary={t("intelligence.trend.series")}
              />
            </div>
          )}
        </SectionCard>
      )}
      {anomalies && (
        <SectionCard title={t("intelligence.overview.anomalies")} limitations={anomalies.limitations}>
          {anomalyItems.length === 0 ? (
            <p className="text-sm text-(--color-ink-muted)">{t("intelligence.empty")}</p>
          ) : (
            <ul className="space-y-2">
              {anomalyItems.slice(0, 5).map((anomaly) => (
                <li key={`${anomaly.metric}-${anomaly.detected_at ?? ""}`} className="flex items-center justify-between gap-3 text-sm">
                  <span className="text-(--color-ink)">{anomaly.metric}</span>
                  <span className="text-(--color-ink-muted)">
                    {anomaly.observed_value} {anomaly.deviation_pct !== null && anomaly.deviation_pct !== undefined ? `(+${anomaly.deviation_pct.toFixed(0)}%)` : ""}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </SectionCard>
      )}
      {clusters && (
        <SectionCard title={t("intelligence.overview.clusters")} limitations={clusters.limitations}>
          {clusterItems.length === 0 ? (
            <p className="text-sm text-(--color-ink-muted)">{t("intelligence.empty")}</p>
          ) : (
            <ul className="space-y-2">
              {clusterItems.slice(0, 5).map((cluster) => (
                <li key={cluster.cluster_key} className="flex items-center justify-between gap-3 text-sm">
                  <span className="text-(--color-ink)">{cluster.label ?? cluster.cluster_key}</span>
                  <span className="text-(--color-ink-muted)">
                    {cluster.report_count} {t("intelligence.cluster.reports")}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </SectionCard>
      )}
      {recurring && (
        <SectionCard title={t("intelligence.overview.recurring")} limitations={recurring.limitations}>
          {recurringItems.length === 0 ? (
            <p className="text-sm text-(--color-ink-muted)">{t("intelligence.empty")}</p>
          ) : (
            <ul className="space-y-2">
              {recurringItems.slice(0, 5).map((item, index) => (
                <li key={index} className="flex items-center justify-between gap-3 text-sm">
                  <span className="text-(--color-ink)">{item.geography_name ?? item.institution_name ?? "—"}</span>
                  <span className="text-(--color-ink-muted)">
                    {item.distinct_months} {t("intelligence.recurring.months")}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </SectionCard>
      )}
      {freshness && (
        <SectionCard title={t("intelligence.overview.freshness")} limitations={freshness.limitations}>
          {freshnessItems.length === 0 ? (
            <p className="text-sm text-(--color-ink-muted)">{t("intelligence.freshness.healthy")}</p>
          ) : (
            <ul className="space-y-2">
              {freshnessItems.slice(0, 5).map((item, index) => (
                <li key={index} className="flex items-center justify-between gap-3 text-sm">
                  <span className="text-(--color-ink)">{item.label}</span>
                  <span className="text-(--color-ink-muted)">{fmtDate(item.last_updated_at, "en")}</span>
                </li>
              ))}
            </ul>
          )}
        </SectionCard>
      )}
    </div>
  )
}
