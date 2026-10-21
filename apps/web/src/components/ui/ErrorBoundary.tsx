"use client"

import React from "react"

import { Button } from "@/components/ui/primitives"
import { ApiError } from "@/lib/api"

interface Props {
  children: React.ReactNode
  fallback?: React.ReactNode
  onReset?: () => void
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends React.Component<Props, State> {
  state: State = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    // structured log without leaking PII
    console.error("[ErrorBoundary]", error, info.componentStack?.slice(0, 500))
  }

  reset = (): void => {
    this.setState({ hasError: false, error: null })
    this.props.onReset?.()
  }

  render(): React.ReactNode {
    if (!this.state.hasError) return this.props.children
    if (this.props.fallback) return this.props.fallback

    const err = this.state.error
    const apiErr = err instanceof ApiError ? err : null
    const title = apiErr ? apiErr.body.title ?? "Something went wrong" : "Something went wrong"
    const detail = apiErr ? apiErr.toUserMessage() : err?.message ?? "Unexpected error"

    return (
      <div
        role="alert"
        className="rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface) p-6 text-center shadow-sm"
      >
        <h2 className="text-lg font-bold text-(--color-error)">{title}</h2>
        <p className="mx-auto mt-2 max-w-prose text-sm text-(--color-ink-muted)">{detail}</p>
        {apiErr?.requestId && (
          <p className="mt-2 font-mono text-xs text-(--color-ink-muted)">Ref: {apiErr.requestId}</p>
        )}
        <div className="mt-4 flex justify-center gap-2">
          <Button variant="primary" onClick={this.reset}>
            Try again
          </Button>
          {/* eslint-disable-next-line @next/next/no-location-assign-relative-destination -- global error fallback outside Next router */}
          <Button variant="secondary" onClick={() => (window.location.href = "/")}>
            Go home
          </Button>
        </div>
      </div>
    )
  }
}

export function InlineError({
  error,
  onRetry,
  className,
}: {
  error: unknown
  onRetry?: () => void
  className?: string
}): React.ReactNode {
  const apiErr = error instanceof ApiError ? error : null
  const message = apiErr ? apiErr.toUserMessage() : error instanceof Error ? error.message : String(error)
  return (
    <div
      role="alert"
      className={["rounded-md border border-(--color-error)/30 bg-(--color-error)/5 p-3 text-sm", className].join(" ")}
    >
      <p className="font-medium text-(--color-error)">{apiErr?.body.title ?? "Error"}</p>
      <p className="mt-1 text-(--color-ink-muted)">{message}</p>
      {apiErr?.requestId && <p className="mt-1 font-mono text-xs opacity-70">Ref {apiErr.requestId}</p>}
      {onRetry && (
        <Button size="sm" variant="ghost" onClick={onRetry} className="mt-2">
          Retry
        </Button>
      )}
    </div>
  )
}
