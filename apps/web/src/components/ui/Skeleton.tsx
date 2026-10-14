"use client"

export function Skeleton({ className }: { className?: string }): React.ReactNode {
  return (
    <div
      aria-hidden
      className={["animate-pulse rounded-md bg-(--color-line)/60", className ?? "h-4 w-full"].join(" ")}
    />
  )
}

export function CardSkeleton(): React.ReactNode {
  return (
    <div className="rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface) p-4">
      <Skeleton className="h-5 w-3/4" />
      <Skeleton className="mt-3 h-3 w-full" />
      <Skeleton className="mt-2 h-3 w-5/6" />
      <div className="mt-4 flex gap-2">
        <Skeleton className="h-6 w-16 rounded-full" />
        <Skeleton className="h-6 w-20 rounded-full" />
      </div>
    </div>
  )
}

export function ListSkeleton({ count = 3 }: { count?: number }): React.ReactNode {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }).map((_, i) => (
        <CardSkeleton key={i} />
      ))}
    </div>
  )
}
