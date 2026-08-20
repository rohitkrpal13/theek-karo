"use client"

import { useCallback, useEffect, useState } from "react"
import { ProvenanceBadge } from "@/components/ui/data"
import { Skeleton } from "@/components/ui/primitives"
import { govdataApi } from "@/lib/api"
import type {
  DataQualityReport,
  EntityMatchReviewItem,
  DataSourceItem,
} from "@/lib/types"

export default function AdminGovernmentDataPage() {
  const [quality, setQuality] = useState<DataQualityReport | null>(null)
  const [matches, setMatches] = useState<EntityMatchReviewItem[]>([])
  const [sources, setSources] = useState<DataSourceItem[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedSource, setSelectedSource] = useState<string>("")
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState<string | null>(null)

  const loadAdminData = useCallback(async () => {
    try {
      const [qData, mData, sData] = await Promise.all([
        govdataApi.getDataQualityReport().catch(() => null),
        govdataApi.listEntityMatches({ review_status: "pending" }).catch(() => []),
        govdataApi.listDataSources().catch(() => []),
      ])
      setQuality(qData)
      setMatches(mData)
      setSources(sData)
      if (sData.length > 0 && !selectedSource) {
        setSelectedSource(sData[0].id)
      }
    } catch (err) {
      console.error("Failed to load admin government data", err)
    } finally {
      setLoading(false)
    }
  }, [selectedSource])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      const [qData, mData, sData] = await Promise.all([
        govdataApi.getDataQualityReport().catch(() => null),
        govdataApi.listEntityMatches({ review_status: "pending" }).catch(() => [] as EntityMatchReviewItem[]),
        govdataApi.listDataSources().catch(() => [] as DataSourceItem[]),
      ])
      if (cancelled) return
      setQuality(qData)
      setMatches(mData)
      setSources(sData)
      setSelectedSource((cur) =>
        cur && sData.some((s) => s.id === cur) ? cur : (sData[0]?.id ?? "")
      )
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const handleReviewDecision = async (
    reviewId: string,
    decision: "confirm" | "reject" | "create_new"
  ) => {
    try {
      await govdataApi.reviewEntityMatch(reviewId, { decision })
      setMatches((prev) => prev.filter((m) => m.id !== reviewId))
    } catch (err) {
      console.error("Failed to submit review decision", err)
    }
  }

  const handleTriggerImport = async (dryRun: boolean = false) => {
    if (!selectedSource) return
    setImporting(true)
    setImportResult(null)
    try {
      const job = await govdataApi.triggerImportJob({
        dataset_id: selectedSource,
        dry_run: dryRun,
        raw_payload: {
          records: [
            {
              school_name: "Govt Secondary School Jaipur West",
              udise_code: "UDISE-0812999",
              total_students: 480,
              sanctioned_teachers: 15,
              working_teachers: 14,
              vacancies: 1,
              toilets_total: 6,
              drinking_water: true,
            },
          ],
        },
      })
      setImportResult(
        `Import job ${job.run_id} completed: ${job.rows_imported || 0} rows imported, ${
          job.rows_total || 0
        } total rows.`
      )
      void loadAdminData()
    } catch (err: unknown) {
      setImportResult(`Import failed: ${err instanceof Error ? err.message : "Unknown error"}`)
    } finally {
      setImporting(false)
    }
  }

  if (loading) {
    return (
      <div className="space-y-6 max-w-6xl mx-auto py-6">
        <Skeleton height={100} />
        <Skeleton height={200} />
        <Skeleton height={300} />
      </div>
    )
  }

  return (
    <div className="space-y-8 max-w-6xl mx-auto py-6">
      {/* Admin Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-(--color-line) pb-5">
        <div>
          <div className="flex items-center gap-2">
            <ProvenanceBadge tier="official" />
            <span className="rounded-full bg-rose-500/10 border border-rose-500/20 px-2.5 py-0.5 text-xs font-semibold text-rose-600 dark:text-rose-400">
              Admin & Analyst Portal
            </span>
          </div>
          <h1 className="mt-2 text-2xl font-black text-(--color-ink) tracking-tight">
            Government Data & Entity Match Control Center
          </h1>
          <p className="text-xs text-(--color-ink-muted)">
            Manage connector ingestions, entity resolution reviews, and data quality metrics.
          </p>
        </div>

        <button
          type="button"
          onClick={() => {
            setLoading(true)
            void loadAdminData()
          }}
          className="rounded-xl border border-(--color-line) bg-(--color-surface-raised) hover:bg-(--color-surface-sunken) px-4 py-2 text-xs font-semibold text-(--color-ink) transition self-start sm:self-auto"
        >
          Refresh Data
        </button>
      </div>

      {/* Quality Scorecard */}
      {quality && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="rounded-2xl border border-(--color-line) bg-(--color-surface) p-4 backdrop-blur-xl">
            <span className="text-xs text-(--color-ink-muted)">Official Datasets</span>
            <div className="mt-1 text-2xl font-black text-(--color-ink)">{quality.total_datasets}</div>
            <span className="text-[11px] text-emerald-700 dark:text-emerald-400">100% Active</span>
          </div>

          <div className="rounded-2xl border border-(--color-line) bg-(--color-surface) p-4 backdrop-blur-xl">
            <span className="text-xs text-(--color-ink-muted)">Data Coverage</span>
            <div className="mt-1 text-2xl font-black text-sky-700 dark:text-sky-400">{quality.official_data_coverage_pct}%</div>
            <span className="text-[11px] text-(--color-ink-muted)">Across Institutions</span>
          </div>

          <div className="rounded-2xl border border-(--color-line) bg-(--color-surface) p-4 backdrop-blur-xl">
            <span className="text-xs text-(--color-ink-muted)">Pending Match Reviews</span>
            <div className="mt-1 text-2xl font-black text-amber-700 dark:text-amber-400">{quality.pending_entity_matches_count}</div>
            <span className="text-[11px] text-(--color-ink-muted)">Awaiting Decision</span>
          </div>

          <div className="rounded-2xl border border-(--color-line) bg-(--color-surface) p-4 backdrop-blur-xl">
            <span className="text-xs text-(--color-ink-muted)">Flagged Discrepancies</span>
            <div className="mt-1 text-2xl font-black text-purple-600 dark:text-purple-400">{quality.total_discrepancies_flagged}</div>
            <span className="text-[11px] text-(--color-ink-muted)">Active Investigations</span>
          </div>
        </div>
      )}

      {/* Connector Ingestion Trigger Panel */}
      <div className="rounded-2xl border border-(--color-line) bg-(--color-surface) p-6 backdrop-blur-xl">
        <h2 className="text-base font-bold text-(--color-ink)">Trigger Government Data Connector Import</h2>
        <p className="mt-1 text-xs text-(--color-ink-muted)">
          Execute automated schema validation, PII scrubbing, canonical transformation, and entity resolution.
        </p>

        <div className="mt-4 flex flex-col sm:flex-row items-center gap-3">
          <select
            value={selectedSource}
            onChange={(e) => setSelectedSource(e.target.value)}
            className="w-full sm:w-80 rounded-xl border border-(--color-line) bg-(--color-surface-raised) px-3.5 py-2 text-xs text-(--color-ink) focus:outline-none focus:border-sky-500"
          >
            {sources.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} ({s.source_type})
              </option>
            ))}
          </select>

          <div className="flex gap-2 w-full sm:w-auto">
            <button
              type="button"
              disabled={importing || !selectedSource}
              onClick={() => handleTriggerImport(true)}
              className="flex-1 sm:flex-none rounded-xl border border-(--color-line) bg-(--color-surface-raised) hover:bg-(--color-surface-sunken) px-4 py-2 text-xs font-semibold text-(--color-ink) transition disabled:opacity-50"
            >
              Dry Run
            </button>
            <button
              type="button"
              disabled={importing || !selectedSource}
              onClick={() => handleTriggerImport(false)}
              className="flex-1 sm:flex-none rounded-xl bg-sky-500 hover:bg-sky-400 px-4 py-2 text-xs font-semibold text-(--color-ink) shadow-lg shadow-sky-500/20 transition disabled:opacity-50"
            >
              {importing ? "Importing..." : "Execute Import"}
            </button>
          </div>
        </div>

        {importResult && (
          <div className="mt-3.5 rounded-xl border border-(--color-line) bg-(--color-surface-sunken) p-3 text-xs font-mono text-(--color-ink)">
            {importResult}
          </div>
        )}
      </div>

      {/* Entity Match Review Queue */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-(--color-ink)">
            Entity Match Resolution Queue ({matches.length})
          </h2>
          <span className="text-xs text-(--color-ink-muted)">
            Manual verification for low-confidence or conflicting record matches
          </span>
        </div>

        {matches.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-(--color-line) p-8 text-center text-sm text-(--color-ink-muted)">
            No pending entity matches awaiting administrative review. All records resolved.
          </div>
        ) : (
          <div className="space-y-3">
            {matches.map((m) => (
              <div
                key={m.id}
                className="rounded-2xl border border-(--color-line) bg-(--color-surface) p-4 backdrop-blur-xl flex flex-col md:flex-row md:items-center justify-between gap-4"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="rounded-full bg-amber-500/10 border border-amber-500/20 px-2.5 py-0.5 text-xs font-semibold text-amber-700 dark:text-amber-400">
                      Score: {Math.round(m.match_confidence * 100)}% ({m.match_status})
                    </span>
                    <span className="font-mono text-xs text-(--color-ink-muted)">Key: {m.external_key}</span>
                  </div>

                  <h3 className="mt-2 text-sm font-bold text-(--color-ink)">
                    External Record: {typeof m.raw_data?.school_name === "string" ? m.raw_data.school_name : ""}
                  </h3>
                  <p className="text-xs text-(--color-ink-muted)">
                    Candidate Target: <strong className="text-(--color-ink)">{m.candidate_institution_name || "No matching institution found"}</strong>
                  </p>
                </div>

                <div className="flex items-center gap-2 self-end md:self-auto">
                  <button
                    type="button"
                    onClick={() => handleReviewDecision(m.id, "confirm")}
                    className="rounded-lg bg-emerald-500/20 border border-emerald-500/30 hover:bg-emerald-500/30 px-3 py-1.5 text-xs font-semibold text-emerald-700 dark:text-emerald-400 transition"
                  >
                    Confirm Match
                  </button>
                  <button
                    type="button"
                    onClick={() => handleReviewDecision(m.id, "reject")}
                    className="rounded-lg bg-(--color-surface-raised) hover:bg-(--color-surface-sunken) px-3 py-1.5 text-xs font-semibold text-(--color-ink-muted) transition"
                  >
                    Reject
                  </button>
                  <button
                    type="button"
                    onClick={() => handleReviewDecision(m.id, "create_new")}
                    className="rounded-lg bg-sky-500/20 border border-sky-500/30 hover:bg-sky-500/30 px-3 py-1.5 text-xs font-semibold text-sky-700 dark:text-sky-400 transition"
                  >
                    Create New
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
