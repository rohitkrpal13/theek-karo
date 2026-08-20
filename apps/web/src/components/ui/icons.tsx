"use client"

/** Minimal dependency-free SVG icon set (no emoji as UI signals). */
import type { ReactNode, SVGProps } from "react"

export type IconName =
  | "home" | "explore" | "map" | "report" | "activity" | "bell" | "user"
  | "search" | "chevron" | "check" | "clock" | "close" | "warning" | "info"
  | "kebab" | "pin" | "camera" | "refresh" | "lock" | "building" | "trash"
  | "edit" | "shield" | "database"

const paths: Record<IconName, ReactNode> = {
  home: <path d="M4 11l8-7 8 7v8a1 1 0 0 1-1 1h-4v-5h-6v5H5a1 1 0 0 1-1-1z" />,
  explore: (
    <>
      <circle cx="12" cy="12" r="8" />
      <path d="M12 8l2.5 3.5L12 16 9.5 11.5z" />
    </>
  ),
  map: <path d="M9 4L3 6v14l6-2 6 2 6-2V4l-6 2zM9 4v14M15 6v14" />,
  report: <path d="M7 3h7l5 5v13H7zM14 3v5h5M10 12h5M10 16h5" />,
  activity: <path d="M3 12h4l2-7 4 14 2-7h6" />,
  bell: <path d="M6 17h12M8 17a4 4 0 0 1 8 0M12 4a3 3 0 0 1 3 3v3M9 7a3 3 0 0 1 3-3" />,
  user: (
    <>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 20c1.5-3.5 4.5-5 8-5s6.5 1.5 8 5" />
    </>
  ),
  search: (
    <>
      <circle cx="11" cy="11" r="6" />
      <path d="M16 16l5 5" />
    </>
  ),
  chevron: <path d="M9 6l6 6-6 6" />,
  check: <path d="M5 12l5 5 9-10" />,
  clock: (
    <>
      <circle cx="12" cy="12" r="8" />
      <path d="M12 8v4l3 2" />
    </>
  ),
  close: <path d="M6 6l12 12M18 6L6 18" />,
  warning: (
    <>
      <path d="M12 4 3 20h18z" />
      <path d="M12 10v4M12 17v.5" />
    </>
  ),
  info: (
    <>
      <circle cx="12" cy="12" r="8" />
      <path d="M12 11v5M12 8v.5" />
    </>
  ),
  kebab: (
    <>
      <circle cx="12" cy="6" r="1" />
      <circle cx="12" cy="12" r="1" />
      <circle cx="12" cy="18" r="1" />
    </>
  ),
  pin: (
    <>
      <path d="M12 21s-6-5.2-6-10a6 6 0 0 1 12 0c0 4.8-6 10-6 10z" />
      <circle cx="12" cy="11" r="2" />
    </>
  ),
  camera: (
    <>
      <path d="M4 8h3l2-3h6l2 3h3a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z" />
      <circle cx="12" cy="13" r="3" />
    </>
  ),
  refresh: <path d="M20 12a8 8 0 1 1-2.4-5.7M20 4v4h-4" />,
  lock: (
    <>
      <rect x="5" y="10" width="14" height="10" rx="2" />
      <path d="M8 10V7a4 4 0 0 1 8 0v3" />
    </>
  ),
  building: (
    <>
      <path d="M3 21h18M5 21V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16M9 9h1M9 13h1M9 17h1M14 9h1M14 13h1M14 17h1" />
    </>
  ),
  trash: (
    <>
      <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6M10 11v6M14 11v6" />
    </>
  ),
  edit: <path d="M4 20h4l10-10-4-4L4 16zM13.5 6.5l4 4" />,
  shield: (
    <>
      <path d="M12 3l7 3v5c0 4.6-3 8.1-7 10-4-1.9-7-5.4-7-10V6z" />
      <path d="M9 12l2 2 4-4" />
    </>
  ),
  database: (
    <>
      <ellipse cx="12" cy="5.5" rx="7" ry="3" />
      <path d="M5 5.5v7c0 1.7 3.1 3 7 3s7-1.3 7-3v-7" />
      <path d="M5 12.5v7c0 1.7 3.1 3 7 3s7-1.3 7-3v-7" />
    </>
  ),
}

export function Icon({
  name,
  size = 20,
  ...rest
}: { name: IconName; size?: number } & SVGProps<SVGSVGElement>) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...rest}
    >
      {paths[name]}
    </svg>
  )
}