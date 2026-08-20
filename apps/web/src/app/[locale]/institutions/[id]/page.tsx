"use client"

import { useParams } from "next/navigation"
import { useEffect, useState } from "react"

import { MapExplore } from "@/components/map/MapExplore"
import { Breadcrumbs, Skeleton, EmptyState } from "@/components/ui/primitives"
import { ProvenanceBadge, ReportCard, type ReportCardData } from "@/components/ui/data"
import { Icon } from "@/components/ui/icons"
import { OfficialDataCard } from "@/components/govdata/OfficialDataCard"
import { DiscrepancyCard } from "@/components/govdata/DiscrepancyCard"
import { institutionsApi, reportsApi, govdataApi } from "@/lib/api"
import type {
  InstitutionDetail,
  Report,
  InstitutionComparisonResponse,
  OfficialDataResponse,
} from "@/lib/types"
import { useT } from "@/lib/i18n-client"

export default function InstitutionDigitalTwinPage() {
  const params = useParams<{ id: string; locale?: string }>()
  const locale = params.locale ?? "en"
  const t = useT()

  const [institution, setInstitution] = useState<InstitutionDetail | null>(null)
  const [reports, setReports] = useState<Report[]>([])
  const [comparison, setComparison] = useState<InstitutionComparisonResponse | null>(null)
  const [officialData, setOfficialData] = useState<OfficialDataResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<
    "overview" | "comparison" | "infrastructure" | "staffing" | "issues" | "timeline"
  >("overview")
  const [issueFilter, setIssueFilter] = useState<string>("all")

  useEffect(() => {
    let cancelled = false

    async function loadDigitalTwin() {
      setLoading(true)
      try {
        const [inst, reportRes, compRes, offRes] = await Promise.all([
          institutionsApi.get(params.id),
          reportsApi.list({ institution_id: params.id, limit: 30 }),
          govdataApi.getComparison(params.id).catch(() => null),
          govdataApi.getOfficialData(params.id).catch(() => null),
        ])
        if (!cancelled) {
          setInstitution(inst)
          setReports(reportRes.items)
          setComparison(compRes)
          setOfficialData(offRes)
        }
      } catch (err) {
        console.error("Failed to load institution digital twin", err)
        if (!cancelled) setInstitution(null)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    if (params.id) {
      void loadDigitalTwin()
    }
    return () => {
      cancelled = true
    }
  }, [params.id])

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton height={40} />
        <Skeleton height={200} />
        <Skeleton height={300} />
      </div>
    )
  }

  if (!institution) {
    return (
      <div className="py-12">
        <h1 className="sr-only">Institution not found</h1>
        <EmptyState icon="info" title="Institution not found">
          This institution is not currently registered in the digital twin database.
        </EmptyState>
      </div>
    )
  }

  // Filter reports based on issue status tab
  const filteredReports = reports.filter((r) => {
    if (issueFilter === "open")
      return ["submitted", "under_verification", "verified"].includes(r.status)
    if (issueFilter === "in_progress")
      return ["assigned", "in_progress"].includes(r.status)
    if (issueFilter === "resolved")
      return ["resolved", "resolution_verified", "closed"].includes(r.status)
    return true
  })

  // Format breadcrumbs
  const breadcrumbs = [
    { label: "India", href: `/${locale}/explore` },
    ...(institution.geography
      ? [
          {
            label: institution.geography.name,
            href: `/${locale}/explore?geography_id=${institution.geography.id}`,
          },
        ]
      : []),
    { label: institution.name },
  ]

  const lon =
    institution.location_lon ?? institution.location_geojson?.coordinates?.[0] ?? 75.7873
  const lat =
    institution.location_lat ?? institution.location_geojson?.coordinates?.[1] ?? 26.9124

  return (
    <div className="space-y-8">
      {/* Breadcrumbs */}
      <Breadcrumbs items={breadcrumbs} />

      {/* Institution Digital Twin Header */}
      <header className="rounded-(--radius-xl) border border-(--color-line) bg-(--color-surface) p-6 shadow-xs">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-(--color-surface-sunken) px-3 py-0.5 text-xs font-bold text-(--color-primary-strong) uppercase">
                {institution.type?.code ?? "Public Institution"}
              </span>
              <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 capitalize dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300">
                {institution.operational_status.replace("_", " ")}
              </span>
              <ProvenanceBadge
                tier={
                  institution.verification_state === "official"
                    ? "official"
                    : "community_verified"
                }
              />
              {comparison && comparison.overall_discrepancy_state === "POSSIBLE_DISCREPANCY" && (
                <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-0.5 text-xs font-semibold text-amber-400">
                  Observation Discrepancy Flagged
                </span>
              )}
            </div>

            <h1 className="text-3xl font-black text-(--color-ink)">
              {institution.name}
            </h1>

            <p className="text-sm text-(--color-ink-muted)">
              {institution.geography?.name ?? "India"}
              {institution.official_id ? ` · Official ID: ${institution.official_id}` : ""}
            </p>
          </div>

          <div className="flex items-center gap-2">
            {comparison && (
              <span className="rounded-(--radius-md) border border-(--color-line) bg-(--color-page) px-3 py-2 text-center">
                <span className="block text-xs font-semibold text-(--color-ink-muted)">Official Coverage</span>
                <span className="text-lg font-black text-sky-400">{comparison.official_data_coverage_pct}%</span>
              </span>
            )}
            <span className="rounded-(--radius-md) border border-(--color-line) bg-(--color-page) px-3 py-2 text-center">
              <span className="block text-xs font-semibold text-(--color-ink-muted)">Reports</span>
              <span className="text-lg font-black text-(--color-ink)">{reports.length}</span>
            </span>
          </div>
        </div>

        {institution.description ? (
          <p className="mt-4 border-t border-(--color-line) pt-4 text-sm text-(--color-ink)">
            {institution.description}
          </p>
        ) : null}
      </header>

      {/* Navigation Tabs */}
      <div
        role="tablist"
        aria-label="Institution detail tabs"
        className="flex overflow-x-auto border-b border-(--color-line) scrollbar-none"
      >
        {[
          { key: "overview", label: "Overview" },
          { key: "comparison", label: "Official vs Citizen Comparison" },
          { key: "infrastructure", label: t("institutions.infrastructure") },
          { key: "staffing", label: t("institutions.staffing") },
          { key: "issues", label: `${t("institutions.issues")} (${reports.length})` },
          { key: "timeline", label: t("institutions.timeline") },
        ].map((tab) => (
          <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.key}
            onClick={() => setActiveTab(tab.key as never)}
            className={`shrink-0 border-b-2 px-4 pb-3 text-sm font-bold transition-colors ${
              activeTab === tab.key
                ? "border-(--color-primary) text-(--color-primary-strong)"
                : "border-transparent text-(--color-ink-muted) hover:text-(--color-ink)"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* TAB CONTENT: Overview */}
      {activeTab === "overview" && (
        <div className="grid gap-6 md:grid-cols-3">
          <div className="space-y-6 md:col-span-2">
            {/* Quick Metrics */}
            <section aria-labelledby="quick-stats" className="space-y-3">
              <h2 id="quick-stats" className="text-lg font-bold">
                Status & Verification
              </h2>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                <div className="rounded-(--radius-md) border border-(--color-line) bg-(--color-surface) p-3">
                  <span className="text-xs text-(--color-ink-muted)">Verification State</span>
                  <p className="text-sm font-bold capitalize text-(--color-ink)">
                    {institution.verification_state.replace("_", " ")}
                  </p>
                </div>
                <div className="rounded-(--radius-md) border border-(--color-line) bg-(--color-surface) p-3">
                  <span className="text-xs text-(--color-ink-muted)">Data Confidence</span>
                  <p className="text-sm font-bold text-(--color-ink)">
                    {Math.round(institution.confidence_score * 100)}%
                  </p>
                </div>
                <div className="rounded-(--radius-md) border border-(--color-line) bg-(--color-surface) p-3">
                  <span className="text-xs text-(--color-ink-muted)">Last Updated</span>
                  <p className="text-sm font-bold text-(--color-ink)">
                    {new Date(institution.updated_at).toLocaleDateString()}
                  </p>
                </div>
              </div>
            </section>

            {/* Official Data Card Preview */}
            {officialData && (
              <section aria-labelledby="official-heading">
                <OfficialDataCard data={officialData} />
              </section>
            )}

            {/* Location Map */}
            <section aria-labelledby="location-heading" className="space-y-3">
              <h2 id="location-heading" className="text-lg font-bold">
                Location & Coordinates
              </h2>
              <MapExplore
                entities={[
                  {
                    id: institution.id,
                    kind: "institution",
                    title: institution.name,
                    subtitle: institution.operational_status,
                    lon,
                    lat,
                  },
                ]}
              />
              <p className="text-xs text-(--color-ink-muted)">
                GPS Coordinates: {lat.toFixed(5)}, {lon.toFixed(5)}
              </p>
            </section>
          </div>

          {/* AI Civic Summary Slot */}
          <div className="space-y-6">
            <section
              aria-labelledby="ai-summary"
              className="rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface-sunken) p-4"
            >
              <div className="flex items-center gap-2">
                <Icon name="explore" size={18} />
                <h2 id="ai-summary" className="text-sm font-bold">
                  Civic Synthesis & Observations
                </h2>
              </div>
              <p className="mt-2 text-xs text-(--color-ink-muted)">
                {comparison && comparison.overall_discrepancy_state === "POSSIBLE_DISCREPANCY"
                  ? "Observation reports differ in one or more resource metrics compared to published official baseline figures. Community members can submit verifications."
                  : "Automated synthesis of official datasets and citizen reports. All citations are maintained with provenance integrity."}
              </p>
            </section>

            {/* Official Source Provenance */}
            <section
              aria-labelledby="sources-heading"
              className="rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface) p-4"
            >
              <h2 id="sources-heading" className="text-sm font-bold">
                Data Provenance
              </h2>
              <ul className="mt-2 space-y-2 text-xs text-(--color-ink-muted)">
                <li className="flex items-center gap-2">
                  <Icon name="check" size={14} />
                  <span>Verified Public Institution Registry (T1 Official)</span>
                </li>
                <li className="flex items-center gap-2">
                  <Icon name="check" size={14} />
                  <span>Citizen Issue Observations (T5 Citizen)</span>
                </li>
              </ul>
            </section>
          </div>
        </div>
      )}

      {/* TAB CONTENT: Comparison (Phase 10 Core) */}
      {activeTab === "comparison" && (
        <section aria-labelledby="comparison-heading" className="space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h2 id="comparison-heading" className="text-xl font-black text-white">
                Official Benchmark vs Community Observations
              </h2>
              <p className="mt-1 text-xs text-zinc-400">
                Transparent comparison between published administrative records and verified citizen reports.
              </p>
            </div>

            {comparison && (
              <div className="flex items-center gap-3">
                <span className="text-xs text-zinc-400">
                  Overall Status:
                </span>
                <span className="rounded-full border border-sky-500/30 bg-sky-500/10 px-3 py-1 text-xs font-semibold text-sky-400">
                  {comparison.overall_discrepancy_state.replace(/_/g, " ")}
                </span>
              </div>
            )}
          </div>

          {/* Official Data Top Card */}
          {officialData && <OfficialDataCard data={officialData} />}

          {/* Comparative Matrix Cards */}
          {comparison && comparison.comparison_matrix.length > 0 ? (
            <div className="space-y-4">
              <h3 className="text-sm font-bold uppercase tracking-wider text-zinc-400">
                Resource Discrepancy & Consistency Matrix
              </h3>
              <div className="grid gap-4 md:grid-cols-2">
                {comparison.comparison_matrix.map((item) => (
                  <DiscrepancyCard
                    key={item.resource_key}
                    item={item}
                    onVerify={() => setActiveTab("issues")}
                  />
                ))}
              </div>
            </div>
          ) : (
            <div className="rounded-2xl border border-dashed border-zinc-800 p-8 text-center text-sm text-zinc-400">
              Comparative matrix requires official baseline datasets to be imported.
            </div>
          )}
        </section>
      )}

      {/* TAB CONTENT: Infrastructure */}
      {activeTab === "infrastructure" && (
        <section aria-labelledby="infra-heading" className="space-y-4">
          <h2 id="infra-heading" className="text-lg font-bold">
            Infrastructure & Facilities
          </h2>
          {officialData && Object.keys(officialData.canonical_data).length > 0 ? (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {Object.entries(officialData.canonical_data).map(([k, v]) => (
                <div
                  key={k}
                  className="rounded-(--radius-md) border border-(--color-line) bg-(--color-surface) p-3"
                >
                  <span className="text-xs font-semibold text-(--color-ink-muted) capitalize">
                    {k.replace(/_/g, " ")}
                  </span>
                  <p className="mt-1 text-sm font-bold text-(--color-ink)">
                    {typeof v === "boolean" ? (v ? "Yes" : "No") : String(v)}
                  </p>
                </div>
              ))}
            </div>
          ) : institution.attributes && institution.attributes.length > 0 ? (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {institution.attributes.map((attr) => (
                <div
                  key={attr.id}
                  className="rounded-(--radius-md) border border-(--color-line) bg-(--color-surface) p-3"
                >
                  <span className="text-xs font-semibold text-(--color-ink-muted)">
                    {attr.label_key ?? attr.attribute_key}
                  </span>
                  <p className="mt-1 text-sm font-bold text-(--color-ink)">
                    {attr.value_string ??
                      attr.value_integer ??
                      (attr.value_boolean !== null
                        ? attr.value_boolean
                          ? "Yes"
                          : "No"
                        : "—")}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-(--radius-md) border border-dashed border-(--color-line) p-8 text-center text-xs text-(--color-ink-muted)">
              No official infrastructure attributes recorded yet for this facility.
            </div>
          )}
        </section>
      )}

      {/* TAB CONTENT: Staffing */}
      {activeTab === "staffing" && (
        <section aria-labelledby="staff-heading" className="space-y-4">
          <h2 id="staff-heading" className="text-lg font-bold">
            Staffing & Personnel Data
          </h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <div className="rounded-(--radius-md) border border-(--color-line) bg-(--color-surface) p-3">
              <span className="text-xs text-(--color-ink-muted)">Sanctioned Posts</span>
              <p className="text-sm font-bold text-(--color-ink)">
                {officialData?.canonical_data.sanctioned_teachers ??
                  officialData?.canonical_data.doctors_sanctioned ??
                  "Awaiting official data"}
              </p>
            </div>
            <div className="rounded-(--radius-md) border border-(--color-line) bg-(--color-surface) p-3">
              <span className="text-xs text-(--color-ink-muted)">Active Staff</span>
              <p className="text-sm font-bold text-(--color-ink)">
                {officialData?.canonical_data.working_teachers ??
                  officialData?.canonical_data.doctors_available ??
                  "Awaiting official data"}
              </p>
            </div>
            <div className="rounded-(--radius-md) border border-(--color-line) bg-(--color-surface) p-3">
              <span className="text-xs text-(--color-ink-muted)">Open Vacancies</span>
              <p className="text-sm font-bold text-(--color-ink)">
                {officialData?.canonical_data.vacancies ?? "0 recorded"}
              </p>
            </div>
          </div>
        </section>
      )}

      {/* TAB CONTENT: Civic Issues */}
      {activeTab === "issues" && (
        <section aria-labelledby="issues-heading" className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 id="issues-heading" className="text-lg font-bold">
              Citizen Reports for this Institution
            </h2>
            <div className="flex gap-1 text-xs">
              {["all", "open", "in_progress", "resolved"].map((f) => (
                <button
                  key={f}
                  type="button"
                  onClick={() => setIssueFilter(f)}
                  className={`rounded-full px-3 py-1 font-medium capitalize ${
                    issueFilter === f
                      ? "bg-(--color-primary) text-white"
                      : "bg-(--color-surface-sunken) text-(--color-ink-muted)"
                  }`}
                >
                  {f.replace("_", " ")}
                </button>
              ))}
            </div>
          </div>

          {filteredReports.length > 0 ? (
            <div className="grid gap-3 sm:grid-cols-2">
              {filteredReports.map((r) => {
                const cardData: ReportCardData = {
                  id: r.id,
                  title: r.title,
                  location: institution.name,
                  status: r.status,
                  tier: "citizen",
                  timeAgo: r.created_at,
                }
                return <ReportCard key={r.id} report={cardData} />
              })}
            </div>
          ) : (
            <div className="rounded-(--radius-lg) border border-dashed border-(--color-line) p-8 text-center text-sm text-(--color-ink-muted)">
              No reports found for this status.
            </div>
          )}
        </section>
      )}

      {/* TAB CONTENT: Timeline */}
      {activeTab === "timeline" && (
        <section aria-labelledby="timeline-heading" className="space-y-4">
          <h2 id="timeline-heading" className="text-lg font-bold">
            Institutional & Community Activity History
          </h2>
          <div className="rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface) p-6 text-sm text-(--color-ink-muted)">
            <p>
              Historical digital twin updates, data reconciliations, and verified resolutions appear in chronological sequence.
            </p>
          </div>
        </section>
      )}
    </div>
  )
}
