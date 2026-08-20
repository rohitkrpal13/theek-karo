"use client"

import Link from "next/link"
import { useParams } from "next/navigation"
import { useCallback, useMemo, useState } from "react"

import { Button } from "@/components/ui/primitives"
import { StatusBadge } from "@/components/ui/data"
import type { ReportSeverity } from "@/lib/types"

export interface MapEntity {
  id: string
  kind: "report" | "institution"
  title: string
  subtitle?: string
  status?: string
  severity?: ReportSeverity | string
  lon: number
  lat: number
  ticket_no?: string
  open_reports_count?: number
  resolved_reports_count?: number
  operational_status?: string
  type_code?: string
  type_name?: string
  verification_state?: string
  trust_score?: number
}

interface Props {
  entities: MapEntity[]
  selectedEntity?: MapEntity | null
  onSelectEntity?: (entity: MapEntity | null) => void
  center?: [number, number]
  zoom?: number
  onCenterChange?: (center: [number, number], zoom: number) => void
  showHeatmap?: boolean
  onToggleHeatmap?: () => void
  activeLayers?: {
    institutions: boolean
    reports: boolean
    heatmap: boolean
  }
}

const DEFAULT_CENTER: [number, number] = [75.7873, 26.9124]
const W = 600
const H = 400

export function MapExplore({
  entities,
  selectedEntity,
  onSelectEntity,
  center = DEFAULT_CENTER,
  zoom = 10,
  onCenterChange,
  showHeatmap = false,
  onToggleHeatmap,
  activeLayers = { institutions: true, reports: true, heatmap: false },
}: Props) {
  const params = useParams<{ locale?: string }>()
  const locale = params.locale ?? "en"

  const [mode, setMode] = useState<"map" | "list">("map")
  const [internalSelected, setInternalSelected] = useState<MapEntity | null>(null)
  const [currentZoom, setCurrentZoom] = useState(zoom)
  const [currentCenter, setCurrentCenter] = useState<[number, number]>(center)
  const [isPanning, setIsPanning] = useState(false)
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null)

  const activeSelected = selectedEntity ?? internalSelected

  function handleSelect(item: MapEntity | null) {
    if (onSelectEntity) {
      onSelectEntity(item)
    } else {
      setInternalSelected(item)
    }
  }

  // Geographic span calculation based on zoom level
  const span = useMemo(() => {
    return Math.max(0.05, 40 / Math.pow(2, currentZoom - 5))
  }, [currentZoom])

  // Coordinate projection from [lon, lat] to SVG [x, y]
  const project = useCallback(
    (lon: number, lat: number): [number, number] => {
      const minLon = currentCenter[0] - span / 2
      const maxLat = currentCenter[1] + (span * (H / W)) / 2
      const x = ((lon - minLon) / span) * W
      const y = ((maxLat - lat) / (span * (H / W))) * H
      return [x, y]
    },
    [currentCenter, span]
  )

  // Reverse project from SVG [x, y] to [lon, lat]
  function unproject(x: number, y: number): [number, number] {
    const minLon = currentCenter[0] - span / 2
    const maxLat = currentCenter[1] + (span * (H / W)) / 2
    const lon = minLon + (x / W) * span
    const lat = maxLat - (y / H) * (span * (H / W))
    return [lon, lat]
  }

  // Filter visible entities by active layer toggles
  const visibleEntities = useMemo(() => {
    return entities.filter((e) => {
      if (e.kind === "institution" && !activeLayers.institutions) return false
      if (e.kind === "report" && !activeLayers.reports) return false
      return true
    })
  }, [entities, activeLayers])

  // Spatial clustering algorithm
  const CLUSTER_RADIUS = 36
  const clusters = useMemo(() => {
    const groups: Array<{
      x: number
      y: number
      items: MapEntity[]
    }> = []

    for (const entity of visibleEntities) {
      const [x, y] = project(entity.lon, entity.lat)
      if (x < -40 || y < -40 || x > W + 40 || y > H + 40) continue

      const group = groups.find((g) => Math.hypot(g.x - x, g.y - y) < CLUSTER_RADIUS)
      if (group) {
        group.items.push(entity)
        group.x = (group.x * (group.items.length - 1) + x) / group.items.length
        group.y = (group.y * (group.items.length - 1) + y) / group.items.length
      } else {
        groups.push({ x, y, items: [entity] })
      }
    }

    return groups.map((g) =>
      g.items.length === 1
        ? { x: g.x, y: g.y, items: g.items, item: g.items[0] }
        : { x: g.x, y: g.y, items: g.items, item: undefined }
    )
  }, [visibleEntities, project])

  // Zoom controls
  function handleZoomIn() {
    const newZoom = Math.min(18, currentZoom + 1)
    setCurrentZoom(newZoom)
    onCenterChange?.(currentCenter, newZoom)
  }

  function handleZoomOut() {
    const newZoom = Math.max(3, currentZoom - 1)
    setCurrentZoom(newZoom)
    onCenterChange?.(currentCenter, newZoom)
  }

  function handleClusterClick(group: { x: number; y: number; items: MapEntity[] }) {
    if (group.items.length === 1 && group.items[0]) {
      handleSelect(group.items[0])
      return
    }
    // Zoom in on cluster center
    const [cLon, cLat] = unproject(group.x, group.y)
    const newZoom = Math.min(18, currentZoom + 2)
    setCurrentCenter([cLon, cLat])
    setCurrentZoom(newZoom)
    onCenterChange?.([cLon, cLat], newZoom)
  }

  // Pan / Drag handlers
  function onMouseDown(e: React.MouseEvent<SVGSVGElement>) {
    setIsPanning(true)
    setDragStart({ x: e.clientX, y: e.clientY })
  }

  function onMouseMove(e: React.MouseEvent<SVGSVGElement>) {
    if (!isPanning || !dragStart) return
    const dx = e.clientX - dragStart.x
    const dy = e.clientY - dragStart.y
    if (Math.abs(dx) > 2 || Math.abs(dy) > 2) {
      const dLon = -(dx / W) * span
      const dLat = (dy / H) * (span * (H / W))
      const newCenter: [number, number] = [currentCenter[0] + dLon, currentCenter[1] + dLat]
      setCurrentCenter(newCenter)
      setDragStart({ x: e.clientX, y: e.clientY })
      onCenterChange?.(newCenter, currentZoom)
    }
  }

  function onMouseUp() {
    setIsPanning(false)
    setDragStart(null)
  }

  const severityColor = (severity?: string) => {
    switch (severity) {
      case "critical":
        return "#dc2626"
      case "high":
        return "#ea580c"
      case "medium":
        return "#d97706"
      default:
        return "#16a34a"
    }
  }

  const severitySymbol = (severity?: string) => {
    switch (severity) {
      case "critical":
      case "high":
        return "▲"
      case "medium":
        return "◆"
      default:
        return "●"
    }
  }

  return (
    <div className="space-y-3">
      {/* Top Map/List Controls Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-(--color-line) pb-2">
        <div className="flex items-center gap-2">
          <p className="text-xs font-semibold text-(--color-ink-muted)" role="status">
            Showing <span className="font-bold text-(--color-ink)">{visibleEntities.length}</span> items in viewport
          </p>
          {showHeatmap && (
            <span className="rounded-full bg-orange-100 px-2 py-0.5 text-[10px] font-bold text-orange-800 dark:bg-orange-950 dark:text-orange-300">
              Density Heatmap Active
            </span>
          )}
        </div>

        <div className="flex items-center gap-1.5" role="group" aria-label="View toggle">
          <Button
            variant={mode === "map" ? "primary" : "outline"}
            size="sm"
            aria-pressed={mode === "map"}
            icon="map"
            onClick={() => setMode("map")}
          >
            Map View
          </Button>
          <Button
            variant={mode === "list" ? "primary" : "outline"}
            size="sm"
            aria-pressed={mode === "list"}
            icon="activity"
            onClick={() => setMode("list")}
          >
            List View ({visibleEntities.length})
          </Button>
        </div>
      </div>

      {mode === "map" ? (
        <div className="relative overflow-hidden rounded-(--radius-xl) border border-(--color-line) bg-slate-50 dark:bg-slate-950">
          {/* SVG Map Canvas */}
          <svg
            role="application"
            aria-label="Interactive civic map"
            viewBox={`0 0 ${W} ${H}`}
            className="h-[420px] w-full cursor-grab active:cursor-grabbing sm:h-[500px]"
            onMouseDown={onMouseDown}
            onMouseMove={onMouseMove}
            onMouseUp={onMouseUp}
            onMouseLeave={onMouseUp}
          >
            {/* Background Grid Lines & Coordinates */}
            <g stroke="currentColor" strokeWidth="0.5" className="text-slate-200 dark:text-slate-800">
              {Array.from({ length: 11 }, (_, i) => (i * W) / 10).map((x) => (
                <line key={`v${x}`} x1={x} y1={0} x2={x} y2={H} />
              ))}
              {Array.from({ length: 8 }, (_, i) => (i * H) / 7).map((y) => (
                <line key={`h${y}`} x1={0} y1={y} x2={W} y2={y} />
              ))}
            </g>

            {/* Density Heatmap Layer */}
            {showHeatmap &&
              clusters.map((cluster, index) => (
                <g key={`heat-${index}`}>
                  <circle
                    cx={cluster.x}
                    cy={cluster.y}
                    r={Math.min(80, 16 + cluster.items.length * 8)}
                    fill="url(#heatGrad)"
                    opacity="0.6"
                  />
                </g>
              ))}

            {/* Heatmap Radial Gradient Definition */}
            <defs>
              <radialGradient id="heatGrad">
                <stop offset="0%" stopColor="#f97316" stopOpacity="0.8" />
                <stop offset="50%" stopColor="#fbbf24" stopOpacity="0.4" />
                <stop offset="100%" stopColor="#38bdf8" stopOpacity="0" />
              </radialGradient>
            </defs>

            {/* Render Clusters & Markers */}
            {clusters.map((cluster, index) => {
              if (cluster.items.length === 1 && cluster.item) {
                const item = cluster.item
                const isSelected = activeSelected?.id === item.id
                const isInst = item.kind === "institution"
                const color = isInst ? "#2563eb" : severityColor(item.severity)

                return (
                  <g
                    key={`item-${item.id}-${index}`}
                    role="button"
                    tabIndex={0}
                    aria-label={`${item.kind}: ${item.title}`}
                    onClick={(e) => {
                      e.stopPropagation()
                      handleSelect(item)
                    }}
                    onKeyDown={(e) => e.key === "Enter" && handleSelect(item)}
                    className="cursor-pointer transition-transform hover:scale-125"
                  >
                    {isSelected && (
                      <circle
                        cx={cluster.x}
                        cy={cluster.y}
                        r={16}
                        fill="none"
                        stroke="#4f46e5"
                        strokeWidth="2.5"
                        strokeDasharray="4,2"
                        className="animate-pulse"
                      />
                    )}
                    <circle
                      cx={cluster.x}
                      cy={cluster.y}
                      r={isSelected ? 10 : 8}
                      fill={color}
                      stroke="#ffffff"
                      strokeWidth="2"
                    />
                    <text
                      x={cluster.x}
                      y={cluster.y + 3}
                      textAnchor="middle"
                      fontSize="7"
                      fill="#ffffff"
                      fontWeight="bold"
                    >
                      {isInst ? "🏛" : severitySymbol(item.severity)}
                    </text>
                  </g>
                )
              } else {
                // Multi-item cluster badge
                const hasHighSev = cluster.items.some(
                  (i) => i.severity === "high" || i.severity === "critical"
                )
                const clusterColor = hasHighSev ? "#ea580c" : "#0284c7"

                return (
                  <g
                    key={`cluster-${index}`}
                    role="button"
                    tabIndex={0}
                    aria-label={`Cluster of ${cluster.items.length} items`}
                    onClick={(e) => {
                      e.stopPropagation()
                      handleClusterClick(cluster)
                    }}
                    onKeyDown={(e) => e.key === "Enter" && handleClusterClick(cluster)}
                    className="cursor-pointer transition-transform hover:scale-110"
                  >
                    <circle
                      cx={cluster.x}
                      cy={cluster.y}
                      r={18}
                      fill={clusterColor}
                      opacity="0.25"
                    />
                    <circle
                      cx={cluster.x}
                      cy={cluster.y}
                      r={11}
                      fill={clusterColor}
                      stroke="#ffffff"
                      strokeWidth="2"
                    />
                    <text
                      x={cluster.x}
                      y={cluster.y + 3.5}
                      textAnchor="middle"
                      fontSize="9"
                      fill="#ffffff"
                      fontWeight="bold"
                    >
                      {cluster.items.length}
                    </text>
                  </g>
                )
              }
            })}
          </svg>

          {/* Floating Map Controls */}
          <div className="absolute right-3 top-3 flex flex-col gap-1.5 rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface)/90 p-1 shadow-xs backdrop-blur-xs">
            <button
              type="button"
              aria-label="Zoom in"
              onClick={handleZoomIn}
              className="flex h-8 w-8 items-center justify-center rounded-(--radius-md) hover:bg-(--color-surface-sunken) text-sm font-bold text-(--color-ink)"
            >
              +
            </button>
            <button
              type="button"
              aria-label="Zoom out"
              onClick={handleZoomOut}
              className="flex h-8 w-8 items-center justify-center rounded-(--radius-md) hover:bg-(--color-surface-sunken) text-sm font-bold text-(--color-ink)"
            >
              −
            </button>
            <div className="my-0.5 h-px bg-(--color-line)" />
            {onToggleHeatmap && (
              <button
                type="button"
                aria-label="Toggle density heatmap"
                aria-pressed={showHeatmap}
                onClick={onToggleHeatmap}
                className={`flex h-8 w-8 items-center justify-center rounded-(--radius-md) text-xs ${
                  showHeatmap
                    ? "bg-orange-500 text-white font-bold"
                    : "hover:bg-(--color-surface-sunken) text-(--color-ink)"
                }`}
                title="Toggle Density Heatmap"
              >
                🔥
              </button>
            )}
          </div>

          {/* Map Scale & Coords Legend */}
          <div className="absolute bottom-3 left-3 rounded-(--radius-md) border border-(--color-line) bg-(--color-surface)/80 px-2 py-1 text-[10px] font-mono text-(--color-ink-muted) backdrop-blur-xs">
            {currentCenter[1].toFixed(4)}° N, {currentCenter[0].toFixed(4)}° E · Zoom {currentZoom}x
          </div>

          {/* Selected Marker Detail Card / Drawer */}
          {activeSelected && (
            <div className="absolute bottom-3 right-3 left-3 sm:left-auto sm:max-w-xs rounded-(--radius-xl) border border-(--color-line) bg-(--color-surface) p-4 shadow-lg animate-in slide-in-from-bottom-2">
              <div className="flex items-start justify-between gap-2">
                <div className="space-y-1">
                  <div className="flex items-center gap-1.5">
                    <span
                      className={`inline-block h-2 w-2 rounded-full ${
                        activeSelected.kind === "institution" ? "bg-blue-500" : "bg-orange-500"
                      }`}
                    />
                    <span className="text-[10px] font-bold uppercase tracking-wider text-(--color-ink-muted)">
                      {activeSelected.kind === "institution" ? "Public Institution" : "Civic Issue"}
                    </span>
                    {activeSelected.severity && (
                      <span className="text-[10px] font-bold uppercase text-orange-600 dark:text-orange-400">
                        {severitySymbol(activeSelected.severity)} {activeSelected.severity}
                      </span>
                    )}
                  </div>
                  <h3 className="text-sm font-bold text-(--color-ink) line-clamp-1">
                    {activeSelected.title}
                  </h3>
                </div>
                <button
                  type="button"
                  onClick={() => handleSelect(null)}
                  className="rounded-(--radius-sm) p-1 text-xs text-(--color-ink-muted) hover:bg-(--color-surface-sunken)"
                >
                  ✕
                </button>
              </div>

              {activeSelected.subtitle && (
                <p className="mt-1 text-xs text-(--color-ink-muted) line-clamp-2">
                  {activeSelected.subtitle}
                </p>
              )}

              {activeSelected.kind === "institution" && (
                <div className="mt-3 flex items-center justify-between border-t border-(--color-line) pt-2 text-xs">
                  <span className="text-(--color-ink-muted)">
                    Status: <span className="font-semibold text-(--color-ink) capitalize">{activeSelected.operational_status ?? "Active"}</span>
                  </span>
                  <Link href={`/${locale}/institutions/${activeSelected.id}`}>
                    <Button variant="primary" size="sm">
                      View Twin →
                    </Button>
                  </Link>
                </div>
              )}

              {activeSelected.kind === "report" && (
                <div className="mt-3 flex items-center justify-between border-t border-(--color-line) pt-2 text-xs">
                  <span className="font-mono text-(--color-ink-muted)">
                    {activeSelected.ticket_no ?? activeSelected.id.slice(0, 8)}
                  </span>
                  <Link href={`/${locale}/reports/${activeSelected.id}`}>
                    <Button variant="primary" size="sm">
                      View Report →
                    </Button>
                  </Link>
                </div>
              )}
            </div>
          )}
        </div>
      ) : (
        /* Synchronized Accessible List View Alternative */
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            {visibleEntities.map((item) => (
              <div
                key={item.id}
                onClick={() => handleSelect(item)}
                className={`flex cursor-pointer flex-col justify-between rounded-(--radius-lg) border p-4 transition-colors ${
                  activeSelected?.id === item.id
                    ? "border-(--color-primary) bg-(--color-primary-soft)"
                    : "border-(--color-line) bg-(--color-surface) hover:border-(--color-primary)"
                }`}
              >
                <div className="space-y-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-(--color-ink-muted)">
                      {item.kind === "institution" ? "🏛 Institution" : "⚠️ Civic Issue"}
                    </span>
                    {item.status && <StatusBadge status={item.status} />}
                  </div>
                  <h3 className="text-sm font-bold text-(--color-ink)">{item.title}</h3>
                  {item.subtitle && (
                    <p className="text-xs text-(--color-ink-muted) line-clamp-2">
                      {item.subtitle}
                    </p>
                  )}
                </div>

                <div className="mt-3 flex items-center justify-between border-t border-(--color-line) pt-2 text-xs">
                  <span className="font-mono text-[11px] text-(--color-ink-muted)">
                    {item.lat.toFixed(4)}, {item.lon.toFixed(4)}
                  </span>
                  {item.kind === "institution" ? (
                    <Link href={`/${locale}/institutions/${item.id}`}>
                      <span className="font-semibold text-(--color-primary-strong) hover:underline">
                        View Twin →
                      </span>
                    </Link>
                  ) : (
                    <Link href={`/${locale}/reports/${item.id}`}>
                      <span className="font-semibold text-(--color-primary-strong) hover:underline">
                        View Report →
                      </span>
                    </Link>
                  )}
                </div>
              </div>
            ))}
          </div>

          {visibleEntities.length === 0 && (
            <div className="rounded-(--radius-lg) border border-dashed border-(--color-line) p-8 text-center text-xs text-(--color-ink-muted)">
              No institutions or reports match the active viewport and filters. Try zooming out or adjusting layer filters.
            </div>
          )}
        </div>
      )}

      {/* Accessible Map Legend */}
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-(--radius-md) border border-(--color-line) bg-(--color-surface-sunken) p-3 text-xs text-(--color-ink-muted)">
        <span className="font-bold text-(--color-ink)">Map Legend:</span>
        <div className="flex flex-wrap items-center gap-4">
          <span className="flex items-center gap-1">
            <span className="inline-block h-3 w-3 rounded-full bg-blue-600" />
            <span>Public Institution (🏛)</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="font-bold text-red-600">▲</span>
            <span>Critical / High Severity</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="font-bold text-amber-600">◆</span>
            <span>Medium Severity</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="font-bold text-emerald-600">●</span>
            <span>Low Severity</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="flex h-4 w-4 items-center justify-center rounded-full bg-sky-700 text-[11px] font-bold text-white">
              12
            </span>
            <span>Cluster Badge</span>
          </span>
        </div>
      </div>
    </div>
  )
}