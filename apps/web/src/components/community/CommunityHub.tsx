"use client"

import { useCallback, useEffect, useState } from "react"

import {
  Button,
  EmptyState,
  ErrorState,
  Input,
  Label,
  Modal,
  Skeleton,
  Spinner,
  Tabs,
  Textarea,
  useToast,
} from "@/components/ui/primitives"
import { communityApi } from "@/lib/api"
import type {
  Badge,
  CommunityGroup,
  Initiative,
  VolunteerOpportunity,
  VolunteerProfile,
} from "@/lib/api/community"
import { useAuth } from "@/lib/auth"
import { useT } from "@/lib/i18n-client"
import { en, type TFunction } from "@/lib/i18n"

const STATUS_LABELS: Record<string, string> = {
  draft: "community.initiative.status.draft",
  submitted: "community.initiative.status.submitted",
  review: "community.initiative.status.review",
  approved: "community.initiative.status.approved",
  active: "community.initiative.status.active",
  completed: "community.initiative.status.completed",
  archived: "community.initiative.status.archived",
  rejected: "community.initiative.status.rejected",
}

function statusLabel(t: TFunction, status: string): string {
  const key = STATUS_LABELS[status]
  return key ? t(key as keyof typeof en) : status
}

function InitiativeCard({
  initiative,
  onChanged,
}: {
  initiative: Initiative
  onChanged: () => void
}) {
  const t = useT()
  const [busy, setBusy] = useState(false)

  async function act(action: "join" | "leave" | "follow" | "unfollow") {
    setBusy(true)
    try {
      if (action === "join") await communityApi.joinInitiative(initiative.id)
      else if (action === "leave") await communityApi.leaveInitiative(initiative.id)
      else if (action === "follow") await communityApi.followInitiative(initiative.id)
      else await communityApi.unfollowInitiative(initiative.id)
      onChanged()
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="rounded-lg border border-stone-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-ink">{initiative.title}</h3>
          <p className="text-xs text-stone-500">
            {t("community.initiative.by")}{" "}
            {initiative.initiator?.display_name ?? "—"} ·{" "}
            {statusLabel(t, initiative.status)}
          </p>
        </div>
        {initiative.status === "active" && (
          <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
            {statusLabel(t, initiative.status)}
          </span>
        )}
      </div>
      <p className="mt-2 line-clamp-2 text-sm text-stone-600">{initiative.description}</p>
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-stone-500">
        <span>
          {initiative.participant_count} {t("community.initiative.participants")}
        </span>
        <span>
          {initiative.observation_count} {t("community.initiative.observations")}
        </span>
        <span>
          {initiative.accepted_evidence_count} {t("community.initiative.evidence")}
        </span>
      </div>
      <div className="mt-3 flex gap-2">
        {initiative.is_member ? (
          <Button size="sm" variant="secondary" disabled={busy} onClick={() => act("leave")}>
            {t("community.initiative.leave")}
          </Button>
        ) : (
          <Button size="sm" disabled={busy} onClick={() => act("join")}>
            {t("community.initiative.join")}
          </Button>
        )}
        <Button
          size="sm"
          variant="secondary"
          disabled={busy}
          onClick={() => act(initiative.is_following ? "unfollow" : "follow")}
        >
          {t(initiative.is_following ? "community.initiative.unfollow" : "community.initiative.follow")}
        </Button>
      </div>
    </div>
  )
}

function InitiativesTab() {
  const t = useT()
  const { user } = useAuth()
  const [items, setItems] = useState<Initiative[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [title, setTitle] = useState("")
  const [description, setDescription] = useState("")
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    try {
      const res = await communityApi.listInitiatives({ limit: 50 })
      setItems(res.items)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }, [])

  useEffect(() => {
    // deferred so the fetch does not synchronously setState in the effect
    const timer = window.setTimeout(() => void load(), 0)
    return () => window.clearTimeout(timer)
  }, [load])

  async function createInitiative() {
    setSaving(true)
    try {
      await communityApi.createInitiative({ title, description })
      setCreating(false)
      setTitle("")
      setDescription("")
      await load()
    } finally {
      setSaving(false)
    }
  }

  if (error) return <ErrorState title={t("community.initiative.title")} detail={error} onRetry={load} />
  if (!items)
    return (
      <div className="space-y-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} height={96} />
        ))}
      </div>
    )

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-stone-500">{t("community.initiative.subtitle")}</p>
        {user && (
          <Button size="sm" onClick={() => setCreating(true)}>
            {t("community.initiative.create")}
          </Button>
        )}
      </div>
      {items.length === 0 ? (
        <EmptyState icon="user" title={t("community.initiative.title")}>
          {t("community.initiative.empty")}
        </EmptyState>
      ) : (
        <div className="space-y-3">
          {items.map((initiative) => (
            <InitiativeCard key={initiative.id} initiative={initiative} onChanged={load} />
          ))}
        </div>
      )}
      <Modal open={creating} onClose={() => setCreating(false)} title={t("community.initiative.create")}>
        <div className="space-y-4">
          <div>
            <Label htmlFor="init-title">{t("community.initiative.title")}</Label>
            <Input
              id="init-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Clean water survey"
            />
          </div>
          <div>
            <Label htmlFor="init-desc">{t("community.initiative.subtitle")}</Label>
            <Textarea
              id="init-desc"
              rows={4}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <Button disabled={saving || title.trim().length < 5 || description.trim().length < 20} onClick={createInitiative}>
            {saving ? <Spinner label="…" /> : t("community.initiative.create")}
          </Button>
        </div>
      </Modal>
    </div>
  )
}

function OpportunityCard({
  opportunity,
  onChanged,
}: {
  opportunity: VolunteerOpportunity
  onChanged: () => void
}) {
  const t = useT()
  const [busy, setBusy] = useState(false)
  const isOpen = opportunity.status === "open"
  const isFull = opportunity.participants_count >= opportunity.participants_needed

  async function act(action: "join" | "withdraw") {
    setBusy(true)
    try {
      if (action === "join") await communityApi.joinOpportunity(opportunity.id)
      else await communityApi.withdrawOpportunity(opportunity.id)
      onChanged()
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="rounded-lg border border-stone-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-ink">{opportunity.title}</h3>
          <p className="text-xs text-stone-500">
            {opportunity.location_label ?? "—"} · {opportunity.skills.join(", ") || "—"}
          </p>
        </div>
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-medium ${
            isOpen ? (isFull ? "bg-amber-100 text-amber-700" : "bg-emerald-100 text-emerald-700") : "bg-stone-100 text-stone-500"
          }`}
        >
          {isOpen ? (isFull ? t("community.volunteer.full") : t("community.volunteer.open")) : t("community.volunteer.closed")}
        </span>
      </div>
      <p className="mt-2 line-clamp-2 text-sm text-stone-600">{opportunity.description}</p>
      <p className="mt-2 text-xs text-stone-500">
        {opportunity.participants_count} / {opportunity.participants_needed}
      </p>
      <div className="mt-3">
        {opportunity.my_status === "joined" ? (
          <Button size="sm" variant="secondary" disabled={busy} onClick={() => act("withdraw")}>
            {t("community.volunteer.withdraw")}
          </Button>
        ) : (
          <Button size="sm" disabled={busy || !isOpen || isFull} onClick={() => act("join")}>
            {t("community.volunteer.join")}
          </Button>
        )}
      </div>
    </div>
  )
}

function VolunteerTab() {
  const t = useT()
  const { user } = useAuth()
  const [items, setItems] = useState<VolunteerOpportunity[] | null>(null)
  const [profile, setProfile] = useState<VolunteerProfile | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [skills, setSkills] = useState("")
  const [interests, setInterests] = useState("")
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    try {
      const [opps, prof] = await Promise.all([
        communityApi.listOpportunities({ limit: 50 }),
        user ? communityApi.getVolunteerProfile() : Promise.resolve(null),
      ])
      setItems(opps.items)
      setProfile(prof)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }, [user])

  useEffect(() => {
    // deferred so the fetch does not synchronously setState in the effect
    const timer = window.setTimeout(() => void load(), 0)
    return () => window.clearTimeout(timer)
  }, [load])

  async function saveProfile() {
    setSaving(true)
    try {
      const skillsList = skills.split(",").map((s) => s.trim()).filter(Boolean)
      const interestsList = interests.split(",").map((s) => s.trim()).filter(Boolean)
      const updated = await communityApi.updateVolunteerProfile({ skills: skillsList, interests: interestsList })
      setProfile(updated)
    } finally {
      setSaving(false)
    }
  }

  if (error) return <ErrorState title={t("community.volunteer.title")} detail={error} onRetry={load} />
  if (!items)
    return (
      <div className="space-y-3">
        {[0, 1].map((i) => (
          <Skeleton key={i} height={96} />
        ))}
      </div>
    )

  return (
    <div className="space-y-6">
      <p className="text-sm text-stone-500">{t("community.volunteer.subtitle")}</p>
      {user && (
        <div className="rounded-lg border border-stone-200 bg-white p-4 shadow-sm">
          <h3 className="font-semibold text-ink">{t("community.volunteer.profile")}</h3>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <div>
              <Label>{t("community.volunteer.skills")}</Label>
              <Input
                value={skills}
                onChange={(e) => setSkills(e.target.value)}
                placeholder="photography, translation"
                defaultValue={profile?.skills?.join(", ")}
              />
            </div>
            <div>
              <Label>{t("community.volunteer.interests")}</Label>
              <Input
                value={interests}
                onChange={(e) => setInterests(e.target.value)}
                placeholder="education, water"
                defaultValue={profile?.interests?.join(", ")}
              />
            </div>
          </div>
          <Button className="mt-3" size="sm" disabled={saving} onClick={saveProfile}>
            {saving ? <Spinner label="…" /> : t("community.volunteer.save")}
          </Button>
        </div>
      )}
      <div className="space-y-3">
        {items.length === 0 ? (
          <EmptyState icon="user" title={t("community.volunteer.title")}>
            {t("community.volunteer.empty")}
          </EmptyState>
        ) : (
          items.map((opportunity) => (
            <OpportunityCard key={opportunity.id} opportunity={opportunity} onChanged={load} />
          ))
        )}
      </div>
    </div>
  )
}

function GroupCard({ group, onChanged }: { group: CommunityGroup; onChanged: () => void }) {
  const t = useT()
  const [busy, setBusy] = useState(false)

  async function act(action: "join" | "leave") {
    setBusy(true)
    try {
      if (action === "join") await communityApi.joinGroup(group.id)
      else await communityApi.leaveGroup(group.id)
      onChanged()
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="rounded-lg border border-stone-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-ink">{group.name}</h3>
          <p className="text-xs text-stone-500">
            {group.owner?.display_name ?? "—"} · {group.member_count} {t("community.group.members")}
          </p>
        </div>
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-medium ${
            group.status === "active"
              ? "bg-emerald-100 text-emerald-700"
              : "bg-amber-100 text-amber-700"
          }`}
        >
          {group.status === "active"
            ? t("community.group.status.active")
            : t("community.group.status.requested")}
        </span>
      </div>
      {group.description && <p className="mt-2 line-clamp-2 text-sm text-stone-600">{group.description}</p>}
      <div className="mt-3">
        {group.my_role ? (
          <Button size="sm" variant="secondary" disabled={busy || group.my_role === "owner"} onClick={() => act("leave")}>
            {t("community.group.leave")}
          </Button>
        ) : (
          <Button size="sm" disabled={busy} onClick={() => act("join")}>
            {t("community.group.join")}
          </Button>
        )}
      </div>
    </div>
  )
}

function GroupsTab() {
  const t = useT()
  const { user } = useAuth()
  const toast = useToast()
  const [items, setItems] = useState<CommunityGroup[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    try {
      const res = await communityApi.listGroups({ limit: 50 })
      setItems(res.items)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }, [])

  useEffect(() => {
    // deferred so the fetch does not synchronously setState in the effect
    const timer = window.setTimeout(() => void load(), 0)
    return () => window.clearTimeout(timer)
  }, [load])

  async function createGroup() {
    setSaving(true)
    try {
      await communityApi.createGroup({ name, description })
      setCreating(false)
      setName("")
      setDescription("")
      toast.toast("success", t("community.group.create"))
      await load()
    } finally {
      setSaving(false)
    }
  }

  if (error) return <ErrorState title={t("community.group.title")} detail={error} onRetry={load} />
  if (!items)
    return (
      <div className="space-y-3">
        {[0, 1].map((i) => (
          <Skeleton key={i} height={96} />
        ))}
      </div>
    )

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-stone-500">{t("community.group.subtitle")}</p>
        {user && (
          <Button size="sm" onClick={() => setCreating(true)}>
            {t("community.group.create")}
          </Button>
        )}
      </div>
      {items.length === 0 ? (
        <EmptyState icon="user" title={t("community.group.title")}>
          {t("community.group.empty")}
        </EmptyState>
      ) : (
        <div className="space-y-3">
          {items.map((group) => (
            <GroupCard key={group.id} group={group} onChanged={load} />
          ))}
        </div>
      )}
      <Modal open={creating} onClose={() => setCreating(false)} title={t("community.group.create")}>
        <div className="space-y-4">
          <div>
            <Label htmlFor="group-name">{t("community.group.title")}</Label>
            <Input
              id="group-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Patna Civic Community"
            />
          </div>
          <div>
            <Label htmlFor="group-desc">{t("community.group.subtitle")}</Label>
            <Textarea
              id="group-desc"
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <Button disabled={saving || name.trim().length < 3} onClick={createGroup}>
            {saving ? <Spinner label="…" /> : t("community.group.create")}
          </Button>
        </div>
      </Modal>
    </div>
  )
}

function BadgesTab() {
  const t = useT()
  const { user } = useAuth()
  const [badges, setBadges] = useState<Badge[] | null>(null)
  const [mine, setMine] = useState<{ earned: Array<Badge & { current: number }>; in_progress: Array<Badge & { current: number }> } | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const [all, me] = await Promise.all([
        communityApi.listBadges(),
        user ? communityApi.myBadges() : Promise.resolve(null),
      ])
      setBadges(all.items)
      setMine(me)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }, [user])

  useEffect(() => {
    // deferred so the fetch does not synchronously setState in the effect
    const timer = window.setTimeout(() => void load(), 0)
    return () => window.clearTimeout(timer)
  }, [load])

  if (error) return <ErrorState title={t("community.badge.title")} detail={error} onRetry={load} />
  if (!badges)
    return (
      <div className="space-y-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} height={64} />
        ))}
      </div>
    )

  const earnedCodes = new Set(mine?.earned?.map((b) => b.code) ?? [])

  return (
    <div className="space-y-4">
      <p className="text-sm text-stone-500">{t("community.badge.subtitle")}</p>
      {user && mine && (
        <div className="rounded-lg border border-stone-200 bg-white p-4 shadow-sm">
          <h3 className="font-semibold text-ink">{t("community.badge.earned")}</h3>
          <div className="mt-2 flex flex-wrap gap-2">
            {mine.earned.length === 0 ? (
              <span className="text-sm text-stone-500">{t("community.badge.inProgress")}</span>
            ) : (
              mine.earned.map((badge) => (
                <span key={badge.code} className="rounded-full bg-(--color-primary)-50 px-3 py-1 text-xs font-medium text-(--color-primary-strong)">
                  {badge.name}
                </span>
              ))
            )}
          </div>
        </div>
      )}
      <div className="space-y-2">
        {badges.map((badge) => {
          const earned = earnedCodes.has(badge.code)
          return (
            <div key={badge.code} className="rounded-lg border border-stone-200 bg-white p-4 shadow-sm">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="font-semibold text-ink">
                    {badge.name} {earned && <span className="text-xs text-emerald-600">✓</span>}
                  </h3>
                  <p className="mt-1 text-sm text-stone-600">{badge.description}</p>
                  <p className="mt-1 text-xs text-stone-400">
                    {t("community.badge.criteria")}: {badge.criteria.metric} ≥ {badge.criteria.min}
                  </p>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export function CommunityHub({ initialTab = "initiatives" }: { initialTab?: string }) {
  const t = useT()
  const [tab, setTab] = useState(initialTab)

  const tabs = [
    { id: "initiatives", label: t("community.tab.initiatives") },
    { id: "volunteer", label: t("community.tab.volunteer") },
    { id: "groups", label: t("community.tab.groups") },
    { id: "badges", label: t("community.tab.badges") },
  ]

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-(--color-primary-strong)">{t("community.title")}</h1>
        <p className="text-sm text-stone-500">{t("community.subtitle")}</p>
        <p className="mt-1 text-xs text-stone-400">{t("community.guidelines.short")}</p>
      </div>
      <Tabs tabs={tabs} active={tab} onChange={setTab} />
      {tab === "initiatives" && <InitiativesTab />}
      {tab === "volunteer" && <VolunteerTab />}
      {tab === "groups" && <GroupsTab />}
      {tab === "badges" && <BadgesTab />}
    </div>
  )
}
