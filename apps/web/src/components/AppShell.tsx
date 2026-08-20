"use client"

/* Application shell: responsive global navigation (Phase 6).
 * Mobile: bottom navigation (thumb zone) + top search bar. Tablet+: top navigation;
 * desktop header includes GlobalSearch, language selector, theme toggle, and user menu. */

import Link from "next/link"
import { useParams, usePathname } from "next/navigation"
import { useState } from "react"

import { Icon, type IconName } from "@/components/ui/icons"
import { LanguageSelector } from "@/components/ui/data"
import { Button, SkipLink } from "@/components/ui/primitives"
import { GlobalSearch } from "@/components/GlobalSearch"
import { useTheme } from "@/lib/theme"
import { useAuth } from "@/lib/auth"
import { useT } from "@/lib/i18n-client"

const baseNav: Array<{
  href: (locale: string) => string
  label: string
  icon: IconName
}> = [
  { href: (l) => `/${l}/`, label: "nav.home", icon: "home" },
  { href: (l) => `/${l}/explore`, label: "nav.explore", icon: "explore" },
  { href: (l) => `/${l}/institutions`, label: "nav.institutions", icon: "building" },
  { href: (l) => `/${l}/map`, label: "nav.map", icon: "map" },
  { href: (l) => `/${l}/submit`, label: "nav.submit", icon: "report" },
  { href: (l) => `/${l}/activity`, label: "nav.activity", icon: "activity" },
  { href: (l) => `/${l}/trust`, label: "nav.trust", icon: "shield" },
  { href: (l) => `/${l}/open-data`, label: "nav.open-data", icon: "database" },
  { href: (l) => `/${l}/profile`, label: "nav.profile", icon: "user" },
]

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const params = useParams<{ locale?: string }>()
  const locale = params.locale ?? "en"
  const t = useT()
  const { resolved, toggle } = useTheme()
  const { user } = useAuth()
  const [mobileSearchOpen, setMobileSearchOpen] = useState(false)

  const isActive = (href: string) =>
    pathname === href || (href !== `/${locale}/` && pathname.startsWith(href))

  return (
    <div className="flex min-h-dvh flex-col bg-(--color-page) text-(--color-ink)">
      <SkipLink />

      {/* Global Header */}
      <header className="sticky top-0 z-40 border-b border-(--color-line) bg-(--color-page)/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
          {/* Logo */}
          <Link
            href={`/${locale}/`}
            className="flex shrink-0 items-center gap-2 text-lg font-black tracking-tight text-(--color-primary-strong)"
          >
            <span
              aria-hidden="true"
              className="flex h-8 w-8 items-center justify-center rounded-(--radius-md) bg-(--color-primary) text-white shadow-xs"
            >
              <Icon name="check" size={18} />
            </span>
            <span>Theek Karo</span>
          </Link>

          {/* Desktop Nav Links */}
          <nav
            aria-label="Primary navigation"
            className="hidden items-center gap-4 md:flex lg:gap-6"
          >
            <Link
              href={`/${locale}/explore`}
              className={`text-sm font-medium transition-colors ${
                isActive(`/${locale}/explore`)
                  ? "font-semibold text-(--color-primary-strong)"
                  : "text-(--color-ink-muted) hover:text-(--color-ink)"
              }`}
            >
              {t("nav.explore")}
            </Link>
            <Link
              href={`/${locale}/institutions`}
              className={`text-sm font-medium transition-colors ${
                isActive(`/${locale}/institutions`)
                  ? "font-semibold text-(--color-primary-strong)"
                  : "text-(--color-ink-muted) hover:text-(--color-ink)"
              }`}
            >
              {t("nav.institutions")}
            </Link>
            <Link
              href={`/${locale}/map`}
              className={`text-sm font-medium transition-colors ${
                isActive(`/${locale}/map`)
                  ? "font-semibold text-(--color-primary-strong)"
                  : "text-(--color-ink-muted) hover:text-(--color-ink)"
              }`}
            >
              {t("nav.map")}
            </Link>
            <Link
              href={`/${locale}/submit`}
              className={`text-sm font-medium transition-colors ${
                isActive(`/${locale}/submit`)
                  ? "font-semibold text-(--color-primary-strong)"
                  : "text-(--color-ink-muted) hover:text-(--color-ink)"
              }`}
            >
              {t("nav.submit")}
            </Link>
            <Link
              href={`/${locale}/activity`}
              className={`text-sm font-medium transition-colors ${
                isActive(`/${locale}/activity`)
                  ? "font-semibold text-(--color-primary-strong)"
                  : "text-(--color-ink-muted) hover:text-(--color-ink)"
              }`}
            >
              {t("nav.activity")}
            </Link>
            <Link
              href={`/${locale}/intelligence`}
              className={`text-sm font-medium transition-colors ${
                isActive(`/${locale}/intelligence`)
                  ? "font-semibold text-(--color-primary-strong)"
                  : "text-(--color-ink-muted) hover:text-(--color-ink)"
              }`}
            >
              {t("nav.intelligence")}
            </Link>
          </nav>

          {/* Desktop Global Search Bar */}
          <div className="hidden max-w-xs flex-1 md:block lg:max-w-sm">
            <GlobalSearch />
          </div>

          {/* Header Controls (Theme, Language, User Menu) */}
          <div className="flex items-center gap-2">
            {/* Mobile Search Button */}
            <button
              type="button"
              onClick={() => setMobileSearchOpen((prev) => !prev)}
              aria-label="Toggle mobile search"
              className="flex h-8 w-8 items-center justify-center rounded-(--radius-md) border border-(--color-line) text-(--color-ink-muted) hover:text-(--color-ink) md:hidden"
            >
              <Icon name="search" size={16} />
            </button>

            {/* Theme Toggle */}
            <Button
              variant="ghost"
              size="sm"
              data-theme-toggle
              icon={resolved === "dark" ? "info" : "clock"}
              onClick={toggle}
              aria-label={`Switch theme (currently ${resolved})`}
            >
              <span className="hidden sm:inline">
                {resolved === "dark" ? "Light" : "Dark"}
              </span>
            </Button>

            {/* Language Selector */}
            <details className="relative">
              <summary
                className="cursor-pointer list-none rounded-(--radius-md) border border-(--color-line) px-2.5 py-1 text-sm font-medium text-(--color-ink)"
                aria-label="Change language"
              >
                {locale.toUpperCase()}
              </summary>
              <div className="absolute right-0 top-9 z-50 w-56 rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface-raised) p-2 shadow-(--elevation-lg)">
                <LanguageSelector />
              </div>
            </details>

            {/* Profile / Login */}
            {user ? (
              <Link
                href={`/${locale}/profile`}
                aria-label="Profile"
                className="flex h-8 w-8 items-center justify-center rounded-full bg-(--color-primary-soft) text-(--color-primary-strong) hover:ring-2 hover:ring-(--color-primary)"
              >
                <Icon name="user" size={16} />
              </Link>
            ) : (
              <Link
                href={`/${locale}/auth/login`}
                className="rounded-(--radius-md) bg-(--color-primary) px-3 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-(--color-primary-strong)"
              >
                {t("nav.login")}
              </Link>
            )}
          </div>
        </div>

        {/* Mobile Search Expandable Tray */}
        {mobileSearchOpen && (
          <div className="border-t border-(--color-line) bg-(--color-surface) p-3 md:hidden">
            <GlobalSearch autoFocus />
          </div>
        )}
      </header>

      {/* Main Content Area */}
      <main
        id="main"
        className="mx-auto w-full max-w-6xl flex-1 px-4 pb-20 pt-4 md:pb-8"
      >
        {children}
      </main>

      {/* Mobile Bottom Thumb Navigation */}
      <nav
        aria-label="Primary mobile navigation"
        className="fixed inset-x-0 bottom-0 z-40 border-t border-(--color-line) bg-(--color-page)/95 backdrop-blur md:hidden"
      >
        <ul className="mx-auto grid max-w-md grid-cols-6">
          {baseNav.filter((item) => item.label !== "nav.activity").map((item) => {
            const href = item.href(locale)
            const active = isActive(href)
            return (
              <li key={item.label}>
                <Link
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={`flex flex-col items-center gap-1 px-1 py-2 text-(--text-caption) transition-colors ${
                    active
                      ? "font-bold text-(--color-primary-strong)"
                      : "text-(--color-ink-muted) hover:text-(--color-ink)"
                  }`}
                >
                  <Icon name={item.icon} size={20} />
                  <span className="truncate">{t(item.label as never)}</span>
                </Link>
              </li>
            )
          })}
        </ul>
      </nav>
    </div>
  )
}