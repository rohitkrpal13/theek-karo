"use client"

import { useParams, useSearchParams } from "next/navigation"
import { useEffect, useState } from "react"

import { MapExplore, type MapEntity } from "@/components/map/MapExplore"
import { Breadcrumbs, Button, Skeleton } from "@/components/ui/primitives"
import { ReportCard, type ReportCardData } from "@/components/ui/data"
import { InstitutionCard } from "@/components/InstitutionCard"
import {
  geographyApi,
  civicApi,
  institutionsApi,
  reportsApi,
} from "@/lib/api"
import type {
  Category,
  Geography,
  GeographyType,
  Institution,
  InstitutionType,
  Report,
} from "@/lib/types"
import { useT } from "@/lib/i18n-client"

export default function ExplorePage() {
  const params = useParams<{ locale?: string }>()
  const searchParams = useSearchParams()
  const locale = params.locale ?? "en"
  const t = useT()

  // Filters from URL or state
  const initialCategory = searchParams.get("category_slug") ?? ""
  const initialGeography = searchParams.get("geography_id") ?? ""

  const [selectedGeoId, setSelectedGeoId] = useState<string>(initialGeography)
  const [selectedCategory, setSelectedCategory] = useState<string>(initialCategory)
  const [selectedStatus, setSelectedStatus] = useState<string>("")
  const [selectedInstType, setSelectedInstType] = useState<string>("")
  const [activeTab, setActiveTab] = useState<"reports" | "institutions">("reports")

  // Data states
  const [geoTypes, setGeoTypes] = useState<GeographyType[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [instTypes, setInstTypes] = useState<InstitutionType[]>([])
  const [childGeographies, setChildGeographies] = useState<Geography[]>([])
  const [currentGeography, setCurrentGeography] = useState<Geography | null>(null)
  const [breadcrumbs, setBreadcrumbs] = useState<Array<{ label: string; href?: string }>>([
    { label: "India" },
  ])

  const [reports, setReports] = useState<Report[]>([])
  const [institutions, setInstitutions] = useState<Institution[]>([])
  const [mapEntities, setMapEntities] = useState<MapEntity[]>([])
  const [loading, setLoading] = useState(true)

  // 1. Initial lookup metadata (Geo types, categories, institution types)
  useEffect(() => {
    async function loadMeta() {
      try {
        const [types, cats, iTypes] = await Promise.all([
          geographyApi.listTypes(),
          civicApi.listCategories(),
          institutionsApi.listTypes(),
        ])
        setGeoTypes(types)
        setCategories(cats.items)
        setInstTypes(iTypes)
      } catch (err) {
        console.error("Failed to load explore metadata", err)
      }
    }
    void loadMeta()
  }, [])

  // 2. Load Geography Hierarchy Node & Children
  useEffect(() => {
    async function loadGeoHierarchy() {
      if (!selectedGeoId) {
        try {
          const rootChildren = await geographyApi.list({ limit: 40 })
          setChildGeographies(rootChildren.items)
          setCurrentGeography(null)
          setBreadcrumbs([{ label: "India" }])
        } catch {
          setChildGeographies([])
        }
        return
      }

      try {
        const [geoDetail, children] = await Promise.all([
          geographyApi.get(selectedGeoId),
          geographyApi.getChildren(selectedGeoId),
        ])
        setCurrentGeography(geoDetail)
        setChildGeographies(children)

        const ancestorCrumbs = (geoDetail.ancestors ?? []).map((anc) => ({
          label: anc.name,
          href: `/${locale}/explore?geography_id=${anc.id}`,
        }))
        setBreadcrumbs([
          { label: "India", href: `/${locale}/explore` },
          ...ancestorCrumbs,
          { label: geoDetail.name },
        ])
      } catch (err) {
        console.error("Failed to load geography hierarchy", err)
      }
    }

    void loadGeoHierarchy()
  }, [selectedGeoId, locale])

  // 3. Load Reports and Institutions in Scope
  useEffect(() => {
    let cancelled = false

    async function loadScopedData() {
      setLoading(true)
      try {
        const [reportsRes, instRes] = await Promise.all([
          reportsApi.list({
            category_slug: selectedCategory || undefined,
            status: (selectedStatus as never) || undefined,
            boundary_id: selectedGeoId || undefined,
            limit: 20,
          }),
          institutionsApi.list({
            type_id: selectedInstType || undefined,
            geography_id: selectedGeoId || undefined,
            limit: 20,
          }),
        ])

        if (cancelled) return

        setReports(reportsRes.items)
        setInstitutions(instRes.items)

        // Build map entities combining reports and institutions
        const rEntities: MapEntity[] = reportsRes.items.map((r) => ({
          id: r.id,
          kind: "report",
          title: r.title,
          status: r.status,
          severity: r.severity,
          lon: r.location?.coordinates?.[0] ?? 75.7873,
          lat: r.location?.coordinates?.[1] ?? 26.9124,
        }))

        const iEntities: MapEntity[] = instRes.items.map((inst) => ({
          id: inst.id,
          kind: "institution",
          title: inst.name,
          subtitle: inst.operational_status,
          status: inst.operational_status,
          lon: inst.location_lon ?? 75.7873,
          lat: inst.location_lat ?? 26.9124,
        }))

        setMapEntities([...rEntities, ...iEntities])
      } catch (err) {
        console.error("Failed to load scoped explore data", err)
        if (!cancelled) {
          setReports([])
          setInstitutions([])
          setMapEntities([])
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void loadScopedData()
    return () => {
      cancelled = true
    }
  }, [selectedGeoId, selectedCategory, selectedStatus, selectedInstType])

  void geoTypes

  return (
    <div className="space-y-6">
      {/* Header & Breadcrumbs */}
      <div>
        <h1 className="text-2xl font-black tracking-tight">{t("explore.title")}</h1>
        <p className="text-sm text-(--color-ink-muted)">
          {t("explore.subtitle")}
        </p>
      </div>

      <Breadcrumbs items={breadcrumbs} />

      {/* Filter Bar */}
      <div className="flex flex-wrap items-center gap-3 rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface) p-3 shadow-xs">
        {/* Category Filter */}
        <div className="flex flex-col gap-1">
          <label htmlFor="cat-filter" className="text-xs font-semibold text-(--color-ink-muted)">
            {t("explore.filter.category")}
          </label>
          <select
            id="cat-filter"
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="rounded-(--radius-md) border border-(--color-line) bg-(--color-page) px-2.5 py-1.5 text-xs text-(--color-ink)"
          >
            <option value="">{t("explore.filter.all")}</option>
            {categories.map((cat) => (
              <option key={cat.id} value={cat.slug}>
                {cat.slug.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        </div>

        {/* Institution Type Filter */}
        <div className="flex flex-col gap-1">
          <label htmlFor="inst-type-filter" className="text-xs font-semibold text-(--color-ink-muted)">
            {t("explore.filter.type")}
          </label>
          <select
            id="inst-type-filter"
            value={selectedInstType}
            onChange={(e) => setSelectedInstType(e.target.value)}
            className="rounded-(--radius-md) border border-(--color-line) bg-(--color-page) px-2.5 py-1.5 text-xs text-(--color-ink)"
          >
            <option value="">{t("explore.filter.all")}</option>
            {instTypes.map((it) => (
              <option key={it.id} value={it.id}>
                {it.code.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        </div>

        {/* Status Filter */}
        <div className="flex flex-col gap-1">
          <label htmlFor="status-filter" className="text-xs font-semibold text-(--color-ink-muted)">
            {t("explore.filter.status")}
          </label>
          <select
            id="status-filter"
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
            className="rounded-(--radius-md) border border-(--color-line) bg-(--color-page) px-2.5 py-1.5 text-xs text-(--color-ink)"
          >
            <option value="">{t("explore.filter.all")}</option>
            <option value="submitted">Submitted</option>
            <option value="under_verification">Under Verification</option>
            <option value="verified">Verified</option>
            <option value="in_progress">In Progress</option>
            <option value="resolved">Resolved</option>
          </select>
        </div>

        {/* Geolocation Button */}
        <div className="ml-auto flex items-end">
          <Button
            variant="outline"
            size="sm"
            icon="map"
            onClick={() => {
              if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(
                  (pos) => {
                    console.info("Geolocation coordinate:", pos.coords)
                  },
                  (err) => console.warn("Geolocation denied:", err),
                )
              }
            }}
          >
            Near me
          </Button>
        </div>
      </div>

      {/* Child Geographic Boundaries Drilldown */}
      {childGeographies.length > 0 && (
        <section aria-labelledby="sub-geographies-heading" className="space-y-2">
          <h2 id="sub-geographies-heading" className="text-sm font-bold text-(--color-ink-muted) uppercase tracking-wide">
            {currentGeography ? `Districts & Areas in ${currentGeography.name}` : "States & Regions"}
          </h2>
          <div className="flex flex-wrap gap-2">
            {childGeographies.map((geo) => (
              <button
                key={geo.id}
                type="button"
                onClick={() => setSelectedGeoId(geo.id)}
                className="rounded-(--radius-md) border border-(--color-line) bg-(--color-surface) px-3 py-1.5 text-xs font-medium text-(--color-ink) transition-colors hover:border-(--color-primary) hover:text-(--color-primary)"
              >
                {geo.name}
              </button>
            ))}
          </div>
        </section>
      )}

      {/* Map & View Controls */}
      <section aria-labelledby="map-section-heading" className="space-y-3">
        <h2 id="map-section-heading" className="sr-only">
          Map Explorer
        </h2>
        {loading ? (
          <Skeleton height={280} />
        ) : (
          <MapExplore entities={mapEntities} />
        )}
      </section>

      {/* Tabs: Reports vs Institutions */}
      <div className="space-y-4">
        <div
          role="tablist"
          aria-label="Explore content tabs"
          className="flex items-center gap-4 border-b border-(--color-line)"
        >
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "reports"}
            onClick={() => setActiveTab("reports")}
            className={`border-b-2 pb-2 text-sm font-bold transition-colors ${
              activeTab === "reports"
                ? "border-(--color-primary) text-(--color-primary-strong)"
                : "border-transparent text-(--color-ink-muted) hover:text-(--color-ink)"
            }`}
          >
            Citizen Reports ({reports.length})
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "institutions"}
            onClick={() => setActiveTab("institutions")}
            className={`border-b-2 pb-2 text-sm font-bold transition-colors ${
              activeTab === "institutions"
                ? "border-(--color-primary) text-(--color-primary-strong)"
                : "border-transparent text-(--color-ink-muted) hover:text-(--color-ink)"
            }`}
          >
            Public Institutions ({institutions.length})
          </button>
        </div>

        {loading ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <Skeleton height={140} />
            <Skeleton height={140} />
          </div>
        ) : activeTab === "reports" ? (
          reports.length > 0 ? (
            <div className="grid gap-3 sm:grid-cols-2">
              {reports.map((report) => {
                const cardData: ReportCardData = {
                  id: report.id,
                  title: report.title,
                  location: currentGeography?.name ?? "Reported location",
                  status: report.status,
                  tier: "citizen",
                  timeAgo: report.created_at,
                }
                return <ReportCard key={report.id} report={cardData} />
              })}
            </div>
          ) : (
            <div className="rounded-(--radius-lg) border border-dashed border-(--color-line) p-8 text-center">
              <p className="text-sm text-(--color-ink-muted)">
                No reports found matching the selected filters.
              </p>
            </div>
          )
        ) : institutions.length > 0 ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {institutions.map((inst) => (
              <InstitutionCard
                key={inst.id}
                institution={inst}
                geographyName={currentGeography?.name}
              />
            ))}
          </div>
        ) : (
          <div className="rounded-(--radius-lg) border border-dashed border-(--color-line) p-8 text-center">
            <p className="text-sm text-(--color-ink-muted)">
              {t("institutions.empty")}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
