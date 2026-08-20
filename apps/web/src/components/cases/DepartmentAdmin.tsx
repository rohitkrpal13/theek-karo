"use client"

import { useCallback, useEffect, useState } from "react"

import {
  departmentsApi,
  type DepartmentListItem,
  type DepartmentMember,
  type DepartmentType,
  type OrganizationVerification,
} from "@/lib/api/departments"
import { useT } from "@/lib/i18n-client"
import { Badge, Button, EmptyState, ErrorState, Input, Select, Spinner } from "@/components/ui/primitives"

type Tab = "departments" | "verifications"

export function DepartmentAdmin() {
  const t = useT()
  const [tab, setTab] = useState<Tab>("departments")
  const [types, setTypes] = useState<DepartmentType[]>([])
  const [departments, setDepartments] = useState<DepartmentListItem[] | null>(null)
  const [verifications, setVerifications] = useState<OrganizationVerification[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const [typesRes, deptRes, verRes] = await Promise.all([
        departmentsApi.listTypes(),
        departmentsApi.list({ include_inactive: true }),
        departmentsApi.listVerifications({}),
      ])
      setTypes(typesRes)
      setDepartments(deptRes)
      setVerifications(verRes)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    async function loadAdmin() {
      try {
        const [typesRes, deptRes, verRes] = await Promise.all([
          departmentsApi.listTypes(),
          departmentsApi.list({ include_inactive: true }),
          departmentsApi.listVerifications({}),
        ])
        if (!cancelled) {
          setTypes(typesRes)
          setDepartments(deptRes)
          setVerifications(verRes)
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err))
      }
    }
    void loadAdmin()
    return () => {
      cancelled = true
    }
  }, [])

  if (error) return <ErrorState title={t("departments.title")} detail={error} onRetry={load} />
  if (departments === null || verifications === null) return <Spinner label={t("departments.title")} />

  return (
    <div className="space-y-6">
      {notice && (
        <p className="rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">{notice}</p>
      )}

      <div className="flex gap-2">
        <Button variant={tab === "departments" ? "primary" : "ghost"} onClick={() => setTab("departments")}>
          {t("departments.title")}
        </Button>
        <Button variant={tab === "verifications" ? "primary" : "ghost"} onClick={() => setTab("verifications")}>
          {t("departments.verifications")}
        </Button>
      </div>

      {tab === "departments" ? (
        <RegistryView
          types={types}
          departments={departments}
          onChanged={load}
          onNotice={setNotice}
        />
      ) : (
        <VerificationsView verifications={verifications} onChanged={load} onNotice={setNotice} />
      )}
    </div>
  )
}

function RegistryView({
  types,
  departments,
  onChanged,
  onNotice,
}: {
  types: DepartmentType[]
  departments: DepartmentListItem[]
  onChanged: () => Promise<void>
  onNotice: (msg: string) => void
}) {
  const t = useT()
  const [typeCode, setTypeCode] = useState("")
  const [typeNameKey, setTypeNameKey] = useState("")
  const [name, setName] = useState("")
  const [slug, setSlug] = useState("")
  const [departmentTypeId, setDepartmentTypeId] = useState("")
  const [description, setDescription] = useState("")
  const [busy, setBusy] = useState(false)

  async function run(action: () => Promise<unknown>, success: string) {
    setBusy(true)
    try {
      await action()
      await onChanged()
      onNotice(success)
    } catch (err) {
      onNotice(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      <section className="rounded-md border border-stone-200 bg-white p-4">
        <h2 className="mb-2 text-sm font-semibold text-stone-700">{t("departments.types.create")}</h2>
        <div className="flex flex-wrap items-end gap-2">
          <Input placeholder={t("departments.types.code")} value={typeCode} onChange={(e) => setTypeCode(e.target.value)} className="w-44" />
          <Input placeholder={t("departments.types.name_key")} value={typeNameKey} onChange={(e) => setTypeNameKey(e.target.value)} className="w-44" />
          <Button
            disabled={busy || typeCode.trim() === "" || typeNameKey.trim() === ""}
            onClick={() =>
              void run(
                () => departmentsApi.createType({ code: typeCode, name_key: typeNameKey }),
                "type ✓",
              )
            }
          >
            {t("departments.types.create")}
          </Button>
        </div>
      </section>

      <section className="rounded-md border border-stone-200 bg-white p-4">
        <h2 className="mb-2 text-sm font-semibold text-stone-700">{t("departments.create")}</h2>
        <div className="flex flex-wrap items-end gap-2">
          <Input placeholder={t("departments.create.name")} value={name} onChange={(e) => setName(e.target.value)} className="w-48" />
          <Input placeholder={t("departments.create.slug")} value={slug} onChange={(e) => setSlug(e.target.value)} className="w-48" />
          <Select value={departmentTypeId} onChange={(e) => setDepartmentTypeId(e.target.value)}>
            <option value="">—</option>
            {types.map((tp) => (
              <option key={tp.id} value={tp.id}>
                {tp.code}
              </option>
            ))}
          </Select>
          <Button
            disabled={busy || name.trim() === "" || slug.trim() === "" || departmentTypeId === ""}
            onClick={() =>
              void run(
                () => departmentsApi.create({ slug, name, department_type_id: departmentTypeId, description: description || null }),
                "department ✓",
              )
            }
          >
            {t("departments.create")}
          </Button>
        </div>
        <Input
          placeholder={t("departments.description")}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          className="mt-2 w-full"
        />
      </section>

      {departments.map((d) => (
        <DepartmentCard key={d.id} department={d} onNotice={onNotice} />
      ))}
    </div>
  )
}

function DepartmentCard({
  department,
  onNotice,
}: {
  department: DepartmentListItem
  onNotice: (msg: string) => void
}) {
  const t = useT()
  const [members, setMembers] = useState<DepartmentMember[] | null>(null)
  const [userId, setUserId] = useState("")
  const [role, setRole] = useState("member")
  const [expanded, setExpanded] = useState(false)
  const [busy, setBusy] = useState(false)

  async function toggle() {
    if (expanded) {
      setExpanded(false)
      return
    }
    setExpanded(true)
    if (members === null) {
      try {
        setMembers(await departmentsApi.listMembers(department.id))
      } catch {
        setMembers([])
      }
    }
  }

  return (
    <section className="rounded-md border border-stone-200 bg-white p-4">
      <button type="button" onClick={() => void toggle()} className="flex w-full items-center gap-2 text-left">
        <span className="font-medium text-stone-800">{department.name}</span>
        <Badge tone={department.status === "active" ? "success" : "default"}>
          {t(`departments.status.${department.status}` as never)}
        </Badge>
        <span className="ml-auto text-xs text-stone-400">{department.slug}</span>
      </button>
      {expanded && (
        <div className="mt-3 space-y-3">
          <div>
            <h3 className="mb-1 text-xs font-semibold text-stone-500">{t("departments.members")}</h3>
            <ul className="space-y-1 text-sm text-stone-600">
              {(members ?? []).map((m) => (
                <li key={m.id} className="flex items-center gap-2">
                  <span className="font-mono text-xs">{m.user_id}</span>
                  <Badge>{t(`departments.member.role.${m.role_in_department}` as never)}</Badge>
                  {!m.is_active && <span className="text-xs text-stone-400">✕</span>}
                </li>
              ))}
            </ul>
          </div>
          <div className="flex flex-wrap items-end gap-2">
            <Input
              placeholder={t("departments.members.user_id")}
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              className="w-64 font-mono text-xs"
            />
            <Select value={role} onChange={(e) => setRole(e.target.value)}>
              {["member", "manager", "reviewer"].map((r) => (
                <option key={r} value={r}>
                  {t(`departments.member.role.${r}` as never)}
                </option>
              ))}
            </Select>
            <Button
              disabled={busy || userId.trim() === ""}
              onClick={async () => {
                setBusy(true)
                try {
                  await departmentsApi.addMember(department.id, { user_id: userId, role_in_department: role })
                  setMembers(await departmentsApi.listMembers(department.id))
                  setUserId("")
                  onNotice("member ✓")
                } catch (err) {
                  onNotice(err instanceof Error ? err.message : String(err))
                } finally {
                  setBusy(false)
                }
              }}
            >
              {t("departments.members.add")}
            </Button>
          </div>
        </div>
      )}
    </section>
  )
}

function VerificationsView({
  verifications,
  onChanged,
  onNotice,
}: {
  verifications: OrganizationVerification[]
  onChanged: () => Promise<void>
  onNotice: (msg: string) => void
}) {
  const t = useT()
  const [busy, setBusy] = useState(false)
  if (verifications.length === 0) return <EmptyState title={t("departments.verifications.empty")} />
  return (
    <ul className="space-y-3">
      {verifications.map((v) => (
        <li key={v.id} className="rounded-md border border-stone-200 bg-white p-4">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium text-stone-800">{v.organization_name}</span>
            <Badge tone={v.verification_state === "verified" ? "success" : "warning"}>
              {t(`departments.verifications.state.${v.verification_state}` as never)}
            </Badge>
          </div>
          {v.submitted_reason && <p className="mt-1 text-sm text-stone-500">{v.submitted_reason}</p>}
          <div className="mt-2 flex items-center gap-2 text-xs text-stone-400">
            <span className="font-mono">{v.user_id}</span>
            <span>{new Date(v.created_at).toLocaleDateString()}</span>
          </div>
          {v.verification_state === "pending" && (
            <div className="mt-3 flex gap-2">
              <Button
                disabled={busy}
                onClick={() =>
                  void (async () => {
                    setBusy(true)
                    try {
                      await departmentsApi.reviewVerification(v.id, { state: "verified" })
                      await onChanged()
                      onNotice("approved ✓")
                    } catch (err) {
                      onNotice(err instanceof Error ? err.message : String(err))
                    } finally {
                      setBusy(false)
                    }
                  })()
                }
              >
                {t("departments.verifications.approve")}
              </Button>
              <Button
                variant="danger"
                disabled={busy}
                onClick={() =>
                  void (async () => {
                    setBusy(true)
                    try {
                      await departmentsApi.reviewVerification(v.id, { state: "revoked" })
                      await onChanged()
                      onNotice("revoked")
                    } catch (err) {
                      onNotice(err instanceof Error ? err.message : String(err))
                    } finally {
                      setBusy(false)
                    }
                  })()
                }
              >
                {t("departments.verifications.revoke")}
              </Button>
            </div>
          )}
        </li>
      ))}
    </ul>
  )
}