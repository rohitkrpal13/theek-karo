"use client"

import Link from "next/link"
import { useParams } from "next/navigation"

import { FormattedDate } from "@/components/FormattedDate"
import { useT } from "@/lib/i18n-client"
import type { Category, Report } from "@/lib/types"

const ICONS: Record<string, string> = {
  school: "🏫",
  hospital: "🏥",
  road: "🛣️",
  water: "💧",
  sanitation: "🗑️",
  public_transport: "🚌",
  police_station: "🛡️",
  court: "⚖️",
  public_facility: "🏞️",
  panchayat: "🏛️",
  municipal_service: "🏗️",
  government_office: "🏢",
  bridge: "🌉",
  other: "📌",
}

export function CategoryCard({ category }: { category: Category }) {
  const t = useT()
  const params = useParams<{ locale?: string }>()
  const submitPath = `/${params.locale ?? "en"}/submit?category=${encodeURIComponent(category.slug)}`

  return (
    <Link
      href={submitPath}
      className="flex items-center gap-3 rounded-lg border border-stone-200 bg-white p-4 shadow-sm transition hover:border-(--color-primary) hover:shadow"
    >
      <span aria-hidden="true" className="text-2xl">
        {ICONS[category.slug] ?? "📌"}
      </span>
      <span>
        <span className="block text-sm font-semibold text-ink">
          {t(`category.${category.slug}.label` as never) || category.slug}
        </span>
        <span className="block text-xs text-stone-600">
          {t(`category.${category.slug}.description` as never) || "—"}
        </span>
      </span>
    </Link>
  )
}

export function ReportCard({ report }: { report: Report }) {
  const params = useParams<{ locale?: string }>()
  const path = `/${params.locale ?? "en"}/reports/${report.id}`

  return (
    <Link
      href={path}
      className="block rounded-lg border border-stone-200 bg-white p-4 shadow-sm transition hover:border-(--color-primary)"
    >
      <div className="flex items-start justify-between gap-2">
        <h3 lang="en" className="font-semibold text-ink">{report.title}</h3>
        <span className="shrink-0 font-mono text-xs text-stone-600">{report.ticket_no}</span>
      </div>
      <p className="mt-1 line-clamp-2 text-sm text-stone-600">{report.description}</p>
      <div className="mt-3 flex items-center gap-3 text-xs text-stone-600">
        <StatusPill status={report.status} />
        <FormattedDate iso={report.created_at} />
      </div>
    </Link>
  )
}

export function StatusPill({ status }: { status: string }) {
  const t = useT()
  const tones: Record<string, string> = {
    submitted: "bg-amber-100 text-amber-900",
    under_verification: "bg-sky-100 text-sky-900",
    verified: "bg-teal-100 text-teal-900",
    assigned: "bg-indigo-100 text-indigo-900",
    in_progress: "bg-indigo-100 text-indigo-900",
    resolved: "bg-emerald-100 text-emerald-900",
    resolution_verified: "bg-teal-100 text-teal-900",
    closed: "bg-stone-200 text-stone-700",
    rejected: "bg-red-100 text-red-900",
    reopened: "bg-orange-100 text-orange-900",
    duplicate_merged: "bg-stone-200 text-stone-700",
  }
  return (
    <span
      className={`rounded-full px-2 py-0.5 font-medium ${tones[status] ?? "bg-stone-100 text-stone-700"}`}
    >
      {t(`report.status.${status}` as never)}
    </span>
  )
}