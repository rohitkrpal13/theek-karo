"use client"

/* Theek Karo UI primitives (Phase 4) — semantic, accessible building blocks. */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type RefObject,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react"

import { Icon, type IconName } from "@/components/ui/icons"

/* ---------------------------------- Button -------------------------------- */

type Variant = "primary" | "secondary" | "ghost" | "danger" | "outline"
type Size = "sm" | "md" | "lg"

export function buttonClass(variant: Variant = "primary", size: Size = "md") {
  const base =
    "inline-flex items-center justify-center gap-2 font-semibold rounded-(--radius-md) " +
    "transition-colors focus-visible:outline-3 focus-visible:outline-(--color-focusring) " +
    "disabled:opacity-50 disabled:pointer-events-none"
  const sizes = { sm: "px-2.5 py-1.5 text-(--text-button)", md: "px-4 py-2 text-sm", lg: "px-5 py-3 text-base" }
  const variants: Record<Variant, string> = {
    primary: "bg-(--color-primary) text-white hover:bg-(--color-primary-strong)",
    secondary: "bg-(--color-primary-soft) text-(--color-primary-strong) hover:opacity-90",
    ghost: "bg-transparent text-(--color-ink) hover:bg-(--color-line)",
    danger: "bg-(--color-error) text-white hover:opacity-90",
    outline: "border border-(--color-line) bg-(--color-surface) text-(--color-ink) hover:border-(--color-primary)",
  }
  return `${base} ${sizes[size]} ${variants[variant]}`
}

export function Button({
  variant = "primary",
  size = "md",
  icon,
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size; icon?: IconName }) {
  return (
    <button className={buttonClass(variant, size)} {...rest}>
      {icon ? <Icon name={icon} size={size === "sm" ? 16 : 18} /> : null}
      {children}
    </button>
  )
}

/* ---------------------------------- Field -------------------------------- */

const fieldClass =
  "w-full rounded-(--radius-md) border border-(--color-line) bg-(--color-surface) " +
  "px-3 py-2 text-(--text-body) text-(--color-ink) placeholder:text-(--color-ink-muted) " +
  "focus:border-(--color-primary) focus:outline-2 focus:outline-(--color-primary-soft)"

export function Label({ children, htmlFor }: { children: ReactNode; htmlFor?: string }) {
  return (
    <label htmlFor={htmlFor} className="mb-1 block text-(--text-label) font-medium text-(--color-ink-muted)">
      {children}
    </label>
  )
}

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={fieldClass} {...props} />
}

export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={`${fieldClass} min-h-24`} {...props} />
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={fieldClass} {...props} />
}

/* ------------------------------ Combobox (search input w/ list) ----------- */

export function Combobox({
  options,
  onSelect,
  placeholder,
  label,
}: {
  options: Array<{ value: string; label: string }>
  onSelect: (value: string) => void
  placeholder?: string
  label: string
}) {
  const [query, setQuery] = useState("")
  const [open, setOpen] = useState(false)
  const id = useId()
  const filtered = query ? options.filter((o) => o.label.toLowerCase().includes(query.toLowerCase())) : options.slice(0, 6)

  return (
    <div>
      <Label htmlFor={id}>{label}</Label>
      <input
        id={id}
        role="combobox"
        aria-expanded={open}
        aria-controls={`${id}-list`}
        aria-autocomplete="list"
        className={fieldClass}
        placeholder={placeholder}
        value={query}
        onChange={(e) => {
          setQuery(e.target.value)
          setOpen(true)
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
      />
      {open && filtered.length > 0 && (
        <ul id={`${id}-list`} role="listbox" className="mt-1 overflow-hidden rounded-(--radius-md) border border-(--color-line) bg-(--color-surface-raised) shadow-(--elevation-md)">
          {filtered.map((option) => (
            <li key={option.value}>
              <button
                type="button"
                role="option"
                aria-selected={false}
                className="block w-full px-3 py-2 text-left text-sm hover:bg-(--color-primary-soft)"
                onMouseDown={() => {
                  onSelect(option.value)
                  setQuery("")
                  setOpen(false)
                }}
              >
                {option.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

/* ------------------------------ Toggles/checks ---------------------------- */

export function Checkbox({
  label,
  checked,
  onChange,
}: {
  label: string
  checked: boolean
  onChange: (next: boolean) => void
}) {
  return (
    <label className="flex items-start gap-2 text-sm">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-0.5 h-4 w-4 accent-(--color-primary)"
      />
      <span>{label}</span>
    </label>
  )
}

export function RadioGroup({
  name,
  options,
  value,
  onChange,
}: {
  name: string
  options: Array<{ value: string; label: string }>
  value: string
  onChange: (next: string) => void
}) {
  return (
    <fieldset className="space-y-1" role="radiogroup">
      {options.map((option) => (
        <label key={option.value} className="flex items-center gap-2 text-sm">
          <input type="radio" name={name} value={option.value} checked={value === option.value} onChange={() => onChange(option.value)} />
          {option.label}
        </label>
      ))}
    </fieldset>
  )
}

export function Switch({
  label,
  checked,
  onChange,
}: {
  label: string
  checked: boolean
  onChange: (next: boolean) => void
}) {
  return (
    <label className="flex items-center gap-2 text-sm">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        onClick={() => onChange(!checked)}
        className={`relative h-6 w-11 rounded-full transition-colors ${checked ? "bg-(--color-primary)" : "bg-(--color-line)"}`}
      >
        <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform ${checked ? "translate-x-5" : "translate-x-0.5"}`} />
      </button>
      {label}
    </label>
  )
}

/* --------------------------------- Badges -------------------------------- */

export function Badge({ children, tone = "default", className = "" }: { children: ReactNode; tone?: string; className?: string }) {
  const tones: Record<string, string> = {
    default: "bg-(--color-line) text-(--color-ink)",
    success: "bg-(--color-primary-soft) text-(--color-primary-strong)",
    warning: "bg-(--color-secondary-soft) text-(--color-secondary)",
    error: "bg-(--color-error) text-white",
    info: "bg-(--color-info) text-white",
  }
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-(--text-caption) font-medium ${tones[tone] || tones.default} ${className}`}>
      {children}
    </span>
  )
}

export function Avatar({ name, size = 40 }: { name: string; size?: number }) {
  const initials = name
    .split(" ")
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase()
  return (
    <span
      aria-hidden="true"
      className="inline-flex items-center justify-center rounded-full bg-(--color-primary-soft) font-semibold text-(--color-primary-strong)"
      style={{ width: size, height: size, fontSize: size / 2.6 }}
    >
      {initials || "?"}
    </span>
  )
}

/* ------------------------------- Feedback -------------------------------- */

export function Skeleton({ width = "100%", height = 16 }: { width?: number | string; height?: number }) {
  return <span aria-hidden="true" className="block animate-pulse rounded-(--radius-sm) bg-(--color-line)" style={{ width, height }} />
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <span role="status" className="inline-flex items-center gap-2 text-sm text-(--color-ink-muted)">
      <span aria-hidden="true" className="h-4 w-4 animate-spin rounded-full border-2 border-(--color-line) border-t-(--color-primary)" />
      {label}
    </span>
  )
}

export function EmptyState({
  icon = "info",
  title,
  children,
  action,
}: {
  icon?: IconName
  title: string
  children?: ReactNode
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-(--radius-lg) border border-dashed border-(--color-line) p-8 text-center">
      <Icon name={icon} size={28} className="text-(--color-ink-muted)" />
      <p className="font-semibold">{title}</p>
      {children ? <p className="max-w-md text-sm text-(--color-ink-muted)">{children}</p> : null}
      {action}
    </div>
  )
}

export function ErrorState({ title, detail, onRetry }: { title: string; detail?: string; onRetry?: () => void }) {
  return (
    <EmptyState icon="warning" title={title} action={onRetry ? <Button variant="outline" size="sm" onClick={onRetry}>Retry</Button> : undefined}>
      {detail}
    </EmptyState>
  )
}

/* --------------------------------- Tabs ---------------------------------- */

export function Tabs({
  tabs,
  active,
  onChange,
}: {
  tabs: Array<{ id: string; label: string; icon?: IconName }>
  active: string
  onChange: (id: string) => void
}) {
  return (
    <div role="tablist" className="flex gap-1 overflow-x-auto border-b border-(--color-line)">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          role="tab"
          aria-selected={active === tab.id}
          onClick={() => onChange(tab.id)}
          className={`flex shrink-0 items-center gap-1.5 border-b-2 px-3 py-2 text-sm font-medium ${
            active === tab.id ? "border-(--color-primary) text-(--color-primary-strong)" : "border-transparent text-(--color-ink-muted) hover:text-(--color-ink)"
          }`}
        >
          {tab.icon ? <Icon name={tab.icon} size={16} /> : null}
          {tab.label}
        </button>
      ))}
    </div>
  )
}

/* ------------------------------ Toast system ------------------------------ */

type ToastKind = "success" | "error" | "info"
interface ToastMessage {
  id: number
  kind: ToastKind
  text: string
}

const ToastContext = createContext<{ toast: (kind: ToastKind, text: string) => void }>({
  toast: () => undefined,
})

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastMessage[]>([])
  const nextId = useRef(1)

  const toast = useCallback((kind: ToastKind, text: string) => {
    const id = nextId.current++
    setToasts((prev) => [...prev, { id, kind, text }])
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 4000)
  }, [])

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div aria-live="polite" className="fixed bottom-20 left-1/2 z-50 flex w-[calc(100%-2rem)] max-w-sm -translate-x-1/2 flex-col gap-2">
        {toasts.map((message) => (
          <div
            key={message.id}
            className={`flex items-center gap-2 rounded-(--radius-md) px-4 py-3 text-sm text-white shadow-(--elevation-lg) ${
              message.kind === "success" ? "bg-(--color-success)" : message.kind === "error" ? "bg-(--color-error)" : "bg-(--color-info)"
            }`}
          >
            <Icon name={message.kind === "success" ? "check" : message.kind === "error" ? "warning" : "info"} size={18} />
            {message.text}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  return useContext(ToastContext)
}

/* ------------------------------ Modal / Drawer ---------------------------- */

function useEscape(open: boolean, onClose: () => void) {
  useEffect(() => {
    if (!open) return
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose()
    }
    document.addEventListener("keydown", handler)
    document.body.style.overflow = "hidden"
    return () => {
      document.removeEventListener("keydown", handler)
      document.body.style.overflow = ""
    }
  }, [open, onClose])
}

function useFocusTrap(open: boolean, panelRef: RefObject<HTMLElement | null>) {
  const restoreRef = useRef<HTMLElement | null>(null)
  useEffect(() => {
    if (!open) return
    restoreRef.current = document.activeElement as HTMLElement | null
    const panel = panelRef.current
    if (!panel) return
    const focusables = () =>
      Array.from(
        panel.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])',
        ),
      ).filter((el) => el.offsetParent !== null)
    const first = focusables()[0]
    if (first) first.focus()
    const handler = (event: KeyboardEvent) => {
      if (event.key !== "Tab") return
      const items = focusables()
      if (items.length === 0) return
      const firstEl = items[0]
      const lastEl = items[items.length - 1]
      if (event.shiftKey && document.activeElement === firstEl) {
        event.preventDefault()
        lastEl.focus()
      } else if (!event.shiftKey && document.activeElement === lastEl) {
        event.preventDefault()
        firstEl.focus()
      }
    }
    document.addEventListener("keydown", handler)
    return () => {
      document.removeEventListener("keydown", handler)
      restoreRef.current?.focus()
      restoreRef.current = null
    }
  }, [open, panelRef])
}

export function Modal({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  useEscape(open, onClose)
  const panelRef = useRef<HTMLDivElement>(null)
  useFocusTrap(open, panelRef)
  if (!open) return null
  return (
    <div role="dialog" aria-modal="true" aria-labelledby="modal-title" className="fixed inset-0 z-40 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-(--color-scrim)" onClick={onClose} />
      <div ref={panelRef} className="relative w-full max-w-lg rounded-(--radius-xl) bg-(--color-surface-raised) p-5 shadow-(--elevation-overlay)">
        <div className="mb-3 flex items-center justify-between">
          <h2 id="modal-title" className="text-lg font-bold">{title}</h2>
          <Button variant="ghost" size="sm" aria-label="Close" onClick={onClose} icon="close" />
        </div>
        {children}
      </div>
    </div>
  )
}

export function Drawer({ open, onClose, children }: { open: boolean; onClose: () => void; children: ReactNode }) {
  useEscape(open, onClose)
  const panelRef = useRef<HTMLDivElement>(null)
  useFocusTrap(open, panelRef)
  return (
    <div aria-hidden={!open} className={`fixed inset-0 z-40 ${open ? "" : "pointer-events-none"}`}>
      <div className={`absolute inset-0 bg-(--color-scrim) transition-opacity ${open ? "opacity-100" : "opacity-0"}`} onClick={onClose} />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label="Menu"
        className={`absolute inset-y-0 right-0 w-full max-w-sm overflow-y-auto bg-(--color-surface-raised) p-4 shadow-(--elevation-overlay) transition-transform ${open ? "translate-x-0" : "translate-x-full"}`}
      >
        {children}
      </div>
    </div>
  )
}

/* ------------------------------ Misc primitives --------------------------- */

export function Breadcrumbs({ items }: { items: Array<{ label: string; href?: string }> }) {
  return (
    <nav aria-label="Breadcrumb">
      <ol className="flex flex-wrap items-center gap-1 text-sm text-(--color-ink-muted)">
        {items.map((item, index) => (
          <li key={index} className="flex items-center gap-1">
            {index > 0 ? <Icon name="chevron" size={14} /> : null}
            {item.href ? (
              <a href={item.href} className="hover:text-(--color-primary-strong) hover:underline">{item.label}</a>
            ) : (
              <span aria-current="page" className="font-medium text-(--color-ink)">{item.label}</span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  )
}

export function Pagination({ page, totalPages, onChange }: { page: number; totalPages: number; onChange: (page: number) => void }) {
  return (
    <nav aria-label="Pagination" className="flex items-center justify-center gap-3">
      <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => onChange(page - 1)}>Previous</Button>
      <span className="text-sm text-(--color-ink-muted)">
        Page <strong className="text-(--color-ink)">{page}</strong> of {totalPages}
      </span>
      <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => onChange(page + 1)}>Next</Button>
    </nav>
  )
}

export function Tooltip({ label, children }: { label: string; children: ReactNode }) {
  const id = useId()
  return (
    <span className="group relative inline-flex">
      <span tabIndex={0} aria-describedby={id}>{children}</span>
      <span role="tooltip" id={id} className="pointer-events-none absolute bottom-full left-1/2 mb-1 -translate-x-1/2 whitespace-nowrap rounded-(--radius-sm) bg-(--color-ink) px-2 py-1 text-(--text-caption) text-(--color-page) opacity-0 transition-opacity group-focus-within:opacity-100 group-hover:opacity-100">
        {label}
      </span>
    </span>
  )
}

export function SkipLink() {
  return <a href="#main" className="skip-link">Skip to content</a>
}