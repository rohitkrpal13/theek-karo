import Link from "next/link"

import { CommunityHub } from "@/components/community/CommunityHub"
import { t, type Locale } from "@/lib/i18n"

export default async function CommunityPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params
  const lang = locale as Locale

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <CommunityHub />
      <div className="text-center text-xs text-stone-400">
        <Link href={`/${locale}/community/guidelines`} className="underline hover:text-(--color-primary-strong)">
          {t(lang, "community.guidelines.link")}
        </Link>
      </div>
    </div>
  )
}
