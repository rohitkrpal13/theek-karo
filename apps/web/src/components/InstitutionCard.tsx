"use client"

import Link from "next/link"
import { useParams } from "next/navigation"
import { Icon } from "@/components/ui/icons"
import { ProvenanceBadge } from "@/components/ui/data"
import type { Institution, TrustTier } from "@/lib/types"

export interface InstitutionCardProps {
  institution: Institution
  typeName?: string
  geographyName?: string
}

export function InstitutionCard({
  institution,
  typeName,
  geographyName,
}: InstitutionCardProps) {
  const params = useParams<{ locale?: string }>()
  const locale = params?.locale ?? "en"

  const statusColor =
    institution.operational_status === "operational"
      ? "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800"
      : institution.operational_status === "under_construction"
        ? "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800"
        : "bg-stone-50 text-stone-700 border-stone-200 dark:bg-stone-900/40 dark:text-stone-300 dark:border-stone-700"

  const trustTier: TrustTier =
    institution.verification_state === "official"
      ? "official"
      : institution.verification_state === "community_verified"
        ? "community_verified"
        : "citizen"

  return (
    <article className="group flex flex-col justify-between rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface) p-4 transition-all hover:border-(--color-primary) hover:shadow-(--elevation-sm)">
      <div className="space-y-2">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <span className="inline-block rounded-full bg-(--color-surface-sunken) px-2.5 py-0.5 text-xs font-semibold text-(--color-primary-strong) uppercase">
              {typeName ?? "Public Institution"}
            </span>
            <h3 className="mt-1 text-base font-bold text-(--color-ink) transition-colors group-hover:text-(--color-primary)">
              <Link
                href={`/${locale}/institutions/${institution.id}`}
                className="focus:outline-hidden"
              >
                {institution.name}
              </Link>
            </h3>
          </div>
          <span
            className={`shrink-0 rounded-full border px-2 py-0.5 text-xs font-medium capitalize ${statusColor}`}
          >
            {institution.operational_status.replace("_", " ")}
          </span>
        </div>

        {institution.description ? (
          <p className="line-clamp-2 text-xs text-(--color-ink-muted)">
            {institution.description}
          </p>
        ) : null}

        <div className="flex flex-wrap items-center gap-3 pt-1 text-xs text-(--color-ink-muted)">
          {geographyName ? (
            <span className="flex items-center gap-1">
              <Icon name="map" size={14} />
              {geographyName}
            </span>
          ) : null}
          {institution.official_id ? (
            <span className="font-mono text-(--text-caption)">
              ID: {institution.official_id}
            </span>
          ) : null}
        </div>
      </div>

      <div className="mt-4 flex items-center justify-between border-t border-(--color-line) pt-3">
        <ProvenanceBadge tier={trustTier} />
        <Link
          href={`/${locale}/institutions/${institution.id}`}
          className="flex items-center gap-1 text-xs font-semibold text-(--color-primary-strong) hover:underline"
        >
          <span>View Digital Twin</span>
          <Icon name="chevron" size={14} />
        </Link>
      </div>
    </article>
  )
}
