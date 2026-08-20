"use client"

import React, { useState } from "react"
import type { OfficialDataResponse } from "@/lib/types"
import { ProvenancePanel } from "./ProvenancePanel"

interface OfficialDataCardProps {
  data: OfficialDataResponse
  className?: string
}

export function OfficialDataCard({ data, className = "" }: OfficialDataCardProps) {
  const [showProvenance, setShowProvenance] = useState(false)
  const canonical = data.canonical_data || {}

  const formatKey = (key: string) => {
    return key
      .replace(/_/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase())
  }

  const formatVal = (val: unknown) => {
    if (typeof val === "boolean") {
      return val ? (
        <span className="inline-flex items-center gap-1 text-emerald-700 dark:text-emerald-400 font-medium">
          <span className="h-2 w-2 rounded-full bg-emerald-400" /> Available
        </span>
      ) : (
        <span className="inline-flex items-center gap-1 text-(--color-ink-muted) font-medium">
          <span className="h-2 w-2 rounded-full bg-zinc-500" /> Unavailable
        </span>
      )
    }
    if (Array.isArray(val)) {
      return val.length > 0 ? val.join(", ") : "None published"
    }
    if (val === null || val === undefined) {
      return <span className="text-(--color-ink-muted)">Not recorded</span>
    }
    return String(val)
  }

  const entries = Object.entries(canonical)

  return (
    <div
      className={`rounded-2xl border border-(--color-line)/80 bg-(--color-surface) p-6 backdrop-blur-xl shadow-xl ${className}`}
      data-testid="official-data-card"
    >
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-(--color-line)/60 pb-5">
        <div>
          <div className="flex items-center gap-2.5">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-sky-500/30 bg-sky-500/10 px-3 py-1 text-xs font-semibold text-sky-700 dark:text-sky-400">
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
              Official Public Record
            </span>
            {data.official_identifier && (
              <span className="text-xs font-mono text-(--color-ink-muted) bg-(--color-surface-sunken) px-2.5 py-0.5 rounded-md border border-(--color-line)/50">
                Code: {data.official_identifier}
              </span>
            )}
          </div>
          <h3 className="mt-2 text-xl font-bold text-(--color-ink) tracking-tight">
            {data.institution_name}
          </h3>
          <p className="mt-1 text-xs text-(--color-ink-muted) flex items-center gap-2">
            <span>Type: <strong className="text-(--color-ink-muted) font-medium capitalize">{data.institution_type}</strong></span>
            <span>•</span>
            <span className="text-emerald-700 dark:text-emerald-400/90">{data.freshness_label}</span>
          </p>
        </div>

        {data.provenance && (
          <button
            type="button"
            onClick={() => setShowProvenance(true)}
            className="inline-flex items-center gap-2 self-start sm:self-auto rounded-xl border border-(--color-line)/80 bg-(--color-surface-sunken) hover:bg-(--color-surface-sunken)/80 px-3.5 py-2 text-xs font-medium text-(--color-ink) transition shadow-sm hover:text-(--color-ink)"
          >
            <svg className="h-4 w-4 text-sky-700 dark:text-sky-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Audit Provenance
          </button>
        )}
      </div>

      {/* Structured Canonical Attributes Grid */}
      {entries.length === 0 ? (
        <div className="py-8 text-center text-sm text-(--color-ink-muted)">
          No official indicators currently recorded for this institution.
        </div>
      ) : (
        <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {entries.map(([key, val]) => (
            <div
              key={key}
              className="rounded-xl border border-(--color-line)/60 bg-(--color-surface-sunken) p-3.5 hover:border-(--color-line) transition"
            >
              <div className="text-xs font-medium text-(--color-ink-muted)">
                {formatKey(key)}
              </div>
              <div className="mt-1 text-sm font-semibold text-(--color-ink)">
                {formatVal(val)}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Provenance Details Drawer Modal */}
      {showProvenance && data.provenance && (
        <ProvenancePanel
          provenance={data.provenance}
          onClose={() => setShowProvenance(false)}
        />
      )}
    </div>
  )
}
