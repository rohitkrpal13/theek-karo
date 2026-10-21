export default function RootLoading() {
  return (
    <div className="flex min-h-[50vh] items-center justify-center p-8" aria-busy="true">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-(--color-primary) border-t-transparent" aria-label="Loading" />
    </div>
  )
}
