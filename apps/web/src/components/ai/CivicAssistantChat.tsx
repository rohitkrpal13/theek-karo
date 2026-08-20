"use client"

import { useState, useRef, useEffect } from "react"
import Link from "next/link"
import { aiApi } from "@/lib/api/ai"
import type {
  CitationItem,
  CivicChatResponse,
  RelatedEntityRef,
} from "@/lib/types"
import { Badge, Button, Input } from "@/components/ui/primitives"
import { Icon } from "@/components/ui/icons"

interface Message {
  id: string
  role: "user" | "assistant"
  text: string
  citations?: CitationItem[]
  related_entities?: RelatedEntityRef[]
  confidence_label?: string
  model_id?: string
  latency_ms?: number
  timestamp: string
  feedbackState?: "helpful" | "unhelpful" | null
}

let msgSeq = 0
const makeMsgId = (prefix: string) => {
  msgSeq += 1
  return `${prefix}-${msgSeq}-${Date.now()}`
}
const fmtTime = () =>
  new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })

const WELCOME_MESSAGE: Message = {
  id: "welcome",
  role: "assistant",
  text: "Namaste! I am the Theek Karo Evidence-Grounded Civic Research Assistant. I analyze official government open data alongside verified citizen observation reports. Every factual statement is backed by verifiable citations.",
  timestamp: fmtTime(),
}

const SUPPORTED_LANGUAGES = [
  { code: "en", label: "English" },
  { code: "hi", label: "हिंदी (Hindi)" },
  { code: "bn", label: "বাংলা (Bengali)" },
  { code: "te", label: "తెలుగు (Telugu)" },
  { code: "mr", label: "मराठी (Marathi)" },
  { code: "ta", label: "தமிழ் (Tamil)" },
  { code: "gu", label: "ગુજરાતી (Gujarati)" },
  { code: "ur", label: "اردو (Urdu)" },
  { code: "kn", label: "ಕನ್ನಡ (Kannada)" },
  { code: "or", label: "ଓଡ଼ିଆ (Odia)" },
  { code: "ml", label: "മലയാളം (Malayalam)" },
  { code: "pa", label: "ਪੰਜਾਬੀ (Punjabi)" },
  { code: "as", label: "অসমীয়া (Assamese)" },
  { code: "mai", label: "मैथिली (Maithili)" },
]

const DEFAULT_SUGGESTED = [
  "Show unresolved school infrastructure issues in Patna",
  "Compare official teacher sanctions with citizen reports in Jaipur",
  "What healthcare facilities have emergency water disruptions?",
  "Analyze road and pothole reports near civil hospital",
]

export function CivicAssistantChat() {
  const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE])
  const [inputQuery, setInputQuery] = useState("")
  const [selectedLang, setSelectedLang] = useState("en")
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [activeCitation, setActiveCitation] = useState<CitationItem | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const chatBottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, loading])

  const handleSend = async (queryText?: string) => {
    const textToSend = queryText || inputQuery.trim()
    if (!textToSend || loading) return

    setErrorMsg(null)
    const userMsg: Message = {
      id: makeMsgId("user"),
      role: "user",
      text: textToSend,
      timestamp: fmtTime(),
    }

    setMessages((prev) => [...prev, userMsg])
    setInputQuery("")
    setLoading(true)

    try {
      const resp: CivicChatResponse = await aiApi.chat({
        message: textToSend,
        conversation_id: conversationId,
        language: selectedLang,
      })

      if (resp.conversation_id) {
        setConversationId(resp.conversation_id)
      }

      const assistantMsg: Message = {
        id: makeMsgId("ai"),
        role: "assistant",
        text: resp.answer,
        citations: resp.citations,
        related_entities: resp.related_entities,
        confidence_label: resp.confidence_label,
        model_id: resp.model_id,
        latency_ms: resp.latency_ms,
        timestamp: fmtTime(),
      }

      setMessages((prev) => [...prev, assistantMsg])
    } catch (err: unknown) {
      setErrorMsg(
        err instanceof Error && err.message
          ? err.message
          : "Failed to contact civic assistant. Please try again."
      )
    } finally {
      setLoading(false)
    }
  }

  const handleFeedback = async (msgId: string, rating: 1 | -1) => {
    try {
      await aiApi.submitFeedback({
        task_kind: "chat_assistant",
        rating,
        feedback_text: `User rating for message ${msgId}`,
      })
      setMessages((prev) =>
        prev.map((m) =>
          m.id === msgId ? { ...m, feedbackState: rating === 1 ? "helpful" : "unhelpful" } : m
        )
      )
    } catch (err) {
      console.error("Feedback submit failed:", err)
    }
  }

  return (
    <div className="flex flex-col h-[760px] max-w-5xl mx-auto border border-(--color-line) rounded-xl bg-(--color-surface) shadow-sm overflow-hidden">
      {/* Top Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-6 py-4 border-b border-(--color-line) bg-(--color-surface-sunken)">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-(--color-primary-soft) text-(--color-primary-strong)">
            <Icon name="activity" size={22} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-(--color-ink)">Civic Intelligence Assistant</h2>
              <Badge tone="success">Evidence Grounded</Badge>
            </div>
            <p className="text-xs text-(--color-ink-muted)">
              Multilingual · Access Controlled · Zero Hallucination Policy
            </p>
          </div>
        </div>

        {/* Language Selection */}
        <div className="flex items-center gap-2">
          <label htmlFor="lang-select" className="text-xs font-medium text-(--color-ink-muted)">
            Language:
          </label>
          <select
            id="lang-select"
            value={selectedLang}
            onChange={(e) => setSelectedLang(e.target.value)}
            className="text-xs py-1.5 px-3 rounded-md border border-(--color-line) bg-(--color-surface) text-(--color-ink) focus:outline-(--color-primary)"
          >
            {SUPPORTED_LANGUAGES.map((l) => (
              <option key={l.code} value={l.code}>
                {l.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-(--color-surface)">
        {messages.map((m) => (
          <div
            key={m.id}
            className={`flex flex-col ${m.role === "user" ? "items-end" : "items-start"}`}
          >
            <div
              className={`max-w-[85%] rounded-2xl px-5 py-4 text-sm leading-relaxed shadow-xs ${
                m.role === "user"
                  ? "bg-(--color-primary) text-white rounded-br-xs"
                  : "bg-(--color-surface-sunken) border border-(--color-line) text-(--color-ink) rounded-bl-xs"
              }`}
            >
              {/* Message Header */}
              <div className="flex items-center justify-between gap-4 mb-2 pb-1 border-b border-black/5 text-xs opacity-75">
                <span className="font-semibold">
                  {m.role === "user" ? "You" : "Theek Karo Intelligence"}
                </span>
                <span>{m.timestamp}</span>
              </div>

              {/* Message Text */}
              <div className="whitespace-pre-wrap">{m.text}</div>

              {/* Citations Tray */}
              {m.citations && m.citations.length > 0 && (
                <div className="mt-4 pt-3 border-t border-(--color-line) space-y-2">
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-(--color-ink-muted)">
                    <Icon name="building" size={14} />
                    <span>Evidence Sources ({m.citations.length})</span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {m.citations.map((c, idx) => (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => setActiveCitation(c)}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-md bg-(--color-surface) border border-(--color-line) hover:border-(--color-primary) text-(--color-ink) transition-colors cursor-pointer"
                      >
                        <span className="font-medium">[{idx + 1}]</span>
                        <span className="truncate max-w-[180px]">{c.dataset_name}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Related Entities */}
              {m.related_entities && m.related_entities.length > 0 && (
                <div className="mt-3 pt-2 border-t border-(--color-line)/60">
                  <span className="text-[11px] font-semibold text-(--color-ink-muted) block mb-1.5">
                    Referenced Entities
                  </span>
                  <div className="flex flex-wrap gap-2">
                    {m.related_entities.map((ent) => (
                      <Link
                        key={ent.id}
                        href={ent.kind === "institution" ? `/institutions/${ent.id}` : `/reports/${ent.id}`}
                        className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-full bg-(--color-primary-soft) text-(--color-primary-strong) hover:underline"
                      >
                        <span>{ent.kind === "institution" ? "🏫" : "📋"}</span>
                        <span>{ent.title}</span>
                      </Link>
                    ))}
                  </div>
                </div>
              )}

              {/* AI Metadata & Feedback */}
              {m.role === "assistant" && m.id !== "welcome" && (
                <div className="mt-3 pt-2 flex flex-wrap items-center justify-between gap-2 text-[11px] text-(--color-ink-muted)">
                  <div className="flex items-center gap-2">
                    {m.confidence_label && (
                      <Badge
                        tone={
                          m.confidence_label === "high"
                            ? "success"
                            : m.confidence_label === "moderate"
                            ? "default"
                            : "error"
                        }
                      >
                        {m.confidence_label} confidence
                      </Badge>
                    )}
                    {m.latency_ms && <span>{m.latency_ms}ms</span>}
                  </div>

                  <div className="flex items-center gap-1.5">
                    <span className="text-[10px]">Helpful?</span>
                    <button
                      type="button"
                      disabled={Boolean(m.feedbackState)}
                      onClick={() => handleFeedback(m.id, 1)}
                      className={`p-1 rounded hover:bg-(--color-line) transition-colors ${
                        m.feedbackState === "helpful" ? "text-(--color-primary) font-bold" : ""
                      }`}
                      aria-label="Helpful"
                    >
                      👍
                    </button>
                    <button
                      type="button"
                      disabled={Boolean(m.feedbackState)}
                      onClick={() => handleFeedback(m.id, -1)}
                      className={`p-1 rounded hover:bg-(--color-line) transition-colors ${
                        m.feedbackState === "unhelpful" ? "text-(--color-error) font-bold" : ""
                      }`}
                      aria-label="Not Helpful"
                    >
                      👎
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex items-center gap-3 text-xs text-(--color-ink-muted) p-3 bg-(--color-surface-sunken) rounded-xl w-fit animate-pulse border border-(--color-line)">
            <Icon name="refresh" size={16} />
            <span>Consulting official datasets & citizen observation reports...</span>
          </div>
        )}

        {errorMsg && (
          <div className="p-3 text-xs rounded-lg bg-(--color-error)/10 text-(--color-error) border border-(--color-error)/30">
            {errorMsg}
          </div>
        )}

        <div ref={chatBottomRef} />
      </div>

      {/* Suggested Questions Bar */}
      {messages.length <= 2 && (
        <div className="px-6 py-2.5 bg-(--color-surface-sunken) border-t border-(--color-line) flex items-center gap-2 overflow-x-auto">
          <span className="text-xs font-semibold text-(--color-ink-muted) whitespace-nowrap">
            Suggested:
          </span>
          {DEFAULT_SUGGESTED.map((q, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => handleSend(q)}
              className="text-xs px-3 py-1 rounded-full border border-(--color-line) bg-(--color-surface) text-(--color-ink) hover:border-(--color-primary) hover:text-(--color-primary) transition-colors whitespace-nowrap cursor-pointer shadow-2xs"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {/* Chat Input Bar */}
      <form
        onSubmit={(e) => {
          e.preventDefault()
          handleSend()
        }}
        className="flex items-center gap-3 p-4 bg-(--color-surface) border-t border-(--color-line)"
      >
        <Input
          value={inputQuery}
          onChange={(e) => setInputQuery(e.target.value)}
          placeholder="Ask a civic research question (e.g. 'Show water supply issues in Jaipur schools')..."
          disabled={loading}
          className="flex-1"
          aria-label="Civic research question"
        />
        <Button
          type="submit"
          variant="primary"
          disabled={loading || !inputQuery.trim()}
          icon="search"
        >
          {loading ? "Analyzing..." : "Ask Assistant"}
        </Button>
      </form>

      {/* Citation Detail Modal / Drawer */}
      {activeCitation && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs">
          <div className="w-full max-w-lg p-6 rounded-xl bg-(--color-surface) border border-(--color-line) shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-(--color-line) pb-3">
              <div className="flex items-center gap-2">
                <Icon name="building" size={20} />
                <h3 className="text-base font-bold text-(--color-ink)">Official Source Provenance</h3>
              </div>
              <button
                type="button"
                onClick={() => setActiveCitation(null)}
                className="text-(--color-ink-muted) hover:text-(--color-ink) p-1 rounded-md"
              >
                <Icon name="close" size={18} />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <span className="font-semibold text-(--color-ink-muted) block">Dataset</span>
                <span className="text-sm font-medium text-(--color-ink)">{activeCitation.dataset_name}</span>
              </div>

              {activeCitation.dataset_version && (
                <div>
                  <span className="font-semibold text-(--color-ink-muted) block">Version</span>
                  <span>{activeCitation.dataset_version}</span>
                </div>
              )}

              {activeCitation.publication_date && (
                <div>
                  <span className="font-semibold text-(--color-ink-muted) block">Published Date</span>
                  <span>{new Date(activeCitation.publication_date).toLocaleDateString()}</span>
                </div>
              )}

              <div>
                <span className="font-semibold text-(--color-ink-muted) block mb-1">Grounded Excerpt</span>
                <div className="p-3 rounded-lg bg-(--color-surface-sunken) border border-(--color-line) font-mono text-[11px] leading-relaxed text-(--color-ink)">
                  {activeCitation.snippet}
                </div>
              </div>

              {activeCitation.url && (
                <div className="pt-2">
                  <a
                    href={activeCitation.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 text-(--color-primary) font-semibold hover:underline"
                  >
                    <span>View Official Portal / Dataset Record</span>
                    <Icon name="explore" size={14} />
                  </a>
                </div>
              )}
            </div>

            <div className="pt-2 flex justify-end">
              <Button variant="outline" size="sm" onClick={() => setActiveCitation(null)}>
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
