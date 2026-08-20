"use client"

import { useState } from "react"

import { ClustersTab } from "@/components/intelligence/ClustersTab"
import { ForecastsTab } from "@/components/intelligence/ForecastsTab"
import { FreshnessTab } from "@/components/intelligence/FreshnessTab"
import { ModelsTab } from "@/components/intelligence/ModelsTab"
import { OverviewTab } from "@/components/intelligence/OverviewTab"
import { ReportsTab } from "@/components/intelligence/ReportsTab"
import { ResolutionTab } from "@/components/intelligence/ResolutionTab"
import { SignalsTab } from "@/components/intelligence/SignalsTab"
import { TrendsTab } from "@/components/intelligence/TrendsTab"
import { Tabs } from "@/components/ui/primitives"
import { useT } from "@/lib/i18n-client"

export function IntelligenceHub({ initialTab = "overview" }: { initialTab?: string }) {
  const t = useT()
  const [tab, setTab] = useState(initialTab)

  const tabs = [
    { id: "overview", label: t("intelligence.tab.overview") },
    { id: "trends", label: t("intelligence.tab.trends") },
    { id: "clusters", label: t("intelligence.tab.clusters") },
    { id: "freshness", label: t("intelligence.tab.freshness") },
    { id: "resolution", label: t("intelligence.tab.resolution") },
    { id: "forecasts", label: t("intelligence.tab.forecasts") },
    { id: "signals", label: t("intelligence.tab.signals") },
    { id: "reports", label: t("intelligence.tab.reports") },
    { id: "models", label: t("intelligence.tab.models") },
  ]

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-(--color-primary-strong)">{t("intelligence.title")}</h1>
        <p className="text-sm text-(--color-ink-muted)">{t("intelligence.subtitle")}</p>
      </div>
      <Tabs tabs={tabs} active={tab} onChange={setTab} />
      {tab === "overview" && <OverviewTab />}
      {tab === "trends" && <TrendsTab />}
      {tab === "clusters" && <ClustersTab />}
      {tab === "freshness" && <FreshnessTab />}
      {tab === "resolution" && <ResolutionTab />}
      {tab === "forecasts" && <ForecastsTab />}
      {tab === "signals" && <SignalsTab />}
      {tab === "reports" && <ReportsTab />}
      {tab === "models" && <ModelsTab />}
    </div>
  )
}
