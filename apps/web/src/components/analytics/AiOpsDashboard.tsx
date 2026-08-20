"use client"

import type { AiOpsAnalyticsResponse } from "@/lib/types"

interface AiOpsDashboardProps {
  aiOps: AiOpsAnalyticsResponse
}

export function AiOpsDashboard({ aiOps }: AiOpsDashboardProps) {
  return (
    <div className="rounded-(--radius-xl) border border-(--color-line) bg-(--color-surface) p-5 space-y-4">
      <div>
        <h3 className="text-base font-bold text-(--color-ink)">AI Intelligence Operations & Cost Telemetry</h3>
        <p className="text-xs text-(--color-ink-muted)">
          Telemetry on model usage, estimated LLM expenditure, latency percentiles, and grounded response quality.
        </p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface-raised) p-3 text-center">
          <span className="text-xs text-(--color-ink-muted)">Total Inferences</span>
          <p className="text-2xl font-extrabold text-(--color-ink) mt-1">
            {aiOps.total_requests.toLocaleString()}
          </p>
          <span className="text-[10px] text-(--color-ink-muted)">Autonomous task executions</span>
        </div>

        <div className="rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface-raised) p-3 text-center">
          <span className="text-xs text-(--color-ink-muted)">Token Volume</span>
          <p className="text-2xl font-extrabold text-blue-600 mt-1">
            {aiOps.total_tokens.toLocaleString()}
          </p>
          <span className="text-[10px] text-(--color-ink-muted)">Prompt + completion tokens</span>
        </div>

        <div className="rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface-raised) p-3 text-center">
          <span className="text-xs text-(--color-ink-muted)">Estimated Cost</span>
          <p className="text-2xl font-extrabold text-emerald-600 mt-1">
            ${aiOps.estimated_cost_usd.toFixed(4)}
          </p>
          <span className="text-[10px] text-(--color-ink-muted)">Model provider fees</span>
        </div>

        <div className="rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface-raised) p-3 text-center">
          <span className="text-xs text-(--color-ink-muted)">Response Latency</span>
          <p className="text-2xl font-extrabold text-(--color-ink) mt-1">
            {aiOps.avg_latency_ms}ms
          </p>
          <span className="text-[10px] text-(--color-ink-muted)">P95: {aiOps.p95_latency_ms}ms</span>
        </div>
      </div>

      {/* Task & Model Distributions */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-3 border-t border-(--color-line)">
        <div className="space-y-2">
          <p className="text-xs font-semibold text-(--color-ink-muted)">Task Distribution:</p>
          <div className="space-y-1.5 text-xs">
            {Object.entries(aiOps.task_breakdown).map(([task, cnt]) => (
              <div
                key={task}
                className="flex items-center justify-between p-2 rounded bg-(--color-surface-raised) border border-(--color-line)"
              >
                <span className="font-mono text-(--color-ink)">{task}</span>
                <span className="font-semibold text-(--color-ink-muted)">{cnt} runs</span>
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-2">
          <p className="text-xs font-semibold text-(--color-ink-muted)">Model Distribution:</p>
          <div className="space-y-1.5 text-xs">
            {Object.entries(aiOps.model_breakdown).map(([model, cnt]) => (
              <div
                key={model}
                className="flex items-center justify-between p-2 rounded bg-(--color-surface-raised) border border-(--color-line)"
              >
                <span className="font-mono text-(--color-ink)">{model}</span>
                <span className="font-semibold text-(--color-ink-muted)">{cnt} calls</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
