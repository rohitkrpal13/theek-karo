import { CommunityHub } from "@/components/community/CommunityHub"

export default async function InitiativesPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <CommunityHub initialTab="initiatives" />
    </div>
  )
}
