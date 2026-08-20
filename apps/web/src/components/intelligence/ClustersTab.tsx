"use client"

import { useCallback, useEffect, useState } from "react"

import { SectionCard, fmtDate } from "@/components/intelligence/shared"
import { Badge, EmptyState, ErrorState, Skeleton } from "@/components/ui/primitives"
import { intelligenceApi } from "@/lib/api"
import type { ClusterItem, RecurringIssueItem } from "@/lib/api"
import { useT } from "@/lib/i18n-client"

export function ClustersTab() {
  const t = useT()
  const [clusters, setClusters] = useState<ClusterItem[] | null>(null)
  const [recurring, setRecurring] = useState<RecurringIssueItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const [clusterRes, recurringRes] = await Promise.all([
        intelligenceApi.clusters(),
        intelligenceApi.recurring(),
      ])
      setClusters(clusterRes.clusters)
      setRecurring(recurringRes.items)
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
  if (!clusters || !recurring)
    return (
      <div className="space-y-3">
        {[0, 1].map((i) => (
          <Skeleton key={i} height={120} />
        ))}
      </div>
    )

  return (
    <div className="space-y-5">
      <SectionCard title={t("intelligence.overview.clusters")}>
        {clusters.length === 0 ? (
          <EmptyState icon="info" title={t("intelligence.empty")} />
        ) : (
          <ul className="space-y-3">
            {clusters.map((cluster) => (
              <li key={cluster.cluster_key} className="rounded-(--radius-lg) border border-(--color-line) p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-medium text-(--color-ink)">{cluster.label ?? cluster.cluster_key}</span>
                  <Badge tone={cluster.status === "open" ? "warning" : "success"}>{cluster.status}</Badge>
                </div>
                <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-sm text-(--color-ink-muted)">
                  <span>
                    {cluster.report_count} {t("intelligence.cluster.reports")}
                  </span>
                  <span>
                    {cluster.evidence_count} {t("intelligence.cluster.evidence")}
                  </span>
                  <span>
                    {t("intelligence.cluster.since")}: {fmtDate(cluster.first_seen, "en")}
                  </span>
                  <span>
                    {t("intelligence.cluster.until")}: {fmtDate(cluster.last_seen, "en")}
                  </span>
                </div>
                {(cluster.geography_name || cluster.institution_name) && (
                  <p className="mt-1 text-xs text-(--color-ink-muted)">
                    {[cluster.geography_name, cluster.institution_name].filter(Boolean).join(" · ")}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </SectionCard>
      <SectionCard title={t("intelligence.overview.recurring")}>
        {recurring.length === 0 ? (
          <EmptyState icon="info" title={t("intelligence.empty")} />
        ) : (
          <ul className="space-y-2">
            {recurring.map((item, index) => (
              <li key={index} className="flex flex-wrap items-center justify-between gap-3 rounded-(--radius-lg) border border-(--color-line) p-3 text-sm">
                <span className="font-medium text-(--color-ink)">
                  {item.geography_name ?? item.institution_name ?? item.category_slug ?? "—"}
                </span>
                <span className="text-(--color-ink-muted)">
                  {item.distinct_months} {t("intelligence.recurring.months")} · {item.total_reports}{" "}
                  {t("intelligence.cluster.reports")} · {item.open_reports} {t("intelligence.recurring.open")}
                </span>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>
    </div>
  )
}
