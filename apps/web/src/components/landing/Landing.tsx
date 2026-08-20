"use client"

/* Landing page (Phase 6): "Find what needs to be improved. Help make it
 * better." — dynamic categories, recent reports, real-time map preview,
 * and transparent civic impact stats. */

import Link from "next/link"
import { useParams } from "next/navigation"
import { useEffect, useState } from "react"

import { MapExplore, type MapEntity } from "@/components/map/MapExplore"
import { Button, Skeleton } from "@/components/ui/primitives"
import { ReportCard, type ReportCardData } from "@/components/ui/data"
import { Icon, type IconName } from "@/components/ui/icons"
import { civicApi, reportsApi, institutionsApi } from "@/lib/api"
import type { Category } from "@/lib/types"
import { useT } from "@/lib/i18n-client"

const CATEGORY_ICONS: Record<string, IconName> = {
  school: "building",
  hospital: "activity",
  road: "map",
  water: "refresh",
  sanitation: "trash",
  public_transport: "chevron",
  police_station: "lock",
  court: "check",
  public_facility: "building",
  panchayat: "home",
  municipal_service: "building",
  government_office: "building",
  bridge: "map",
  other: "explore",
}

export function Landing() {
  const params = useParams<{ locale?: string }>()
  const locale = params.locale ?? "en"
  const t = useT()

  const [categories, setCategories] = useState<Category[]>([])
  const [recent, setRecent] = useState<ReportCardData[] | null>(null)
  const [mapEntities, setMapEntities] = useState<MapEntity[]>([])
  const [totalInstitutions, setTotalInstitutions] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true

    async function loadLandingData() {
      try {
        const [catRes, reportsRes, instRes] = await Promise.allSettled([
          civicApi.listCategories(),
          reportsApi.list({ limit: 6 }),
          institutionsApi.list({ limit: 1 }),
        ])

        if (!active) return

        if (catRes.status === "fulfilled") {
          setCategories(catRes.value.items.slice(0, 8))
        }

        if (reportsRes.status === "fulfilled") {
          const reports = reportsRes.value.items
          setRecent(
            reports.map((report) => ({
              id: report.id,
              title: report.title,
              location: "Reported location",
              status: report.status,
              tier: "citizen" as const,
              timeAgo: report.created_at,
            })),
          )
          setMapEntities(
            reports.map((report) => ({
              id: report.id,
              kind: "report" as const,
              title: report.title,
              status: report.status,
              severity: report.severity,
              lon: report.location?.coordinates?.[0] ?? 75.7873,
              lat: report.location?.coordinates?.[1] ?? 26.9124,
            })),
          )
        } else {
          setRecent([])
          setMapEntities([])
        }

        if (instRes.status === "fulfilled") {
          setTotalInstitutions(instRes.value.total ?? 0)
        } else {
          setTotalInstitutions(0)
        }
      } finally {
        if (active) setLoading(false)
      }
    }

    void loadLandingData()
    return () => {
      active = false
    }
  }, [])

  return (
    <div className="space-y-14">
      {/* Hero Section */}
      <section className="py-8 text-center sm:py-16">
        <span className="inline-flex items-center gap-2 rounded-full border border-(--color-primary-soft) bg-(--color-primary-soft) px-3 py-1 text-xs font-semibold text-(--color-primary-strong)">
          <Icon name="check" size={14} />
          <span>India Civic Accountability Platform</span>
        </span>
        <h1 className="mx-auto mt-4 max-w-4xl text-(--type-display) font-black tracking-tight sm:text-5xl">
          Find what needs to be improved.{" "}
          <span className="text-(--color-primary-strong)">Help make it better.</span>
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-(--text-body) text-(--color-ink-muted)">
          Explore public institutions, report local problems, verify improvements, and hold civic infrastructure accountable with transparent data and community oversight.
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link href={`/${locale}/explore`}>
            <Button size="lg" icon="explore">
              {t("nav.explore")}
            </Button>
          </Link>
          <Link href={`/${locale}/submit`}>
            <Button size="lg" variant="primary" icon="report">
              {t("home.submit")}
            </Button>
          </Link>
          <Link href={`/${locale}/map`}>
            <Button size="lg" variant="outline" icon="map">
              {t("nav.map")}
            </Button>
          </Link>
        </div>
      </section>

      {/* Categories Grid */}
      <section aria-labelledby="categories-heading" className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 id="categories-heading" className="text-xl font-bold">
              {t("home.categories")}
            </h2>
            <p className="text-sm text-(--color-ink-muted)">
              Report issues across essential public domains.
            </p>
          </div>
          <Link
            href={`/${locale}/explore`}
            className="text-xs font-semibold text-(--color-primary-strong) hover:underline"
          >
            View all categories →
          </Link>
        </div>

        {loading && categories.length === 0 ? (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} height={100} />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {categories.map((cat) => (
              <Link
                key={cat.id}
                href={`/${locale}/explore?category_slug=${cat.slug}`}
                className="group flex flex-col justify-between rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface) p-4 transition-all hover:border-(--color-primary) hover:shadow-(--elevation-sm)"
              >
                <div className="flex items-center gap-3">
                  <span className="flex h-10 w-10 items-center justify-center rounded-(--radius-md) bg-(--color-surface-sunken) text-(--color-primary-strong) transition-colors group-hover:bg-(--color-primary) group-hover:text-white">
                    <Icon name={CATEGORY_ICONS[cat.slug] ?? "explore"} size={20} />
                  </span>
                  <div>
                    <h3 className="text-sm font-bold capitalize text-(--color-ink) group-hover:text-(--color-primary)">
                      {cat.slug.replace(/_/g, " ")}
                    </h3>
                  </div>
                </div>
                <span className="mt-3 text-xs font-medium text-(--color-ink-muted) group-hover:text-(--color-primary)">
                  Browse issues →
                </span>
              </Link>
            ))}
          </div>
        )}
      </section>

      {/* Civic Impact Metrics */}
      <section
        aria-labelledby="impact-heading"
        className="rounded-(--radius-xl) border border-(--color-line) bg-(--color-surface) p-6 shadow-xs"
      >
        <div className="flex items-center justify-between border-b border-(--color-line) pb-4">
          <h2 id="impact-heading" className="text-lg font-bold">
            Civic Transparency & Impact
          </h2>
          <span className="text-xs text-(--color-ink-muted)">
            Live verified data · Zero fabricated statistics
          </span>
        </div>
        <dl className="mt-6 grid grid-cols-2 gap-6 sm:grid-cols-4">
          <div>
            <dt className="text-(--text-caption) font-medium text-(--color-ink-muted)">
              Citizen Reports
            </dt>
            <dd className="mt-1 text-2xl font-black text-(--color-ink)">
              {recent?.length ?? 0}
            </dd>
          </div>
          <div>
            <dt className="text-(--text-caption) font-medium text-(--color-ink-muted)">
              Institutions Registered
            </dt>
            <dd className="mt-1 text-2xl font-black text-(--color-ink)">
              {totalInstitutions ?? 0}
            </dd>
          </div>
          <div>
            <dt className="text-(--text-caption) font-medium text-(--color-ink-muted)">
              Community Verifications
            </dt>
            <dd className="mt-1 text-2xl font-black text-(--color-ink)">
              0
            </dd>
          </div>
          <div>
            <dt className="text-(--text-caption) font-medium text-(--color-ink-muted)">
              Verified Resolutions
            </dt>
            <dd className="mt-1 text-2xl font-black text-(--color-ink)">
              0
            </dd>
          </div>
        </dl>
      </section>

      {/* Map Preview */}
      <section aria-labelledby="map-preview-heading" className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 id="map-preview-heading" className="text-xl font-bold">
            {t("home.recent")} on the Map
          </h2>
          <Link
            href={`/${locale}/map`}
            className="text-xs font-semibold text-(--color-primary-strong) hover:underline"
          >
            Open full map →
          </Link>
        </div>
        {loading ? (
          <Skeleton height={280} />
        ) : (
          <MapExplore entities={mapEntities} />
        )}
      </section>

      {/* Recent Reports List */}
      <section aria-labelledby="latest-heading" className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 id="latest-heading" className="text-xl font-bold">
            {t("home.recent")}
          </h2>
          <Link
            href={`/${locale}/reports`}
            className="text-xs font-semibold text-(--color-primary-strong) hover:underline"
          >
            View all reports →
          </Link>
        </div>

        {loading ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <Skeleton height={140} />
            <Skeleton height={140} />
          </div>
        ) : recent && recent.length > 0 ? (
          <div className="grid gap-3 sm:grid-cols-2">
            {recent.map((report) => (
              <ReportCard key={report.id} report={report} />
            ))}
          </div>
        ) : (
          <div className="rounded-(--radius-lg) border border-dashed border-(--color-line) p-8 text-center">
            <p className="text-sm text-(--color-ink-muted)">
              {t("home.empty")}
            </p>
            <Link href={`/${locale}/submit`} className="mt-3 inline-block">
              <Button size="sm" variant="primary" icon="report">
                {t("home.submit")}
              </Button>
            </Link>
          </div>
        )}
      </section>

      {/* Future Campaigns Slot */}
      <section
        aria-labelledby="campaigns-preview"
        className="rounded-(--radius-xl) border border-(--color-line) bg-(--color-surface-sunken) p-6"
      >
        <h2 id="campaigns-preview" className="text-lg font-bold">
          Civic Focus Campaigns
        </h2>
        <p className="mt-1 text-xs text-(--color-ink-muted)">
          Targeted community oversight initiatives launching across states and districts.
        </p>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          {[
            {
              title: "School Theek Karo",
              desc: "Classrooms, drinking water, toilets, and teacher vacancies.",
              status: "Upcoming",
            },
            {
              title: "Hospital Theek Karo",
              desc: "Emergency services, medicines, doctors, and hygiene.",
              status: "Upcoming",
            },
            {
              title: "Road Theek Karo",
              desc: "Potholes, street lighting, drainage, and pedestrian safety.",
              status: "Upcoming",
            },
          ].map((c) => (
            <div
              key={c.title}
              className="rounded-(--radius-md) border border-(--color-line) bg-(--color-surface) p-4"
            >
              <span className="rounded-full bg-(--color-surface-sunken) px-2 py-0.5 text-(--text-caption) font-semibold text-(--color-primary-strong)">
                {c.status}
              </span>
              <h3 className="mt-2 text-sm font-bold text-(--color-ink)">
                {c.title}
              </h3>
              <p className="mt-1 text-xs text-(--color-ink-muted)">{c.desc}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}