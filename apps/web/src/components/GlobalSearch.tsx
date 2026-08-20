"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { useRouter, useParams } from "next/navigation"
import { Icon, type IconName } from "@/components/ui/icons"
import { searchApi } from "@/lib/api"
import type { SearchDomain, SearchResultItem } from "@/lib/types"
import { useT } from "@/lib/i18n-client"

interface GlobalSearchProps {
  initialQuery?: string
  initialDomain?: SearchDomain
  onSelect?: (item: SearchResultItem) => void
  isExpanded?: boolean
  autoFocus?: boolean
  className?: string
}

const DOMAINS: Array<{ key: SearchDomain; labelKey: string }> = [
  { key: "all", labelKey: "search.domain.all" },
  { key: "reports", labelKey: "search.domain.reports" },
  { key: "institutions", labelKey: "search.domain.institutions" },
  { key: "geography", labelKey: "search.domain.geography" },
  { key: "categories", labelKey: "search.domain.categories" },
]

export function GlobalSearch({
  initialQuery = "",
  initialDomain = "all",
  onSelect,
  isExpanded = false,
  autoFocus = false,
  className = "",
}: GlobalSearchProps) {
  const router = useRouter()
  const params = useParams<{ locale?: string }>()
  const locale = params.locale ?? "en"
  const t = useT()

  const [query, setQuery] = useState(initialQuery)
  const [domain, setDomain] = useState<SearchDomain>(initialDomain)
  const [results, setResults] = useState<SearchResultItem[]>([])
  const [loading, setLoading] = useState(false)
  const [isOpen, setIsOpen] = useState(isExpanded)
  const [activeIndex, setActiveIndex] = useState<number>(-1)
  const [error, setError] = useState<string | null>(null)

  const containerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const debounceTimer = useRef<NodeJS.Timeout | null>(null)

  const performSearch = useCallback(
    async (q: string, dom: SearchDomain) => {
      const trimmed = q.trim()
      if (trimmed.length === 0) {
        setResults([])
        setLoading(false)
        return
      }

      setLoading(true)
      setError(null)
      try {
        const res = await searchApi.search(trimmed, dom, isExpanded ? 30 : 8)
        setResults(res.items)
      } catch (err) {
        setError(err instanceof Error ? err.message : "Search failed")
        setResults([])
      } finally {
        setLoading(false)
      }
    },
    [isExpanded],
  )

  useEffect(() => {
    if (debounceTimer.current) clearTimeout(debounceTimer.current)

    debounceTimer.current = setTimeout(() => {
      void performSearch(query, domain)
    }, 250)

    return () => {
      if (debounceTimer.current) clearTimeout(debounceTimer.current)
    }
  }, [query, domain, performSearch])

  // Handle click outside to close dropdown if not in expanded mode
  useEffect(() => {
    if (isExpanded) return

    function handleClickOutside(event: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false)
      }
    }

    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [isExpanded])

  function handleSelect(item: SearchResultItem) {
    setIsOpen(false)
    if (onSelect) {
      onSelect(item)
      return
    }

    // Default routing
    if (item.domain === "report") {
      router.push(`/${locale}/reports/${item.id}`)
    } else if (item.domain === "institution") {
      router.push(`/${locale}/institutions/${item.id}`)
    } else if (item.domain === "geography") {
      router.push(`/${locale}/explore?geography_id=${item.id}`)
    } else if (item.domain === "category") {
      router.push(`/${locale}/explore?category_slug=${item.id}`)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault()
      if (!isOpen) setIsOpen(true)
      setActiveIndex((prev) => (prev < results.length - 1 ? prev + 1 : 0))
    } else if (e.key === "ArrowUp") {
      e.preventDefault()
      setActiveIndex((prev) => (prev > 0 ? prev - 1 : results.length - 1))
    } else if (e.key === "Enter") {
      e.preventDefault()
      if (activeIndex >= 0 && activeIndex < results.length) {
        handleSelect(results[activeIndex])
      } else if (query.trim()) {
        router.push(
          `/${locale}/search?q=${encodeURIComponent(query)}&domain=${domain}`,
        )
        setIsOpen(false)
      }
    } else if (e.key === "Escape") {
      setIsOpen(false)
      setActiveIndex(-1)
    }
  }

  function getDomainIcon(dom: SearchResultItem["domain"]): IconName {
    switch (dom) {
      case "institution":
        return "building"
      case "report":
        return "report"
      case "geography":
        return "map"
      case "category":
        return "explore"
      default:
        return "search"
    }
  }

  return (
    <div
      ref={containerRef}
      className={`relative w-full ${className}`}
      role="search"
    >
      {/* Search Input Box */}
      <div className="relative flex items-center">
        <span
          className="pointer-events-none absolute left-3 text-(--color-ink-muted)"
          aria-hidden="true"
        >
          <Icon name="search" size={18} />
        </span>
        <input
          ref={inputRef}
          type="search"
          role="combobox"
          aria-expanded={isOpen && results.length > 0}
          aria-autocomplete="list"
          aria-controls="global-search-results"
          aria-activedescendant={
            activeIndex >= 0 ? `search-item-${activeIndex}` : undefined
          }
          placeholder={t("search.placeholder")}
          value={query}
          autoFocus={autoFocus}
          onChange={(e) => {
            setQuery(e.target.value)
            setIsOpen(true)
            setActiveIndex(-1)
          }}
          onFocus={() => {
            if (query.trim().length > 0) setIsOpen(true)
          }}
          onKeyDown={handleKeyDown}
          className="w-full rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface) py-2 pl-10 pr-10 text-sm text-(--color-ink) placeholder-(--color-ink-muted) focus:border-(--color-primary) focus:outline-hidden focus:ring-2 focus:ring-(--color-primary-soft)"
        />
        {loading ? (
          <span
            className="absolute right-3 text-(--color-ink-muted) animate-spin"
            aria-hidden="true"
          >
            <Icon name="clock" size={16} />
          </span>
        ) : query.length > 0 ? (
          <button
            type="button"
            onClick={() => {
              setQuery("")
              setResults([])
              inputRef.current?.focus()
            }}
            aria-label="Clear search"
            className="absolute right-3 text-(--color-ink-muted) hover:text-(--color-ink)"
          >
            <Icon name="close" size={16} />
          </button>
        ) : null}
      </div>

      {/* Domain Filters (shown when expanded or active) */}
      {(isExpanded || isOpen) && (
        <div
          role="tablist"
          aria-label="Search domain filter"
          className="mt-2 flex flex-wrap gap-1 border-b border-(--color-line) pb-2"
        >
          {DOMAINS.map((d) => (
            <button
              key={d.key}
              role="tab"
              type="button"
              aria-selected={domain === d.key}
              onClick={() => {
                setDomain(d.key)
                setActiveIndex(-1)
              }}
              className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                domain === d.key
                  ? "bg-(--color-primary) text-white"
                  : "bg-(--color-surface-sunken) text-(--color-ink-muted) hover:bg-(--color-surface-raised)"
              }`}
            >
              {t(d.labelKey as never)}
            </button>
          ))}
        </div>
      )}

      {/* Dropdown / Inline Results */}
      {isOpen && (
        <div
          id="global-search-results"
          role={results.length > 0 ? "listbox" : undefined}
          className={
            isExpanded
              ? "mt-4 space-y-2"
              : "absolute left-0 right-0 top-full z-50 mt-1 max-h-96 overflow-y-auto rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface-raised) p-2 shadow-(--elevation-lg)"
          }
        >
          {error ? (
            <div className="p-3 text-center text-sm text-(--color-danger)">
              {error}
            </div>
          ) : loading && results.length === 0 ? (
            <div className="p-4 text-center text-sm text-(--color-ink-muted)">
              {t("search.loading")}
            </div>
          ) : results.length > 0 ? (
            <ul className="space-y-1">
              {results.map((item, idx) => {
                const isActive = activeIndex === idx
                return (
                  <li
                    key={`${item.domain}-${item.id}`}
                    id={`search-item-${idx}`}
                    role="option"
                    aria-selected={isActive}
                    onClick={() => handleSelect(item)}
                    onMouseEnter={() => setActiveIndex(idx)}
                    className={`flex cursor-pointer items-start gap-3 rounded-(--radius-md) p-2.5 transition-colors ${
                      isActive
                        ? "bg-(--color-primary-soft) text-(--color-primary-strong)"
                        : "hover:bg-(--color-surface-sunken)"
                    }`}
                  >
                    <span
                      className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-(--radius-sm) bg-(--color-surface-sunken) text-(--color-ink-muted)"
                      aria-hidden="true"
                    >
                      <Icon name={getDomainIcon(item.domain)} size={16} />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate text-sm font-semibold text-(--color-ink)">
                          {item.title}
                        </span>
                        <span className="shrink-0 rounded-full bg-(--color-surface-sunken) px-2 py-0.5 text-(--text-caption) text-(--color-ink-muted) capitalize">
                          {item.domain}
                        </span>
                      </div>
                      {item.subtitle ? (
                        <p className="truncate text-xs text-(--color-ink-muted)">
                          {item.subtitle}
                        </p>
                      ) : null}
                      {item.snippet ? (
                        <p className="mt-0.5 line-clamp-1 text-xs text-(--color-ink-muted)">
                          {item.snippet}
                        </p>
                      ) : null}
                    </div>
                  </li>
                )
              })}
            </ul>
          ) : query.trim().length > 0 && !loading ? (
            <div className="p-4 text-center text-sm text-(--color-ink-muted)">
              {t("search.no_results", { query })}
            </div>
          ) : (
            <div className="p-4 text-center text-xs text-(--color-ink-muted)">
              {t("search.empty")}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
