"use client"

import Link from "next/link"
import { useCallback, useEffect, useState } from "react"

import {
  casesApi,
  type CaseAction,
  type CaseDetail,
  type CaseResponse,
  type CaseStatus,
  type CaseTimeline,
  type CaseTimelineEntry,
  type SlaInstanceRead,
} from "@/lib/api/cases"
import { resolutionsApi, type ResolutionSubmission } from "@/lib/api/resolutions"
import { en } from "@/lib/i18n"
import { useAuth } from "@/lib/auth"
import { useLocale, useT } from "@/lib/i18n-client"
import { Badge, Button, ErrorState, Input, Select, Spinner, Textarea } from "@/components/ui/primitives"
import { caseStatusLabel, CaseStatusBadge } from "@/components/cases/CaseList"

const CASE_EDGES: Record<string, CaseStatus[]> = {
  submitted: ["under_review", "needs_information", "rejected", "duplicate"],
  under_review: ["verified", "needs_information", "in_progress", "rejected", "duplicate"],
  needs_information: ["under_review", "rejected", "duplicate"],
  verified: ["assigned", "duplicate"],
  assigned: ["acknowledged", "rejected", "duplicate"],
  acknowledged: ["action_planned", "in_progress"],
  action_planned: ["in_progress"],
  in_progress: ["waiting_for_information", "resolution_submitted"],
  waiting_for_information: ["in_progress"],
  resolution_rejected: ["in_progress", "resolution_submitted"],
  partially_resolved: ["resolved", "closed"],
  resolved: ["closed", "reopened"],
  reopened: ["assigned", "in_progress"],
  closed: [],
  rejected: [],
  duplicate: [],
}

const SLA_TONE: Record<string, string> = {
  within_sla: "success",
  at_risk: "warning",
  breached: "danger",
  paused: "default",
  exempt: "default",
  not_started: "default",
}

type Thunk = () => Promise<unknown>

export function CaseDetailPanel({ caseId }: { caseId: string }) {
  const t = useT()
  const locale = useLocale()
  const { hasPermission, user } = useAuth()
  const [data, setData] = useState<CaseDetail | null>(null)
  const [timeline, setTimeline] = useState<CaseTimeline | null>(null)
  const [sla, setSla] = useState<SlaInstanceRead | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)

  const isStaff = hasPermission("cases.read_internal")
  const isAdmin = hasPermission("departments.manage") || hasPermission("sla.manage")

  const load = useCallback(async () => {
    try {
      const [detail, tl] = await Promise.all([
        casesApi.get(caseId),
        casesApi.timeline(caseId).catch(() => null),
      ])
      setData(detail)
      setTimeline(tl)
      if (isAdmin || isStaff) {
        casesApi.getSla(caseId).then(setSla).catch(() => undefined)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }, [caseId, isAdmin, isStaff])

  useEffect(() => {
    let cancelled = false
    async function loadPanel() {
      try {
        const [detail, tl] = await Promise.all([
          casesApi.get(caseId),
          casesApi.timeline(caseId).catch(() => null),
        ])
        if (cancelled) return
        setData(detail)
        setTimeline(tl)
        if (isAdmin || isStaff) {
          casesApi.getSla(caseId).then(setSla).catch(() => undefined)
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err))
      }
    }
    void loadPanel()
    return () => {
      cancelled = true
    }
  }, [caseId, isAdmin, isStaff])

  async function run(action: Thunk) {
    setBusy(true)
    setNotice(null)
    try {
      await action()
      await load()
    } catch (err) {
      setNotice(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  if (error) return <ErrorState title={t("cases.title")} detail={error} onRetry={load} />
  if (!data) return <Spinner label={t("cases.title")} />

  const reportHref = `/${locale}/reports/${data.report_id}`
  const slaStatus = data.internal?.sla_status ?? sla?.status

  return (
    <div className="space-y-6">
      {notice && (
        <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{notice}</p>
      )}

      <section className="rounded-md border border-stone-200 bg-white p-4">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="font-mono text-xl font-bold text-(--color-primary-strong)">{data.case_no}</h1>
          <CaseStatusBadge status={data.status} />
          {data.severity && <Badge>{t(`report.severity.${data.severity}` as keyof typeof en)}</Badge>}
          <Link href={reportHref} className="ml-auto text-sm text-(--color-primary-strong) underline">
            {t("report.timeline")} ↗
          </Link>
        </div>
        {slaStatus && (
          <p className="mt-2 text-sm text-stone-600">
            {t("cases.sla.title")}:{" "}
            <Badge tone={SLA_TONE[slaStatus] ?? "default"}>
              {t(`cases.sla.status.${slaStatus}` as keyof typeof en)}
            </Badge>
            {sla?.remaining_hours !== undefined && sla.remaining_hours !== null && (
              <span className="ml-2 text-xs text-stone-500">
                {t("cases.sla.remaining")}: {sla.remaining_hours}h
              </span>
            )}
          </p>
        )}
      </section>

      {isStaff && data.status in CASE_EDGES && (
        <Transitions status={data.status} disabled={busy} onDone={(toStatus, reason) => void run(() => casesApi.transition(caseId, { to_status: toStatus, reason }))} />
      )}

      {isStaff && <Responses caseId={caseId} responses={data.responses} disabled={busy} run={run} />}

      {isStaff && <ActionsPanel caseId={caseId} actions={data.actions} disabled={busy} run={run} />}

      {isAdmin && sla && <SlaPanel sla={sla} disabled={busy} run={run} caseId={caseId} />}

      {isStaff && <EscalationPanel caseId={caseId} disabled={busy} run={run} />}

      {isStaff && (data.status === "in_progress" || data.status === "resolution_rejected") && (
        <ResolutionSubmit caseId={caseId} disabled={busy} run={run} />
      )}

      {isStaff && (data.status === "resolution_submitted" || data.status === "resolution_under_review") && (
        <ResolutionReview caseId={caseId} disabled={busy} run={run} />
      )}

      {user && (data.status === "resolved" || data.status === "closed") && (
        <ReopenRequest caseId={caseId} disabled={busy} run={run} />
      )}

      {timeline && (
        <section className="rounded-md border border-stone-200 bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-stone-700">{t("cases.timeline")}</h2>
          <ol className="space-y-2">
            {timeline.items.map((entry: CaseTimelineEntry, i: number) => (
              <li key={i} className="flex flex-wrap items-center gap-2 text-sm text-stone-600">
                {entry.type === "status_change" ? (
                  <>
                    <CaseStatusBadge status={entry.from_status!} />
                    <span>→</span>
                    <CaseStatusBadge status={entry.to_status!} />
                  </>
                ) : (
                  <span>{entry.body}</span>
                )}
                {entry.reason && <span className="text-xs italic text-stone-400">— {entry.reason}</span>}
                <span className="ml-auto text-xs text-stone-400">
                  {new Date(entry.at).toLocaleString()}
                </span>
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  )
}

function Transitions({
  status,
  disabled,
  onDone,
}: {
  status: CaseStatus
  disabled: boolean
  onDone: (to: CaseStatus, reason?: string) => void
}) {
  const t = useT()
  const [to, setTo] = useState<CaseStatus>(status)
  const [reason, setReason] = useState("")
  const [showReason, setShowReason] = useState(false)
  const edges = CASE_EDGES[status] ?? []
  if (edges.length === 0) return null
  return (
    <section className="rounded-md border border-stone-200 bg-white p-4">
      <h2 className="mb-2 text-sm font-semibold text-stone-700">{t("cases.transition.action")}</h2>
      <div className="flex flex-wrap items-end gap-2">
        <Select value={to} onChange={(e) => setTo(e.target.value as CaseStatus)}>
          {edges.map((edge) => (
            <option key={edge} value={edge}>
              {caseStatusLabel(t, edge)}
            </option>
          ))}
        </Select>
        {showReason && (
          <Input
            placeholder={t("cases.assign.reason")}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className="w-48"
          />
        )}
        <label className="flex items-center gap-1 text-xs text-stone-500">
          <input type="checkbox" checked={showReason} onChange={(e) => setShowReason(e.target.checked)} />
          {t("cases.assign.reason")}
        </label>
        <Button disabled={disabled} onClick={() => onDone(to, reason || undefined)}>
          {t("cases.transition.action")}
        </Button>
      </div>
    </section>
  )
}

function Responses({
  caseId,
  responses,
  disabled,
  run,
}: {
  caseId: string
  responses: CaseResponse[]
  disabled: boolean
  run: (action: Thunk) => Promise<void>
}) {
  const t = useT()
  const [body, setBody] = useState("")
  const [visibility, setVisibility] = useState<"public" | "internal">("public")
  const kind = visibility === "internal" ? "internal_note" : "public_response"
  return (
    <section className="rounded-md border border-stone-200 bg-white p-4">
      <h2 className="mb-2 text-sm font-semibold text-stone-700">{t("cases.responses")}</h2>
      <ul className="mb-3 space-y-2">
        {responses.map((r) => (
          <li key={r.id} className="flex items-start gap-2 text-sm">
            <Badge tone={r.visibility === "internal" ? "warning" : "default"}>
              {t(`cases.response.kind.${r.kind}` as keyof typeof en)}
            </Badge>
            <span className="text-stone-700">{r.body}</span>
            <span className="ml-auto text-xs text-stone-400">
              {new Date(r.created_at).toLocaleString()}
            </span>
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap items-start gap-2">
        <Textarea
          placeholder={t("cases.respond.placeholder")}
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={2}
          className="min-w-56 flex-1"
        />
        <div className="flex flex-col gap-2">
          <Select
            value={visibility}
            onChange={(e) => setVisibility(e.target.value as "public" | "internal")}
          >
            <option value="public">{t("cases.respond.public")}</option>
            <option value="internal">{t("cases.respond.internal")}</option>
          </Select>
          <Button
            disabled={disabled || body.trim() === ""}
            onClick={() => {
              const text = body
              setBody("")
              void run(() => casesApi.respond(caseId, { kind, visibility, body: text }))
            }}
          >
            {t("cases.respond.send")}
          </Button>
        </div>
      </div>
    </section>
  )
}

function ActionsPanel({
  caseId,
  actions,
  disabled,
  run,
}: {
  caseId: string
  actions: CaseAction[]
  disabled: boolean
  run: (action: Thunk) => Promise<void>
}) {
  const t = useT()
  const [title, setTitle] = useState("")
  const [description, setDescription] = useState("")
  const [responsibleTeam, setResponsibleTeam] = useState("")
  const [targetDate, setTargetDate] = useState("")
  return (
    <section className="rounded-md border border-stone-200 bg-white p-4">
      <h2 className="mb-2 text-sm font-semibold text-stone-700">{t("cases.actions")}</h2>
      {actions.length === 0 ? (
        <p className="text-sm text-stone-500">{t("cases.actions.no_actions")}</p>
      ) : (
        <ul className="mb-3 space-y-2">
          {actions.map((a) => (
            <li key={a.id} className="flex flex-wrap items-center gap-2 text-sm">
              <Badge>{t(`cases.actions.status.${a.status}` as keyof typeof en)}</Badge>
              <span className="font-medium text-stone-800">{a.title}</span>
              {a.description && <span className="text-stone-500">{a.description}</span>}
              {a.target_date && (
                <span className="text-xs text-stone-400">
                  {new Date(a.target_date).toLocaleDateString()}
                </span>
              )}
              <span className="ml-auto flex gap-1">
                {(["in_progress", "completed", "blocked"] as const).map((s) => (
                  <button
                    key={s}
                    type="button"
                    disabled={disabled}
                    onClick={() => void run(() => casesApi.updateAction(caseId, a.id, { status: s }))}
                    className="rounded border border-stone-300 px-1.5 py-0.5 text-xs text-stone-600 hover:bg-stone-100 disabled:opacity-50"
                  >
                    {t(`cases.actions.status.${s}` as keyof typeof en)}
                  </button>
                ))}
              </span>
            </li>
          ))}
        </ul>
      )}
      <div className="flex flex-wrap gap-2">
        <Input
          placeholder={t("cases.actions.title")}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="w-44"
        />
        <Input
          placeholder={t("cases.actions.responsible_team")}
          value={responsibleTeam}
          onChange={(e) => setResponsibleTeam(e.target.value)}
          className="w-40"
        />
        <Input type="date" value={targetDate} onChange={(e) => setTargetDate(e.target.value)} className="w-36" />
        <Button
          disabled={disabled || title.trim() === ""}
          onClick={() => {
            void run(() =>
              casesApi.createAction(caseId, {
                title,
                description: description || null,
                responsible_team: responsibleTeam || null,
                target_date: targetDate || null,
              }),
            )
            setTitle("")
            setDescription("")
            setResponsibleTeam("")
            setTargetDate("")
          }}
        >
          {t("cases.actions.add")}
        </Button>
      </div>
      <Input
        placeholder={t("cases.actions.description")}
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        className="mt-2 w-full"
      />
    </section>
  )
}

function SlaPanel({
  caseId,
  sla,
  disabled,
  run,
}: {
  caseId: string
  sla: SlaInstanceRead
  disabled: boolean
  run: (action: Thunk) => Promise<void>
}) {
  const t = useT()
  const [reason, setReason] = useState("")
  return (
    <section className="rounded-md border border-stone-200 bg-white p-4">
      <h2 className="mb-2 text-sm font-semibold text-stone-700">{t("cases.sla.title")}</h2>
      <p className="mb-2 text-sm text-stone-600">
        <Badge tone={SLA_TONE[sla.status] ?? "default"}>
          {t(`cases.sla.status.${sla.status}` as keyof typeof en)}
        </Badge>
        {sla.remaining_hours !== null && sla.remaining_hours !== undefined && (
          <span className="ml-2">
            {t("cases.sla.remaining")}: {sla.remaining_hours}h
          </span>
        )}
        {sla.target_resolution_at && (
          <span className="ml-2">
            {t("cases.sla.target")}: {new Date(sla.target_resolution_at).toLocaleString()}
          </span>
        )}
      </p>
      {sla.status === "paused" ? (
        <Button disabled={disabled} onClick={() => void run(() => casesApi.resumeSla(caseId))}>
          {t("cases.sla.resume")}
        </Button>
      ) : sla.status !== "exempt" ? (
        <div className="flex flex-wrap items-end gap-2">
          <Input
            placeholder={t("cases.sla.pause.reason")}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className="w-64"
          />
          <Button
            disabled={disabled || reason.trim() === ""}
            onClick={() => void run(() => casesApi.pauseSla(caseId, { reason }))}
          >
            {t("cases.sla.pause")}
          </Button>
        </div>
      ) : null}
    </section>
  )
}

function EscalationPanel({
  caseId,
  disabled,
  run,
}: {
  caseId: string
  disabled: boolean
  run: (action: Thunk) => Promise<void>
}) {
  const t = useT()
  const [level, setLevel] = useState(1)
  const [reason, setReason] = useState("")
  return (
    <section className="rounded-md border border-stone-200 bg-white p-4">
      <h2 className="mb-2 text-sm font-semibold text-stone-700">{t("cases.escalations")}</h2>
      <div className="flex flex-wrap items-end gap-2">
        <Select value={level} onChange={(e) => setLevel(Number(e.target.value))}>
          {[1, 2, 3, 4, 5].map((l) => (
            <option key={l} value={l}>
              {t("cases.escalation.level", { level: String(l) })}
            </option>
          ))}
        </Select>
        <Input
          placeholder={t("cases.escalate.reason")}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          className="w-64"
        />
        <Button
          disabled={disabled || reason.trim() === ""}
          onClick={() => void run(() => casesApi.escalate(caseId, { level, reason }))}
        >
          {t("cases.escalate")}
        </Button>
      </div>
    </section>
  )
}

function ResolutionSubmit({
  caseId,
  disabled,
  run,
}: {
  caseId: string
  disabled: boolean
  run: (action: Thunk) => Promise<void>
}) {
  const t = useT()
  const [explanation, setExplanation] = useState("")
  const [notes, setNotes] = useState("")
  const [referenceNumbers, setReferenceNumbers] = useState("")
  const [evidenceNotes, setEvidenceNotes] = useState("")
  const [submitted, setSubmitted] = useState(false)
  if (submitted) return <p className="text-sm text-green-700">{t("cases.resolution.submitted")}</p>
  return (
    <section className="rounded-md border border-stone-200 bg-white p-4">
      <h2 className="mb-2 text-sm font-semibold text-stone-700">{t("cases.resolution.submit")}</h2>
      <div className="space-y-2">
        <Textarea
          placeholder={t("cases.resolution.explanation")}
          value={explanation}
          onChange={(e) => setExplanation(e.target.value)}
          rows={2}
          className="w-full"
        />
        <Input
          placeholder={t("cases.resolution.notes")}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          className="w-full"
        />
        <Input
          placeholder={t("cases.resolution.evidence.notes")}
          value={evidenceNotes}
          onChange={(e) => setEvidenceNotes(e.target.value)}
          className="w-full"
        />
        <Input
          placeholder={t("cases.resolution.reference")}
          value={referenceNumbers}
          onChange={(e) => setReferenceNumbers(e.target.value)}
          className="w-full"
        />
        <Button
          disabled={disabled || explanation.trim() === ""}
          onClick={() => {
            let refs: Record<string, unknown> | null = null
            if (referenceNumbers.trim() !== "") {
              try {
                refs = JSON.parse(referenceNumbers) as Record<string, unknown>
              } catch {
                refs = { raw: referenceNumbers }
              }
            }
            void run(() =>
              resolutionsApi.submit({
                case_id: caseId,
                explanation,
                notes: notes || null,
                reference_numbers: refs,
                evidence: [{ kind: "after", notes: evidenceNotes || null }],
              }),
            )
            setSubmitted(true)
          }}
        >
          {t("cases.resolution.submit")}
        </Button>
      </div>
    </section>
  )
}

function ResolutionReview({
  caseId,
  disabled,
  run,
}: {
  caseId: string
  disabled: boolean
  run: (action: Thunk) => Promise<void>
}) {
  const t = useT()
  const [reason, setReason] = useState("")
  const [submissions, setSubmissions] = useState<ResolutionSubmission[]>([])

  useEffect(() => {
    resolutionsApi
      .list({ case_id: caseId })
      .then((res) => setSubmissions(res.items))
      .catch(() => undefined)
  }, [caseId])

  return (
    <section className="rounded-md border border-stone-200 bg-white p-4">
      <h2 className="mb-2 text-sm font-semibold text-stone-700">{t("cases.resolution.review")}</h2>
      {submissions.map((sub) => (
        <div key={sub.id} className="mb-3 rounded border border-stone-200 p-2">
          <p className="text-sm text-stone-600">
            {sub.explanation ?? sub.notes}
            {sub.status !== "submitted" && sub.status !== "under_review" && (
              <Badge tone={sub.status === "verified" ? "success" : "danger"}>{sub.status}</Badge>
            )}
          </p>
          <div className="mt-2 flex flex-wrap items-end gap-2">
            <Input
              placeholder={t("cases.resolution.reason")}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="w-56"
            />
            {(["verified", "partially_verified", "more_evidence_required", "rejected"] as const).map(
              (d) => (
                <Button key={d} disabled={disabled} onClick={() => void run(() => resolutionsApi.review(sub.id, { decision: d, reason: reason || null }))}>
                  {t(`cases.resolution.decision.${d}` as keyof typeof en)}
                </Button>
              ),
            )}
          </div>
        </div>
      ))}
    </section>
  )
}

function ReopenRequest({
  caseId,
  disabled,
  run,
}: {
  caseId: string
  disabled: boolean
  run: (action: Thunk) => Promise<void>
}) {
  const t = useT()
  const [reason, setReason] = useState("")
  const [evidence, setEvidence] = useState("")
  const [submitted, setSubmitted] = useState(false)
  if (submitted) return <p className="text-sm text-green-700">{t("cases.reopen.request")} ✓</p>
  return (
    <section className="rounded-md border border-stone-200 bg-white p-4">
      <h2 className="mb-2 text-sm font-semibold text-stone-700">{t("cases.reopen.request")}</h2>
      <div className="flex flex-wrap items-end gap-2">
        <Input
          placeholder={t("cases.reopen.reason")}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          className="w-64"
        />
        <Input
          placeholder={t("cases.reopen.evidence")}
          value={evidence}
          onChange={(e) => setEvidence(e.target.value)}
          className="w-64"
        />
        <Button
          disabled={disabled || reason.trim() === ""}
          onClick={() => {
            void run(() => casesApi.requestReopen(caseId, { reason, evidence: evidence || null }))
            setSubmitted(true)
          }}
        >
          {t("cases.reopen.request")}
        </Button>
      </div>
    </section>
  )
}