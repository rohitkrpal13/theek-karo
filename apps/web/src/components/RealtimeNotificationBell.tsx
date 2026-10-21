"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { useParams } from "next/navigation"
import { Icon } from "@/components/ui/icons"
import { api } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { useRealtimeEvents } from "@/hooks/useRealtimeEvents"

export function RealtimeNotificationBell() {
  const params = useParams<{ locale?: string }>()
  const locale = params.locale ?? "en"
  const { user } = useAuth()

  const [unreadCount, setUnreadCount] = useState<number>(0)

  // Fetch unread count if authenticated
  useEffect(() => {
    if (!user) return
    api
      .get<Record<string, number>>("/notifications/unread-count")
      .then((res) => {
        setUnreadCount(res.unread ?? 0)
      })
      .catch(() => undefined)
  }, [user])

  // Increment badge on incoming real-time civic events
  useRealtimeEvents({
    enabled: !!user,
    onEvent: (event) => {
      if (
        event === "report.created" ||
        event === "report.updated" ||
        event === "case.assigned" ||
        event === "case.transitioned" ||
        event === "alert.issued"
      ) {
        setUnreadCount((c) => c + 1)
      }
    },
  })

  return (
    <Link
      href={`/${locale}/notifications`}
      className="relative flex h-8 w-8 items-center justify-center rounded-(--radius-md) border border-(--color-line) text-(--color-ink-muted) hover:text-(--color-ink) transition-colors"
      aria-label={`Notifications (${unreadCount} unread)`}
    >
      <Icon name="bell" size={16} />
      {unreadCount > 0 && (
        <span className="absolute -top-1 -right-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-bold text-white shadow-xs animate-pulse">
          {unreadCount > 99 ? "99+" : unreadCount}
        </span>
      )}
    </Link>
  )
}
