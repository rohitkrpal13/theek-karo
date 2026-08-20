"use client"

import type { ReactNode } from "react"

import { Badge } from "@/components/ui/primitives"
import { en, type TFunction } from "@/lib/i18n"

export function SectionCard({
  title,
  children,
  limitations = [],
}: {
  title: string
  children: ReactNode
  limitations?: string[]
}) {
  return (
    <section className="rounded-(--radius-xl) border border-(--color-line) bg-(--color-surface) p-5 shadow-xs">
      <h3 className="font-semibold text-(--color-ink)">{title}</h3>
      <div className="mt-3">{children}</div>
      {limitations.length > 0 && (
        <ul className="mt-4 space-y-1 border-t border-(--color-line) pt-3 text-xs text-(--color-ink-muted)">
          {limitations.map((limitation) => (
            <li key={limitation}>• {limitation}</li>
          ))}
        </ul>
      )}
    </section>
  )
}

export const DIRECTION_LABELS: Record<string, string> = {
  increasing: "intelligence.direction.increasing",
  decreasing: "intelligence.direction.decreasing",
  stable: "intelligence.direction.stable",
  insufficient_data: "intelligence.insufficientData",
}

export function directionTone(direction: string): string {
  if (direction === "increasing") return "error"
  if (direction === "decreasing") return "success"
  if (direction === "stable") return "default"
  return "info"
}

export function directionLabel(t: TFunction, direction: string): string {
  const key = DIRECTION_LABELS[direction]
  return key ? t(key as keyof typeof en) : direction
}

export function signalStatusTone(status: string): string {
  const tones: Record<string, string> = {
    NEW: "info",
    IN_REVIEW: "warning",
    CONFIRMED: "success",
    MONITORED: "warning",
    RESOLVED: "success",
    ESCALATED: "error",
    DISMISSED: "default",
  }
  return tones[status] ?? "default"
}

export function severityTone(severity: string): string {
  const tones: Record<string, string> = {
    CRITICAL: "error",
    HIGH: "error",
    MEDIUM: "warning",
    LOW: "default",
  }
  return tones[severity] ?? "default"
}

export function statusBadge(t: TFunction, status: string): ReactNode {
  const key = `intelligence.signal.status.${status}` as keyof typeof en
  const label = key in en ? t(key) : status
  return <Badge tone={signalStatusTone(status)}>{label}</Badge>
}

export function fmtDate(value: string | null | undefined, locale: string): string {
  if (!value) return "—"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "—"
  return new Intl.DateTimeFormat(locale, { dateStyle: "medium" }).format(date)
}

export function fmtNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—"
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}
