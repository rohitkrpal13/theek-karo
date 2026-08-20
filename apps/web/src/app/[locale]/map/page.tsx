"use client"

import { useParams, useRouter, useSearchParams } from "next/navigation"
import { useEffect, useState, useTransition } from "react"

import { MapExplore, type MapEntity } from "@/components/map/MapExplore"
import { Button, Skeleton } from "@/components/ui/primitives"
import { civicApi, geographyApi, gisApi } from "@/lib/api"
import type {
  Category,
  Geography,
  MapInstitutionItem,
  MapReportItem,
  MapSummary,
} from "@/lib/types"

export default function MapPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const params = useParams<{ locale?: string }>()
  const locale = params.locale ?? "en"
  const [, startTransition] = useTransition()

  // URL state parameters
  const initialLat = searchParams.get("lat") ? parseFloat(searchParams.get("lat")!) : 26.9124
  const initialLng = searchParams.get("lng") ? parseFloat(searchParams.get("lng")!) : 75.7873
  const initialZoom = searchParams.get("zoom") ? parseInt(searchParams.get("zoom")!, 10) : 10
  const initialCategory = searchParams.get("category") || undefined
  const initialStatus = searchParams.get("status") || undefined
  const initialGeoId = searchParams.get("geography_id") || undefined

  // Map Viewport State
  const [center, setCenter] = useState<[number, number]>([initialLng, initialLat])
  const [zoom, setZoom] = useState(initialZoom)
  const [entities, setEntities] = useState<MapEntity[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedEntity, setSelectedEntity] = useState<MapEntity | null>(null)

  // Layers & Heatmap
  const [activeLayers, setActiveLayers] = useState({
    institutions: true,
    reports: true,
    heatmap: false,
  })

  // Filter state
  const [categories, setCategories] = useState<Category[]>([])
  const [selectedCategory, setSelectedCategory] = useState<string | undefined>(initialCategory)
  const [selectedStatus, setSelectedStatus] = useState<string | undefined>(initialStatus)
  const [selectedInstType] = useState<string | undefined>(undefined)

  // Geographic Hierarchy & Summary
  const [geographyId, setGeographyId] = useState<string | undefined>(initialGeoId)
  const [currentGeography, setCurrentGeography] = useState<Geography | null>(null)
  const [ancestorNodes, setAncestorNodes] = useState<Array<{ id: string; name: string }>>([])
  const [mapSummary, setMapSummary] = useState<MapSummary | null>(null)

  // Geocoding Search
  const [searchQuery, setSearchQuery] = useState("")
  const [isLocating, setIsLocating] = useState(false)
  const [locationNotice, setLocationNotice] = useState<string | null>(null)

  // Load filter options (categories)
  useEffect(() => {
    async function loadOptions() {
      try {
        const catRes = await civicApi.listCategories()
        setCategories(catRes.items)
      } catch (err) {
        console.warn("Failed to load map filter options", err)
      }
    }
    void loadOptions()
  }, [])

  // Load Geography Hierarchy & Summary when geographyId changes
  useEffect(() => {
    async function loadGeoContext() {
      if (!geographyId) {
        setCurrentGeography(null)
        setAncestorNodes([])
        try {
          const sum = await gisApi.mapSummary()
          setMapSummary(sum)
        } catch (e) {
          console.warn("Summary error:", e)
        }
        return
      }

      try {
        const [geoDetail, sum] = await Promise.all([
          geographyApi.get(geographyId),
          gisApi.mapSummary({ geography_id: geographyId }),
        ])
        setCurrentGeography(geoDetail)
        setAncestorNodes(geoDetail.ancestors ?? [])
        setMapSummary(sum)
      } catch (err) {
        console.warn("Failed to load geography context", err)
      }
    }
    void loadGeoContext()
  }, [geographyId])

  // Fetch institutions and reports for current viewport
  useEffect(() => {
    async function loadViewportData() {
      setLoading(true)
      const span = Math.max(0.05, 40 / Math.pow(2, zoom - 5))
      const minLon = center[0] - span / 2
      const maxLon = center[0] + span / 2
      const minLat = center[1] - (span * 0.6) / 2
      const maxLat = center[1] + (span * 0.6) / 2

      try {
        const [insts, reps] = await Promise.all([
          activeLayers.institutions
            ? gisApi.mapInstitutions({
                min_lon: minLon,
                min_lat: minLat,
                max_lon: maxLon,
                max_lat: maxLat,
                type_id: selectedInstType,
                limit: 100,
              })
            : Promise.resolve([]),
          activeLayers.reports
            ? gisApi.mapReports({
                min_lon: minLon,
                min_lat: minLat,
                max_lon: maxLon,
                max_lat: maxLat,
                category_slug: selectedCategory,
                status: selectedStatus,
                limit: 100,
              })
            : Promise.resolve([]),
        ])

        const mapItems: MapEntity[] = [
          ...insts.map((i: MapInstitutionItem) => ({
            id: i.id,
            kind: "institution" as const,
            title: i.name,
            subtitle: `${i.type_name ?? "Institution"} · Status: ${i.operational_status}`,
            lon: i.location.coordinates[0],
            lat: i.location.coordinates[1],
            open_reports_count: i.open_reports_count,
            resolved_reports_count: i.resolved_reports_count,
            operational_status: i.operational_status,
            type_code: i.type_code || undefined,
            type_name: i.type_name || undefined,
          })),
          ...reps.map((r: MapReportItem) => ({
            id: r.id,
            kind: "report" as const,
            title: r.title,
            subtitle: `Ticket #${r.ticket_no} · ${r.category_slug ?? "Civic"}`,
            status: r.status,
            severity: r.severity,
            lon: r.location.coordinates[0],
            lat: r.location.coordinates[1],
            ticket_no: r.ticket_no,
            trust_score: r.trust_score,
          })),
        ]

        setEntities(mapItems)
      } catch (err) {
        console.warn("Failed to load map entities", err)
        setEntities([])
      } finally {
        setLoading(false)
      }
    }

    const timer = setTimeout(() => {
      void loadViewportData()
    }, 300)

    return () => clearTimeout(timer)
  }, [center, zoom, activeLayers, selectedCategory, selectedStatus, selectedInstType])

  // Sync state with URL params
  function updateUrl(newCenter: [number, number], newZoom: number) {
    const params = new URLSearchParams()
    params.set("lng", newCenter[0].toFixed(4))
    params.set("lat", newCenter[1].toFixed(4))
    params.set("zoom", newZoom.toString())
    if (selectedCategory) params.set("category", selectedCategory)
    if (selectedStatus) params.set("status", selectedStatus)
    if (geographyId) params.set("geography_id", geographyId)

    startTransition(() => {
      router.replace(`/${locale}/map?${params.toString()}`, { scroll: false })
    })
  }

  // Handle Geolocation
  function handleFindNearMe() {
    if (!navigator.geolocation) {
      setLocationNotice("Geolocation is not supported by your browser.")
      return
    }

    setIsLocating(true)
    setLocationNotice(null)

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const newCenter: [number, number] = [pos.coords.longitude, pos.coords.latitude]
        setCenter(newCenter)
        setZoom(13)
        setIsLocating(false)
        updateUrl(newCenter, 13)
      },
      (err) => {
        setIsLocating(false)
        setLocationNotice(`Location permission denied or unavailable (${err.message}).`)
      },
      { enableHighAccuracy: true, timeout: 10000 }
    )
  }

  // Forward Geocode search selection
  async function handleSearchSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!searchQuery.trim()) return

    try {
      const res = await gisApi.forwardGeocode(searchQuery.trim(), 5)
      if (res.results.length > 0) {
        const top = res.results[0]
        const newCenter: [number, number] = [top.lng, top.lat]
        setCenter(newCenter)
        setZoom(13)
        if (top.kind === "geography" && top.id) {
          setGeographyId(top.id)
        }
        updateUrl(newCenter, 13)
      } else {
        setLocationNotice(`No locations found matching "${searchQuery}".`)
      }
    } catch (err) {
      console.warn("Geocoding search failed", err)
    }
  }

  return (
    <div className="space-y-6">
      {/* Search Bar & Geolocation Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1">
          <h1 className="text-2xl font-black tracking-tight text-(--color-ink)">
            Civic Geographic Intelligence
          </h1>
          <p className="text-xs text-(--color-ink-muted)">
            Explore administrative hierarchies, public institutions, and verified observation reports across India.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            icon="map"
            disabled={isLocating}
            onClick={handleFindNearMe}
          >
            {isLocating ? "Detecting GPS…" : "Find Near Me"}
          </Button>
        </div>
      </div>

      {locationNotice && (
        <div role="status" className="rounded-(--radius-md) border border-amber-200 bg-amber-50 p-2.5 text-xs text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-300">
          {locationNotice}
        </div>
      )}

      {/* Structured Geocoding Search Form */}
      <form onSubmit={handleSearchSubmit} className="flex gap-2">
        <div className="relative flex-1">
          <input
            type="text"
            placeholder="Search state, district, block, institution, or coordinate (lat, lng)…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface) py-2.5 pl-3 pr-8 text-xs text-(--color-ink) focus:border-(--color-primary) focus:outline-hidden"
          />
        </div>
        <Button type="submit" variant="primary" size="md">
          Search
        </Button>
      </form>

      {/* Geographic Breadcrumbs Navigation */}
      <nav aria-label="Geographic hierarchy" className="flex items-center gap-1.5 overflow-x-auto text-xs font-semibold text-(--color-ink-muted)">
        <button
          type="button"
          onClick={() => {
            setGeographyId(undefined)
            setCenter([78.9629, 20.5937])
            setZoom(5)
          }}
          className="hover:text-(--color-primary-strong) whitespace-nowrap"
        >
          National (India)
        </button>
        {ancestorNodes.map((anc) => (
          <span key={anc.id} className="flex items-center gap-1.5">
            <span>/</span>
            <button
              type="button"
              onClick={() => setGeographyId(anc.id)}
              className="hover:text-(--color-primary-strong) whitespace-nowrap"
            >
              {anc.name}
            </button>
          </span>
        ))}
        {currentGeography && (
          <span className="flex items-center gap-1.5">
            <span>/</span>
            <span className="font-bold text-(--color-ink) whitespace-nowrap">
              {currentGeography.name}
            </span>
          </span>
        )}
      </nav>

      {/* Civic Intelligence Summary Banner */}
      {mapSummary && (
        <div className="grid grid-cols-2 gap-3 rounded-(--radius-xl) border border-(--color-line) bg-(--color-surface) p-4 sm:grid-cols-5">
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-(--color-ink-muted)">
              Institutions
            </span>
            <p className="text-lg font-black text-(--color-ink)">
              {mapSummary.institution_count.toLocaleString()}
            </p>
          </div>
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-(--color-ink-muted)">
              Reported Issues
            </span>
            <p className="text-lg font-black text-(--color-ink)">
              {mapSummary.report_count.toLocaleString()}
            </p>
          </div>
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-amber-700 dark:text-amber-400">
              Open / In Progress
            </span>
            <p className="text-lg font-black text-amber-700 dark:text-amber-400">
              {mapSummary.open_report_count.toLocaleString()}
            </p>
          </div>
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-700 dark:text-emerald-400">
              Verified / Resolved
            </span>
            <p className="text-lg font-black text-emerald-700 dark:text-emerald-400">
              {mapSummary.resolved_report_count.toLocaleString()}
            </p>
          </div>
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-(--color-ink-muted)">
              Data Coverage
            </span>
            <p className="text-lg font-black text-(--color-primary-strong)">
              {mapSummary.data_coverage_pct}%
            </p>
          </div>
        </div>
      )}

      {/* Layer Toggles & Filter Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface-sunken) p-3 text-xs">
        {/* Layer Switches */}
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-1.5 cursor-pointer font-semibold text-(--color-ink)">
            <input
              type="checkbox"
              checked={activeLayers.institutions}
              onChange={(e) =>
                setActiveLayers((prev) => ({ ...prev, institutions: e.target.checked }))
              }
              className="rounded text-(--color-primary)"
            />
            <span>🏛 Institutions</span>
          </label>
          <label className="flex items-center gap-1.5 cursor-pointer font-semibold text-(--color-ink)">
            <input
              type="checkbox"
              checked={activeLayers.reports}
              onChange={(e) =>
                setActiveLayers((prev) => ({ ...prev, reports: e.target.checked }))
              }
              className="rounded text-(--color-primary)"
            />
            <span>⚠️ Civic Reports</span>
          </label>
          <label className="flex items-center gap-1.5 cursor-pointer font-semibold text-(--color-ink)">
            <input
              type="checkbox"
              checked={activeLayers.heatmap}
              onChange={(e) =>
                setActiveLayers((prev) => ({ ...prev, heatmap: e.target.checked }))
              }
              className="rounded text-(--color-primary)"
            />
            <span>🔥 Density Heatmap</span>
          </label>
        </div>

        {/* Dropdown Filters */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Category Filter */}
          <select
            aria-label="Filter by category"
            value={selectedCategory ?? ""}
            onChange={(e) => setSelectedCategory(e.target.value || undefined)}
            className="rounded-(--radius-md) border border-(--color-line) bg-(--color-surface) px-2.5 py-1 text-xs text-(--color-ink)"
          >
            <option value="">All Categories</option>
            {categories.map((c) => (
              <option key={c.id} value={c.slug}>
                {c.slug.replace(/_/g, " ")}
              </option>
            ))}
          </select>

          {/* Status Filter */}
          <select
            aria-label="Filter by report status"
            value={selectedStatus ?? ""}
            onChange={(e) => setSelectedStatus(e.target.value || undefined)}
            className="rounded-(--radius-md) border border-(--color-line) bg-(--color-surface) px-2.5 py-1 text-xs text-(--color-ink)"
          >
            <option value="">All Statuses</option>
            <option value="submitted">Reported</option>
            <option value="under_verification">Under Verification</option>
            <option value="verified">Verified</option>
            <option value="assigned">Assigned</option>
            <option value="in_progress">In Progress</option>
            <option value="resolved">Resolved</option>
            <option value="closed">Closed</option>
          </select>
        </div>
      </div>

      {/* Main Interactive Map Component */}
      {loading && entities.length === 0 ? (
        <Skeleton height={420} />
      ) : (
        <MapExplore
          entities={entities}
          selectedEntity={selectedEntity}
          onSelectEntity={setSelectedEntity}
          center={center}
          zoom={zoom}
          onCenterChange={(newCenter, newZoom) => {
            setCenter(newCenter)
            setZoom(newZoom)
            updateUrl(newCenter, newZoom)
          }}
          showHeatmap={activeLayers.heatmap}
          onToggleHeatmap={() =>
            setActiveLayers((prev) => ({ ...prev, heatmap: !prev.heatmap }))
          }
          activeLayers={activeLayers}
        />
      )}
    </div>
  )
}
