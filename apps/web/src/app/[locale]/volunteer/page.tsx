import { CommunityHub } from "@/components/community/CommunityHub"

export default async function VolunteerPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <CommunityHub initialTab="volunteer" />
    </div>
  )
}
