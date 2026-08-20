"use client"

import { useSearchParams } from "next/navigation"
import { GlobalSearch } from "@/components/GlobalSearch"
import type { SearchDomain } from "@/lib/types"
import { useT } from "@/lib/i18n-client"

export default function SearchPage() {
  const searchParams = useSearchParams()
  const t = useT()

  const q = searchParams.get("q") ?? ""
  const domain = (searchParams.get("domain") as SearchDomain) ?? "all"

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-black tracking-tight">{t("search.title")}</h1>
        <p className="text-sm text-(--color-ink-muted)">
          Discover public institutions, local geographical areas, civic issue reports, and service categories.
        </p>
      </div>

      <div className="rounded-(--radius-xl) border border-(--color-line) bg-(--color-surface) p-6 shadow-xs">
        <GlobalSearch
          initialQuery={q}
          initialDomain={domain}
          isExpanded={true}
          autoFocus={!q}
        />
      </div>
    </div>
  )
}
