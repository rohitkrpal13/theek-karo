"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { useParams } from "next/navigation"
import { Icon } from "@/components/ui/icons"
import { realtimeApi, type PublicAlertItem } from "@/lib/api/realtime"
import { useRealtimeEvents } from "@/hooks/useRealtimeEvents"
import { t } from "@/lib/i18n"

function visibleAlerts(items: PublicAlertItem[]): PublicAlertItem[] {
  return items.filter(
    (alert) =>
      alert.status === "published" &&
      alert.verified &&
      (!alert.expires_at || new Date(alert.expires_at).getTime() > Date.now()),
  )
}

export function RealtimeAlertBanner() {
  const params = useParams<{ locale?: string }>()
  const locale = params.locale ?? "en"

  const [alerts, setAlerts] = useState<PublicAlertItem[]>([])
  const [dismissed, setDismissed] = useState<Record<string, boolean>>({})
  const [loadError, setLoadError] = useState(false)

  const loadAlerts = useCallback(async () => {
    try {
      const res = await realtimeApi.publicAlerts()
      setAlerts(visibleAlerts(res.items))
      setLoadError(false)
    } catch (error) {
      console.error("Failed to load public civic alerts", error)
      setLoadError(true)
    }
  }, [])

  useEffect(() => {
    let isMounted = true
    void realtimeApi
      .publicAlerts()
      .then((res) => {
        if (isMounted) {
          setAlerts(visibleAlerts(res.items))
          setLoadError(false)
        }
      })
      .catch((error: unknown) => {
        console.error("Failed to load public civic alerts", error)
        if (isMounted) setLoadError(true)
      })

    return () => {
      isMounted = false
    }
  }, [])

  // Listen to real-time alert events
  useRealtimeEvents({
    onEvent: (event, data) => {
      if (event === "alert.issued" && data && typeof data === "object") {
        const newAlert = data as PublicAlertItem
        const isNotExpired =
          !newAlert.expires_at || new Date(newAlert.expires_at).getTime() > Date.now()
        if (newAlert.status === "published" && newAlert.verified && isNotExpired) {
          setAlerts((prev) => [newAlert, ...prev.filter((a) => a.id !== newAlert.id)])
        }
      } else if (event === "alert.resolved" && data && typeof data === "object") {
        const resolved = data as { id: string }
        setAlerts((prev) => prev.filter((a) => a.id !== resolved.id))
      }
    },
  })

  const activeAlerts = alerts.filter((a) => !dismissed[a.id])
  if (activeAlerts.length === 0) {
    if (!loadError) return null
    return (
      <div role="status" className="px-4 py-2 text-center text-sm text-(--color-danger)">
        {t(locale === "hi" ? "hi" : "en", "alerts.load_error")}{" "}
        <button type="button" onClick={() => void loadAlerts()} className="underline">
          {t(locale === "hi" ? "hi" : "en", "common.retry")}
        </button>
      </div>
    )
  }

  const current = activeAlerts[0]
  const isCritical = current.severity === "critical" || current.severity === "emergency"

  return (
    <div
      role="alert"
      className={`relative z-30 px-4 py-2.5 text-sm transition-all duration-300 ${
        isCritical
          ? "bg-red-600 text-white shadow-md animate-pulse"
          : "bg-amber-500 text-amber-950 shadow-sm"
      }`}
    >
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-white/20">
            <Icon name="warning" size={14} />
          </span>
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-bold uppercase tracking-wider text-xs px-2 py-0.5 rounded bg-black/20">
              CIVIC ALERT · {current.severity}
            </span>
            <span className="font-semibold">{current.title}</span>
            <span className="hidden md:inline text-xs opacity-90 truncate max-w-md">
              — {current.summary}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <Link
            href={`/${locale}/explore`}
            className="text-xs font-bold underline hover:opacity-80 underline-offset-2"
          >
            Details
          </Link>
          <button
            type="button"
            onClick={() => setDismissed((prev) => ({ ...prev, [current.id]: true }))}
            className="rounded p-1 hover:bg-black/10 transition-colors"
            aria-label="Dismiss alert"
          >
            <Icon name="close" size={14} />
          </button>
        </div>
      </div>
    </div>
  )
}
