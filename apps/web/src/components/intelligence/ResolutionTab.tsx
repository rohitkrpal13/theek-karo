"use client"

import { useCallback, useEffect, useState } from "react"

import { SectionCard, fmtNumber } from "@/components/intelligence/shared"
import { Badge, EmptyState, ErrorState, Skeleton } from "@/components/ui/primitives"
import { intelligenceApi } from "@/lib/api"
import type { ImprovementItem, ResolutionIntelligenceResponse } from "@/lib/api"
import { useT } from "@/lib/i18n-client"

function HoursStat({ label, value }: { label: string; value: number | null }) {
  const t = useT()
  return (
    <div className="rounded-(--radius-lg) border border-(--color-line) p-3">
      <p className="text-xs text-(--color-ink-muted)">{label}</p>
      <p className="mt-1 text-lg font-semibold text-(--color-ink)">{value === null ? "—" : `${fmtNumber(value)} ${t("intelligence.resolution.hours")}`}</p>
    </div>
  )
}

export function ResolutionTab() {
  const t = useT()
  const [resolution, setResolution] = useState<ResolutionIntelligenceResponse | null>(null)
  const [improvements, setImprovements] = useState<ImprovementItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const [res, imp] = await Promise.all([
        intelligenceApi.resolution(),
        intelligenceApi.improvements({ limit: 20 }),
      ])
      setResolution(res)
      setImprovements(imp.items)
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
  if (!resolution || !improvements)
    return (
      <div className="space-y-3">
        {[0, 1].map((i) => (
          <Skeleton key={i} height={120} />
        ))}
      </div>
    )

  const slaTone = resolution.sla_compliance_pct >= 90 ? "success" : resolution.sla_compliance_pct >= 70 ? "warning" : "error"

  return (
    <div className="space-y-5">
      <SectionCard title={t("intelligence.resolution.response")} limitations={resolution.limitations}>
        <div className="grid gap-3 sm:grid-cols-3">
          <HoursStat label={`${t("intelligence.resolution.avg")} (${t("intelligence.resolution.response")})`} value={resolution.avg_response_hours} />
          <HoursStat label={`${t("intelligence.resolution.median")} (${t("intelligence.resolution.response")})`} value={resolution.median_response_hours} />
          <HoursStat label={`${t("intelligence.resolution.p90")} (${t("intelligence.resolution.response")})`} value={resolution.p90_response_hours} />
          <HoursStat label={`${t("intelligence.resolution.avg")} (${t("intelligence.resolution.resolution")})`} value={resolution.avg_resolution_hours} />
          <HoursStat label={`${t("intelligence.resolution.median")} (${t("intelligence.resolution.resolution")})`} value={resolution.median_resolution_hours} />
          <HoursStat label={`${t("intelligence.resolution.p90")} (${t("intelligence.resolution.resolution")})`} value={resolution.p90_resolution_hours} />
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Badge tone={slaTone}>
            {t("intelligence.resolution.sla")}: {resolution.sla_compliance_pct.toFixed(1)}%
          </Badge>
          <span className="text-sm text-(--color-ink-muted)">
            {t("intelligence.resolution.within")}: {resolution.within_sla_count} · {t("intelligence.resolution.atRisk")}: {resolution.at_risk_count} ·{" "}
            {t("intelligence.resolution.breached")}: {resolution.breached_count}
          </span>
          <span className="text-sm text-(--color-ink-muted)">
            {t("intelligence.resolution.reopens")}: {resolution.reopen_count} · {t("intelligence.resolution.followups")}: {resolution.followup_signals} ·{" "}
            {t("intelligence.resolution.confirmed")}: {resolution.community_confirmed_count}
          </span>
        </div>
      </SectionCard>
      <SectionCard title={t("intelligence.resolution.aging")}>
        {resolution.aging_buckets.length === 0 ? (
          <p className="text-sm text-(--color-ink-muted)">{t("intelligence.empty")}</p>
        ) : (
          <ul className="space-y-2">
            {resolution.aging_buckets.map((bucket, index) => (
              <li key={index} className="flex items-center justify-between gap-3 text-sm">
                <span className="text-(--color-ink)">{bucket.bucket_label}</span>
                <span className="text-(--color-ink-muted)">
                  {bucket.count} · {bucket.pct.toFixed(0)}%
                </span>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>
      <SectionCard title={t("intelligence.improvements")}>
        <p className="text-xs text-(--color-ink-muted)">{t("intelligence.improvements.note")}</p>
        {improvements.length === 0 ? (
          <EmptyState icon="info" title={t("intelligence.empty")} />
        ) : (
          <ul className="mt-3 space-y-2">
            {improvements.map((item, index) => (
              <li key={index} className="flex flex-wrap items-center justify-between gap-3 rounded-(--radius-lg) border border-(--color-line) p-3 text-sm">
                <div>
                  <span className="font-medium text-(--color-ink)">{item.title ?? item.case_no ?? "—"}</span>
                  {item.institution_name && <p className="text-xs text-(--color-ink-muted)">{item.institution_name}</p>}
                </div>
                <span className="text-(--color-ink-muted)">
                  {item.evidence_count} {t("intelligence.cluster.evidence")}
                </span>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>
    </div>
  )
}
