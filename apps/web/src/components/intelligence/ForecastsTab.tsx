"use client"

import { useCallback, useEffect, useState } from "react"

import { SectionCard, fmtDate, fmtNumber } from "@/components/intelligence/shared"
import { Badge, Button, EmptyState, ErrorState, Input, Label, Select, Skeleton, Spinner, useToast } from "@/components/ui/primitives"
import { intelligenceApi } from "@/lib/api"
import type { ForecastRun } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { useT } from "@/lib/i18n-client"

export function ForecastsTab() {
  const t = useT()
  const { hasRole } = useAuth()
  const toast = useToast()
  const [runs, setRuns] = useState<ForecastRun[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [metric, setMetric] = useState("reports")
  const [horizon, setHorizon] = useState("30")
  const [interval, setInterval] = useState("week")
  const [saving, setSaving] = useState(false)
  const canRun = hasRole("admin") || hasRole("department_representative") || hasRole("department_manager")

  const load = useCallback(async () => {
    try {
      const res = await intelligenceApi.listForecasts({ limit: 10 })
      setRuns(res.runs)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0)
    return () => window.clearTimeout(timer)
  }, [load])

  async function run() {
    setSaving(true)
    try {
      await intelligenceApi.runForecast({
        metric: metric as "reports",
        horizon_days: Math.min(180, Math.max(7, Number(horizon) || 30)),
        interval: interval as "week",
      })
      toast.toast("success", t("intelligence.forecast.run"))
      await load()
    } catch (err) {
      toast.toast("error", err instanceof Error ? err.message : String(err))
    } finally {
      setSaving(false)
    }
  }

  if (error) return <ErrorState title={t("intelligence.error")} detail={error} onRetry={load} />
  if (!runs)
    return (
      <div className="space-y-3">
        {[0, 1].map((i) => (
          <Skeleton key={i} height={120} />
        ))}
      </div>
    )

  return (
    <div className="space-y-5">
      <p className="text-xs text-(--color-ink-muted)">{t("intelligence.forecast.note")}</p>
      {canRun && (
        <SectionCard title={t("intelligence.forecast.run")}>
          <div className="grid gap-3 sm:grid-cols-3">
            <div>
              <Label htmlFor="fc-metric">{t("intelligence.forecast.metric")}</Label>
              <Select id="fc-metric" value={metric} onChange={(e) => setMetric(e.target.value)}>
                <option value="reports">reports</option>
                <option value="resolved">resolved</option>
                <option value="reports_per_week">reports_per_week</option>
              </Select>
            </div>
            <div>
              <Label htmlFor="fc-horizon">{t("intelligence.forecast.horizon")}</Label>
              <Input id="fc-horizon" type="number" min={7} max={180} value={horizon} onChange={(e) => setHorizon(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="fc-interval">{t("intelligence.forecast.interval")}</Label>
              <Select id="fc-interval" value={interval} onChange={(e) => setInterval(e.target.value)}>
                <option value="week">{t("intelligence.forecast.week")}</option>
                <option value="month">{t("intelligence.forecast.month")}</option>
              </Select>
            </div>
          </div>
          <Button className="mt-3" size="sm" disabled={saving} onClick={run}>
            {saving ? <Spinner label="…" /> : t("intelligence.forecast.run")}
          </Button>
        </SectionCard>
      )}
      {runs.length === 0 ? (
        <EmptyState icon="info" title={t("intelligence.forecast.empty")} />
      ) : (
        runs.map((run) => (
          <SectionCard key={run.id} title={`${run.metric} · ${run.horizon_days}d`}>
            <div className="flex flex-wrap items-center gap-3 text-sm text-(--color-ink-muted)">
              <Badge tone={run.status === "ready" ? "success" : run.status === "failed" ? "error" : "warning"}>{run.status}</Badge>
              {run.model_version && (
                <span>
                  {t("intelligence.models.version")}: {run.model_version}
                </span>
              )}
              {run.method && (
                <span>
                  {t("intelligence.forecast.method")}: {run.method}
                </span>
              )}
              {run.training_start && run.training_end && (
                <span>
                  {t("intelligence.forecast.training")}: {fmtDate(run.training_start, "en")} → {fmtDate(run.training_end, "en")}
                </span>
              )}
            </div>
            {run.error && <p className="mt-2 text-sm text-(--color-error)">{run.error}</p>}
            {run.points.length > 0 && (
              <div className="mt-3 overflow-x-auto rounded-(--radius-md) border border-(--color-line)">
                <table className="w-full min-w-96 border-collapse text-sm">
                  <thead>
                    <tr className="border-b border-(--color-line) bg-(--color-surface-raised) text-left">
                      <th scope="col" className="px-3 py-2 font-semibold text-(--color-ink-muted)">{t("intelligence.forecast.point")}</th>
                      <th scope="col" className="px-3 py-2 font-semibold text-(--color-ink-muted)">{t("intelligence.forecast.range")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {run.points.map((point, index) => (
                      <tr key={index} className="border-b border-(--color-line) last:border-0">
                        <td className="px-3 py-2">{fmtDate(point.point, "en")}</td>
                        <td className="px-3 py-2">
                          {fmtNumber(point.low)} – {fmtNumber(point.point_value)} – {fmtNumber(point.high)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </SectionCard>
        ))
      )}
    </div>
  )
}
