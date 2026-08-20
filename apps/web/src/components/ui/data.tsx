"use client"

/* Domain data components: status/severity/provenance badges (icon+text+color,
 * never color alone), report/institution cards, timeline, table, comments,
 * AI insight + citations, language/theme selectors, search bar. */

import Link from "next/link"
import { useParams } from "next/navigation"

import type { ReactNode } from "react"

import { Avatar, Badge, Button, Combobox } from "@/components/ui/primitives"
import { Icon as IconCmp, type IconName } from "@/components/ui/icons"
import { languages as languageRegistry } from "@/theme/tokens"

/* ------------------------------- StatusBadge ------------------------------
 * WCAG: status is always icon + text + color. */

export type ReportStatus =
  | "draft" | "submitted" | "under_verification" | "verified" | "assigned"
  | "in_progress" | "resolution_submitted" | "resolution_review" | "resolved"
  | "resolution_verified" | "community_verified" | "needs_information"
  | "reopened" | "rejected" | "duplicate_merged" | "archived" | "closed"

const statusMeta: Record<ReportStatus, { icon: IconName; label: string; tone: string }> = {
  draft: { icon: "edit", label: "Draft", tone: "default" },
  submitted: { icon: "pin", label: "Submitted", tone: "info" },
  under_verification: { icon: "clock", label: "Under verification", tone: "warning" },
  verified: { icon: "check", label: "Verified", tone: "success" },
  assigned: { icon: "user", label: "Assigned", tone: "info" },
  in_progress: { icon: "activity", label: "In progress", tone: "warning" },
  resolution_submitted: { icon: "activity", label: "Resolution submitted", tone: "warning" },
  resolution_review: { icon: "clock", label: "Resolution review", tone: "warning" },
  resolved: { icon: "check", label: "Resolved", tone: "success" },
  resolution_verified: { icon: "check", label: "Resolution verified", tone: "success" },
  community_verified: { icon: "check", label: "Community verified", tone: "success" },
  needs_information: { icon: "clock", label: "Needs more information", tone: "warning" },
  reopened: { icon: "refresh", label: "Reopened", tone: "warning" },
  rejected: { icon: "close", label: "Rejected", tone: "error" },
  duplicate_merged: { icon: "info", label: "Duplicate merged", tone: "warning" },
  archived: { icon: "lock", label: "Archived", tone: "default" },
  closed: { icon: "check", label: "Closed", tone: "success" },
}

export function StatusBadge({ status }: { status: string }) {
  const meta = statusMeta[status as ReportStatus] ?? { icon: "info" as IconName, label: status, tone: "default" }
  return (
    <Badge tone={meta.tone}>
      <IconCmp name={meta.icon} size={14} />
      {meta.label}
    </Badge>
  )
}

/* ------------------------------- SeverityBadge ---------------------------- */

const severityMeta: Record<string, { icon: IconName; label: string; tone: string }> = {
  low: { icon: "info", label: "Low", tone: "success" },
  medium: { icon: "warning", label: "Medium", tone: "warning" },
  high: { icon: "warning", label: "High", tone: "warning" },
  critical: { icon: "warning", label: "Critical", tone: "error" },
}

export function SeverityBadge({ severity }: { severity: string }) {
  const meta = severityMeta[severity] ?? { icon: "info" as IconName, label: severity, tone: "default" }
  return (
    <Badge tone={meta.tone}>
      <IconCmp name={meta.icon} size={14} />
      {meta.label}
    </Badge>
  )
}

/* ------------------------------ ProvenanceBadge --------------------------- */

export type ProvenanceTier =
  | "official"
  | "verified"
  | "community_verified"
  | "community"
  | "citizen"
  | "ai"
  | "unverified"

const tierMeta: Record<ProvenanceTier, { label: string; tone: string; icon: IconName }> = {
  official: { label: "Official data", tone: "info", icon: "lock" },
  verified: { label: "Community verified", tone: "success", icon: "check" },
  community_verified: { label: "Community verified", tone: "success", icon: "check" },
  community: { label: "Community", tone: "info", icon: "user" },
  citizen: { label: "Citizen report", tone: "default", icon: "user" },
  ai: { label: "AI analysis", tone: "default", icon: "activity" },
  unverified: { label: "Unverified", tone: "warning", icon: "clock" },
}

export function ProvenanceBadge({ tier }: { tier: ProvenanceTier }) {
  const meta = tierMeta[tier]
  return (
    <Badge tone={meta.tone}>
      <IconCmp name={meta.icon} size={14} />
      {meta.label}
    </Badge>
  )
}

/* -------------------------------- ReportCard ------------------------------ */

export interface ReportCardData {
  id: string
  title: string
  location: string
  institution?: string
  status: string
  severity?: string
  tier: ProvenanceTier
  timeAgo: string
  reporter?: string
  hasMedia?: boolean
}

export function ReportCard({ report, expanded = false }: { report: ReportCardData; expanded?: boolean }) {
  const params = useParams<{ locale?: string }>()
  const href = `/${params.locale ?? "en"}/reports/${report.id}`
  return (
    <article className="rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface) p-4 shadow-(--elevation-sm)">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={report.status} />
            {report.severity ? <SeverityBadge severity={report.severity} /> : null}
            {report.tier ? <ProvenanceBadge tier={report.tier} /> : null}
          </div>
          <h3 className="mt-2 text-base font-semibold">
            <Link href={href} className="hover:underline">{report.title}</Link>
          </h3>
          <p className="text-sm text-(--color-ink-muted)">
            {report.location}
            {report.institution ? ` · ${report.institution}` : ""}
          </p>
        </div>
        {report.hasMedia ? <IconCmp name="camera" className="shrink-0 text-(--color-ink-muted)" /> : null}
      </div>
      {expanded ? (
        <div className="mt-3 flex items-center justify-between text-sm text-(--color-ink-muted)">
          <span>{report.reporter ?? "Citizen"}</span>
          <time dateTime={report.timeAgo}>{report.timeAgo}</time>
        </div>
      ) : (
        <p className="mt-3 text-(--text-caption) text-(--color-ink-muted)">
          {report.reporter ?? "Citizen"} · <time dateTime={report.timeAgo}>{report.timeAgo}</time>
        </p>
      )}
    </article>
  )
}

/* --------------------------- InstitutionCard ------------------------------ */

export interface InstitutionCardData {
  id: string
  name: string
  location: string
  type: string
  open: number
  resolved: number
  status?: string
}

export function InstitutionCard({ institution }: { institution: InstitutionCardData }) {
  const params = useParams<{ locale?: string }>()
  const href = `/${params.locale ?? "en"}/institutions/${institution.id}`
  return (
    <article className="rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface) p-4 shadow-(--elevation-sm)">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-semibold">
            <Link href={href} className="hover:underline">{institution.name}</Link>
          </h3>
          <p className="text-sm text-(--color-ink-muted)">{institution.type} · {institution.location}</p>
        </div>
        <Avatar name={institution.name} size={36} />
      </div>
      <div className="mt-3 flex gap-4 text-sm">
        <span><strong className="text-(--color-warning)">{institution.open}</strong> open</span>
        <span><strong className="text-(--color-success)">{institution.resolved}</strong> resolved</span>
        {institution.status ? <span className="text-(--color-ink-muted)">{institution.status}</span> : null}
      </div>
    </article>
  )
}

/* --------------------------------- Timeline ------------------------------- */

export interface TimelineEvent {
  id: string
  status: string
  actor?: string
  reason?: string
  when: string
}

export function Timeline({ events }: { events: TimelineEvent[] }) {
  return (
    <ol className="relative space-y-4 border-l border-(--color-line) pl-4">
      {events.map((event) => (
        <li key={event.id} className="relative">
          <span aria-hidden="true" className="absolute -left-[21px] mt-1 h-2.5 w-2.5 rounded-full bg-(--color-primary)" />
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={event.status} />
            <span className="text-(--text-caption) text-(--color-ink-muted)">
              {event.actor ?? "System"} · <time dateTime={event.when}>{event.when}</time>
            </span>
          </div>
          {event.reason ? <p className="mt-1 text-sm text-(--color-ink-muted)">{event.reason}</p> : null}
        </li>
      ))}
    </ol>
  )
}

/* -------------------------------- DataTable ------------------------------- */

export function DataTable({
  columns,
  rows,
  caption,
}: {
  columns: Array<{ key: string; label: string }>
  rows: Array<Record<string, ReactNode>>
  caption: string
}) {
  return (
    <div tabIndex={0} className="overflow-x-auto rounded-(--radius-md) border border-(--color-line)">
      <table className="w-full min-w-96 border-collapse text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b border-(--color-line) bg-(--color-surface-raised) text-left">
            {columns.map((column) => (
              <th key={column.key} scope="col" className="px-3 py-2 font-semibold text-(--color-ink-muted)">{column.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index} className="border-b border-(--color-line) last:border-0 hover:bg-(--color-primary-soft)">
              {columns.map((column) => (
                <td key={column.key} className="px-3 py-2">{row[column.key] ?? "—"}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/* ------------------------------ Accessible Chart ---------------------------
 * SVG bars/lines + a screen-reader text summary (the summary is the
 * accessible alternative; the graphic is aria-hidden). */

export function ChartBars({
  series,
  unit,
  summary,
}: {
  series: Array<{ label: string; value: number }>
  unit?: string
  summary: string
}) {
  const max = Math.max(...series.map((s) => s.value), 1)
  const width = 640
  const height = 220
  const pad = 28
  const innerWidth = width - pad * 2
  const barWidth = innerWidth / Math.max(series.length, 1) * 0.6
  return (
    <div>
      <p className="sr-only">{summary}</p>
      <svg
        role="img"
        aria-hidden="true"
        viewBox={`0 0 ${width} ${height}`}
        className="w-full"
      >
        {series.map((item, index) => {
          const x = pad + index * (innerWidth / Math.max(series.length, 1)) + (innerWidth / Math.max(series.length, 1) - barWidth) / 2
          const barHeight = (item.value / max) * (height - pad * 2)
          const y = height - pad - barHeight
          return (
            <g key={item.label}>
              <rect x={x} y={y} width={barWidth} height={barHeight} fill="var(--color-primary)" rx="3" />
              <text x={x + barWidth / 2} y={height - 10} textAnchor="middle" fontSize="10" fill="var(--color-ink-muted)">
                {item.label}
              </text>
              <text x={x + barWidth / 2} y={y - 6} textAnchor="middle" fontSize="10" fill="var(--color-ink)">
                {item.value}{unit ?? ""}
              </text>
            </g>
          )
        })}
      </svg>
      <p className="mt-1 text-sm text-(--color-ink-muted)">{summary}</p>
    </div>
  )
}

/* --------------------------------- AI Insight ------------------------------
 * "AI suggestion" is always labelled; accept/edit/reject never mutates user
 * input silently. */

export function AIInsight({
  suggestions,
  onAccept,
  onReject,
}: {
  suggestions: Array<{ label: string; value: string }>
  onAccept?: (value: string) => void
  onReject?: () => void
}) {
  return (
    <section aria-label="AI suggestion" className="rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface-raised) p-4">
      <div className="flex items-center gap-2">
        <IconCmp name="activity" size={18} className="text-(--color-tier-ai)" />
        <h4 className="text-sm font-semibold text-(--color-tier-ai)">AI suggestion</h4>
      </div>
      <ul className="mt-2 space-y-1">
        {suggestions.map((suggestion) => (
          <li key={suggestion.label} className="flex items-center justify-between gap-3 text-sm">
            <span className="text-(--color-ink-muted)">{suggestion.label}:</span>
            <strong>{suggestion.value}</strong>
          </li>
        ))}
      </ul>
      <div className="mt-3 flex gap-2">
        <Button size="sm" onClick={() => onAccept?.(suggestions[0]?.value ?? "")}>Accept</Button>
        <Button size="sm" variant="outline">Edit</Button>
        <Button size="sm" variant="ghost" onClick={onReject}>Reject</Button>
      </div>
    </section>
  )
}

/* ------------------------------ SourceCitation ---------------------------- */

export function SourceCitation({ source, url }: { source: string; url?: string }) {
  return (
    <li className="flex items-start gap-2 text-sm text-(--color-ink-muted)">
      <IconCmp name="lock" size={14} className="mt-0.5 shrink-0" />
      <span>
        {source}
        {url ? (
          <>
            {" "}
            ·{" "}
            <a href={url} target="_blank" rel="noopener noreferrer" className="text-(--color-info) underline">
              source
            </a>
          </>
        ) : null}
      </span>
    </li>
  )
}

/* ------------------------------ LanguageSelector --------------------------- */

export function LanguageSelector({ compact = false }: { compact?: boolean }) {
  const languages = languageRegistry
  const current = useParams<{ locale?: string }>().locale ?? "en"

  return (
    <nav aria-label="Language" className={compact ? "" : "rounded-(--radius-md) border border-(--color-line)"}>
      <ul className={compact ? "flex flex-wrap gap-1" : "max-h-72 overflow-y-auto p-2"}>
        {languages.map((language) => (
          <li key={language.code}>
            <Link
              href={`/${language.code}`}
              lang={language.code}
              dir={language.script === "urdu" ? "rtl" : "ltr"}
              aria-current={current === language.code ? "true" : undefined}
              className={`block px-3 py-1.5 text-sm ${
                current === language.code
                  ? "font-semibold text-(--color-primary-strong) bg-(--color-primary-soft)"
                  : "text-(--color-ink-muted) hover:bg-(--color-line)"
              }`}
            >
              {language.native}
              {!compact ? <span className="ml-2 text-(--text-caption) text-(--color-ink-muted)">— {language.english}</span> : null}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  )
}

/* --------------------------------- SearchBar ------------------------------ */

export function SearchBar({ placeholder = "Search institutions, places, reports…" }: { placeholder?: string }) {
  return (
    <Combobox
      label="Search"
      placeholder={placeholder}
      options={[]}
      onSelect={() => undefined}
    />
  )
}

/* -------------------------------- UserMenu -------------------------------- */

export function UserMenu({ displayName, onSignOut }: { displayName?: string; onSignOut?: () => void }) {
  return (
    <div className="flex items-center gap-2">
      {displayName ? <Avatar name={displayName} size={32} /> : <IconCmp name="user" />}
      {onSignOut ? (
        <Button variant="ghost" size="sm" onClick={onSignOut} icon="close">Sign out</Button>
      ) : null}
    </div>
  )
}

/* ------------------------------ NotificationItem --------------------------- */

export function NotificationItem({ icon, title, body, when, unread }: { icon: IconName; title: string; body?: string; when: string; unread?: boolean }) {
  return (
    <article className={`flex gap-3 rounded-(--radius-md) p-3 ${unread ? "bg-(--color-primary-soft)" : ""}`}>
      <div className={`mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${unread ? "bg-(--color-primary)" : "bg-(--color-line)"} ${unread ? "text-white" : "text-(--color-ink-muted)"}`}>
        <IconCmp name={icon} size={18} />
      </div>
      <div className="min-w-0">
        <p className="text-sm font-medium">{title}</p>
        {body ? <p className="text-sm text-(--color-ink-muted)">{body}</p> : null}
        <time className="text-(--text-caption) text-(--color-ink-muted)" dateTime={when}>{when}</time>
      </div>
    </article>
  )
}

/* ------------------------------ FilterPanel ------------------------------- */

export function FilterChip({ active, children, onClick }: { active: boolean; children: ReactNode; onClick: () => void }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={`rounded-full px-3 py-1 text-sm ${active ? "bg-(--color-primary) text-white" : "border border-(--color-line) bg-(--color-surface) text-(--color-ink-muted)"}`}
    >
      {children}
    </button>
  )
}

