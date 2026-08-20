"use client"

import { useEffect, useState } from "react"
import { analyticsApi } from "@/lib/api"
import { KpiCard } from "@/components/analytics/KpiCard"
import { ModerationBacklogView } from "@/components/analytics/ModerationBacklogView"
import { DataQualityScorecard } from "@/components/analytics/DataQualityScorecard"
import { AiOpsDashboard } from "@/components/analytics/AiOpsDashboard"
import { DepartmentAdmin } from "@/components/cases/DepartmentAdmin"
import { Icon as IconCmp } from "@/components/ui/icons"
import { Badge } from "@/components/ui/primitives"
import type {
  AiOpsAnalyticsResponse,
  DataQualityScorecardResponse,
  ModerationAnalyticsResponse,
  OverviewAnalyticsResponse,
} from "@/lib/types"

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState<"platform" | "moderation" | "govdata" | "ai" | "security" | "departments">("platform")
  const [overview, setOverview] = useState<OverviewAnalyticsResponse | null>(null)
  const [moderation, setModeration] = useState<ModerationAnalyticsResponse | null>(null)
  const [dataQuality, setDataQuality] = useState<DataQualityScorecardResponse | null>(null)
  const [aiOps, setAiOps] = useState<AiOpsAnalyticsResponse | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let isMounted = true
    async function loadAdminData() {
      setLoading(true)
      try {
        const [ovRes, modRes, dqRes, aiRes] = await Promise.allSettled([
          analyticsApi.getOverview({ date_preset: "30d" }),
          analyticsApi.getModeration(),
          analyticsApi.getDataQuality(),
          analyticsApi.getAiOps(),
        ])
        if (isMounted) {
          if (ovRes.status === "fulfilled") setOverview(ovRes.value)
          if (modRes.status === "fulfilled") setModeration(modRes.value)
          if (dqRes.status === "fulfilled") setDataQuality(dqRes.value)
          if (aiRes.status === "fulfilled") setAiOps(aiRes.value)
        }
      } catch (err) {
        console.error("Failed to load admin analytics:", err)
      } finally {
        if (isMounted) setLoading(false)
      }
    }
    loadAdminData()
    return () => {
      isMounted = false
    }
  }, [])

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-(--color-ink)">
              Platform Command Center
            </h1>
            <Badge tone="default" className="text-xs">
              Admin & Ops Console
            </Badge>
          </div>
          <p className="mt-1 text-sm text-(--color-ink-muted)">
            Mission-critical telemetry across citizen reporting, ground verification, government data pipelines, and AI operations.
          </p>
        </div>
      </div>

      {/* Navigation Tabs */}
      <nav aria-label="Admin Navigation Tabs" className="flex items-center gap-2 border-b border-(--color-line) pb-2 overflow-x-auto">
        {(
          [
            { id: "platform", label: "Platform Overview", icon: "activity" as const },
            { id: "moderation", label: "Civic Backlog & Triage", icon: "clock" as const },
            { id: "govdata", label: "Government Data Quality", icon: "check" as const },
            { id: "ai", label: "AI Operations & Costs", icon: "explore" as const },
            { id: "security", label: "Security & Auditing", icon: "lock" as const },
            { id: "departments", label: "Departments & Cases", icon: "building" as const },
          ] as const
        ).map((tab) => {
          const isActive = activeTab === tab.id
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-3 py-2 text-sm font-semibold rounded-(--radius-md) transition whitespace-nowrap ${
                isActive
                  ? "bg-(--color-primary) text-white shadow-xs"
                  : "text-(--color-ink-muted) hover:bg-(--color-surface-raised) hover:text-(--color-ink)"
              }`}
            >
              <IconCmp name={tab.icon} size={16} />
              <span>{tab.label}</span>
            </button>
          )
        })}
      </nav>

      {loading ? (
        <div className="py-12 text-center text-sm text-(--color-ink-muted)">
          Loading system telemetry...
        </div>
      ) : (
        <div className="space-y-6">
          {/* Tab 1: Platform Overview */}
          {activeTab === "platform" && overview ? (
            <div className="space-y-6">
              <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {overview.kpis.map((kpi) => (
                  <KpiCard key={kpi.metric_id} kpi={kpi} />
                ))}
              </section>
            </div>
          ) : null}

          {/* Tab 2: Moderation & Civic Backlog */}
          {activeTab === "moderation" && moderation ? (
            <ModerationBacklogView moderation={moderation} />
          ) : null}

          {/* Tab 3: Government Data Quality */}
          {activeTab === "govdata" && dataQuality ? (
            <DataQualityScorecard scorecard={dataQuality} />
          ) : null}

          {/* Tab 4: AI Operations & Costs */}
          {activeTab === "ai" && aiOps ? (
            <AiOpsDashboard aiOps={aiOps} />
          ) : null}

          {/* Tab 5: Security & Auditing */}
          {activeTab === "security" ? (
            <div className="rounded-(--radius-xl) border border-(--color-line) bg-(--color-surface) p-6 space-y-4">
              <div className="flex items-center gap-2">
                <IconCmp name="lock" size={20} className="text-(--color-primary)" />
                <h3 className="text-base font-bold text-(--color-ink)">Security Policies & Access Guards</h3>
              </div>
              <ul className="space-y-3 text-sm text-(--color-ink-muted)">
                <li className="flex items-start gap-2">
                  <IconCmp name="check" size={16} className="text-emerald-600 mt-0.5" />
                  <span><strong>Small-cell privacy threshold:</strong> Granular cells with &lt; 5 records in sensitive dimensions are suppressed to protect citizen anonymity.</span>
                </li>
                <li className="flex items-start gap-2">
                  <IconCmp name="check" size={16} className="text-emerald-600 mt-0.5" />
                  <span><strong>RBAC Scoped Endpoints:</strong> Government data quality scorecards and AI expenditure metrics are restricted to administrators and analysts.</span>
                </li>
                <li className="flex items-start gap-2">
                  <IconCmp name="check" size={16} className="text-emerald-600 mt-0.5" />
                  <span><strong>Export Auditing:</strong> Bulk dataset exports are logged with requesting actor ID, timestamp, and filter scopes.</span>
                </li>
              </ul>
            </div>
          ) : null}

          {/* Tab 6: Departments, cases & resolution (Phase 14) */}
          {activeTab === "departments" ? <DepartmentAdmin /> : null}
        </div>
      )}
    </div>
  )
}
