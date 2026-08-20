"use client"

import { useCallback, useEffect, useState } from "react"

import { departmentsApi, type DepartmentListItem, type MyDepartment } from "@/lib/api/departments"
import { useAuth } from "@/lib/auth"
import { useT } from "@/lib/i18n-client"
import { Badge, Button, EmptyState, ErrorState, Input, Spinner, Textarea } from "@/components/ui/primitives"

export function DepartmentsDirectory() {
  const t = useT()
  const { user } = useAuth()
  const [departments, setDepartments] = useState<DepartmentListItem[] | null>(null)
  const [myDepartments, setMyDepartments] = useState<MyDepartment[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const [list, mine] = await Promise.all([
        departmentsApi.list({}),
        user ? departmentsApi.my().catch(() => []) : Promise.resolve([]),
      ])
      setDepartments(list)
      setMyDepartments(mine)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }, [user])

  useEffect(() => {
    let cancelled = false
    async function loadDirectory() {
      try {
        const [list, mine] = await Promise.all([
          departmentsApi.list({}),
          user ? departmentsApi.my().catch(() => []) : Promise.resolve([]),
        ])
        if (!cancelled) {
          setDepartments(list)
          setMyDepartments(mine)
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err))
      }
    }
    void loadDirectory()
    return () => {
      cancelled = true
    }
  }, [user])

  if (error) return <ErrorState title={t("departments.title")} detail={error} onRetry={load} />
  if (departments === null) return <Spinner label={t("departments.title")} />

  return (
    <div className="space-y-6">
      {notice && (
        <p className="rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">{notice}</p>
      )}
      {myDepartments && myDepartments.length > 0 && (
        <section>
          <h2 className="mb-2 text-sm font-semibold text-stone-700">{t("departments.my")}</h2>
          <ul className="space-y-1 text-sm text-stone-600">
            {myDepartments.map((m) => (
              <li key={m.department_id} className="flex items-center gap-2">
                <span>{m.department_name ?? m.department_slug}</span>
                <Badge>{t(`departments.member.role.${m.role_in_department}` as never)}</Badge>
              </li>
            ))}
          </ul>
        </section>
      )}

      {departments.length === 0 ? (
        <EmptyState title={t("departments.empty")} />
      ) : (
        <ul className="divide-y divide-stone-200 rounded-md border border-stone-200 bg-white">
          {departments.map((d) => (
            <li key={d.id} className="px-4 py-3">
              <div className="flex items-center gap-2">
                <span className="font-medium text-stone-800">{d.name}</span>
                <Badge tone={d.status === "active" ? "success" : "default"}>
                  {t(`departments.status.${d.status}` as never)}
                </Badge>
              </div>
              {d.description && <p className="mt-1 text-sm text-stone-500">{d.description}</p>}
            </li>
          ))}
        </ul>
      )}

      {user && <VerificationRequest onDone={() => setNotice(t("departments.verifications.request") + " ✓")} />}
    </div>
  )
}

function VerificationRequest({ onDone }: { onDone: () => void }) {
  const t = useT()
  const [organizationName, setOrganizationName] = useState("")
  const [reason, setReason] = useState("")
  const [busy, setBusy] = useState(false)
  return (
    <section className="rounded-md border border-stone-200 bg-white p-4">
      <h2 className="mb-2 text-sm font-semibold text-stone-700">{t("departments.verifications.request")}</h2>
      <div className="space-y-2">
        <Input
          placeholder={t("departments.verifications.organization")}
          value={organizationName}
          onChange={(e) => setOrganizationName(e.target.value)}
          className="w-full"
        />
        <Textarea
          placeholder={t("departments.verifications.reason")}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={2}
          className="w-full"
        />
        <Button
          disabled={busy || organizationName.trim() === ""}
          onClick={async () => {
            setBusy(true)
            try {
              await departmentsApi.requestVerification({
                organization_name: organizationName,
                submitted_reason: reason || null,
              })
              onDone()
            } finally {
              setBusy(false)
            }
          }}
        >
          {t("departments.verifications.submit")}
        </Button>
      </div>
    </section>
  )
}