"use client"

import { createContext, useCallback, useContext, useMemo, useState } from "react"

type ToastKind = "info" | "success" | "error" | "warning"

interface ToastItem {
  id: string
  kind: ToastKind
  message: string
  detail?: string
}

interface ToastApi {
  push: (kind: ToastKind, message: string, detail?: string) => void
  info: (m: string, d?: string) => void
  success: (m: string, d?: string) => void
  error: (m: string, d?: string) => void
  warning: (m: string, d?: string) => void
}

const Ctx = createContext<ToastApi | null>(null)

export function useToast(): ToastApi {
  const v = useContext(Ctx)
  if (!v) throw new Error("useToast outside ToastProvider")
  return v
}

export function ToastProvider({ children }: { children: React.ReactNode }): React.ReactNode {
  const [items, setItems] = useState<ToastItem[]>([])

  const push = useCallback((kind: ToastKind, message: string, detail?: string) => {
    const id = Math.random().toString(36).slice(2)
    setItems((prev) => [...prev, { id, kind, message, detail }])
    setTimeout(() => setItems((prev) => prev.filter((t) => t.id !== id)), 4500)
  }, [])

  const api = useMemo<ToastApi>(
    () => ({
      push,
      info: (m, d) => push("info", m, d),
      success: (m, d) => push("success", m, d),
      error: (m, d) => push("error", m, d),
      warning: (m, d) => push("warning", m, d),
    }),
    [push],
  )

  return (
    <Ctx.Provider value={api}>
      {children}
      <div
        aria-live="polite"
        aria-atomic
        className="pointer-events-none fixed inset-x-0 bottom-4 z-[100] mx-auto flex max-w-md flex-col gap-2 px-4 md:bottom-6"
      >
        {items.map((t) => (
          <div
            key={t.id}
            role="status"
            className={[
              "pointer-events-auto rounded-(--radius-md) border px-4 py-3 shadow-lg backdrop-blur",
              t.kind === "error"
                ? "border-(--color-error)/30 bg-(--color-error)/10 text-(--color-error)"
                : t.kind === "success"
                  ? "border-(--color-success)/30 bg-(--color-success)/10 text-(--color-success)"
                  : t.kind === "warning"
                    ? "border-(--color-warning)/30 bg-(--color-warning)/10 text-(--color-warning)"
                    : "border-(--color-line) bg-(--color-surface-raised) text-(--color-ink)",
            ].join(" ")}
          >
            <p className="text-sm font-semibold">{t.message}</p>
            {t.detail && <p className="mt-1 text-xs opacity-80">{t.detail}</p>}
          </div>
        ))}
      </div>
    </Ctx.Provider>
  )
}
