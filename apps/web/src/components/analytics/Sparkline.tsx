"use client"

type Point = { x: number; y: number }

export function Sparkline({
  values,
  width = 120,
  height = 32,
  stroke = "var(--color-primary)",
  fill,
  ariaLabel = "trend",
}: {
  values: number[]
  width?: number
  height?: number
  stroke?: string
  fill?: string
  ariaLabel?: string
}): React.ReactNode {
  if (values.length === 0) return <span className="text-xs text-(--color-ink-muted)">—</span>
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  const points: Point[] = values.map((v, i) => ({
    x: (i / Math.max(1, values.length - 1)) * width,
    y: height - ((v - min) / range) * height,
  }))
  const d = points.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" ")
  const fillD = `${d} L ${width} ${height} L 0 ${height} Z`

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={ariaLabel} className="overflow-visible">
      {fill && <path d={fillD} fill={fill} opacity={0.14} />}
      <path d={d} fill="none" stroke={stroke} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" />
      {/* last point dot */}
      <circle cx={points[points.length - 1].x} cy={points[points.length - 1].y} r={2.5} fill={stroke} />
    </svg>
  )
}

export function KpiSparkCard({
  label,
  value,
  delta,
  trend,
  hint,
}: {
  label: string
  value: string | number
  delta?: string
  trend?: number[]
  hint?: string
}): React.ReactNode {
  return (
    <div className="rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface) p-3">
      <p className="text-xs font-medium text-(--color-ink-muted)">{label}</p>
      <div className="mt-1 flex items-end justify-between gap-3">
        <div>
          <p className="text-xl font-black tracking-tight">{value}</p>
          {delta && <p className={`text-xs ${delta.startsWith("-") ? "text-emerald-600" : delta.startsWith("+") ? "text-amber-600" : "text-(--color-ink-muted)"}`}>{delta}</p>}
          {hint && <p className="text-xs text-(--color-ink-muted)">{hint}</p>}
        </div>
        {trend && trend.length > 1 && <Sparkline values={trend} />}
      </div>
    </div>
  )
}
