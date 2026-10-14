"use client"

import { useEffect } from "react"

import { Button } from "@/components/ui/primitives"
import { ApiError } from "@/lib/api"

export default function LocaleError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error("[LocaleError]", error)
  }, [error])

  const apiErr = error instanceof ApiError ? error : null

  return (
    <div role="alert" className="mx-auto max-w-lg rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface) p-6 text-center shadow-sm">
      <h2 className="text-base font-bold text-(--color-error)">{apiErr?.body.title ?? "Something went wrong"}</h2>
      <p className="mt-2 text-sm text-(--color-ink-muted)">{apiErr ? apiErr.toUserMessage() : error.message}</p>
      {apiErr?.requestId && <p className="mt-2 font-mono text-xs opacity-60">Ref: {apiErr.requestId}</p>}
      {error.digest && <p className="mt-1 font-mono text-xs opacity-60">Digest: {error.digest}</p>}
      <div className="mt-4 flex justify-center gap-2">
        <Button variant="primary" onClick={() => reset()}>
          Retry
        </Button>
        <Button variant="secondary" onClick={() => window.location.reload()}>
          Reload
        </Button>
      </div>
    </div>
  )
}
