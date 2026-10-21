"use client"

import { useParams, useSearchParams } from "next/navigation"
import { useEffect, useState, type FormEvent } from "react"
import Link from "next/link"

import { MapExplore, type MapEntity } from "@/components/map/MapExplore"
import { Breadcrumbs, Button, Skeleton } from "@/components/ui/primitives"
import { ReportCard, type ReportCardData } from "@/components/ui/data"
import { InstitutionCard } from "@/components/InstitutionCard"
import { Icon } from "@/components/ui/icons"
import {
  geographyApi,
  civicApi,
  gisApi,
  institutionsApi,
  reportsApi,
} from "@/lib/api"
import type {
  Category,
  Geography,
  GeographyType,
  Institution,
  InstitutionType,
  MapNearbyResponse,
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
  const [institutionQuery, setInstitutionQuery] = useState("")
  const [appliedInstitutionQuery, setAppliedInstitutionQuery] = useState("")
  const [institutionSuggestions, setInstitutionSuggestions] = useState<Institution[]>([])
  const [suggestionsLoading, setSuggestionsLoading] = useState(false)
  const [suggestionsLoaded, setSuggestionsLoaded] = useState(false)
  const [suggestionsError, setSuggestionsError] = useState(false)
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [activeSuggestionIndex, setActiveSuggestionIndex] = useState(-1)
  const [nearbyInstitutions, setNearbyInstitutions] = useState<
    MapNearbyResponse["institutions"]
  >([])
  const [nearbyRadius, setNearbyRadius] = useState(5000)
  const [nearbySearched, setNearbySearched] = useState(false)
  const [nearbyLoading, setNearbyLoading] = useState(false)
  const [nearbyError, setNearbyError] = useState(false)
  const [locationMessage, setLocationMessage] = useState("")

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
  const [dataError, setDataError] = useState(false)
  const [reloadVersion, setReloadVersion] = useState(0)

  useEffect(() => {
    const query = institutionQuery.trim()
    if (query.length < 2 || !showSuggestions) return

    const controller = new AbortController()
    const timer = setTimeout(() => {
      setSuggestionsLoading(true)
      setSuggestionsLoaded(false)
      setSuggestionsError(false)
      void institutionsApi
        .list({ q: query, type_id: selectedInstType || undefined, limit: 5 }, {
          signal: controller.signal,
        })
        .then((res) => {
          setInstitutionSuggestions(res.items)
          setSuggestionsLoaded(true)
        })
        .catch((err: unknown) => {
          if (controller.signal.aborted) return
          console.error("Failed to load institution suggestions", err)
          setInstitutionSuggestions([])
          setSuggestionsError(true)
          setSuggestionsLoaded(true)
        })
        .finally(() => {
          if (!controller.signal.aborted) setSuggestionsLoading(false)
        })
    }, 250)

    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [institutionQuery, selectedInstType, showSuggestions])

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
      setDataError(false)
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
            q: appliedInstitutionQuery || undefined,
            limit: 20,
          }),
        ])

        if (cancelled) return

        setReports(reportsRes.items)
        setInstitutions(instRes.items)

        // Build map entities combining reports and institutions
        const isValidCoordinates = (lon: number, lat: number) =>
          Number.isFinite(lon) &&
          Number.isFinite(lat) &&
          lon >= -180 &&
          lon <= 180 &&
          lat >= -90 &&
          lat <= 90

        const rEntities: MapEntity[] = reportsRes.items.flatMap((report) => {
          const [lon, lat] = report.location?.coordinates ?? [NaN, NaN]
          if (!isValidCoordinates(lon, lat)) return []
          return [{
            id: report.id,
            kind: "report" as const,
            title: report.title,
            status: report.status,
            severity: report.severity,
            lon,
            lat,
          }]
        })

        const iEntities: MapEntity[] = instRes.items.flatMap((institution) => {
          const lon = institution.location_lon
          const lat = institution.location_lat
          if (lon === null || lon === undefined || lat === null || lat === undefined || !isValidCoordinates(lon, lat)) {
            return []
          }
          return [{
            id: institution.id,
            kind: "institution" as const,
            title: institution.name,
            subtitle: institution.operational_status,
            status: institution.operational_status,
            lon,
            lat,
          }]
        })

        setMapEntities([...rEntities, ...iEntities])
      } catch (err) {
        console.error("Failed to load scoped explore data", err)
        if (!cancelled) {
          setReports([])
          setInstitutions([])
          setMapEntities([])
          setDataError(true)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void loadScopedData()
    return () => {
      cancelled = true
    }
  }, [
    selectedGeoId,
    selectedCategory,
    selectedStatus,
    selectedInstType,
    appliedInstitutionQuery,
    reloadVersion,
  ])

  function handleInstitutionSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setAppliedInstitutionQuery(institutionQuery.trim())
    setActiveSuggestionIndex(-1)
    setActiveTab("institutions")
    setShowSuggestions(false)
  }

  function handleUseCurrentLocation() {
    if (!navigator.geolocation) {
      setLocationMessage(t("explore.location.unsupported"))
      return
    }

    setNearbyLoading(true)
    setNearbyError(false)
    setNearbySearched(false)
    setNearbyInstitutions([])
    setLocationMessage("")
    navigator.geolocation.getCurrentPosition(
      (position) => {
        void gisApi
          .mapNearby(
            position.coords.latitude,
            position.coords.longitude,
            nearbyRadius,
            "institutions",
            undefined,
            20,
          )
          .then((result) => {
            setNearbyInstitutions(result.institutions)
            setNearbySearched(true)
            setActiveTab("institutions")
          })
          .catch((err: unknown) => {
            console.error("Failed to load nearby institutions", err)
            setNearbyError(true)
            setNearbySearched(true)
          })
          .finally(() => setNearbyLoading(false))
      },
      (error) => {
        setNearbyLoading(false)
        setLocationMessage(
          error.code === error.PERMISSION_DENIED
            ? t("explore.location.denied")
            : error.code === error.TIMEOUT
              ? t("explore.location.timeout")
              : t("explore.location.unavailable"),
        )
      },
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 120000 },
    )
  }

  function selectInstitutionSuggestion(institution: Institution) {
    setInstitutionQuery(institution.name)
    setAppliedInstitutionQuery(institution.name)
    setActiveSuggestionIndex(-1)
    setShowSuggestions(false)
    setActiveTab("institutions")
  }

  const suggestionListVisible =
    showSuggestions &&
    institutionQuery.trim().length >= 2 &&
    (suggestionsLoading || suggestionsError || suggestionsLoaded)

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

      <section
        aria-label={t("explore.institutions.search")}
        className="rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface) p-4"
      >
        <form
          className="flex flex-col gap-2 sm:flex-row"
          onSubmit={handleInstitutionSearch}
        >
          <div className="relative min-w-0 flex-1">
            <label
              htmlFor="institution-search"
              className="mb-1 block text-xs font-semibold text-(--color-ink-muted)"
            >
              {t("explore.institutions.search")}
            </label>
            <div className="relative">
              <Icon
                name="search"
                size={16}
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-(--color-ink-muted)"
              />
              <input
                id="institution-search"
                type="search"
                autoComplete="off"
                role="combobox"
                aria-autocomplete="list"
                aria-expanded={suggestionListVisible}
                aria-controls="institution-suggestions"
                aria-activedescendant={
                  activeSuggestionIndex >= 0
                    ? `institution-suggestion-${activeSuggestionIndex}`
                    : undefined
                }
                value={institutionQuery}
                onChange={(event) => {
                  const query = event.target.value
                  setInstitutionQuery(query)
                  setActiveSuggestionIndex(-1)
                  setInstitutionSuggestions([])
                  setSuggestionsLoaded(false)
                  setSuggestionsError(false)
                  setSuggestionsLoading(false)
                  setShowSuggestions(true)
                }}
                onFocus={() => setShowSuggestions(true)}
                onKeyDown={(event) => {
                  if (event.key === "Escape") {
                    setShowSuggestions(false)
                    setActiveSuggestionIndex(-1)
                  } else if (
                    event.key === "ArrowDown" &&
                    institutionSuggestions.length > 0
                  ) {
                    event.preventDefault()
                    setShowSuggestions(true)
                    setActiveSuggestionIndex((index) =>
                      Math.min(index + 1, institutionSuggestions.length - 1),
                    )
                  } else if (
                    event.key === "ArrowUp" &&
                    institutionSuggestions.length > 0
                  ) {
                    event.preventDefault()
                    setShowSuggestions(true)
                    setActiveSuggestionIndex((index) =>
                      index <= 0 ? institutionSuggestions.length - 1 : index - 1,
                    )
                  } else if (
                    event.key === "Enter" &&
                    activeSuggestionIndex >= 0 &&
                    institutionSuggestions[activeSuggestionIndex]
                  ) {
                    event.preventDefault()
                    selectInstitutionSuggestion(
                      institutionSuggestions[activeSuggestionIndex],
                    )
                  }
                }}
                placeholder={t("explore.institutions.search_placeholder")}
                className="w-full rounded-(--radius-md) border border-(--color-line) bg-(--color-page) py-2 pl-9 pr-3 text-sm text-(--color-ink) focus:border-(--color-primary) focus:outline-hidden focus:ring-2 focus:ring-(--color-primary-soft)"
              />
              {suggestionListVisible && (
                  <div
                    id="institution-suggestions"
                    role="listbox"
                    className="absolute z-20 mt-1 max-h-64 w-full overflow-auto rounded-(--radius-md) border border-(--color-line) bg-(--color-surface) shadow-lg"
                  >
                    {suggestionsLoading ? (
                      <p className="px-3 py-2 text-sm text-(--color-ink-muted)">
                        {t("explore.institutions.searching")}
                      </p>
                    ) : suggestionsError ? (
                      <p role="alert" className="px-3 py-2 text-sm text-(--color-error)">
                        {t("explore.institutions.search_error")}
                      </p>
                    ) : institutionSuggestions.length === 0 ? (
                      <p className="px-3 py-2 text-sm text-(--color-ink-muted)">
                        {t("explore.institutions.no_suggestions")}
                      </p>
                    ) : (
                      institutionSuggestions.map((institution, index) => (
                        <button
                          key={institution.id}
                          id={`institution-suggestion-${index}`}
                          type="button"
                          role="option"
                          aria-selected={activeSuggestionIndex === index}
                          onMouseEnter={() => setActiveSuggestionIndex(index)}
                          onClick={() => selectInstitutionSuggestion(institution)}
                          className={`flex w-full items-start gap-2 px-3 py-2 text-left text-sm hover:bg-(--color-surface-sunken) focus:bg-(--color-surface-sunken) focus:outline-hidden ${
                            activeSuggestionIndex === index ? "bg-(--color-surface-sunken)" : ""
                          }`}
                        >
                          <Icon name="building" size={16} />
                          <span className="min-w-0">
                            <span className="block truncate font-semibold">
                              {institution.name}
                            </span>
                            {institution.address && (
                              <span className="block truncate text-xs text-(--color-ink-muted)">
                                {institution.address}
                              </span>
                            )}
                          </span>
                        </button>
                      ))
                    )}
                  </div>
              )}
            </div>
          </div>
          <div className="flex items-end gap-2">
            <Button type="submit" variant="primary" size="md">
              {t("explore.institutions.search_button")}
            </Button>
          </div>
        </form>

        <div className="mt-3 flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 text-xs font-semibold text-(--color-ink-muted)">
            {t("explore.institutions.radius")}
            <select
              aria-label={t("explore.institutions.radius")}
              value={nearbyRadius}
              onChange={(event) => {
                setNearbyRadius(Number(event.target.value))
                setNearbySearched(false)
                setNearbyInstitutions([])
                setNearbyError(false)
              }}
              className="rounded-(--radius-md) border border-(--color-line) bg-(--color-page) px-2.5 py-1.5 text-sm text-(--color-ink)"
            >
              <option value={1000}>1 km</option>
              <option value={5000}>5 km</option>
              <option value={10000}>10 km</option>
              <option value={25000}>25 km</option>
            </select>
          </label>
          <Button
            type="button"
            variant="outline"
            size="md"
            icon="map"
            disabled={nearbyLoading}
            onClick={handleUseCurrentLocation}
          >
            {nearbyLoading
              ? t("explore.location.loading")
              : t("explore.location.near_me")}
          </Button>
          <p className="self-center text-xs text-(--color-ink-muted)">
            {t("explore.location.privacy")}
          </p>
        </div>
        {locationMessage && (
          <p role="status" className="mt-2 text-sm text-(--color-error)">
            {locationMessage}
          </p>
        )}
      </section>

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
        {activeTab === "institutions" && nearbySearched && (
          <section aria-labelledby="nearby-institutions-heading" className="space-y-3">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 id="nearby-institutions-heading" className="text-sm font-bold">
                {t("explore.location.results_heading")}
              </h2>
              <span className="text-xs text-(--color-ink-muted)">
                {t("explore.location.results_radius", {
                  radius: String(nearbyRadius / 1000),
                })}
              </span>
            </div>
            {nearbyError ? (
              <div
                role="alert"
                className="rounded-(--radius-lg) border border-(--color-error)/30 bg-(--color-error)/5 p-5 text-center"
              >
                <p className="text-sm text-(--color-ink)">
                  {t("explore.location.search_error")}
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-3"
                  onClick={handleUseCurrentLocation}
                >
                  {t("common.retry")}
                </Button>
              </div>
            ) : nearbyInstitutions.length > 0 ? (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {nearbyInstitutions.map((institution) => (
                  <article
                    key={institution.id}
                    className="rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface) p-4"
                  >
                    <div className="flex items-start gap-3">
                      <Icon name="building" size={18} />
                      <div className="min-w-0 flex-1">
                        <Link
                          href={`/${locale}/institutions/${institution.id}`}
                          className="font-semibold text-(--color-primary-strong) hover:underline"
                        >
                          {institution.name}
                        </Link>
                        <p className="mt-1 text-xs text-(--color-ink-muted)">
                          {institution.type_name ?? institution.type_code ?? t("nav.institutions")}
                        </p>
                        <p className="mt-2 text-xs capitalize text-(--color-ink-muted)">
                          {institution.operational_status.replaceAll("_", " ")}
                          {" · "}
                          {institution.distance_m >= 1000
                            ? `${(institution.distance_m / 1000).toFixed(1)} km`
                            : `${Math.round(institution.distance_m)} m`}
                        </p>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="rounded-(--radius-lg) border border-dashed border-(--color-line) p-6 text-center">
                <p className="text-sm font-semibold">
                  {t("explore.location.no_results")}
                </p>
                <p className="mt-1 text-xs text-(--color-ink-muted)">
                  {t("explore.location.no_results_hint")}
                </p>
              </div>
            )}
          </section>
        )}

        {loading ? (
          <Skeleton height={280} />
        ) : dataError ? (
          <div role="alert" className="rounded-(--radius-lg) border border-(--color-error)/30 bg-(--color-error)/5 p-8 text-center">
            <p className="text-sm text-(--color-ink)">{t("explore.load_error")}</p>
            <Button variant="outline" size="sm" className="mt-4" onClick={() => setReloadVersion((version) => version + 1)}>
              {t("common.retry")}
            </Button>
          </div>
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
        ) : dataError ? null : activeTab === "reports" ? (
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
