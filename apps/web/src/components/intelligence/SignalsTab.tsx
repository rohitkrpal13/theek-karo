"use client"

import { useCallback, useEffect, useState } from "react"

import { fmtDate, severityTone, statusBadge } from "@/components/intelligence/shared"
import { Badge, Button, EmptyState, ErrorState, Input, Label, Modal, Select, Skeleton, Spinner, Textarea, useToast } from "@/components/ui/primitives"
import { intelligenceApi } from "@/lib/api"
import type { SignalAction, SignalRead } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { useT } from "@/lib/i18n-client"

const STAFF_ROLES = ["admin", "department_representative", "department_manager"]
const ACTIONS: SignalAction[] = ["CONFIRM", "DISMISS", "REQUEST_MORE_DATA", "MONITOR", "ESCALATE", "MARK_RESOLVED"]

function SignalCard({ signal, canReview, onChanged }: { signal: SignalRead; canReview: boolean; onChanged: () => void }) {
  const t = useT()
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const [action, setAction] = useState<SignalAction>("CONFIRM")
  const [note, setNote] = useState("")

  async function review() {
    setBusy(true)
    try {
      await intelligenceApi.reviewSignal(signal.id, { action, note: note.trim() || null })
      toast.toast("success", t("intelligence.signal.review"))
      setNote("")
      onChanged()
    } catch (err) {
      toast.toast("error", err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="rounded-(--radius-xl) border border-(--color-line) bg-(--color-surface) p-4 shadow-xs">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-(--color-ink)">{signal.title}</h3>
          <p className="mt-0.5 text-xs text-(--color-ink-muted)">
            {signal.signal_type} · {fmtDate(signal.created_at, "en")}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {statusBadge(t, signal.status)}
          <Badge tone={severityTone(signal.severity)}>{signal.severity}</Badge>
          <Badge>{signal.confidence}</Badge>
        </div>
      </div>
      {signal.description && <p className="mt-2 text-sm text-(--color-ink-muted)">{signal.description}</p>}
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-(--color-ink-muted)">
        <span>
          {signal.evidence_count} {t("intelligence.signal.evidence")}
        </span>
        <span>
          {signal.source_count} {t("intelligence.signal.sources")}
        </span>
        {signal.geography_name && <span>{signal.geography_name}</span>}
        {signal.institution_name && <span>{signal.institution_name}</span>}
      </div>
      {signal.review_history.length > 0 && (
        <ul className="mt-2 space-y-1 border-t border-(--color-line) pt-2 text-xs text-(--color-ink-muted)">
          {signal.review_history.slice(-3).map((review, index) => (
            <li key={index}>
              {t(`intelligence.signal.action.${review.action}` as never)} {review.note ? `· ${review.note}` : ""} · {fmtDate(review.created_at, "en")}
            </li>
          ))}
        </ul>
      )}
      {canReview && (
        <div className="mt-3 flex flex-wrap items-end gap-2 border-t border-(--color-line) pt-3">
          <div className="min-w-40">
            <Label htmlFor={`action-${signal.id}`}>{t("intelligence.signal.action")}</Label>
            <Select id={`action-${signal.id}`} value={action} onChange={(e) => setAction(e.target.value as SignalAction)}>
              {ACTIONS.map((a) => (
                <option key={a} value={a}>
                  {t(`intelligence.signal.action.${a}` as never)}
                </option>
              ))}
            </Select>
          </div>
          <div className="flex-1">
            <Label htmlFor={`note-${signal.id}`}>{t("intelligence.signal.note")}</Label>
            <Input id={`note-${signal.id}`} value={note} onChange={(e) => setNote(e.target.value)} placeholder={t("intelligence.signal.note")} />
          </div>
          <Button size="sm" disabled={busy} onClick={review}>
            {busy ? <Spinner label="…" /> : t("intelligence.signal.review")}
          </Button>
        </div>
      )}
    </div>
  )
}

export function SignalsTab() {
  const t = useT()
  const { hasRole } = useAuth()
  const toast = useToast()
  const [items, setItems] = useState<SignalRead[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [title, setTitle] = useState("")
  const [signalType, setSignalType] = useState("manual")
  const [description, setDescription] = useState("")
  const [severity, setSeverity] = useState("MEDIUM")
  const [saving, setSaving] = useState(false)

  const isStaff = STAFF_ROLES.some((role) => hasRole(role))
  const isAdmin = hasRole("admin")

  const load = useCallback(async () => {
    try {
      const res = await intelligenceApi.listSignals({ limit: 50 })
      setItems(res.items)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0)
    return () => window.clearTimeout(timer)
  }, [load])

  async function createSignal() {
    setSaving(true)
    try {
      await intelligenceApi.createSignal({
        signal_type: signalType,
        title,
        description: description.trim() || null,
        severity: severity as "MEDIUM",
      })
      setCreating(false)
      setTitle("")
      setDescription("")
      toast.toast("success", t("intelligence.signal.create"))
      await load()
    } catch (err) {
      toast.toast("error", err instanceof Error ? err.message : String(err))
    } finally {
      setSaving(false)
    }
  }

  if (error) return <ErrorState title={t("intelligence.error")} detail={error} onRetry={load} />
  if (!items)
    return (
      <div className="space-y-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} height={120} />
        ))}
      </div>
    )

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-(--color-ink-muted)">{t("intelligence.signal.subtitle")}</p>
        {isAdmin && (
          <Button size="sm" onClick={() => setCreating(true)}>
            {t("intelligence.signal.create")}
          </Button>
        )}
      </div>
      {!isStaff && <p className="text-xs text-(--color-ink-muted)">{t("intelligence.roleRequired")}</p>}
      {items.length === 0 ? (
        <EmptyState icon="info" title={t("intelligence.signal.empty")} />
      ) : (
        <div className="space-y-3">
          {items.map((signal) => (
            <SignalCard key={signal.id} signal={signal} canReview={isStaff} onChanged={load} />
          ))}
        </div>
      )}
      <Modal open={creating} onClose={() => setCreating(false)} title={t("intelligence.signal.create")}>
        <div className="space-y-4">
          <div>
            <Label htmlFor="sig-title">{t("intelligence.signal.type")}</Label>
            <Input id="sig-title" value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="sig-type">{t("intelligence.signal.type")}</Label>
            <Select id="sig-type" value={signalType} onChange={(e) => setSignalType(e.target.value)}>
              <option value="manual">manual</option>
              <option value="anomaly">anomaly</option>
              <option value="recurrence">recurrence</option>
              <option value="data_gap">data_gap</option>
            </Select>
          </div>
          <div>
            <Label htmlFor="sig-desc">{t("intelligence.signal.note")}</Label>
            <Textarea id="sig-desc" rows={3} value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="sig-sev">{t("intelligence.signal.severity")}</Label>
            <Select id="sig-sev" value={severity} onChange={(e) => setSeverity(e.target.value)}>
              <option value="LOW">LOW</option>
              <option value="MEDIUM">MEDIUM</option>
              <option value="HIGH">HIGH</option>
              <option value="CRITICAL">CRITICAL</option>
            </Select>
          </div>
          <Button disabled={saving || title.trim().length < 3} onClick={createSignal}>
            {saving ? <Spinner label="…" /> : t("intelligence.signal.create")}
          </Button>
        </div>
      </Modal>
    </div>
  )
}
