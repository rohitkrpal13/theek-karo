"use client"

import { useEffect, useState } from "react"
import { useParams, useSearchParams } from "next/navigation"

import { InstitutionCard } from "@/components/InstitutionCard"
import { Button, Skeleton } from "@/components/ui/primitives"
import { institutionsApi, geographyApi } from "@/lib/api"
import type { Geography, Institution, InstitutionType } from "@/lib/types"
import { useT } from "@/lib/i18n-client"

export default function InstitutionsPage() {
  const params = useParams<{ locale?: string }>()
  const searchParams = useSearchParams()
  const locale = params.locale ?? "en"
  const t = useT()

  const [types, setTypes] = useState<InstitutionType[]>([])
  const [geographies, setGeographies] = useState<Geography[]>([])
  const [institutions, setInstitutions] = useState<Institution[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)

  // Filter state
  const [selectedType, setSelectedType] = useState(searchParams.get("type_id") ?? "")
  const [selectedGeo, setSelectedGeo] = useState(searchParams.get("geography_id") ?? "")
  const [searchQuery, setSearchQuery] = useState("")

  useEffect(() => {
    async function loadMeta() {
      try {
        const [tList, gList] = await Promise.all([
          institutionsApi.listTypes(),
          geographyApi.list({ limit: 50 }),
        ])
        setTypes(tList)
        setGeographies(gList.items)
      } catch (err) {
        console.error("Failed to load institutions metadata", err)
      }
    }
    void loadMeta()
  }, [])

  useEffect(() => {
    let cancelled = false

    async function fetchInstitutions() {
      setLoading(true)
      try {
        const res = await institutionsApi.list({
          type_id: selectedType || undefined,
          geography_id: selectedGeo || undefined,
          q: searchQuery.trim() || undefined,
          page,
          limit: 12,
        })
        if (!cancelled) {
          setInstitutions(res.items)
          setTotal(res.total)
        }
      } catch (err) {
        console.error("Failed to fetch institutions", err)
        if (!cancelled) {
          setInstitutions([])
          setTotal(0)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void fetchInstitutions()
    return () => {
      cancelled = true
    }
  }, [selectedType, selectedGeo, searchQuery, page])

  void locale

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-black tracking-tight">{t("institutions.title")}</h1>
        <p className="text-sm text-(--color-ink-muted)">
          {t("institutions.subtitle")}
        </p>
      </div>

      {/* Filter & Search Bar */}
      <div className="flex flex-wrap items-center gap-3 rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface) p-4 shadow-xs">
        {/* Search input */}
        <div className="flex-1 min-w-[200px]">
          <label htmlFor="inst-search" className="text-xs font-semibold text-(--color-ink-muted)">
            Search by name
          </label>
          <input
            id="inst-search"
            type="search"
            placeholder="e.g. Government High School, AIIMS…"
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value)
              setPage(1)
            }}
            className="mt-1 w-full rounded-(--radius-md) border border-(--color-line) bg-(--color-page) px-3 py-1.5 text-xs text-(--color-ink) focus:border-(--color-primary) focus:outline-hidden"
          />
        </div>

        {/* Institution Type filter */}
        <div className="w-44">
          <label htmlFor="inst-type-select" className="text-xs font-semibold text-(--color-ink-muted)">
            {t("institutions.type")}
          </label>
          <select
            id="inst-type-select"
            value={selectedType}
            onChange={(e) => {
              setSelectedType(e.target.value)
              setPage(1)
            }}
            className="mt-1 w-full rounded-(--radius-md) border border-(--color-line) bg-(--color-page) px-2.5 py-1.5 text-xs text-(--color-ink)"
          >
            <option value="">{t("explore.filter.all")}</option>
            {types.map((type) => (
              <option key={type.id} value={type.id}>
                {type.code.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        </div>

        {/* Geography filter */}
        <div className="w-48">
          <label htmlFor="geo-select" className="text-xs font-semibold text-(--color-ink-muted)">
            State / Region
          </label>
          <select
            id="geo-select"
            value={selectedGeo}
            onChange={(e) => {
              setSelectedGeo(e.target.value)
              setPage(1)
            }}
            className="mt-1 w-full rounded-(--radius-md) border border-(--color-line) bg-(--color-page) px-2.5 py-1.5 text-xs text-(--color-ink)"
          >
            <option value="">{t("explore.filter.all")}</option>
            {geographies.map((geo) => (
              <option key={geo.id} value={geo.id}>
                {geo.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Results Header */}
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-(--color-ink-muted)">
          Showing {institutions.length} of {total} institutions
        </span>
      </div>

      {/* Institution Cards Grid */}
      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} height={180} />
          ))}
        </div>
      ) : institutions.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {institutions.map((inst) => {
            const typeMatch = types.find((t) => t.id === inst.type_id)
            const geoMatch = geographies.find((g) => g.id === inst.geography_id)
            return (
              <InstitutionCard
                key={inst.id}
                institution={inst}
                typeName={typeMatch?.code}
                geographyName={geoMatch?.name}
              />
            )
          })}
        </div>
      ) : (
        <div className="rounded-(--radius-lg) border border-dashed border-(--color-line) p-12 text-center">
          <p className="text-sm text-(--color-ink-muted)">
            {t("institutions.empty")}
          </p>
        </div>
      )}

      {/* Pagination Controls */}
      {total > 12 && (
        <div className="flex items-center justify-center gap-2 pt-4">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            Previous
          </Button>
          <span className="text-xs text-(--color-ink-muted)">
            Page {page} of {Math.ceil(total / 12)}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= Math.ceil(total / 12)}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  )
}
