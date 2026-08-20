"use client"

import { useEffect, useState } from "react"
import { analyticsApi } from "@/lib/api"
import { AnalyticsFilterBar } from "@/components/analytics/AnalyticsFilterBar"
import { KpiCard } from "@/components/analytics/KpiCard"
import { TrendChart } from "@/components/analytics/TrendChart"
import { CategoryBreakdownChart } from "@/components/analytics/CategoryBreakdownChart"
import { ResolutionMatrix } from "@/components/analytics/ResolutionMatrix"
import { AgingBucketChart } from "@/components/analytics/AgingBucketChart"
import { EmptyState } from "@/components/ui/primitives"
import type {
  AnalyticsFilterParams,
  CategoryAnalyticsResponse,
  GeographicAnalyticsResponse,
  OverviewAnalyticsResponse,
  ReportTrendsResponse,
  ResolutionAnalyticsResponse,
  VerificationAndBacklogResponse,
} from "@/lib/types"

export default function AnalyticsPage() {
  const [filters, setFilters] = useState<AnalyticsFilterParams>({
    date_preset: "30d",
    interval: "day",
  })
  const [overview, setOverview] = useState<OverviewAnalyticsResponse | null>(null)
  const [trends, setTrends] = useState<ReportTrendsResponse | null>(null)
  const [categories, setCategories] = useState<CategoryAnalyticsResponse | null>(null)
  const [resolution, setResolution] = useState<ResolutionAnalyticsResponse | null>(null)
  const [verification, setVerification] = useState<VerificationAndBacklogResponse | null>(null)
  const [geography, setGeography] = useState<GeographicAnalyticsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [isExporting, setIsExporting] = useState(false)

  useEffect(() => {
    let isMounted = true
    async function loadData() {
      setLoading(true)
      try {
        const [ovRes, trRes, catRes, resRes, verRes, geoRes] = await Promise.all([
          analyticsApi.getOverview(filters),
          analyticsApi.getTrends(filters),
          analyticsApi.getCategories(filters),
          analyticsApi.getResolution(filters),
          analyticsApi.getVerification(filters),
          analyticsApi.getGeography(filters),
        ])
        if (isMounted) {
          setOverview(ovRes)
          setTrends(trRes)
          setCategories(catRes)
          setResolution(resRes)
          setVerification(verRes)
          setGeography(geoRes)
        }
      } catch (err) {
        console.error("Failed to load analytics:", err)
      } finally {
        if (isMounted) setLoading(false)
      }
    }
    loadData()
    return () => {
      isMounted = false
    }
  }, [filters])

  const handleExport = async (format: "csv" | "json") => {
    setIsExporting(true)
    try {
      const res = await analyticsApi.exportData({
        domain: "reports",
        format,
        filters,
      })
      const blob = new Blob([res.data], {
        type: format === "json" ? "application/json" : "text/csv",
      })
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = res.filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error("Export failed:", err)
    } finally {
      setIsExporting(false)
    }
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div>
        <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-(--color-ink)">
          Civic Analytics & Decision Intelligence
        </h1>
        <p className="mt-1 text-sm text-(--color-ink-muted)">
          Evidence-grounded civic metrics across India. Strictly distinguishing observed reports,
          verified resolutions, and official data baselines.
        </p>
      </div>

      {/* Filter Bar */}
      <AnalyticsFilterBar
        filters={filters}
        onFilterChange={setFilters}
        onExport={handleExport}
        isExporting={isExporting}
      />

      {loading && !overview ? (
        <div className="py-12 text-center text-sm text-(--color-ink-muted)">
          Loading live civic telemetry...
        </div>
      ) : overview && overview.kpis.length > 0 ? (
        <div className="space-y-6">
          {/* KPI Cards Grid */}
          <section aria-labelledby="kpi-section" className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <h2 id="kpi-section" className="sr-only">Key Performance Indicators</h2>
            {overview.kpis.map((kpi) => (
              <KpiCard key={kpi.metric_id} kpi={kpi} />
            ))}
          </section>

          {/* Main Visualizations Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left Column: Trends & Categories */}
            <div className="lg:col-span-2 space-y-6">
              {trends ? (
                <TrendChart series={trends.series} interval={filters.interval} />
              ) : null}

              {categories ? (
                <CategoryBreakdownChart
                  categories={categories.categories}
                  totalReports={categories.total_reports}
                />
              ) : null}
            </div>

            {/* Right Column: Resolution & Backlog Aging */}
            <div className="space-y-6">
              {resolution ? <ResolutionMatrix resolution={resolution} /> : null}

              {verification ? (
                <AgingBucketChart
                  buckets={verification.aging_buckets}
                  title="Open Backlog Aging"
                  description="Distribution of active reports awaiting resolution."
                />
              ) : null}
            </div>
          </div>

          {/* Geographic Drilldown Table */}
          {geography && geography.children.length > 0 ? (
            <section
              aria-labelledby="geo-drilldown"
              className="rounded-(--radius-xl) border border-(--color-line) bg-(--color-surface) p-5 space-y-4"
            >
              <div>
                <h3 id="geo-drilldown" className="text-base font-bold text-(--color-ink)">
                  Geographic Hierarchy Breakdown ({geography.current_level})
                </h3>
                <p className="text-xs text-(--color-ink-muted)">
                  Explore report volumes, resolution velocities, and institution coverage across administrative jurisdictions.
                </p>
              </div>

              <div
                role="region"
                aria-label="Analytics table"
                tabIndex={0}
                className="overflow-x-auto rounded-(--radius-md) border border-(--color-line)"
              >
                <table className="w-full text-left text-xs">
                  <thead className="bg-(--color-surface-raised) text-(--color-ink-muted) border-b border-(--color-line)">
                    <tr>
                      <th className="p-2.5">Region</th>
                      <th className="p-2.5">Type</th>
                      <th className="p-2.5">Reports</th>
                      <th className="p-2.5">Verified</th>
                      <th className="p-2.5">Resolved</th>
                      <th className="p-2.5">Resolution Rate</th>
                      <th className="p-2.5">Institutions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-(--color-line)">
                    {geography.children.map((child) => (
                      <tr key={child.geography_id} className="hover:bg-(--color-surface-raised)">
                        <td className="p-2.5 font-semibold text-(--color-ink)">{child.name}</td>
                        <td className="p-2.5 text-(--color-ink-muted)">{child.type_name}</td>
                        <td className="p-2.5 font-mono font-bold">{child.report_count}</td>
                        <td className="p-2.5 font-mono text-emerald-600">{child.verified_count}</td>
                        <td className="p-2.5 font-mono text-blue-600">{child.resolved_count}</td>
                        <td className="p-2.5 font-mono">{child.resolution_rate.toFixed(1)}%</td>
                        <td className="p-2.5 font-mono">{child.institution_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          ) : null}

          {/* Methodology & Trust Footnote */}
          <footer className="rounded-(--radius-md) bg-(--color-surface-raised) p-4 text-xs text-(--color-ink-muted) border border-(--color-line)">
            <p>
              <strong>Data Provenance Notice:</strong> {overview.data_coverage_note}
            </p>
          </footer>
        </div>
      ) : (
        <EmptyState icon="explore" title="No live data yet">
          Totals, verification, and resolution metrics will populate as citizen reports and public
          institutions are registered in this geography.
        </EmptyState>
      )}
    </div>
  )
}
