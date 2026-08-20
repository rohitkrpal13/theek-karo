import { CommunityHub } from "@/components/community/CommunityHub"

export default async function GroupsPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <CommunityHub initialTab="groups" />
    </div>
  )
}
