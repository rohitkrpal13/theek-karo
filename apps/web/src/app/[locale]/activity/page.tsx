"use client"

import { useEffect, useState } from "react"

import { reportsApi } from "@/lib/api"
import type { Report } from "@/lib/types"
import { ReportCard, type ReportCardData } from "@/components/ui/data"
import { Skeleton } from "@/components/ui/primitives"

function locationLabel(report: Report): string {
  const [lon, lat] = report.location.coordinates
  return `${lat.toFixed(4)}°N, ${lon.toFixed(4)}°E`
}

export default function ActivityPage() {
  const [reports, setReports] = useState<ReportCardData[] | null>(null)

  useEffect(() => {
    void reportsApi
      .list({ limit: 20 })
      .then((body) =>
        setReports(
          body.items.map((report) => ({
            id: report.id,
            title: report.title,
            location: locationLabel(report),
            status: report.status,
            tier: "citizen" as const,
            timeAgo: report.created_at,
          })),
        ),
      )
      .catch(() => setReports([]))
  }, [])

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Community activity</h1>
      {reports === null ? (
        <div className="grid gap-3 sm:grid-cols-2">
          <Skeleton height={140} />
          <Skeleton height={140} />
        </div>
      ) : reports.length === 0 ? (
        <p className="text-sm text-(--color-ink-muted)">No activity yet in this geography.</p>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {reports.map((report) => <ReportCard key={report.id} report={report} expanded />)}
        </div>
      )}
    </div>
  )
}