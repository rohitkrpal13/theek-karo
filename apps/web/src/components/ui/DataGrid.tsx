"use client"

import { useMemo, useState, useRef, useEffect, type ReactNode } from "react"

import { Button } from "@/components/ui/primitives"
import { Skeleton } from "@/components/ui/Skeleton"

export interface Column<T> {
  key: string
  header: string
  width?: string
  sortable?: boolean
  render?: (row: T) => ReactNode
  accessor?: (row: T) => string | number
}

interface DataGridProps<T> {
  data: T[]
  columns: Column<T>[]
  loading?: boolean
  error?: unknown
  onRetry?: () => void
  emptyTitle?: string
  emptyHint?: string
  pageSize?: number
  getRowId?: (row: T, idx: number) => string
  onRowClick?: (row: T) => void
}

export function DataGrid<T>({
  data,
  columns,
  loading,
  error,
  onRetry,
  emptyTitle = "No results",
  emptyHint = "Try adjusting filters or search.",
  pageSize = 10,
  getRowId,
  onRowClick,
}: DataGridProps<T>): ReactNode {
  const [page, setPage] = useState(1)
  const [sortKey, setSortKey] = useState<string | null>(null)
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc")
  const [visibleCount, setVisibleCount] = useState(pageSize)
  const sentinelRef = useRef<HTMLDivElement>(null)

  const sorted = useMemo(() => {
    if (!sortKey) return data
    const col = columns.find((c) => c.key === sortKey)
    if (!col) return data
    const accessor = col.accessor ?? ((r: T) => (r as Record<string, unknown>)[sortKey] as string)
    return [...data].sort((a, b) => {
      const av = String(accessor(a) ?? "")
      const bv = String(accessor(b) ?? "")
      const cmp = av.localeCompare(bv, undefined, { numeric: true, sensitivity: "base" })
      return sortDir === "asc" ? cmp : -cmp
    })
  }, [data, columns, sortKey, sortDir])

  const paged = useMemo(() => sorted.slice(0, visibleCount), [sorted, visibleCount])

  // infinite scroll via IntersectionObserver (virtualized-lite)
  useEffect(() => {
    const el = sentinelRef.current
    if (!el) return
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && visibleCount < sorted.length) {
          setVisibleCount((c) => Math.min(c + pageSize, sorted.length))
        }
      },
      { rootMargin: "200px" },
    )
    io.observe(el)
    return () => io.disconnect()
  }, [sorted.length, visibleCount, pageSize])

  // reset when data changes
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- sync with external data prop
    setVisibleCount(pageSize)
    setPage(1)
  }, [data, pageSize])

  if (loading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="flex gap-2">
            <Skeleton className="h-10 flex-1" />
            <Skeleton className="h-10 w-24" />
          </div>
        ))}
      </div>
    )
  }

  if (error) {
    const msg = error instanceof Error ? error.message : String(error)
    return (
      <div role="alert" className="rounded-(--radius-lg) border border-(--color-error)/20 bg-(--color-error)/5 p-6 text-center">
        <p className="font-semibold text-(--color-error)">Failed to load</p>
        <p className="mt-1 text-sm text-(--color-ink-muted)">{msg}</p>
        {onRetry && <Button variant="outline" size="sm" className="mt-3" onClick={onRetry}>Retry</Button>}
      </div>
    )
  }

  if (data.length === 0) {
    return (
      <div className="rounded-(--radius-lg) border border-dashed border-(--color-line) p-10 text-center">
        <p className="font-semibold">{emptyTitle}</p>
        <p className="mt-1 text-sm text-(--color-ink-muted)">{emptyHint}</p>
      </div>
    )
  }

  const toggleSort = (key: string, sortable?: boolean): void => {
    if (!sortable) return
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"))
    else {
      setSortKey(key)
      setSortDir("asc")
    }
  }

  const totalPages = Math.ceil(sorted.length / pageSize)
  const currentPageSlice = sorted.slice((page - 1) * pageSize, page * pageSize)

  return (
    <div className="overflow-hidden rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface)">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-(--color-surface-sunken) text-left text-xs text-(--color-ink-muted)">
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  style={col.width ? { width: col.width } : undefined}
                  className={`px-3 py-2 font-semibold ${col.sortable ? "cursor-pointer select-none hover:text-(--color-ink)" : ""}`}
                  onClick={() => toggleSort(col.key, col.sortable)}
                  aria-sort={sortKey === col.key ? (sortDir === "asc" ? "ascending" : "descending") : undefined}
                >
                  <span className="inline-flex items-center gap-1">
                    {col.header}
                    {col.sortable && sortKey === col.key && <span aria-hidden>{sortDir === "asc" ? "↑" : "↓"}</span>}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-(--color-line)/60">
            {/* virtualized page or infinite list – here we show paged + sentinel */}
            {(page > 1 ? currentPageSlice : paged).map((row, idx) => (
              <tr
                key={getRowId ? getRowId(row, idx) : String(idx)}
                onClick={() => onRowClick?.(row)}
                className={onRowClick ? "cursor-pointer hover:bg-(--color-primary-soft)/40" : undefined}
              >
                {columns.map((col) => (
                  <td key={col.key} className="px-3 py-2.5 align-top">
                    {col.render ? col.render(row) : String((row as Record<string, unknown>)[col.key] ?? "")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* infinite sentinel */}
      {page === 1 && paged.length < sorted.length && <div ref={sentinelRef} className="h-6" aria-hidden />}

      {/* pagination controls (also accessible) */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between border-t border-(--color-line) px-3 py-2 text-xs">
          <span className="text-(--color-ink-muted)">
            {sorted.length} items • page {page} of {totalPages}
          </span>
          <div className="flex gap-1">
            <Button variant="ghost" size="sm" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>Prev</Button>
            <Button variant="ghost" size="sm" disabled={page >= totalPages} onClick={() => setPage((p) => Math.min(totalPages, p + 1))}>Next</Button>
          </div>
        </div>
      )}
    </div>
  )
}
