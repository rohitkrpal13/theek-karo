"use client"

import { useCallback, useEffect, useState } from "react"

import { fmtDate } from "@/components/intelligence/shared"
import { Badge, Button, EmptyState, ErrorState, Input, Label, Modal, Select, Skeleton, Spinner, useToast } from "@/components/ui/primitives"
import { intelligenceApi } from "@/lib/api"
import type { IntelligenceReport } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { useT } from "@/lib/i18n-client"

const STAFF_ROLES = ["admin", "department_representative", "department_manager"]

export function ReportsTab() {
  const t = useT()
  const { hasRole } = useAuth()
  const toast = useToast()
  const [reports, setReports] = useState<IntelligenceReport[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [title, setTitle] = useState("")
  const [scope, setScope] = useState("PUBLIC")
  const [format, setFormat] = useState("json")
  const [saving, setSaving] = useState(false)
  const [downloading, setDownloading] = useState<string | null>(null)
  const isStaff = STAFF_ROLES.some((role) => hasRole(role))

  const load = useCallback(async () => {
    try {
      const res = await intelligenceApi.listReports({ limit: 20 })
      setReports(res)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0)
    return () => window.clearTimeout(timer)
  }, [load])

  async function createReport() {
    setSaving(true)
    try {
      await intelligenceApi.createReport({ title, scope, format: format as "json" })
      setCreating(false)
      setTitle("")
      toast.toast("success", t("intelligence.report.create"))
      await load()
    } catch (err) {
      toast.toast("error", err instanceof Error ? err.message : String(err))
    } finally {
      setSaving(false)
    }
  }

  async function download(report: IntelligenceReport) {
    if (report.status !== "ready") return
    setDownloading(report.id)
    try {
      const detail = await intelligenceApi.getReport(report.id)
      const url = detail.content?.download_url as string | undefined
      if (url) window.open(url, "_blank", "noopener,noreferrer")
      else toast.toast("error", t("intelligence.report.status"))
    } catch (err) {
      toast.toast("error", err instanceof Error ? err.message : String(err))
    } finally {
      setDownloading(null)
    }
  }

  if (error) return <ErrorState title={t("intelligence.error")} detail={error} onRetry={load} />
  if (!reports)
    return (
      <div className="space-y-3">
        {[0, 1].map((i) => (
          <Skeleton key={i} height={80} />
        ))}
      </div>
    )

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-(--color-ink-muted)">{t("intelligence.report.subtitle")}</p>
        {isStaff && (
          <Button size="sm" onClick={() => setCreating(true)}>
            {t("intelligence.report.create")}
          </Button>
        )}
      </div>
      {!isStaff && <p className="text-xs text-(--color-ink-muted)">{t("intelligence.roleRequired")}</p>}
      {reports.length === 0 ? (
        <EmptyState icon="info" title={t("intelligence.report.empty")} />
      ) : (
        <div className="space-y-3">
          {reports.map((report) => (
            <div key={report.id} className="rounded-(--radius-xl) border border-(--color-line) bg-(--color-surface) p-4 shadow-xs">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h3 className="font-semibold text-(--color-ink)">{report.title}</h3>
                  <p className="mt-0.5 text-xs text-(--color-ink-muted)">
                    {report.format} · {report.scope} · {fmtDate(report.created_at, "en")}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge tone={report.status === "ready" ? "success" : report.status === "failed" ? "error" : "warning"}>
                    {report.status === "ready" ? t("intelligence.report.ready") : report.status}
                  </Badge>
                  {report.status === "ready" && (
                    <Button size="sm" variant="secondary" disabled={downloading === report.id} onClick={() => download(report)}>
                      {downloading === report.id ? <Spinner label="…" /> : t("intelligence.report.download")}
                    </Button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
      <Modal open={creating} onClose={() => setCreating(false)} title={t("intelligence.report.create")}>
        <div className="space-y-4">
          <div>
            <Label htmlFor="rep-title">{t("intelligence.report.reportTitle")}</Label>
            <Input id="rep-title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Monthly civic intelligence digest" />
          </div>
          <div>
            <Label htmlFor="rep-scope">{t("intelligence.report.scope")}</Label>
            <Select id="rep-scope" value={scope} onChange={(e) => setScope(e.target.value)}>
              <option value="PUBLIC">PUBLIC</option>
              <option value="COMMUNITY">COMMUNITY</option>
              <option value="DEPARTMENT">DEPARTMENT</option>
              <option value="ADMIN">ADMIN</option>
              <option value="RESTRICTED">RESTRICTED</option>
            </Select>
          </div>
          <div>
            <Label htmlFor="rep-format">{t("intelligence.report.format")}</Label>
            <Select id="rep-format" value={format} onChange={(e) => setFormat(e.target.value)}>
              <option value="json">JSON</option>
              <option value="csv">CSV</option>
            </Select>
          </div>
          <Button disabled={saving || title.trim().length < 5} onClick={createReport}>
            {saving ? <Spinner label="…" /> : t("intelligence.report.create")}
          </Button>
        </div>
      </Modal>
    </div>
  )
}
