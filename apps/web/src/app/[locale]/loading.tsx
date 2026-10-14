import { ListSkeleton } from "@/components/ui/Skeleton"

export default function Loading() {
  return (
    <div className="space-y-4 p-4" aria-busy="true" aria-label="Loading">
      <div className="h-6 w-48 animate-pulse rounded bg-(--color-line)/60" />
      <ListSkeleton count={4} />
    </div>
  )
}
