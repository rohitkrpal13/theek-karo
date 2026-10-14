"use client"

import Link from "next/link"
import { useCallback, useEffect, useState } from "react"

import { casesApi, type CaseDetail, type CaseStatus } from "@/lib/api/cases"
import { useLocale } from "@/lib/i18n-client"
import { en } from "@/lib/i18n"
import type { TFunction } from "@/lib/i18n"
import { useT } from "@/lib/i18n-client"
import { Badge, EmptyState, ErrorState, Spinner } from "@/components/ui/primitives"
import { useRealtimeEvents } from "@/hooks/useRealtimeEvents"

export const CASE_STATUS_KEYS = new Set([
  "under_review",
  "acknowledged",
  "action_planned",
  "waiting_for_information",
  "resolution_under_review",
  "resolution_rejected",
  "partially_resolved",
])

export function caseStatusLabel(t: TFunction, status: CaseStatus): string {
  const key = (CASE_STATUS_KEYS.has(status)
    ? `case.status.${status}`
    : `report.status.${status}`) as keyof typeof en
  return t(key)
}

export function CaseStatusBadge({ status }: { status: CaseStatus }) {
  const t = useT()
  const tone =
    status === "resolved" || status === "closed"
      ? "success"
      : status === "rejected" || status === "duplicate" || status === "resolution_rejected"
        ? "danger"
        : status === "in_progress" || status === "action_planned" || status === "acknowledged"
          ? "info"
          : "default"
  return <Badge tone={tone}>{caseStatusLabel(t, status)}</Badge>
}

export function CaseList() {
  const t = useT()
  const locale = useLocale()
  const [cases, setCases] = useState<CaseDetail[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const res = await casesApi.list({ limit: 100 })
      setCases(res.items)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }, [])

  // Auto-reload on real-time case events
  const { isConnected } = useRealtimeEvents({
    onEvent: (event) => {
      if (
        event === "case.created" ||
        event === "case.transitioned" ||
        event === "case.assigned" ||
        event === "case.responded" ||
        event === "case.escalated"
      ) {
        void load()
      }
    },
  })

  useEffect(() => {
    let cancelled = false
    async function loadCases() {
      try {
        const res = await casesApi.list({ limit: 100 })
        if (!cancelled) setCases(res.items)
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err))
      }
    }
    void loadCases()
    return () => {
      cancelled = true
    }
  }, [])

  if (error) return <ErrorState title={t("cases.title")} detail={error} onRetry={load} />
  if (cases === null) return <Spinner label={t("cases.title")} />
  if (cases.length === 0) return <EmptyState title={t("cases.empty")} />

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs text-stone-500 px-1">
        <span className="flex items-center gap-1.5 font-medium">
          <span
            className={`inline-block h-2 w-2 rounded-full ${
              isConnected ? "bg-emerald-500 animate-pulse" : "bg-amber-500"
            }`}
          />
          {isConnected ? "Live Case Sync Active" : "Polling Case Status"}
        </span>
        <button
          type="button"
          onClick={() => void load()}
          className="hover:text-stone-800 underline underline-offset-2"
        >
          Refresh
        </button>
      </div>
      <ul className="divide-y divide-stone-200 rounded-md border border-stone-200 bg-white">
      {cases.map((c) => (
        <li key={c.id}>
          <Link
            href={`/${locale}/cases/${c.id}`}
            className="flex flex-wrap items-center gap-3 px-4 py-3 hover:bg-stone-50"
          >
            <span className="font-mono text-sm font-semibold text-(--color-primary-strong)">{c.case_no}</span>
            <CaseStatusBadge status={c.status} />
            {c.severity && (
              <span className="text-xs text-stone-500">
                {t("cases.severity")}:{" "}
                {t(`report.severity.${c.severity}` as keyof typeof en)}
              </span>
            )}
            <span className="ml-auto text-xs text-stone-400">
              {new Date(c.created_at).toLocaleDateString()}
            </span>
          </Link>
        </li>
      ))}
      </ul>
    </div>
  )
}