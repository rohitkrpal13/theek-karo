"use client"

import { AuthProvider } from "@/lib/auth"
import { localeContext } from "@/lib/i18n-client"
import type { Locale } from "@/lib/i18n"

export function Providers({ locale, children }: { locale: Locale; children: React.ReactNode }) {
  return (
    <localeContext.Provider value={locale}>
      <AuthProvider>{children}</AuthProvider>
    </localeContext.Provider>
  )
}