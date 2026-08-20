"use client"

import React from "react"
import type { ProvenanceDetail } from "@/lib/types"

interface ProvenancePanelProps {
  provenance: ProvenanceDetail
  onClose: () => void
}

export function ProvenancePanel({ provenance, onClose }: ProvenancePanelProps) {
  const formatDate = (dStr?: string | null) => {
    if (!dStr) return "Not specified"
    try {
      return new Date(dStr).toLocaleDateString("en-IN", {
        year: "numeric",
        month: "short",
        day: "numeric",
      })
    } catch {
      return dStr
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md animate-fadeIn">
      <div className="relative w-full max-w-lg rounded-2xl border border-(--color-line) bg-(--color-surface-raised) p-6 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-(--color-line) pb-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-700 dark:text-sky-400">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <div>
              <h3 className="text-base font-semibold text-(--color-ink)">Data Provenance & Source Audit</h3>
              <p className="text-xs text-(--color-ink-muted)">Traceability record for canonical indicators</p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded-lg p-1.5 text-(--color-ink-muted) hover:bg-(--color-surface-raised) hover:text-(--color-ink) transition"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Audit Details */}
        <div className="mt-5 space-y-3.5 text-xs">
          <div className="flex justify-between py-1.5 border-b border-(--color-line)/50">
            <span className="text-(--color-ink-muted) font-medium">Source Registry</span>
            <span className="text-(--color-ink) font-medium">{provenance.source_name}</span>
          </div>

          <div className="flex justify-between py-1.5 border-b border-(--color-line)/50">
            <span className="text-(--color-ink-muted) font-medium">Publishing Authority</span>
            <span className="text-(--color-ink) font-medium">{provenance.publisher}</span>
          </div>

          <div className="flex justify-between py-1.5 border-b border-(--color-line)/50">
            <span className="text-(--color-ink-muted) font-medium">Dataset Version</span>
            <span className="font-mono text-(--color-ink)">{provenance.dataset_version || "Latest"}</span>
          </div>

          <div className="flex justify-between py-1.5 border-b border-(--color-line)/50">
            <span className="text-(--color-ink-muted) font-medium">Published Date</span>
            <span className="text-(--color-ink)">{formatDate(provenance.publication_date)}</span>
          </div>

          <div className="flex justify-between py-1.5 border-b border-(--color-line)/50">
            <span className="text-(--color-ink-muted) font-medium">System Retrieval Date</span>
            <span className="text-(--color-ink)">{formatDate(provenance.retrieval_date)}</span>
          </div>

          <div className="flex justify-between py-1.5 border-b border-(--color-line)/50">
            <span className="text-(--color-ink-muted) font-medium">Public License</span>
            <span className="text-emerald-700 dark:text-emerald-400 font-medium">{provenance.license || "Open Government Data (OGD)"}</span>
          </div>

          {provenance.checksum_sha256 && (
            <div className="py-1.5 border-b border-(--color-line)/50">
              <span className="text-(--color-ink-muted) font-medium block mb-1">SHA-256 Checksum</span>
              <span className="font-mono text-[10px] text-(--color-ink-muted) break-all bg-(--color-surface-sunken) px-2 py-1 rounded block border border-(--color-line)">
                {provenance.checksum_sha256}
              </span>
            </div>
          )}

          {provenance.source_url && (
            <div className="pt-2">
              <a
                href={provenance.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-xs text-sky-700 dark:text-sky-400 hover:text-sky-300 font-medium hover:underline"
              >
                <span>Visit Official Source Portal</span>
                <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
              </a>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="mt-6 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl bg-(--color-surface-raised) hover:bg-(--color-surface-sunken) px-4 py-2 text-xs font-semibold text-(--color-ink) transition"
          >
            Close Audit
          </button>
        </div>
      </div>
    </div>
  )
}
