"use client"

import { useOnline } from "@/lib/offline"

export function OfflineBanner(): React.ReactNode {
  const online = useOnline()
  if (online) return null
  return (
    <div
      role="status"
      aria-live="polite"
      className="sticky top-0 z-50 w-full bg-amber-500 px-4 py-2 text-center text-sm font-medium text-white"
    >
      You&apos;re offline — reports will be queued and sent when you reconnect.
    </div>
  )
}
