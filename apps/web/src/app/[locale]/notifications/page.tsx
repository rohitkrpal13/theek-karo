"use client"

import { useEffect, useState } from "react"

import { api } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { Button, EmptyState, Skeleton } from "@/components/ui/primitives"
import { NotificationItem } from "@/components/ui/data"
import type { IconName } from "@/components/ui/icons"

export interface NotificationEntry {
  id: string
  event: string
  channel: string
  subject: string | null
  body: string | null
  payload: Record<string, unknown> | null
  read: boolean
  created_at: string
  count: number
  group_key?: string
}

const EVENT_ICONS: Record<string, IconName> = {
  comment_new: "activity",
  verification_added: "check",
  verification_rejected: "warning",
  status_changed: "clock",
  sla_warning: "warning",
  sla_breach: "warning",
  resolution_submitted: "check",
  mention: "bell",
  campaign_update: "activity",
}

function eventIcon(event: string): IconName {
  return EVENT_ICONS[event] ?? "bell"
}

export default function NotificationsPage() {
  const { user, loading: authLoading } = useAuth()
  const [items, setItems] = useState<NotificationEntry[] | null>(null)
  const [unread, setUnread] = useState(0)
  const [marking, setMarking] = useState(false)

  useEffect(() => {
    if (authLoading || !user) return
    void Promise.all([
      api.get<{ items: NotificationEntry[] }>("/notifications"),
      api.get<Record<string, number>>("/notifications/unread-count"),
    ])
      .then(([list, count]) => {
        setItems(list.items)
        setUnread(count.unread ?? 0)
      })
      .catch(() => setItems([]))
  }, [authLoading, user])

  async function markAllRead() {
    setMarking(true)
    try {
      await api.post("/notifications/mark-read", { all: true })
      void Promise.all([
        api.get<{ items: NotificationEntry[] }>("/notifications"),
        api.get<Record<string, number>>("/notifications/unread-count"),
      ])
        .then(([list, count]) => {
          setItems(list.items)
          setUnread(count.unread ?? 0)
        })
        .catch(() => setItems([]))
    } finally {
      setMarking(false)
    }
  }

  if (authLoading) {
    return (
      <div className="space-y-3">
        <Skeleton height={80} />
        <Skeleton height={80} />
      </div>
    )
  }

  if (!user) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold">Notifications</h1>
        <EmptyState icon="bell" title="Sign in to see your notifications">
          Follow reports, institutions, or locations to get notified about progress.
        </EmptyState>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">
          Notifications
          {unread > 0 && (
            <span className="ml-2 rounded-full bg-(--color-primary) px-2 py-0.5 text-(--text-caption) font-medium text-white">
              {unread} unread
            </span>
          )}
        </h1>
        {unread > 0 && (
          <Button variant="outline" size="sm" onClick={markAllRead} disabled={marking}>
            {marking ? "Marking..." : "Mark all as read"}
          </Button>
        )}
      </div>

      {items === null ? (
        <div className="space-y-3">
          <Skeleton height={80} />
          <Skeleton height={80} />
        </div>
      ) : items.length === 0 ? (
        <EmptyState icon="bell" title="No notifications yet">
          Follow reports, institutions, or locations to get notified about progress.
        </EmptyState>
      ) : (
        <ul className="divide-y divide-(--color-line) overflow-hidden rounded-lg border border-(--color-line) bg-white">
          {items.map((entry) => (
            <li key={entry.id}>
              <NotificationItem
                icon={eventIcon(entry.event)}
                title={
                  entry.subject ??
                  entry.event.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase())
                }
                body={
                  entry.count > 1
                    ? `${entry.body ?? entry.event} (${entry.count})`
                    : (entry.body ?? undefined)
                }
                when={new Date(entry.created_at).toLocaleDateString()}
                unread={!entry.read}
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}