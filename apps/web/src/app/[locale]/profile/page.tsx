"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { useParams } from "next/navigation"

import { Avatar, Button, Skeleton } from "@/components/ui/primitives"
import { ReportCard, type ReportCardData } from "@/components/ui/data"
import { useAuth } from "@/lib/auth"
import { reportsApi } from "@/lib/api"
import type { Report } from "@/lib/types"
import { useT } from "@/lib/i18n-client"

type TabType = "all" | "drafts" | "under_verification" | "in_progress" | "resolved"

export default function ProfilePage() {
  const params = useParams<{ locale?: string }>()
  const locale = params.locale ?? "en"
  const t = useT()
  const { user, logout } = useAuth()

  const [activeTab, setActiveTab] = useState<TabType>("all")
  const [myReports, setMyReports] = useState<Report[]>([])
  const [myDrafts, setMyDrafts] = useState<Report[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!user) return

    let cancelled = false
    async function loadUserData() {
      setLoading(true)
      try {
        const [repRes, draftRes] = await Promise.all([
          reportsApi.list({ limit: 40 }),
          reportsApi.listDrafts().catch(() => ({ items: [] })),
        ])
        if (!cancelled) {
          setMyReports(repRes.items)
          setMyDrafts(draftRes.items)
        }
      } catch (err) {
        console.error("Failed to load profile reports", err)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void loadUserData()
    return () => {
      cancelled = true
    }
  }, [user])

  async function handleDeleteDraft(draftId: string) {
    try {
      await reportsApi.deleteDraft(draftId)
      setMyDrafts((prev) => prev.filter((d) => d.id !== draftId))
    } catch (err) {
      console.warn("Failed to delete draft", err)
    }
  }

  if (!user) {
    return (
      <div className="mx-auto max-w-lg rounded-(--radius-xl) border border-(--color-line) bg-(--color-surface) p-8 text-center shadow-xs">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-(--color-surface-sunken) text-(--color-primary-strong)">
          <Avatar name="Guest" size={48} />
        </div>
        <h1 className="mt-4 text-xl font-bold text-(--color-ink)">
          Sign in to view your profile
        </h1>
        <p className="mt-2 text-sm text-(--color-ink-muted)">
          Access your submitted reports, drafts, verification history, and civic contributions.
        </p>
        <div className="mt-6 flex justify-center gap-3">
          <Link href={`/${locale}/auth/login`}>
            <Button variant="primary" size="md">
              {t("auth.login")}
            </Button>
          </Link>
          <Link href={`/${locale}/auth/register`}>
            <Button variant="outline" size="md">
              {t("auth.register")}
            </Button>
          </Link>
        </div>
      </div>
    )
  }

  const filteredReports =
    activeTab === "all"
      ? myReports
      : activeTab === "under_verification"
        ? myReports.filter((r) => r.status === "under_verification" || r.status === "submitted")
        : activeTab === "in_progress"
          ? myReports.filter((r) => r.status === "in_progress" || r.status === "assigned")
          : activeTab === "resolved"
            ? myReports.filter((r) => r.status === "resolved" || r.status === "closed")
            : []

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      {/* Profile Header Card */}
      <section className="flex flex-wrap items-center justify-between gap-4 rounded-(--radius-xl) border border-(--color-line) bg-(--color-surface) p-6 shadow-xs">
        <div className="flex items-center gap-4">
          <Avatar name={user.display_name} size={64} />
          <div>
            <h1 className="text-2xl font-black text-(--color-ink)">
              {user.display_name}
            </h1>
            <p className="text-xs text-(--color-ink-muted)">
              {user.contact_masked ?? "Verified citizen"} · Role:{" "}
              <span className="font-semibold capitalize text-(--color-primary-strong)">
                {user.roles.join(", ") || "citizen"}
              </span>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Link href={`/${locale}/profile/security`}>
            <Button variant="outline" size="sm">
              Security & Sessions
            </Button>
          </Link>
          <Button
            variant="outline"
            size="sm"
            onClick={() => logout()}
          >
            {t("auth.logout")}
          </Button>
        </div>
      </section>

      {/* Contribution Metrics */}
      <section aria-labelledby="contrib-stats" className="space-y-3">
        <h2 id="contrib-stats" className="text-lg font-bold">
          Civic Ledger Overview
        </h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="rounded-(--radius-md) border border-(--color-line) bg-(--color-surface) p-4">
            <span className="text-xs text-(--color-ink-muted)">Submitted Reports</span>
            <p className="mt-1 text-2xl font-black text-(--color-ink)">
              {myReports.length}
            </p>
          </div>
          <div className="rounded-(--radius-md) border border-(--color-line) bg-(--color-surface) p-4">
            <span className="text-xs text-(--color-ink-muted)">Saved Drafts</span>
            <p className="mt-1 text-2xl font-black text-(--color-ink)">
              {myDrafts.length}
            </p>
          </div>
          <div className="rounded-(--radius-md) border border-(--color-line) bg-(--color-surface) p-4">
            <span className="text-xs text-(--color-ink-muted)">Resolved Issues</span>
            <p className="mt-1 text-2xl font-black text-emerald-600 dark:text-emerald-400">
              {myReports.filter((r) => r.status === "resolved").length}
            </p>
          </div>
          <div className="rounded-(--radius-md) border border-(--color-line) bg-(--color-surface) p-4">
            <span className="text-xs text-(--color-ink-muted)">Trust Rating</span>
            <p className="mt-1 text-base font-bold text-(--color-primary-strong)">
              Active Citizen
            </p>
          </div>
        </div>
      </section>

      {/* My Reports & Drafts Section */}
      <section aria-labelledby="my-reports-heading" className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 id="my-reports-heading" className="text-lg font-bold">
            My Civic Issues
          </h2>
          <Link href={`/${locale}/submit`}>
            <Button variant="primary" size="sm" icon="report">
              New Report
            </Button>
          </Link>
        </div>

        {/* Tab Selector */}
        <div className="flex border-b border-(--color-line) text-xs font-semibold">
          {[
            { id: "all", label: `All Reports (${myReports.length})` },
            { id: "drafts", label: `Drafts (${myDrafts.length})` },
            { id: "under_verification", label: "Verification" },
            { id: "in_progress", label: "In Progress" },
            { id: "resolved", label: "Resolved" },
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id as TabType)}
              className={`border-b-2 px-3 py-2 transition-colors ${
                activeTab === tab.id
                  ? "border-(--color-primary) text-(--color-primary-strong) font-bold"
                  : "border-transparent text-(--color-ink-muted) hover:text-(--color-ink)"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <Skeleton height={140} />
            <Skeleton height={140} />
          </div>
        ) : activeTab === "drafts" ? (
          myDrafts.length > 0 ? (
            <div className="grid gap-3 sm:grid-cols-2">
              {myDrafts.map((draft) => (
                <div
                  key={draft.id}
                  className="rounded-(--radius-lg) border border-(--color-line) bg-(--color-surface) p-4 space-y-3 shadow-xs"
                >
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-mono text-(--color-primary-strong)">{draft.ticket_no}</span>
                    <span className="rounded bg-amber-100 px-2 py-0.5 font-bold uppercase text-amber-800 dark:bg-amber-950 dark:text-amber-300">
                      Draft
                    </span>
                  </div>
                  <h3 className="font-bold text-sm text-(--color-ink)">{draft.title || "Untitled Draft"}</h3>
                  <p className="text-xs text-(--color-ink-muted) line-clamp-2">
                    {draft.description || "No description written yet."}
                  </p>
                  <div className="flex items-center justify-between border-t border-(--color-line) pt-2">
                    <Link href={`/${locale}/submit`}>
                      <Button variant="primary" size="sm">
                        Resume in Wizard
                      </Button>
                    </Link>
                    <button
                      type="button"
                      onClick={() => void handleDeleteDraft(draft.id)}
                      className="text-xs text-(--color-danger) hover:underline"
                    >
                      Delete Draft
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-(--radius-lg) border border-dashed border-(--color-line) p-8 text-center">
              <p className="text-sm text-(--color-ink-muted)">
                You have no active drafts in progress.
              </p>
            </div>
          )
        ) : filteredReports.length > 0 ? (
          <div className="grid gap-3 sm:grid-cols-2">
            {filteredReports.map((report) => {
              const cardData: ReportCardData = {
                id: report.id,
                title: report.title,
                location: report.address_hint || "Reported location",
                status: report.status,
                tier: "citizen",
                timeAgo: report.created_at,
              }
              return <ReportCard key={report.id} report={cardData} />
            })}
          </div>
        ) : (
          <div className="rounded-(--radius-lg) border border-dashed border-(--color-line) p-8 text-center">
            <p className="text-sm text-(--color-ink-muted)">
              No reports matching this category filter.
            </p>
          </div>
        )}
      </section>
    </div>
  )
}
