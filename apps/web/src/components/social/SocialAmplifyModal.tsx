"use client"

import { useEffect, useState } from "react"
import { Button } from "@/components/ui/primitives"
import { reportsApi } from "@/lib/api/reports"
import type { SocialBroadcastResponse, SocialPostResponse, SocialPostTone } from "@/lib/types"
import { CivicStoryCard } from "./CivicStoryCard"

interface Props {
  reportId: string
  isOpen?: boolean
  onClose?: () => void
  embedded?: boolean
}

export function SocialAmplifyModal({
  reportId,
  isOpen = true,
  onClose,
  embedded = false,
}: Props) {
  const [tone, setTone] = useState<SocialPostTone>("urgent")
  const [activeTab, setActiveTab] = useState<"x" | "instagram" | "whatsapp">("x")
  const [data, setData] = useState<SocialPostResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [broadcasting, setBroadcasting] = useState(false)
  const [broadcastRecord, setBroadcastRecord] = useState<SocialBroadcastResponse | null>(null)
  const [broadcastError, setBroadcastError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function fetchSocialPost() {
      try {
        const res = await reportsApi.getSocialPost(reportId, tone)
        if (!cancelled) {
          setData(res)
          setLoading(false)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to generate social post")
          setLoading(false)
        }
      }
    }

    void fetchSocialPost()

    return () => {
      cancelled = true
    }
  }, [reportId, tone])

  // Check if a social broadcast was already created for this report
  useEffect(() => {
    let cancelled = false
    async function checkBroadcast() {
      try {
        const res = await reportsApi.getSocialBroadcastStatus(reportId)
        if (!cancelled && res) {
          setBroadcastRecord(res)
        }
      } catch {
        // Silently ignore 404 or network errors on initial status check
      }
    }
    void checkBroadcast()
    return () => {
      cancelled = true
    }
  }, [reportId])

  // Poll for background worker updates when broadcast is queued or processing
  const broadcastStatus = broadcastRecord?.status
  useEffect(() => {
    const isPending =
      broadcastStatus === "queued" ||
      broadcastStatus === "processing" ||
      broadcastStatus === "retry_wait"

    if (!isPending) return

    const interval = setInterval(async () => {
      try {
        const res = await reportsApi.getSocialBroadcastStatus(reportId)
        if (res) {
          setBroadcastRecord(res)
        }
      } catch {
        // Silently continue polling
      }
    }, 3000)

    return () => clearInterval(interval)
  }, [reportId, broadcastStatus])


  const handleToneChange = (newTone: SocialPostTone) => {
    setLoading(true)
    setError(null)
    setTone(newTone)
  }

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2500)
    } catch {
      // ignore
    }
  }

  const handleBroadcast = async () => {
    setBroadcasting(true)
    setBroadcastError(null)
    try {
      const res = await reportsApi.broadcastSocialPost(reportId, {
        network: "x",
        tone,
        idempotency_key: `client-${reportId}-${Date.now()}`,
      })
      setBroadcastRecord(res)
    } catch (err) {
      setBroadcastError(
        err instanceof Error ? err.message : "Official civic bot broadcast could not be queued."
      )
    } finally {
      setBroadcasting(false)
    }
  }


  // Handle Escape key dismissal for accessibility
  useEffect(() => {
    if (!isOpen || embedded) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose?.()
      }
    }
    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [isOpen, embedded, onClose])

  if (!isOpen && !embedded) return null

  const handleBackdropClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) {
      onClose?.()
    }
  }

  const content = (
    <div className="space-y-6 text-left">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-orange-100 text-orange-600 dark:bg-orange-950 dark:text-orange-400 font-bold text-sm">
              📢
            </span>
            <h2 id="social-amplify-title" className="text-xl font-black tracking-tight text-(--color-ink)">
              Amplify & Tag Authorities
            </h2>
          </div>
          <p className="mt-1 text-xs text-(--color-ink-muted)">
            Hold municipal bodies accountable with auto-tagged handles, hashtags & verified ticket proofs.
          </p>
        </div>

        {!embedded && onClose && (
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-(--color-ink-muted) hover:bg-(--color-surface-sunken) hover:text-(--color-ink)"
            aria-label="Close modal"
          >
            ✕
          </button>
        )}
      </div>

      {/* Tone Switcher */}
      <div className="space-y-1.5">
        <label className="text-xs font-semibold text-(--color-ink-muted)">Select Amplification Tone:</label>
        <div className="grid grid-cols-3 gap-2">
          {(
            [
              { key: "urgent", label: "🚨 Urgent Hazard", desc: "Safety & accident warning" },
              { key: "nudge", label: "🤝 Civic Nudge", desc: "Constructive request" },
              { key: "accountability", label: "📋 SLA Notice", desc: "Official ticket tracking" },
            ] as const
          ).map((t) => (
            <button
              key={t.key}
              onClick={() => handleToneChange(t.key)}
              className={`rounded-xl border p-2.5 text-left transition-all ${
                tone === t.key
                  ? "border-(--color-primary) bg-(--color-primary-soft)/20 ring-1 ring-(--color-primary)"
                  : "border-(--color-line) bg-(--color-surface) hover:border-(--color-ink-muted)/40"
              }`}
            >
              <div className="text-xs font-bold text-(--color-ink)">{t.label}</div>
              <div className="text-[10px] text-(--color-ink-muted)">{t.desc}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Platform Tabs */}
      <div className="flex border-b border-(--color-line)">
        {(
          [
            { id: "x", label: "𝕏 (Twitter)", icon: "𝕏" },
            { id: "instagram", label: "Instagram Story & Post", icon: "📸" },
            { id: "whatsapp", label: "WhatsApp & Groups", icon: "💬" },
          ] as const
        ).map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-1.5 border-b-2 px-4 py-2.5 text-xs font-bold transition-colors ${
              activeTab === tab.id
                ? "border-(--color-primary) text-(--color-primary-strong)"
                : "border-transparent text-(--color-ink-muted) hover:text-(--color-ink)"
            }`}
          >
            <span>{tab.icon}</span>
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex h-48 flex-col items-center justify-center gap-2 text-stone-400">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-orange-500 border-t-transparent" />
          <p className="text-xs">Resolving city authorities & generating optimized post...</p>
        </div>
      ) : error || !data ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-xs text-red-700 dark:border-red-900/50 dark:bg-red-950/20 dark:text-red-300">
          {error || "Could not generate post."}
        </div>
      ) : (
        <div>
          {/* TAB 1: 𝕏 (Twitter) */}
          {activeTab === "x" && (
            <div className="space-y-4">
              {/* Tweet Preview Card */}
              <div className="rounded-2xl border border-stone-800 bg-[#090e17] p-4 text-white shadow-lg">
                <div className="flex items-center justify-between pb-2 border-b border-white/10">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-sm text-stone-200">Theek Karo Citizen</span>
                    <span className="text-xs text-stone-400">@theekkaro</span>
                  </div>
                  <span className="text-[11px] font-mono font-semibold text-emerald-400">
                    #{data.ticket_no}
                  </span>
                </div>

                <p className="mt-3 text-sm leading-relaxed text-stone-100 whitespace-pre-wrap">
                  {data.x_post.text}
                </p>

                <div className="mt-3 flex items-center justify-between text-xs text-stone-400 pt-2 border-t border-white/10">
                  <span>
                    Char Count:{" "}
                    <strong
                      className={
                        data.x_post.char_count <= 280 ? "text-emerald-400" : "text-amber-400"
                      }
                    >
                      {data.x_post.char_count}
                    </strong>{" "}
                    / 280
                  </span>
                  <span className="text-emerald-400 text-[11px]">✓ Ready for 1-Click Tweet</span>
                </div>
              </div>

              {/* Tagged Authorities directory badges */}
              <div className="space-y-1.5">
                <label className="text-[11px] font-semibold text-(--color-ink-muted)">
                  Auto-Tagged Authorities ({data.authorities.length}):
                </label>
                <div className="flex flex-wrap gap-1.5">
                  {data.authorities.map((auth) => (
                    <span
                      key={auth.name}
                      className="inline-flex items-center gap-1.5 rounded-full bg-(--color-surface-sunken) px-2.5 py-1 text-[11px] font-medium text-(--color-ink)"
                    >
                      <span className="font-bold text-(--color-primary-strong)">
                        {auth.x_handle || auth.name}
                      </span>
                      <span className="text-stone-400">({auth.jurisdiction})</span>
                      {auth.verification_status === "verified_official" ? (
                        <span
                          className="rounded bg-emerald-500/15 px-1 py-0.5 text-[9px] font-bold text-emerald-700"
                          title={auth.official_verification_source ? `Verified via ${auth.official_verification_source}` : "Verified official authority"}
                        >
                          ✓ Official
                        </span>
                      ) : (
                        <span
                          className="rounded bg-amber-500/15 px-1 py-0.5 text-[9px] font-medium text-amber-700"
                          title="Handle awaiting official municipal verification"
                        >
                          Unverified
                        </span>
                      )}
                    </span>
                  ))}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex flex-col gap-2 sm:flex-row">
                <a
                  href={data.x_post.intent_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex-1"
                >
                  <Button variant="primary" size="md" className="w-full font-bold">
                    <span>𝕏</span>
                    <span className="ml-1.5">Post on 𝕏 (1-Click)</span>
                  </Button>
                </a>

                <Button
                  variant="outline"
                  size="md"
                  onClick={() => copyToClipboard(data.x_post.text)}
                  className="font-medium"
                >
                  {copied ? "✓ Copied!" : "Copy Tweet Text"}
                </Button>
              </div>

              {/* Official @TheekKaro Bot option */}
              {data.official_broadcast_eligible && (
                <div
                  aria-live="polite"
                  className="rounded-xl border border-orange-200/60 bg-orange-50/50 p-4 dark:border-orange-950/60 dark:bg-orange-950/10 space-y-3"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-1.5">
                        <span className="text-sm">⚡</span>
                        <p className="text-xs font-bold text-orange-900 dark:text-orange-300">
                          Official @TheekKaro Civic Bot Escalation
                        </p>
                      </div>
                      <p className="mt-0.5 text-[11px] text-orange-800/80 dark:text-orange-400">
                        High-severity report eligible for automated official tweet tagging ward commissioner.
                      </p>
                    </div>

                    {!broadcastRecord || broadcastRecord.status === "failed" ? (
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={handleBroadcast}
                        disabled={broadcasting}
                        className="shrink-0 bg-orange-600 hover:bg-orange-700 text-white font-bold"
                      >
                        {broadcasting
                          ? "Queuing..."
                          : broadcastRecord?.status === "failed"
                            ? "Retry Escalation"
                            : "Escalate Bot"}
                      </Button>
                    ) : (
                      <span className="shrink-0 inline-flex items-center gap-1 text-[11px] font-bold">
                        {broadcastRecord.status === "published" && (
                          <span className="text-emerald-700 dark:text-emerald-300 bg-emerald-100 dark:bg-emerald-950/60 px-2 py-0.5 rounded-full">
                            ✓ Published
                          </span>
                        )}
                        {broadcastRecord.status === "simulated" && (
                          <span className="text-amber-700 dark:text-amber-300 bg-amber-100 dark:bg-amber-950/60 px-2 py-0.5 rounded-full">
                            Sandbox Simulated
                          </span>
                        )}
                        {(broadcastRecord.status === "queued" ||
                          broadcastRecord.status === "processing" ||
                          broadcastRecord.status === "retry_wait") && (
                          <span className="text-sky-700 dark:text-sky-300 bg-sky-100 dark:bg-sky-950/60 px-2 py-0.5 rounded-full flex items-center gap-1">
                            <span className="h-2 w-2 rounded-full bg-sky-500 animate-ping" />
                            {broadcastRecord.status === "processing" ? "Publishing..." : "Queued"}
                          </span>
                        )}
                        {broadcastRecord.status === "outcome_unknown" && (
                          <span className="text-amber-800 dark:text-amber-200 bg-amber-100 dark:bg-amber-950/60 px-2 py-0.5 rounded-full">
                            ⚠️ Awaiting Verification
                          </span>
                        )}
                        {broadcastRecord.status === "disabled" && (
                          <span className="text-stone-700 dark:text-stone-300 bg-stone-100 dark:bg-stone-900/60 px-2 py-0.5 rounded-full">
                            Disabled
                          </span>
                        )}
                        {broadcastRecord.status === "not_configured" && (
                          <span className="text-stone-700 dark:text-stone-300 bg-stone-100 dark:bg-stone-900/60 px-2 py-0.5 rounded-full">
                            Not Configured
                          </span>
                        )}
                      </span>
                    )}
                  </div>

                  {/* Status Banner / Output */}
                  {broadcastRecord && (
                    <div className="rounded-lg border border-orange-200/40 bg-white/60 p-2.5 text-xs dark:border-orange-900/40 dark:bg-black/20">
                      <p className="font-medium text-stone-800 dark:text-stone-200">
                        {broadcastRecord.message}
                      </p>

                      {broadcastRecord.published_url && (
                        <div className="mt-2">
                          <a
                            href={broadcastRecord.published_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 font-bold text-sky-600 hover:text-sky-700 dark:text-sky-400 dark:hover:text-sky-300 underline"
                          >
                            <span>View Confirmed Post on 𝕏</span>
                            <span>↗</span>
                          </a>
                        </div>
                      )}
                    </div>
                  )}

                  {broadcastError && (
                    <div className="rounded-lg border border-red-200 bg-red-50 p-2.5 text-xs text-red-700 dark:border-red-900/50 dark:bg-red-950/20 dark:text-red-300">
                      {broadcastError}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* TAB 2: Instagram */}
          {activeTab === "instagram" && (
            <div className="grid gap-6 md:grid-cols-2">
              <div>
                <CivicStoryCard
                  data={data.story_card}
                  captionToCopy={data.instagram_post.caption}
                />
              </div>

              <div className="space-y-4">
                <div>
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-(--color-ink)">
                      Instagram Caption & Hashtags:
                    </label>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => copyToClipboard(data.instagram_post.caption)}
                    >
                      {copied ? "✓ Copied!" : "Copy Caption"}
                    </Button>
                  </div>
                  <div className="mt-2 max-h-72 overflow-y-auto rounded-xl border border-(--color-line) bg-(--color-surface-sunken) p-3 font-mono text-xs leading-relaxed text-(--color-ink) whitespace-pre-wrap select-all">
                    {data.instagram_post.caption}
                  </div>
                </div>

                <div className="rounded-xl border border-(--color-line) bg-(--color-surface) p-3 text-xs text-(--color-ink-muted) space-y-1">
                  <p className="font-semibold text-(--color-ink)">💡 How to post to Instagram:</p>
                  <ol className="list-decimal pl-4 space-y-0.5 text-[11px]">
                    <li>Click <strong>Download Story Image</strong> to save the 1080×1920 graphic.</li>
                    <li>Click <strong>Copy Caption</strong> to copy tags & hashtags.</li>
                    <li>Open Instagram, upload Story / Post, tag <strong className="text-(--color-ink)">{data.instagram_post.handles.join(" ") || "@theekkaro"}</strong>, and paste caption!</li>
                  </ol>
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: WhatsApp & Direct Link */}
          {activeTab === "whatsapp" && (
            <div className="space-y-4">
              <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/5 p-4 text-xs leading-relaxed text-(--color-ink)">
                <p className="font-bold text-sm text-emerald-800 dark:text-emerald-400 mb-1">
                  Mobilize Local RWA & Resident Groups
                </p>
                <p className="text-(--color-ink-muted)">
                  Sharing in neighborhood WhatsApp groups gets nearby residents to corroborate and verify the report, raising its priority on the official civic dashboard.
                </p>
              </div>

              <div className="rounded-xl border border-(--color-line) bg-(--color-surface-sunken) p-3 text-xs font-mono text-(--color-ink) whitespace-pre-wrap">
                {`🚨 Civic Observation Reported: ${data.story_card.title}\n📍 Location: ${data.story_card.address}\n🎫 Ticket: #${data.ticket_no}\n🔗 Verify or support resolution: ${data.report_url}`}
              </div>

              <div className="flex flex-col gap-2 sm:flex-row">
                <a
                  href={`https://api.whatsapp.com/send?text=${encodeURIComponent(
                    `🚨 Civic Observation: ${data.story_card.title} at ${data.story_card.address}. Verified Ticket #${data.ticket_no}. Track resolution: ${data.report_url}`,
                  )}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex-1"
                >
                  <Button variant="primary" size="md" className="w-full bg-emerald-600 hover:bg-emerald-700">
                    <span>💬</span>
                    <span className="ml-1.5">Share to WhatsApp</span>
                  </Button>
                </a>

                <Button
                  variant="outline"
                  size="md"
                  onClick={() => copyToClipboard(data.report_url)}
                >
                  {copied ? "✓ Copied!" : "Copy Report Link"}
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )

  if (embedded) {
    return (
      <div className="rounded-2xl border border-(--color-line) bg-(--color-surface) p-6 shadow-sm">
        {content}
      </div>
    )
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs"
      onClick={handleBackdropClick}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="social-amplify-title"
        className="relative max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-3xl border border-(--color-line) bg-(--color-surface) p-6 shadow-2xl"
      >
        {content}
      </div>
    </div>
  )
}
