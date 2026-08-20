"use client"

import React from "react"
import type { DiscrepancyState, ResourceComparisonItem } from "@/lib/types"

interface DiscrepancyCardProps {
  item: ResourceComparisonItem
  onVerify?: () => void
  className?: string
}

export function DiscrepancyCard({ item, onVerify, className = "" }: DiscrepancyCardProps) {
  const getBadgeStyle = (state: DiscrepancyState) => {
    switch (state) {
      case "NO_DISCREPANCY_DETECTED":
        return {
          bg: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/30",
          label: "Data Consistent",
          icon: "✓",
        }
      case "POSSIBLE_DISCREPANCY":
        return {
          bg: "bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/30",
          label: "Possible Discrepancy",
          icon: "!",
        }
      case "OUTDATED_OFFICIAL_DATA":
        return {
          bg: "bg-sky-500/10 text-sky-700 dark:text-sky-400 border-sky-500/30",
          label: "Official Data May Be Outdated",
          icon: "⏱",
        }
      case "CONFLICTING_DATA":
        return {
          bg: "bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/30",
          label: "Conflicting Information",
          icon: "⟷",
        }
      case "UNDER_REVIEW":
        return {
          bg: "bg-indigo-500/10 text-indigo-400 border-indigo-500/30",
          label: "Under Verification Review",
          icon: "🔍",
        }
      default:
        return {
          bg: "bg-zinc-500/10 text-(--color-ink-muted) border-zinc-500/30",
          label: "Insufficient Observation Data",
          icon: "•",
        }
    }
  }

  const badge = getBadgeStyle(item.discrepancy_state)

  const formatVal = (v: unknown) => {
    if (typeof v === "boolean") return v ? "Available / Functional" : "Unavailable"
    if (v === null || v === undefined) return "Not recorded"
    return String(v)
  }

  return (
    <div
      className={`rounded-2xl border border-(--color-line)/80 bg-(--color-surface-raised)/50 p-5 shadow-lg backdrop-blur-xl transition hover:border-(--color-line)/80 ${className}`}
      data-testid={`discrepancy-card-${item.resource_key}`}
    >
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-(--color-line)/50 pb-3.5">
        <div>
          <h4 className="text-base font-bold text-(--color-ink)">{item.label}</h4>
          <span className="text-xs text-(--color-ink-muted)">
            Source: {item.official_source || "Official Dataset"} ({item.official_updated_at || "Published"})
          </span>
        </div>

        <span
          className={`inline-flex items-center gap-1.5 self-start sm:self-auto rounded-full border px-3 py-1 text-xs font-semibold ${badge.bg}`}
        >
          <span>{badge.icon}</span>
          <span>{badge.label}</span>
        </span>
      </div>

      {/* Comparison Grid: Official vs Citizen vs AI */}
      <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3.5 text-xs">
        {/* Official Baseline */}
        <div className="rounded-xl border border-(--color-line)/80 bg-(--color-surface-sunken) p-3.5">
          <div className="text-(--color-ink-muted) font-semibold flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-sky-400" />
            Official Benchmark
          </div>
          <div className="mt-1.5 text-sm font-bold text-(--color-ink)">
            {formatVal(item.official_value)}
          </div>
        </div>

        {/* Citizen Observations */}
        <div className="rounded-xl border border-(--color-line)/80 bg-(--color-surface-sunken) p-3.5">
          <div className="text-(--color-ink-muted) font-semibold flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-amber-400" />
            Community Observations
          </div>
          <div className="mt-1.5 text-xs text-(--color-ink) font-medium leading-relaxed">
            {item.citizen_observation_summary || "No conflicting observations reported"}
          </div>
        </div>
      </div>

      {/* AI Analysis Note */}
      {item.ai_analysis_note && (
        <div className="mt-3.5 rounded-xl border border-(--color-line)/60 bg-(--color-surface-raised)/20 p-3 text-xs text-(--color-ink-muted)">
          <div className="text-[11px] font-semibold text-sky-700 dark:text-sky-400 flex items-center gap-1.5">
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            System Synthesis Note
          </div>
          <p className="mt-1 text-(--color-ink-muted) leading-normal">
            {item.ai_analysis_note}
          </p>
        </div>
      )}

      {/* Action Footer */}
      {item.discrepancy_state === "POSSIBLE_DISCREPANCY" && (
        <div className="mt-4 flex items-center justify-between pt-2 border-t border-(--color-line)/40">
          <span className="text-[11px] text-(--color-ink-muted)">
            Observations differ from official records. Local verification helps keep data accurate.
          </span>
          {onVerify && (
            <button
              type="button"
              onClick={onVerify}
              className="inline-flex items-center gap-1.5 rounded-lg bg-amber-500/10 border border-amber-500/30 hover:bg-amber-500/20 px-3 py-1.5 text-xs font-semibold text-amber-700 dark:text-amber-400 transition"
            >
              Verify On-Ground
            </button>
          )}
        </div>
      )}
    </div>
  )
}
