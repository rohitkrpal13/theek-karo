"use client"

import { Badge } from "@/components/ui/primitives"
import type { DataQualityScorecardResponse } from "@/lib/types"

interface DataQualityScorecardProps {
  scorecard: DataQualityScorecardResponse
}

export function DataQualityScorecard({ scorecard }: DataQualityScorecardProps) {
  return (
    <div className="rounded-(--radius-xl) border border-(--color-line) bg-(--color-surface) p-5 space-y-4">
      <div>
        <h3 className="text-base font-bold text-(--color-ink)">Government Data Quality & Provenance</h3>
        <p className="text-xs text-(--color-ink-muted)">
          Telemetry on public dataset imports, health states, and entity reconciliation.
        </p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface-raised) p-3 text-center">
          <span className="text-xs text-(--color-ink-muted)">Healthy Datasets</span>
          <p className="text-2xl font-extrabold text-emerald-600 mt-1">
            {scorecard.healthy_sources_count}
          </p>
          <span className="text-[10px] text-(--color-ink-muted)">
            of {scorecard.total_sources} total sources
          </span>
        </div>

        <div className="rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface-raised) p-3 text-center">
          <span className="text-xs text-(--color-ink-muted)">Stale Datasets</span>
          <p className="text-2xl font-extrabold text-amber-600 mt-1">
            {scorecard.stale_sources_count}
          </p>
          <span className="text-[10px] text-(--color-ink-muted)">Needs re-ingestion</span>
        </div>

        <div className="rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface-raised) p-3 text-center">
          <span className="text-xs text-(--color-ink-muted)">Records Ingested</span>
          <p className="text-2xl font-extrabold text-(--color-ink) mt-1">
            {scorecard.total_records_ingested.toLocaleString()}
          </p>
          <span className="text-[10px] text-(--color-ink-muted)">Canonical snapshots</span>
        </div>

        <div className="rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface-raised) p-3 text-center">
          <span className="text-xs text-(--color-ink-muted)">Pending Match Reviews</span>
          <p className="text-2xl font-extrabold text-purple-600 mt-1">
            {scorecard.pending_entity_matches_count}
          </p>
          <span className="text-[10px] text-(--color-ink-muted)">Ambiguous records</span>
        </div>
      </div>

      {/* Sources list */}
      {scorecard.sources_breakdown && scorecard.sources_breakdown.length > 0 ? (
        <div className="overflow-x-auto rounded-(--radius-md) border border-(--color-line)">
          <table className="w-full text-left text-xs">
            <thead className="bg-(--color-surface-raised) text-(--color-ink-muted) border-b border-(--color-line)">
              <tr>
                <th className="p-2.5">Data Source</th>
                <th className="p-2.5">Publisher</th>
                <th className="p-2.5">Status</th>
                <th className="p-2.5">Base Confidence</th>
                <th className="p-2.5">Last Retrieval</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-(--color-line)">
              {scorecard.sources_breakdown.map((s) => (
                <tr key={s.id} className="hover:bg-(--color-surface-raised)">
                  <td className="p-2.5 font-semibold text-(--color-ink)">{s.name}</td>
                  <td className="p-2.5 text-(--color-ink-muted)">{s.publisher}</td>
                  <td className="p-2.5">
                    <Badge tone={s.status === "HEALTHY" ? "success" : "warning"} className="text-[10px]">
                      {s.status}
                    </Badge>
                  </td>
                  <td className="p-2.5 font-mono">{(s.confidence_base * 100).toFixed(0)}%</td>
                  <td className="p-2.5 text-(--color-ink-muted)">
                    {s.retrieval_date ? s.retrieval_date.slice(0, 10) : "N/A"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  )
}
