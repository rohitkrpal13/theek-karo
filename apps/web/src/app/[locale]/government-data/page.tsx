"use client"

import { useEffect, useState } from "react"
import { ProvenanceBadge } from "@/components/ui/data"
import { Skeleton } from "@/components/ui/primitives"
import { ProvenancePanel } from "@/components/govdata/ProvenancePanel"
import { govdataApi } from "@/lib/api"
import type { DataSourceItem, ProvenanceDetail } from "@/lib/types"

export default function GovernmentDataPage() {
  const [sources, setSources] = useState<DataSourceItem[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedProvenance, setSelectedProvenance] = useState<ProvenanceDetail | null>(null)
  const [filterType, setFilterType] = useState<string>("all")

  useEffect(() => {
    let cancelled = false
    async function loadSources() {
      setLoading(true)
      try {
        const data = await govdataApi.listDataSources()
        if (!cancelled) setSources(data)
      } catch (err) {
        console.error("Failed to load government data sources", err)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void loadSources()
    return () => {
      cancelled = true
    }
  }, [])

  const filteredSources = sources.filter((s) => {
    if (filterType === "all") return true
    return s.source_type.toLowerCase() === filterType.toLowerCase()
  })

  const handleOpenAudit = (s: DataSourceItem) => {
    setSelectedProvenance({
      source_id: s.id,
      source_name: s.name,
      publisher: s.publisher || "Official Authority",
      dataset_identifier: s.dataset_identifier || s.version,
      dataset_version: s.version,
      license: s.license,
      source_url: s.url,
      retrieval_date: s.retrieval_date,
      publication_date: s.publication_date,
      transformation_version: "canonical_v1",
    })
  }

  return (
    <div className="space-y-8 max-w-6xl mx-auto py-4">
      {/* Header */}
      <div className="space-y-3">
        <div className="flex items-center gap-2.5">
          <ProvenanceBadge tier="official" />
          <span className="text-xs font-semibold text-sky-700 dark:text-sky-400 bg-sky-500/10 px-2.5 py-0.5 rounded-full border border-sky-500/20">
            Open Civic Registry
          </span>
        </div>
        <h1 className="text-3xl font-black text-(--color-ink) tracking-tight">
          Government & Public Data Registry
        </h1>
        <p className="max-w-3xl text-sm text-(--color-ink-muted) leading-relaxed">
          Official datasets and portal feeds are integrated with complete provenance — publishing authority,
          retrieval timestamp, dataset version, and public license. Absence of data is shown honestly, and citizen
          observations are never conflated with official administrative records.
        </p>
      </div>

      {/* Trust Principles Banner */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 rounded-2xl border border-(--color-line) bg-(--color-surface) p-5 backdrop-blur-xl">
        <div className="space-y-1.5 p-2">
          <div className="text-xs font-bold text-sky-700 dark:text-sky-400 flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-sky-400" />
            Clear Source Provenance
          </div>
          <p className="text-xs text-(--color-ink-muted)">
            Every administrative baseline links to its verified publishing authority and license.
          </p>
        </div>

        <div className="space-y-1.5 p-2">
          <div className="text-xs font-bold text-amber-700 dark:text-amber-400 flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-amber-400" />
            Neutral Comparison
          </div>
          <p className="text-xs text-(--color-ink-muted)">
            Discrepancies highlight differences objectively without accusatory assumptions.
          </p>
        </div>

        <div className="space-y-1.5 p-2">
          <div className="text-xs font-bold text-emerald-700 dark:text-emerald-400 flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-emerald-400" />
            Time-Travel Integrity
          </div>
          <p className="text-xs text-(--color-ink-muted)">
            Records maintain historical snapshots answering what was officially recorded at any given date.
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center justify-between border-b border-(--color-line) pb-4">
        <div className="flex gap-2">
          {[
            { key: "all", label: "All Registries" },
            { key: "official_dataset", label: "Official Datasets" },
            { key: "official_api", label: "Official APIs" },
            { key: "official_portal", label: "Portals" },
          ].map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => setFilterType(tab.key)}
              className={`rounded-full px-3.5 py-1.5 text-xs font-semibold transition ${
                filterType === tab.key
                  ? "bg-sky-500 text-(--color-ink) shadow-md shadow-sky-500/20"
                  : "bg-(--color-surface-sunken) text-(--color-ink-muted) hover:text-(--color-ink)"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <span className="text-xs text-(--color-ink-muted) font-medium">
          {filteredSources.length} Approved Sources
        </span>
      </div>

      {/* Sources Grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Skeleton height={140} />
          <Skeleton height={140} />
          <Skeleton height={140} />
          <Skeleton height={140} />
        </div>
      ) : filteredSources.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-(--color-line) p-12 text-center text-sm text-(--color-ink-muted)">
          No registered data sources match the selected filter.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredSources.map((source) => (
            <div
              key={source.id}
              className="rounded-2xl border border-(--color-line)/80 bg-(--color-surface) p-5 backdrop-blur-xl shadow-lg hover:border-(--color-line) transition flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between gap-2">
                  <span className="rounded-full bg-(--color-surface-raised) px-2.5 py-0.5 text-[11px] font-mono text-(--color-ink-muted) capitalize border border-(--color-line)">
                    {source.source_type.replace(/_/g, " ")}
                  </span>
                  <span className="text-xs font-medium text-emerald-700 dark:text-emerald-400 bg-emerald-500/10 px-2.5 py-0.5 rounded-full border border-emerald-500/20">
                    {source.verification_state}
                  </span>
                </div>

                <h3 className="mt-3 text-base font-bold text-(--color-ink) tracking-tight">
                  {source.name}
                </h3>
                <p className="mt-1 text-xs text-(--color-ink-muted) font-medium">
                  Publisher: <strong className="text-(--color-ink-muted)">{source.publisher || "Central Public Authority"}</strong>
                </p>

                {source.dataset_identifier && (
                  <p className="mt-1 text-xs font-mono text-(--color-ink-muted)">
                    ID: {source.dataset_identifier} (v{source.version || "1.0"})
                  </p>
                )}
              </div>

              <div className="mt-5 flex items-center justify-between pt-3 border-t border-(--color-line)/60 text-xs">
                <span className="text-(--color-ink-muted)">
                  Retrieved: {new Date(source.retrieval_date).toLocaleDateString()}
                </span>
                <button
                  type="button"
                  onClick={() => handleOpenAudit(source)}
                  className="rounded-lg bg-(--color-surface-raised) hover:bg-(--color-surface-sunken) px-3 py-1.5 font-medium text-(--color-ink) hover:text-(--color-ink) transition"
                >
                  View Provenance
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Provenance Audit Modal */}
      {selectedProvenance && (
        <ProvenancePanel
          provenance={selectedProvenance}
          onClose={() => setSelectedProvenance(null)}
        />
      )}
    </div>
  )
}
