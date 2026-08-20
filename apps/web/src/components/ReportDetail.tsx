"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import Image from "next/image"
import { useParams } from "next/navigation"

import { FormattedDate } from "@/components/FormattedDate"
import { MapExplore } from "@/components/map/MapExplore"
import { ProvenanceBadge } from "@/components/ui/data"
import { Icon } from "@/components/ui/icons"
import { Button, Skeleton } from "@/components/ui/primitives"
import { reportsApi, institutionsApi } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { useT } from "@/lib/i18n-client"
import type {
  Analysis,
  Comment,
  DuplicateCandidate,
  Institution,
  ReportDetail as ReportDetailType,
  ReportEvidence,
  TimelineEntry,
  Verification,
} from "@/lib/types"

const FLOW = [
  "submitted",
  "under_verification",
  "verified",
  "assigned",
  "in_progress",
  "resolution_submitted",
  "resolved",
  "closed",
]

function StatusStepper({ current }: { current: string }) {
  const currentIdx = FLOW.indexOf(current)
  return (
    <nav aria-label="Status progress" className="w-full overflow-x-auto py-2">
      <ol className="flex items-center gap-2 text-xs">
        {FLOW.map((step, idx) => {
          const isPast = idx <= currentIdx
          const isCurrent = step === current
          return (
            <li key={step} className="flex items-center gap-2 shrink-0">
              <span
                className={`flex h-6 items-center justify-center rounded-full px-2.5 font-semibold capitalize ${
                  isCurrent
                    ? "bg-(--color-primary) text-white ring-2 ring-(--color-primary-soft)"
                    : isPast
                      ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
                      : "bg-(--color-surface-sunken) text-(--color-ink-muted)"
                }`}
              >
                {step.replace(/_/g, " ")}
              </span>
              {idx < FLOW.length - 1 && (
                <span className="text-(--color-line)" aria-hidden="true">
                  →
                </span>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}

export function ReportDetail({ reportId }: { reportId: string }) {
  const t = useT()
  const params = useParams<{ locale?: string }>()
  const locale = params.locale ?? "en"
  const { user } = useAuth()

  const [report, setReport] = useState<ReportDetailType | null>(null)
  const [institution, setInstitution] = useState<Institution | null>(null)
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [timeline, setTimeline] = useState<TimelineEntry[]>([])
  const [evidenceList, setEvidenceList] = useState<ReportEvidence[]>([])
  const [duplicates, setDuplicates] = useState<DuplicateCandidate[]>([])
  const [comments, setComments] = useState<Comment[]>([])
  const [commentText, setCommentText] = useState("")
  const [replyParentId, setReplyParentId] = useState<string | null>(null)
  const [following, setFollowing] = useState(false)
  const [submittingComment, setSubmittingComment] = useState(false)
  const [verifying, setVerifying] = useState(false)
  const [verifyNotes, setVerifyNotes] = useState("")
  const [showVerifyModal, setShowVerifyModal] = useState<"confirm" | "refute" | "needs_information" | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false

    async function loadReportData() {
      setLoading(true)
      try {
        const [rData, tData, cData, evData, dupData] = await Promise.all([
          reportsApi.get(reportId),
          reportsApi.getTimeline(reportId).catch(() => ({ items: [] })),
          reportsApi.listComments(reportId).catch(() => []),
          reportsApi.listMedia(reportId).catch(() => ({ items: [] })),
          reportsApi.listDuplicates(reportId).catch(() => ({ items: [] })),
        ])

        if (cancelled) return

        setReport(rData)
        setTimeline(tData.items)
        setComments(cData)
        setEvidenceList(evData.items || rData.evidence || [])
        setDuplicates(dupData.items || [])

        // Load linked institution if present
        if (rData.institution_id) {
          institutionsApi
            .get(rData.institution_id)
            .then((inst) => {
              if (!cancelled) setInstitution(inst)
            })
            .catch(() => undefined)
        }

        // Load AI analysis if available
        reportsApi
          .getAnalysis(reportId)
          .then((a) => {
            if (!cancelled) setAnalysis(a)
          })
          .catch(() => undefined)
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load report")
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void loadReportData()
    return () => {
      cancelled = true
    }
  }, [reportId])

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton height={40} />
        <Skeleton height={200} />
        <Skeleton height={300} />
      </div>
    )
  }

  if (!report) {
    return (
      <div className="rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface) p-8 text-center">
        <h1 className="text-lg font-bold text-(--color-danger)">
          Report not found
        </h1>
        <p className="mt-1 text-sm text-(--color-ink-muted)">
          {error ?? "This report could not be retrieved."}
        </p>
      </div>
    )
  }

  async function submitVerification(kind: "confirm" | "refute" | "needs_information") {
    setError(null)
    setVerifying(true)
    try {
      await reportsApi.verify(reportId, {
        kind,
        notes: verifyNotes.trim() || undefined,
        evidence: verifyNotes.trim() || undefined,
      })
      const updated = await reportsApi.get(reportId)
      setReport(updated)
      setShowVerifyModal(null)
      setVerifyNotes("")
    } catch (e) {
      setError(e instanceof Error ? e.message : "Verification failed")
    } finally {
      setVerifying(false)
    }
  }

  async function handleAddComment() {
    if (!commentText.trim()) return
    setSubmittingComment(true)
    setError(null)
    try {
      const created = await reportsApi.addComment(reportId, commentText.trim(), replyParentId)
      setComments((prev) => [...prev, created])
      setCommentText("")
      setReplyParentId(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to post comment")
    } finally {
      setSubmittingComment(false)
    }
  }

  async function toggleFollow() {
    try {
      if (following) {
        await reportsApi.unfollow(reportId)
        setFollowing(false)
      } else {
        await reportsApi.follow(reportId, "all")
        setFollowing(true)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Follow action failed")
    }
  }

  const verifications: Verification[] = report.verifications ?? []
  const confirmations = verifications.filter((v) => v.kind === "confirm")
  const refutations = verifications.filter((v) => v.kind === "refute")

  const severityBadgeClass =
    report.severity === "critical"
      ? "bg-rose-100 text-rose-800 border-rose-300 dark:bg-rose-950 dark:text-rose-300"
      : report.severity === "high"
        ? "bg-orange-100 text-orange-800 border-orange-300 dark:bg-orange-950 dark:text-orange-300"
        : report.severity === "medium"
          ? "bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-950 dark:text-amber-300"
          : "bg-emerald-100 text-emerald-800 border-emerald-300 dark:bg-emerald-950 dark:text-emerald-300"

  const lon = report.location?.coordinates?.[0] ?? 75.7873
  const lat = report.location?.coordinates?.[1] ?? 26.9124

  return (
    <div className="space-y-8">
      {/* Header & Meta */}
      <section aria-labelledby="report-title" className="space-y-4 rounded-(--radius-xl) border border-(--color-line) bg-(--color-surface) p-6 shadow-xs">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs font-bold text-(--color-primary-strong)">
              {report.ticket_no}
            </span>
            <span className={`rounded-full border px-2.5 py-0.5 text-xs font-bold uppercase ${severityBadgeClass}`}>
              {report.severity} Severity
            </span>
            <ProvenanceBadge tier="citizen" />
            {report.coordinate_source && (
              <span className="rounded-md bg-(--color-surface-sunken) px-2 py-0.5 font-mono text-xs text-(--color-ink-muted)">
                {report.coordinate_source}
              </span>
            )}
          </div>
          <div className="text-xs text-(--color-ink-muted) flex items-center gap-2">
            {report.observed_at && (
              <span>
                Observed: <FormattedDate iso={report.observed_at} />
              </span>
            )}
            <span>·</span>
            <span>
              Submitted: <FormattedDate iso={report.created_at} />
            </span>
          </div>
        </div>

        <h1 id="report-title" className="text-2xl font-black text-(--color-ink) sm:text-3xl">
          {report.title}
        </h1>

        <p className="text-base text-(--color-ink) whitespace-pre-wrap">
          {report.description}
        </p>

        {report.address_hint && (
          <p className="text-xs text-(--color-ink-muted) flex items-center gap-1">
            <Icon name="map" size={14} />
            <span>Landmark: <span className="font-semibold text-(--color-ink)">{report.address_hint}</span></span>
          </p>
        )}

        {/* Linked Institution */}
        {institution && (
          <div className="flex items-center gap-2 rounded-(--radius-md) border border-(--color-line) bg-(--color-surface-sunken) p-3">
            <Icon name="building" size={18} />
            <div className="min-w-0 flex-1">
              <span className="text-xs text-(--color-ink-muted)">Linked Public Institution</span>
              <p className="truncate text-sm font-bold text-(--color-ink)">
                <Link
                  href={`/${locale}/institutions/${institution.id}`}
                  className="text-(--color-primary-strong) hover:underline"
                >
                  {institution.name}
                </Link>
              </p>
            </div>
          </div>
        )}

        {/* Dynamic Category Fields */}
        {report.fields && Object.keys(report.fields).length > 0 && (
          <div className="rounded-(--radius-md) border border-(--color-line) p-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-(--color-ink-muted)">
              Specific Issue Attributes
            </h3>
            <dl className="mt-2 grid grid-cols-2 gap-2 text-xs sm:grid-cols-3">
              {Object.entries(report.fields).map(([k, v]) => (
                <div key={k}>
                  <dt className="text-(--color-ink-muted) capitalize">{k.replace(/_/g, " ")}</dt>
                  <dd className="font-semibold text-(--color-ink)">{String(v)}</dd>
                </div>
              ))}
            </dl>
          </div>
        )}

        {report.duplicate_of && (
          <div className="rounded-(--radius-md) bg-amber-50 border border-amber-200 p-3 text-xs text-amber-800 dark:bg-amber-950/40 dark:border-amber-800 dark:text-amber-200">
            This issue was flagged and merged as a duplicate of ticket{" "}
            <Link href={`/${locale}/reports/${report.duplicate_of}`} className="font-bold underline">
              {report.duplicate_of}
            </Link>
            .
          </div>
        )}
      </section>

      {/* Status Lifecycle Progress */}
      <section aria-labelledby="status-flow-heading" className="space-y-2">
        <h2 id="status-flow-heading" className="text-sm font-bold uppercase tracking-wider text-(--color-ink-muted)">
          Lifecycle Progression
        </h2>
        <StatusStepper current={report.status} />
      </section>

      {/* Evidence Media Gallery */}
      {evidenceList.length > 0 && (
        <section aria-labelledby="evidence-gallery-heading" className="space-y-3">
          <h2 id="evidence-gallery-heading" className="text-lg font-bold">
            Evidence Media Gallery ({evidenceList.length})
          </h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
            {evidenceList.map((ev) => (
              <div
                key={ev.id}
                className="group relative overflow-hidden rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface-sunken)"
              >
                {ev.thumbnail_url || ev.url ? (
                  <Image
                    src={ev.thumbnail_url || ev.url || ""}
                    alt="Corroborating civic evidence"
                    width={640}
                    height={360}
                    unoptimized
                    className="h-36 w-full object-cover transition-transform group-hover:scale-105"
                  />
                ) : (
                  <div className="flex h-36 w-full items-center justify-center bg-(--color-surface)">
                    <Icon name="check" size={24} />
                  </div>
                )}
                <div className="p-2 text-xs">
                  <span className="font-semibold uppercase text-(--color-ink)">{ev.kind}</span>
                  {ev.verification_status && (
                    <span className="ml-1 text-(--color-ink-muted)">({ev.verification_status})</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Map Location */}
      <section aria-labelledby="map-location-heading" className="space-y-3">
        <h2 id="map-location-heading" className="text-lg font-bold">
          Incident Location
        </h2>
        <MapExplore
          entities={[
            {
              id: report.id,
              kind: "report",
              title: report.title,
              status: report.status,
              severity: report.severity,
              lon,
              lat,
            },
          ]}
        />
        <p className="text-xs text-(--color-ink-muted)">
          GPS Coordinates: {lat.toFixed(5)}, {lon.toFixed(5)} (±{report.location_accuracy_m}m accuracy)
        </p>
      </section>

      {/* Verification & Citizen Trust */}
      <section aria-labelledby="verify-heading" className="space-y-4 rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface) p-6">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 id="verify-heading" className="text-lg font-bold">
              Community Verification & Trust
            </h2>
            <p className="text-xs text-(--color-ink-muted)">
              {confirmations.length} Confirmations · {refutations.length} Refutations · Trust Score: {report.trust_score.toFixed(2)} / 1.0
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            icon={following ? "check" : "bell"}
            onClick={() => void toggleFollow()}
          >
            {following ? t("report.unfollow") : t("report.follow")}
          </Button>
        </div>

        {/* Trust Score Progress Bar */}
        <div className="w-full bg-(--color-line) rounded-full h-2">
          <div
            className="bg-emerald-500 h-2 rounded-full transition-all"
            style={{ width: `${Math.min(100, Math.round(report.trust_score * 100))}%` }}
          />
        </div>

        {error && (
          <p role="alert" className="text-xs font-semibold text-(--color-danger)">
            {error}
          </p>
        )}

        {user ? (
          <div className="flex flex-wrap gap-3 border-t border-(--color-line) pt-4">
            <Button
              variant="primary"
              size="sm"
              icon="check"
              onClick={() => setShowVerifyModal("confirm")}
            >
              {t("report.verify_confirm")} (I observed this)
            </Button>
            <Button
              variant="outline"
              size="sm"
              icon="close"
              onClick={() => setShowVerifyModal("refute")}
            >
              {t("report.verify_refute")} (This is inaccurate)
            </Button>
          </div>
        ) : (
          <p className="text-xs text-(--color-ink-muted) border-t border-(--color-line) pt-3">
            <Link href={`/${locale}/auth/login`} className="font-semibold text-(--color-primary-strong) hover:underline">
              Log in
            </Link>{" "}
            to corroborate or refute this observation.
          </p>
        )}

        {/* Verification Modal / Drawer */}
        {showVerifyModal && (
          <div className="rounded-(--radius-lg) border border-(--color-primary) bg-(--color-primary-soft) p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-bold text-xs text-(--color-primary-strong)">
                Confirm Verification ({showVerifyModal.toUpperCase()})
              </span>
              <button
                type="button"
                onClick={() => setShowVerifyModal(null)}
                className="text-xs text-(--color-ink-muted) hover:underline"
              >
                Cancel
              </button>
            </div>
            <textarea
              rows={2}
              value={verifyNotes}
              onChange={(e) => setVerifyNotes(e.target.value)}
              placeholder="Provide verification notes, on-site observations, or reasons…"
              className="w-full rounded-(--radius-md) border border-(--color-line) bg-(--color-surface) p-2 text-xs text-(--color-ink)"
            />
            <Button
              variant="primary"
              size="sm"
              disabled={verifying}
              onClick={() => void submitVerification(showVerifyModal)}
            >
              {verifying ? "Submitting…" : "Submit Verification"}
            </Button>
          </div>
        )}
      </section>

      {/* Candidate Duplicates (if detected) */}
      {duplicates.length > 0 && (
        <section aria-labelledby="duplicates-heading" className="space-y-3 rounded-(--radius-lg) border border-amber-200 bg-amber-50/50 p-4 dark:border-amber-900 dark:bg-amber-950/20">
          <h2 id="duplicates-heading" className="text-sm font-bold text-amber-950 dark:text-amber-200">
            Nearby Potential Duplicate Reports ({duplicates.length})
          </h2>
          <ul className="space-y-2">
            {duplicates.map((dup) => (
              <li
                key={dup.candidate_report_id}
                className="flex items-center justify-between rounded-md bg-(--color-surface) p-2.5 text-xs border border-(--color-line)"
              >
                <div>
                  <span className="font-mono font-bold text-(--color-primary-strong)">{dup.candidate_ticket_no}</span>
                  <p className="font-semibold text-(--color-ink)">{dup.candidate_title}</p>
                  <p className="text-(--color-ink-muted)">Similarity: {(dup.similarity_score * 100).toFixed(0)}% ({dup.confidence} confidence)</p>
                </div>
                <Link href={`/${locale}/reports/${dup.candidate_report_id}`}>
                  <Button variant="outline" size="sm">
                    View
                  </Button>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* AI Analysis / T4 Provenance Slot */}
      <section aria-labelledby="analysis-heading" className="space-y-2">
        <h2 id="analysis-heading" className="text-lg font-bold">
          {t("report.analysis")}
        </h2>
        {analysis ? (
          <div className="rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface-sunken) p-4">
            <p className="text-sm text-(--color-ink)">{analysis.content.summary}</p>
            <p className="mt-2 text-xs text-(--color-ink-muted)">
              Provider: {analysis.run.provider} · Model: {analysis.model_id} · Confidence: {(analysis.confidence * 100).toFixed(0)}%
            </p>
          </div>
        ) : (
          <div className="rounded-(--radius-md) border border-(--color-line) bg-(--color-surface-sunken) p-4 text-xs text-(--color-ink-muted)">
            {t("report.analysis.none")} — AI classification and entity extraction will be computed asynchronously.
          </div>
        )}
      </section>

      {/* Timeline of Lifecycle Transitions */}
      {timeline.length > 0 && (
        <section aria-labelledby="timeline-heading" className="space-y-3">
          <h2 id="timeline-heading" className="text-lg font-bold">
            {t("report.timeline")}
          </h2>
          <ul className="space-y-2 border-l-2 border-(--color-line) pl-4">
            {timeline.map((entry) => (
              <li key={entry.id} className="relative space-y-1">
                <span className="absolute -left-[21px] top-1 h-2.5 w-2.5 rounded-full bg-(--color-primary)" />
                <div className="flex items-center gap-2 text-xs">
                  <span className="font-bold text-(--color-ink) capitalize">
                    {entry.to_status.replace(/_/g, " ")}
                  </span>
                  <span className="text-(--color-ink-muted)">
                    <FormattedDate iso={entry.created_at} />
                  </span>
                </div>
                {entry.reason && (
                  <p className="text-xs text-(--color-ink-muted)">Reason: {entry.reason}</p>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Discussion / Comments */}
      <section aria-labelledby="comments-heading" className="space-y-4">
        <h2 id="comments-heading" className="text-lg font-bold">
          Discussion ({comments.length})
        </h2>

        {comments.length > 0 ? (
          <ul className="space-y-3">
            {comments.map((c) => (
              <li key={c.id} className="rounded-(--radius-md) border border-(--color-line) bg-(--color-surface) p-3 space-y-1">
                <div className="flex items-center justify-between text-xs text-(--color-ink-muted)">
                  <span className="font-semibold text-(--color-ink)">{c.author_name || "Citizen Contributor"}</span>
                  <FormattedDate iso={c.created_at} />
                </div>
                <p className="text-sm text-(--color-ink)">{c.body}</p>
                {user && (
                  <button
                    type="button"
                    onClick={() => {
                      setReplyParentId(c.id)
                      setCommentText(`@${c.author_name || "Citizen"} `)
                    }}
                    className="text-xs text-(--color-primary-strong) hover:underline"
                  >
                    Reply
                  </button>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-(--color-ink-muted)">
            No comments yet. Start the discussion below.
          </p>
        )}

        {user ? (
          <form
            onSubmit={(e) => {
              e.preventDefault()
              void handleAddComment()
            }}
            className="space-y-2"
          >
            {replyParentId && (
              <div className="flex items-center justify-between text-xs bg-(--color-surface-sunken) p-2 rounded">
                <span>Replying to comment thread</span>
                <button type="button" onClick={() => setReplyParentId(null)} className="text-(--color-danger)">
                  Cancel
                </button>
              </div>
            )}
            <textarea
              rows={3}
              value={commentText}
              onChange={(e) => setCommentText(e.target.value)}
              placeholder={t("report.comment.placeholder")}
              aria-label={t("report.comment.placeholder")}
              className="w-full rounded-(--radius-md) border border-(--color-line) bg-(--color-page) p-3 text-sm text-(--color-ink) focus:border-(--color-primary) focus:outline-hidden"
            />
            <Button
              type="submit"
              variant="primary"
              size="sm"
              disabled={submittingComment || !commentText.trim()}
            >
              {submittingComment ? "Posting…" : "Post Comment"}
            </Button>
          </form>
        ) : (
          <p className="text-xs text-(--color-ink-muted)">
            <Link href={`/${locale}/auth/login`} className="font-semibold text-(--color-primary-strong) hover:underline">
              Log in
            </Link>{" "}
            to join the discussion.
          </p>
        )}
      </section>
    </div>
  )
}