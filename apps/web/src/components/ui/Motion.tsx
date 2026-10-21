"use client"

/**
 * Lightweight motion primitives (zero-dep, respects prefers-reduced-motion).
 * Use for stagger, fade, slide. No Framer dependency to keep bundle < 150kb.
 */
import { useEffect, useRef, useState, type HTMLAttributes, type ReactNode } from "react"

function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false)
  useEffect(() => {
    const m = window.matchMedia?.("(prefers-reduced-motion: reduce)")
    if (!m) return
    // eslint-disable-next-line react-hooks/set-state-in-effect -- sync external media query
    setReduced(m.matches)
    const onChange = (e: MediaQueryListEvent): void => setReduced(e.matches)
    m.addEventListener("change", onChange)
    return () => m.removeEventListener("change", onChange)
  }, [])
  return reduced
}

export function FadeIn({
  children,
  delay = 0,
  duration = 200,
  className,
  ...rest
}: {
  children: ReactNode
  delay?: number
  duration?: number
  className?: string
} & HTMLAttributes<HTMLDivElement>): ReactNode {
  const reduced = useReducedMotion()
  const [visible, setVisible] = useState(reduced)
  useEffect(() => {
    if (reduced) return
    const id = setTimeout(() => setVisible(true), delay)
    return () => clearTimeout(id)
  }, [reduced, delay])

  if (reduced) return <div className={className} {...rest}>{children}</div>

  return (
    <div
      className={className}
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? "translateY(0)" : "translateY(6px)",
        transition: `opacity ${duration}ms ease, transform ${duration}ms ease`,
        transitionDelay: `${delay}ms`,
      }}
      {...rest}
    >
      {children}
    </div>
  )
}

export function SlideIn({
  children,
  from = "right",
  className,
}: {
  children: ReactNode
  from?: "right" | "left" | "bottom"
  className?: string
}): ReactNode {
  const reduced = useReducedMotion()
  const [inView, setInView] = useState(reduced)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (reduced) return
    const el = ref.current
    if (!el) return
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true)
          io.disconnect()
        }
      },
      { threshold: 0.08 },
    )
    io.observe(el)
    return () => io.disconnect()
  }, [reduced])

  if (reduced) return <div ref={ref} className={className}>{children}</div>

  const transforms: Record<string, string> = {
    right: "translateX(12px)",
    left: "translateX(-12px)",
    bottom: "translateY(12px)",
  }

  return (
    <div
      ref={ref}
      className={className}
      style={{
        opacity: inView ? 1 : 0,
        transform: inView ? "translate(0,0)" : transforms[from],
        transition: "opacity 280ms ease, transform 320ms cubic-bezier(.2,.8,.2,1)",
      }}
    >
      {children}
    </div>
  )
}

export function Stagger({
  children,
  gap = 60,
}: {
  children: ReactNode[]
  gap?: number
}): ReactNode {
  return (
    <>
      {children.map((child, i) => (
        <FadeIn key={i} delay={i * gap}>
          {child}
        </FadeIn>
      ))}
    </>
  )
}

export function PulseDot({ active = true, className = "" }: { active?: boolean; className?: string }): ReactNode {
  return (
    <span className={`relative inline-flex h-2.5 w-2.5 ${className}`} aria-hidden>
      {active && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />}
      <span className={`relative inline-flex h-2.5 w-2.5 rounded-full ${active ? "bg-emerald-500" : "bg-zinc-300"}`} />
    </span>
  )
}
