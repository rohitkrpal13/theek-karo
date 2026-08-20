"use client"

import { useState } from "react"
import { Icon as IconCmp } from "@/components/ui/icons"
import type { CategoryAnalyticsItem } from "@/lib/types"

interface CategoryBreakdownProps {
  categories: CategoryAnalyticsItem[]
  totalReports: number
}

export function CategoryBreakdownChart({ categories, totalReports }: CategoryBreakdownProps) {
  const [expandedSlug, setExpandedSlug] = useState<string | null>(null)

  if (!categories || categories.length === 0) {
    return (
      <div className="rounded-(--radius-xl) border border-(--color-line) bg-(--color-surface) p-6 text-center text-sm text-(--color-ink-muted)">
        No category distribution data available.
      </div>
    )
  }

  return (
    <div className="rounded-(--radius-xl) border border-(--color-line) bg-(--color-surface) p-5 space-y-4">
      <div>
        <h3 className="text-base font-bold text-(--color-ink)">Issues by Category</h3>
        <p className="text-xs text-(--color-ink-muted)">
          Drill down into specific issue types for each domain. Total: {totalReports.toLocaleString()} reports.
        </p>
      </div>

      <div className="space-y-3">
        {categories.map((cat) => {
          const isExpanded = expandedSlug === cat.category_slug

          return (
            <div
              key={cat.category_slug}
              className="rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface-raised) p-3 transition"
            >
              <div className="flex items-center justify-between gap-3 text-sm">
                <button
                  type="button"
                  onClick={() => setExpandedSlug(isExpanded ? null : cat.category_slug)}
                  className="flex items-center gap-2 font-semibold text-(--color-ink) hover:text-(--color-primary) text-left"
                >
                  <IconCmp
                    name={isExpanded ? "close" : "explore"}
                    size={16}
                    className="text-(--color-primary)"
                  />
                  <span>{cat.category_name}</span>
                </button>
                <div className="flex items-center gap-2 font-mono text-xs">
                  <span className="font-bold">{cat.report_count}</span>
                  <span className="text-(--color-ink-muted)">({cat.pct_of_total}%)</span>
                </div>
              </div>

              {/* Progress bar */}
              <div className="mt-2 h-2 w-full rounded-full bg-(--color-line) overflow-hidden">
                <div
                  className="h-full bg-(--color-primary) rounded-full transition-all duration-300"
                  style={{ width: `${Math.min(100, Math.max(2, cat.pct_of_total))}%` }}
                />
              </div>

              {/* Nested Issue Types */}
              {isExpanded && cat.top_issue_types.length > 0 ? (
                <div className="mt-3 pt-3 border-t border-(--color-line) space-y-2">
                  <p className="text-xs font-semibold text-(--color-ink-muted)">Top Issue Types:</p>
                  <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                    {cat.top_issue_types.map((it) => (
                      <li
                        key={it.slug}
                        className="flex items-center justify-between p-2 rounded bg-(--color-surface) border border-(--color-line)"
                      >
                        <span className="text-(--color-ink)">{it.name}</span>
                        <span className="font-mono font-semibold text-(--color-ink-muted)">
                          {it.count} ({it.pct}%)
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          )
        })}
      </div>
    </div>
  )
}
