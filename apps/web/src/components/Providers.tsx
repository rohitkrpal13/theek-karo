"use client"

import { useEffect } from "react"

import { AuthProvider } from "@/lib/auth"
import { localeContext } from "@/lib/i18n-client"
import type { Locale } from "@/lib/i18n"
import { ThemeProvider } from "@/lib/theme"
import { ErrorBoundary } from "@/components/ui/ErrorBoundary"
import { ToastProvider } from "@/components/ui/Toast"
import { reportWebVitals } from "@/lib/vitals"

export function Providers({ locale, children }: { locale: Locale; children: React.ReactNode }) {
  useEffect(() => {
    reportWebVitals()
  }, [])
  return (
    <ThemeProvider>
      <localeContext.Provider value={locale}>
        <AuthProvider>
          <ToastProvider>
            <ErrorBoundary>{children}</ErrorBoundary>
          </ToastProvider>
        </AuthProvider>
      </localeContext.Provider>
    </ThemeProvider>
  )
}