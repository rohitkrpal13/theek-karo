"use client"

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react"

export type ThemeMode = "light" | "dark" | "system"
export type ResolvedTheme = "light" | "dark"

interface ThemeState {
  mode: ThemeMode
  resolved: ResolvedTheme
  setMode: (mode: ThemeMode) => void
  toggle: () => void
}

const ThemeContext = createContext<ThemeState>({
  mode: "system",
  resolved: "light",
  setMode: () => undefined,
  toggle: () => undefined,
})

const STORAGE_KEY = "tk_theme"

/* Applies the attribute + persist synchronously; callable from anywhere.
 * The head script (layout.tsx) handles the pre-hydration paint; this handles
 * post-hydration changes without depending on effect timing. */
export function applyTheme(resolved: ResolvedTheme, mode: ThemeMode): void {
  if (typeof document === "undefined") return
  document.documentElement.setAttribute("data-theme", resolved)
  document.documentElement.style.colorScheme = resolved
  document.documentElement.dataset.themeMode = mode
  try {
    window.localStorage.setItem(STORAGE_KEY, mode)
  } catch {
    /* storage unavailable (private mode): theme still applies for the page */
  }
  ;(window as unknown as Record<string, unknown>).__tk_theme_probe = resolved
}

export function systemResolved(): ResolvedTheme {
  if (typeof window === "undefined") return "light"
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light"
}

export function storedMode(): ThemeMode {
  if (typeof window === "undefined") return "system"
  const stored = window.localStorage.getItem(STORAGE_KEY)
  return stored === "light" || stored === "dark" || stored === "system" ? stored : "system"
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [mode, setModeState] = useState<ThemeMode>(() =>
    typeof window === "undefined" ? "system" : storedMode(),
  )
  const [systemDark, setSystemDark] = useState<boolean>(() =>
    typeof window === "undefined" ? false : systemResolved() === "dark",
  )

  const resolved: ResolvedTheme = mode === "system" ? (systemDark ? "dark" : "light") : mode

  useEffect(() => {
    applyTheme(resolved, mode)
  }, [resolved, mode])

  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)")
    const listener = (event: MediaQueryListEvent) => setSystemDark(event.matches)
    media.addEventListener("change", listener)
    return () => media.removeEventListener("change", listener)
  }, [])

  const setMode = useCallback((next: ThemeMode) => {
    setModeState(next)
    const resolvedNext: ResolvedTheme = next === "system" ? systemResolved() : next
    applyTheme(resolvedNext, next)
  }, [])

  const toggle = useCallback(() => {
    setModeState((prev) => {
      const nextMode = prev === "dark" ? "light" : prev === "light" ? "dark" : systemResolved() === "dark" ? "light" : "dark"
      applyTheme(nextMode, nextMode)
      return nextMode
    })
  }, [])

  const value = useMemo(() => ({ mode, resolved, setMode, toggle }), [mode, resolved, setMode, toggle])
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme(): ThemeState {
  return useContext(ThemeContext)
}