"use client"

import { useEffect } from "react"
import { Button } from "@/components/ui/primitives"

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error("[GlobalError]", error)
  }, [error])

  return (
    <html lang="en">
      <body className="flex min-h-dvh items-center justify-center bg-(--color-page) p-6">
        <div className="max-w-md rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface) p-8 text-center shadow-sm">
          <h2 className="text-lg font-bold text-(--color-error)">Something went wrong</h2>
          <p className="mt-2 text-sm text-(--color-ink-muted)">
            {error.message || "An unexpected error occurred. Please retry."}
          </p>
          {error.digest && <p className="mt-2 font-mono text-xs opacity-60">Ref: {error.digest}</p>}
          <div className="mt-6 flex justify-center gap-3">
            <Button variant="primary" onClick={() => reset()}>
              Try again
            </Button>
            {/* eslint-disable-next-line @next/next/no-location-assign-relative-destination -- global error outside router */}
            <Button variant="ghost" onClick={() => (window.location.href = "/")}>
              Go home
            </Button>
          </div>
        </div>
      </body>
    </html>
  )
}
