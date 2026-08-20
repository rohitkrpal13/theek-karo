"use client"

import { useEffect, useState } from "react"
import { useParams, useSearchParams } from "next/navigation"

import { ReportCard, type ReportCardData } from "@/components/ui/data"
import { Button, Skeleton } from "@/components/ui/primitives"
import { reportsApi, civicApi } from "@/lib/api"
import type { Category, Report, ReportSeverity, ReportStatus } from "@/lib/types"
import { useT } from "@/lib/i18n-client"

export default function ReportsFeedPage() {
  const params = useParams<{ locale?: string }>()
  const searchParams = useSearchParams()
  const locale = params.locale ?? "en"
  const t = useT()

  const [categories, setCategories] = useState<Category[]>([])
  const [reports, setReports] = useState<Report[]>([])
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)

  // Filters
  const [selectedCategory, setSelectedCategory] = useState(searchParams.get("category") ?? "")
  const [selectedSeverity, setSelectedSeverity] = useState(searchParams.get("severity") ?? "")
  const [selectedStatus, setSelectedStatus] = useState(searchParams.get("status") ?? "")
  const [selectedCampaign] = useState(searchParams.get("campaign_id") ?? "")

  useEffect(() => {
    async function loadCategories() {
      try {
        const res = await civicApi.listCategories()
        setCategories(res.items)
      } catch (err) {
        console.error("Failed to load categories", err)
      }
    }
    void loadCategories()
  }, [])

  useEffect(() => {
    let cancelled = false

    async function loadReports() {
      setLoading(true)
      try {
        const res = await reportsApi.list({
          category_slug: selectedCategory || undefined,
          severity: (selectedSeverity as ReportSeverity) || undefined,
          status: (selectedStatus as ReportStatus) || undefined,
          campaign_id: selectedCampaign || undefined,
          limit: 12,
        })
        if (!cancelled) {
          setReports(res.items)
          setNextCursor(res.next_cursor)
        }
      } catch (err) {
        console.error("Failed to load reports", err)
        if (!cancelled) {
          setReports([])
          setNextCursor(null)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void loadReports()
    return () => {
      cancelled = true
    }
  }, [selectedCategory, selectedSeverity, selectedStatus, selectedCampaign])

  async function handleLoadMore() {
    if (!nextCursor || loadingMore) return
    setLoadingMore(true)
    try {
      const res = await reportsApi.list({
        category_slug: selectedCategory || undefined,
        severity: (selectedSeverity as ReportSeverity) || undefined,
        status: (selectedStatus as ReportStatus) || undefined,
        cursor: nextCursor,
        limit: 12,
      })
      setReports((prev) => [...prev, ...res.items])
      setNextCursor(res.next_cursor)
    } catch (err) {
      console.error("Failed to load more reports", err)
    } finally {
      setLoadingMore(false)
    }
  }

  void locale

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-black tracking-tight">Citizen Reports Feed</h1>
        <p className="text-sm text-(--color-ink-muted)">
          Browse, track, and verify civic issue reports submitted across all public domains.
        </p>
      </div>

      {/* Filter Bar */}
      <div className="flex flex-wrap items-center gap-3 rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface) p-4 shadow-xs">
        {/* Category Filter */}
        <div className="w-48">
          <label htmlFor="report-cat-select" className="text-xs font-semibold text-(--color-ink-muted)">
            {t("explore.filter.category")}
          </label>
          <select
            id="report-cat-select"
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="mt-1 w-full rounded-(--radius-md) border border-(--color-line) bg-(--color-page) px-2.5 py-1.5 text-xs text-(--color-ink)"
          >
            <option value="">{t("explore.filter.all")}</option>
            {categories.map((c) => (
              <option key={c.id} value={c.slug}>
                {c.slug.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        </div>

        {/* Severity Filter */}
        <div className="w-36">
          <label htmlFor="report-sev-select" className="text-xs font-semibold text-(--color-ink-muted)">
            {t("explore.filter.severity")}
          </label>
          <select
            id="report-sev-select"
            value={selectedSeverity}
            onChange={(e) => setSelectedSeverity(e.target.value)}
            className="mt-1 w-full rounded-(--radius-md) border border-(--color-line) bg-(--color-page) px-2.5 py-1.5 text-xs text-(--color-ink)"
          >
            <option value="">{t("explore.filter.all")}</option>
            <option value="low">{t("report.severity.low")}</option>
            <option value="medium">{t("report.severity.medium")}</option>
            <option value="high">{t("report.severity.high")}</option>
            <option value="critical">{t("report.severity.critical")}</option>
          </select>
        </div>

        {/* Status Filter */}
        <div className="w-44">
          <label htmlFor="report-status-select" className="text-xs font-semibold text-(--color-ink-muted)">
            {t("explore.filter.status")}
          </label>
          <select
            id="report-status-select"
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
            className="mt-1 w-full rounded-(--radius-md) border border-(--color-line) bg-(--color-page) px-2.5 py-1.5 text-xs text-(--color-ink)"
          >
            <option value="">{t("explore.filter.all")}</option>
            <option value="submitted">{t("report.status.submitted")}</option>
            <option value="under_verification">{t("report.status.under_verification")}</option>
            <option value="verified">{t("report.status.verified")}</option>
            <option value="assigned">{t("report.status.assigned")}</option>
            <option value="in_progress">{t("report.status.in_progress")}</option>
            <option value="resolution_submitted">{t("report.status.resolution_submitted")}</option>
            <option value="resolved">{t("report.status.resolved")}</option>
            <option value="closed">{t("report.status.closed")}</option>
          </select>
        </div>
      </div>

      {/* Reports Grid */}
      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} height={160} />
          ))}
        </div>
      ) : reports.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {reports.map((report) => {
            const cardData: ReportCardData = {
              id: report.id,
              title: report.title,
              location: "Reported location",
              status: report.status,
              tier: "citizen",
              timeAgo: report.created_at,
            }
            return <ReportCard key={report.id} report={cardData} />
          })}
        </div>
      ) : (
        <div className="rounded-(--radius-lg) border border-dashed border-(--color-line) p-12 text-center">
          <p className="text-sm text-(--color-ink-muted)">
            No reports found matching your criteria.
          </p>
        </div>
      )}

      {/* Load More Button */}
      {nextCursor && (
        <div className="flex justify-center pt-4">
          <Button
            variant="outline"
            size="md"
            disabled={loadingMore}
            onClick={() => void handleLoadMore()}
          >
            {loadingMore ? "Loading more…" : "Load more reports"}
          </Button>
        </div>
      )}
    </div>
  )
}
