"use client"

import { useState } from "react"
import type { TimeSeriesPoint } from "@/lib/types"

interface TrendChartProps {
  series: TimeSeriesPoint[]
  interval?: string
}

export function TrendChart({ series, interval = "day" }: TrendChartProps) {
  const [activeMetric, setActiveMetric] = useState<"total" | "verified" | "resolved" | "critical">("total")
  const [showTable, setShowTable] = useState(false)

  if (!series || series.length === 0) {
    return (
      <div className="rounded-(--radius-xl) border border-(--color-line) bg-(--color-surface) p-6 text-center text-sm text-(--color-ink-muted)">
        No time-series data available for the selected interval.
      </div>
    )
  }

  const values = series.map((s) =>
    activeMetric === "total"
      ? s.total_count
      : activeMetric === "verified"
      ? s.verified_count
      : activeMetric === "resolved"
      ? s.resolved_count
      : s.critical_count
  )

  const max = Math.max(...values, 5)
  const width = 680
  const height = 240
  const pad = 36
  const innerW = width - pad * 2
  const innerH = height - pad * 2

  const metricLabels = {
    total: "Total Reported",
    verified: "Verified",
    resolved: "Resolved",
    critical: "High / Critical",
  }

  const metricColors = {
    total: "var(--color-primary)",
    verified: "#10b981",
    resolved: "#3b82f6",
    critical: "#ef4444",
  }

  return (
    <div className="rounded-(--radius-xl) border border-(--color-line) bg-(--color-surface) p-5 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-base font-bold text-(--color-ink)">Report Volume Trends</h3>
          <p className="text-xs text-(--color-ink-muted)">
            Grouped by {interval} interval. Live platform observations.
          </p>
        </div>

        <div className="flex items-center gap-1.5 flex-wrap">
          {(["total", "verified", "resolved", "critical"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setActiveMetric(m)}
              aria-pressed={activeMetric === m}
              className={`px-2.5 py-1 text-xs font-semibold rounded-full transition ${
                activeMetric === m
                  ? "bg-(--color-primary) text-white"
                  : "border border-(--color-line) bg-(--color-surface-raised) text-(--color-ink-muted) hover:text-(--color-ink)"
              }`}
            >
              {metricLabels[m]}
            </button>
          ))}
          <button
            type="button"
            onClick={() => setShowTable(!showTable)}
            className="ml-2 text-xs text-(--color-primary) hover:underline"
          >
            {showTable ? "View Chart" : "Accessible Table"}
          </button>
        </div>
      </div>

      {!showTable ? (
        <div role="region" aria-label="Trend chart" tabIndex={0} className="w-full overflow-x-auto">
          <svg
            role="img"
            aria-label={`Time series trend chart of ${metricLabels[activeMetric]} reports`}
            viewBox={`0 0 ${width} ${height}`}
            className="w-full min-w-[500px]"
          >
            {/* Horizontal Grid lines */}
            {[0, 0.25, 0.5, 0.75, 1].map((pct) => {
              const y = height - pad - pct * innerH
              const val = Math.round(pct * max)
              return (
                <g key={pct}>
                  <line
                    x1={pad}
                    y1={y}
                    x2={width - pad}
                    y2={y}
                    stroke="var(--color-line)"
                    strokeDasharray="3 3"
                  />
                  <text
                    x={pad - 6}
                    y={y + 4}
                    textAnchor="end"
                    fontSize="10"
                    fill="var(--color-ink-muted)"
                  >
                    {val}
                  </text>
                </g>
              )
            })}

            {/* Bars */}
            {series.map((item, idx) => {
              const count =
                activeMetric === "total"
                  ? item.total_count
                  : activeMetric === "verified"
                  ? item.verified_count
                  : activeMetric === "resolved"
                  ? item.resolved_count
                  : item.critical_count

              const barW = Math.max(4, Math.min(24, (innerW / series.length) * 0.6))
              const step = innerW / Math.max(1, series.length)
              const x = pad + idx * step + (step - barW) / 2
              const barH = (count / max) * innerH
              const y = height - pad - barH

              return (
                <g key={item.timestamp} className="group">
                  <rect
                    x={x}
                    y={y}
                    width={barW}
                    height={barH}
                    fill={metricColors[activeMetric]}
                    rx="3"
                    className="transition hover:opacity-80"
                  />
                  <text
                    x={x + barW / 2}
                    y={height - 12}
                    textAnchor="middle"
                    fontSize="9"
                    fill="var(--color-ink-muted)"
                  >
                    {item.timestamp.slice(-5)}
                  </text>
                  {count > 0 ? (
                    <text
                      x={x + barW / 2}
                      y={y - 4}
                      textAnchor="middle"
                      fontSize="9"
                      fontWeight="bold"
                      fill="var(--color-ink)"
                    >
                      {count}
                    </text>
                  ) : null}
                </g>
              )
            })}
          </svg>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-(--radius-md) border border-(--color-line)">
          <table className="w-full text-left text-xs">
            <thead className="bg-(--color-surface-raised) text-(--color-ink-muted) border-b border-(--color-line)">
              <tr>
                <th className="p-2.5">Date</th>
                <th className="p-2.5">Total</th>
                <th className="p-2.5">Verified</th>
                <th className="p-2.5">Resolved</th>
                <th className="p-2.5">High/Critical</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-(--color-line)">
              {series.map((row) => (
                <tr key={row.timestamp} className="hover:bg-(--color-surface-raised)">
                  <td className="p-2.5 font-mono">{row.timestamp}</td>
                  <td className="p-2.5 font-bold">{row.total_count}</td>
                  <td className="p-2.5 text-emerald-600">{row.verified_count}</td>
                  <td className="p-2.5 text-blue-600">{row.resolved_count}</td>
                  <td className="p-2.5 text-red-600">{row.critical_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
