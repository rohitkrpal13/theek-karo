"use client"

import Link from "next/link"
import { useEffect, useState } from "react"

import { civicApi } from "@/lib/api"
import type { Campaign } from "@/lib/types"
import { Badge, EmptyState, Skeleton } from "@/components/ui/primitives"
import { FormattedDate } from "@/components/FormattedDate"

function campaignLabel(campaign: Campaign): string {
  const fallback = campaign.slug
    .replace(/-(\d{3,5})$/g, "")
    .replace(/-/g, " ")
    .replace(/^\w/, (c) => c.toUpperCase())
  return fallback
}

const STATUS_TONE: Record<Campaign["status"], string> = {
  planned: "default",
  live: "success",
  paused: "warning",
  closed: "error",
}

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[] | null>(null)

  useEffect(() => {
    void civicApi
      .listCampaigns()
      .then((body) => setCampaigns(body.items))
      .catch(() => setCampaigns([]))
  }, [])

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Campaigns</h1>
      <p className="text-sm text-(--color-ink-muted)">
        Civic campaigns gather attention around a class of issues. Join one to follow its reports and progress.
      </p>

      {campaigns === null ? (
        <div className="grid gap-3 sm:grid-cols-2">
          <Skeleton height={120} />
          <Skeleton height={120} />
        </div>
      ) : campaigns.length === 0 ? (
        <EmptyState icon="activity" title="No active campaigns in this geography">
          Civic campaigns gather attention around a class of issues. The first one can be started by administrators.
        </EmptyState>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {campaigns.map((campaign) => (
            <article
              key={campaign.id}
              className="rounded-lg border border-stone-200 bg-white p-4 shadow-sm transition hover:border-(--color-primary)"
            >
              <div className="flex items-start justify-between gap-3">
                <h2 className="text-base font-semibold text-ink">{campaignLabel(campaign)}</h2>
                <Badge tone={STATUS_TONE[campaign.status]}>{campaign.status}</Badge>
              </div>
              {campaign.scope && (
                <p className="mt-1 text-sm text-(--color-ink-muted)">
                  {[campaign.scope.state, campaign.scope.district].filter(Boolean).join(" · ")}
                </p>
              )}
              <p className="mt-2 text-xs text-(--color-ink-muted)">
                {campaign.created_at ? (
                  <>
                    Started <FormattedDate iso={campaign.created_at} />
                  </>
                ) : null}
              </p>
              <Link
                href={`/reports?campaign_id=${campaign.id}`}
                className="mt-3 inline-block text-sm font-medium text-(--color-primary) hover:underline"
              >
                View reports →
              </Link>
            </article>
          ))}
        </div>
      )}
    </div>
  )
}