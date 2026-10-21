"use client"

import { useEffect, useMemo, useState } from "react"
import { useParams, useRouter } from "next/navigation"

import { useT } from "@/lib/i18n-client"

interface Command {
  id: string
  label: string
  hint?: string
  action: () => void
}

export function CommandPalette(): React.ReactNode {
  const router = useRouter()
  const params = useParams<{ locale?: string }>()
  const locale = params.locale ?? "en"
  const t = useT()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")

  useEffect(() => {
    const onKey = (e: KeyboardEvent): void => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault()
        setOpen((v) => !v)
      }
      if (e.key === "Escape") setOpen(false)
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [])

  const commands: Command[] = useMemo(
    () => [
      { id: "home", label: t("nav.home"), action: () => router.push(`/${locale}/`) },
      { id: "explore", label: t("nav.explore"), action: () => router.push(`/${locale}/explore`) },
      { id: "institutions", label: t("nav.institutions"), action: () => router.push(`/${locale}/institutions`) },
      { id: "map", label: t("nav.map"), action: () => router.push(`/${locale}/map`) },
      { id: "submit", label: t("nav.submit"), action: () => router.push(`/${locale}/submit`) },
      { id: "intelligence", label: t("nav.intelligence"), action: () => router.push(`/${locale}/intelligence`) },
      { id: "search", label: t("search.title"), hint: "⌘K", action: () => router.push(`/${locale}/search`) },
      { id: "profile", label: t("nav.profile"), action: () => router.push(`/${locale}/profile`) },
      { id: "trust", label: t("nav.trust"), action: () => router.push(`/${locale}/trust`) },
    ],
    [locale, router, t],
  )

  const filtered = commands.filter((c) => !query || c.label.toLowerCase().includes(query.toLowerCase()))

  if (!open) return null

  return (
    <div className="fixed inset-0 z-[90] flex items-start justify-center bg-black/30 pt-[20vh] backdrop-blur-sm">
      <button type="button" aria-label="Close command palette" className="absolute inset-0 border-0 bg-transparent p-0" onClick={() => setOpen(false)} />
      <div className="relative w-[min(96%,560px)] overflow-hidden rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface) shadow-xl">
        <div className="flex items-center gap-2 border-b border-(--color-line) px-3 py-2">
          <span aria-hidden className="text-(--color-ink-muted)">
            ⌘K
          </span>
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={`${t("search.placeholder")} — ${t("search.title")}`}
            className="flex-1 bg-transparent text-sm outline-none placeholder:text-(--color-ink-muted)"
          />
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="rounded px-2 py-1 text-xs text-(--color-ink-muted) hover:bg-(--color-line)/40"
          >
            Esc
          </button>
        </div>
        <ul role="listbox" className="max-h-64 overflow-auto p-1">
          {filtered.length === 0 && <li className="px-3 py-6 text-center text-sm text-(--color-ink-muted)">{t("search.no_results", { query })}</li>}
          {filtered.map((c) => (
            <li key={c.id}>
              <button
                type="button"
                role="option"
                aria-selected={false}
                onClick={() => {
                  setOpen(false)
                  c.action()
                }}
                className="flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm hover:bg-(--color-primary-soft)"
              >
                <span>{c.label}</span>
                {c.hint && <span className="text-xs text-(--color-ink-muted)">{c.hint}</span>}
              </button>
            </li>
          ))}
        </ul>
        <div className="border-t border-(--color-line) bg-(--color-page)/60 px-3 py-2 text-xs text-(--color-ink-muted)">
          Press <kbd className="rounded border bg-(--color-surface) px-1">Ctrl/⌘ + K</kbd> to toggle
        </div>
      </div>
    </div>
  )
}
