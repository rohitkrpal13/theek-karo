"use client"

import { CivicAssistantChat } from "@/components/ai/CivicAssistantChat"

export default function AssistantPage() {
  return (
    <div className="space-y-6 py-4">
      <div className="max-w-5xl mx-auto space-y-2">
        <h1 className="text-3xl font-extrabold text-(--color-ink) tracking-tight">
          Civic Research Assistant
        </h1>
        <p className="text-sm text-(--color-ink-muted) max-w-3xl leading-relaxed">
          Ask questions about institutions, community reports, and government open data.
          Answers are strictly evidence-grounded with citations to official sources, data freshness,
          and transparent confidence levels.
        </p>
      </div>

      <CivicAssistantChat />
    </div>
  )
}
