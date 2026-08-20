"use client"

import { useSyncExternalStore } from "react"

import { useLocale } from "@/lib/i18n-client"

const UNSUBSCRIBE = () => () => undefined
const HYDRATED = () => true

/** Dates only format after hydration (server/client TZ mismatch → hydration-safe). */
export function FormattedDate({ iso }: { iso: string }) {
  const locale = useLocale()
  const isHydrated = useSyncExternalStore(UNSUBSCRIBE, HYDRATED, () => false)
  if (!isHydrated) return <span suppressHydrationWarning>—</span>
  return (
    <span suppressHydrationWarning>{new Date(iso).toLocaleDateString(locale)}</span>
  )
}