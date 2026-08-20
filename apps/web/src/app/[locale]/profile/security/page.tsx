"use client"

import Link from "next/link"
import { useParams, useRouter } from "next/navigation"
import { useEffect, useState } from "react"

import { Button } from "@/components/ui/primitives"
import { authApi, type UserSessionItem } from "@/lib/api"
import { useAuth } from "@/lib/auth"

export default function ProfileSecurityPage() {
  const params = useParams<{ locale?: string }>()
  const locale = params.locale ?? "en"
  const router = useRouter()
  const { user, logout, logoutAll } = useAuth()

  // Sessions state
  const [sessions, setSessions] = useState<UserSessionItem[]>([])
  const [sessionsLoading, setSessionsLoading] = useState(true)
  const [revokingId, setRevokingId] = useState<string | null>(null)

  // Password change state
  const [currentPassword, setCurrentPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [revokeOther, setRevokeOther] = useState(true)
  const [pwPending, setPwPending] = useState(false)
  const [pwError, setPwError] = useState<string | null>(null)
  const [pwSuccess, setPwSuccess] = useState(false)

  // Delete account state
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [deletePending, setDeletePending] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  // MFA (TOTP) state
  const [mfaEnabled, setMfaEnabled] = useState(false)
  const [mfaRequired, setMfaRequired] = useState(false)
  const [mfaSetup, setMfaSetup] = useState<{ secret: string; otpauth_uri: string } | null>(null)
  const [mfaCode, setMfaCode] = useState("")
  const [mfaPending, setMfaPending] = useState(false)
  const [mfaError, setMfaError] = useState<string | null>(null)
  const [mfaSuccess, setMfaSuccess] = useState<string | null>(null)

  async function loadMfaStatus() {
    try {
      const status = await authApi.getMfaStatus()
      setMfaEnabled(status.enabled)
      setMfaRequired(status.required_by_role)
    } catch {
      // Fallback: leave defaults
    }
  }

  useEffect(() => {
    if (!user) return
    void loadSessions()
    // deferred so the MFA status fetch does not synchronously setState in the effect
    const timer = window.setTimeout(() => void loadMfaStatus(), 0)
    return () => window.clearTimeout(timer)
  }, [user])

  async function handleMfaSetup() {
    setMfaError(null)
    setMfaPending(true)
    try {
      const result = await authApi.setupMfa()
      setMfaSetup(result)
      setMfaCode("")
    } catch (err) {
      setMfaError(err instanceof Error ? err.message : "Failed to start MFA setup")
    } finally {
      setMfaPending(false)
    }
  }

  async function handleMfaEnable(e: React.FormEvent) {
    e.preventDefault()
    setMfaError(null)
    setMfaSuccess(null)
    setMfaPending(true)
    try {
      await authApi.enableMfa(mfaCode)
      setMfaEnabled(true)
      setMfaSetup(null)
      setMfaCode("")
      setMfaSuccess("Two-factor authentication is now enabled.")
    } catch (err) {
      setMfaError(err instanceof Error ? err.message : "Invalid authentication code")
    } finally {
      setMfaPending(false)
    }
  }

  async function handleMfaDisable(e: React.FormEvent) {
    e.preventDefault()
    setMfaError(null)
    setMfaSuccess(null)
    setMfaPending(true)
    try {
      await authApi.disableMfa(mfaCode)
      setMfaEnabled(false)
      setMfaCode("")
      setMfaSuccess("Two-factor authentication is now disabled.")
    } catch (err) {
      setMfaError(err instanceof Error ? err.message : "Invalid authentication code")
    } finally {
      setMfaPending(false)
    }
  }

  async function loadSessions() {
    try {
      setSessionsLoading(true)
      const res = await authApi.getSessions()
      setSessions(res.items)
    } catch {
      // Fallback
    } finally {
      setSessionsLoading(false)
    }
  }

  async function handleRevokeSession(sessionId: string) {
    setRevokingId(sessionId)
    try {
      await authApi.revokeSession(sessionId)
      setSessions((prev) => prev.filter((s) => s.id !== sessionId))
    } catch (err) {
      alert("Failed to revoke session: " + (err instanceof Error ? err.message : "Error"))
    } finally {
      setRevokingId(null)
    }
  }

  async function handlePasswordChange(e: React.FormEvent) {
    e.preventDefault()
    setPwError(null)
    setPwSuccess(false)
    if (newPassword.length < 8) {
      setPwError("New password must be at least 8 characters.")
      return
    }
    if (newPassword !== confirmPassword) {
      setPwError("New passwords do not match.")
      return
    }

    setPwPending(true)
    try {
      await authApi.changePassword(currentPassword, newPassword, revokeOther)
      setPwSuccess(true)
      setCurrentPassword("")
      setNewPassword("")
      setConfirmPassword("")
      void loadSessions()
    } catch (err) {
      setPwError(err instanceof Error ? err.message : "Failed to change password")
    } finally {
      setPwPending(false)
    }
  }

  async function handleDeleteAccount() {
    setDeletePending(true)
    setDeleteError(null)
    try {
      await authApi.deleteAccount()
      await logout()
      router.push(`/${locale}/`)
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "Failed to delete account")
      setDeletePending(false)
    }
  }

  if (!user) {
    return (
      <div className="mx-auto max-w-lg p-8 text-center">
        <p className="text-sm text-stone-600">Please sign in to access security settings.</p>
        <Link href={`/${locale}/auth/login`} className="mt-4 inline-block text-(--color-primary) font-semibold underline">
          Sign In
        </Link>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      {/* Header breadcrumb */}
      <div className="flex items-center justify-between">
        <div>
          <Link
            href={`/${locale}/profile`}
            className="text-xs font-semibold text-(--color-primary) hover:underline"
          >
            ← Back to Profile
          </Link>
          <h1 className="mt-1 text-2xl font-bold text-stone-900">Account Security & Sessions</h1>
        </div>
      </div>

      {/* Password Management */}
      <section className="rounded-xl border border-stone-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-bold text-stone-900">Change Password</h2>
        <p className="mt-1 text-xs text-stone-500">
          Ensure your account uses a strong, unique password with at least 8 characters.
        </p>

        {pwSuccess && (
          <div className="mt-4 rounded-lg bg-green-50 p-3 text-sm text-green-800 border border-green-200">
            Password changed successfully! Other sessions have been signed out.
          </div>
        )}

        {pwError && (
          <div className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700 border border-red-200">
            {pwError}
          </div>
        )}

        <form onSubmit={handlePasswordChange} className="mt-5 space-y-4 max-w-md">
          <label className="block">
            <span className="text-sm font-medium text-stone-700">Current Password</span>
            <input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              required
              autoComplete="current-password"
              className="mt-1 w-full rounded-lg border border-stone-300 px-3.5 py-2 text-sm transition focus:border-(--color-primary) focus:outline-none focus:ring-1 focus:ring-(--color-primary)"
            />
          </label>

          <label className="block">
            <span className="text-sm font-medium text-stone-700">New Password</span>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              minLength={8}
              autoComplete="new-password"
              className="mt-1 w-full rounded-lg border border-stone-300 px-3.5 py-2 text-sm transition focus:border-(--color-primary) focus:outline-none focus:ring-1 focus:ring-(--color-primary)"
            />
          </label>

          <label className="block">
            <span className="text-sm font-medium text-stone-700">Confirm New Password</span>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              minLength={8}
              autoComplete="new-password"
              className="mt-1 w-full rounded-lg border border-stone-300 px-3.5 py-2 text-sm transition focus:border-(--color-primary) focus:outline-none focus:ring-1 focus:ring-(--color-primary)"
            />
          </label>

          <label className="flex items-center gap-2 text-sm text-stone-600">
            <input
              type="checkbox"
              checked={revokeOther}
              onChange={(e) => setRevokeOther(e.target.checked)}
              className="h-4 w-4 rounded border-stone-300 text-(--color-primary)"
            />
            Sign out of all other devices upon password update
          </label>

          <Button type="submit" variant="primary" size="sm" disabled={pwPending}>
            {pwPending ? "Updating Password..." : "Update Password"}
          </Button>
        </form>
      </section>

      {/* Two-Factor Authentication (TOTP) */}
      <section className="rounded-xl border border-stone-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-stone-900">Two-Factor Authentication</h2>
            <p className="text-xs text-stone-500">
              {mfaRequired
                ? "Required for privileged accounts. Add an authenticator app to protect this account."
                : "Add an extra layer of security with a time-based one-time password (TOTP)."}
            </p>
          </div>
          {mfaEnabled && (
            <span className="rounded-full bg-green-100 px-3 py-1 text-xs font-semibold text-green-800">
              Enabled
            </span>
          )}
        </div>

        {mfaSuccess && (
          <div className="mt-4 rounded-lg bg-green-50 p-3 text-sm text-green-800 border border-green-200">
            {mfaSuccess}
          </div>
        )}
        {mfaError && (
          <div className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700 border border-red-200">
            {mfaError}
          </div>
        )}

        {!mfaEnabled && !mfaSetup && (
          <div className="mt-4">
            <Button variant="primary" size="sm" onClick={handleMfaSetup} disabled={mfaPending}>
              {mfaPending ? "Preparing..." : "Set Up Authenticator"}
            </Button>
          </div>
        )}

        {mfaSetup && (
          <div className="mt-4 space-y-4">
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
              <p className="font-semibold">Scan this code with your authenticator app</p>
              <p className="mt-1 break-all font-mono text-xs">{mfaSetup.otpauth_uri}</p>
              <p className="mt-3 text-xs">
                Can&apos;t scan? Enter this key manually:{" "}
                <span className="font-mono font-semibold">{mfaSetup.secret}</span>
              </p>
            </div>
            <form onSubmit={handleMfaEnable} className="flex max-w-sm items-end gap-3">
              <label className="block flex-1">
                <span className="text-sm font-medium text-stone-700">6-digit code</span>
                <input
                  value={mfaCode}
                  onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  inputMode="numeric"
                  pattern="[0-9]{6}"
                  required
                  placeholder="••••••"
                  className="mt-1 w-full rounded-lg border border-stone-300 px-3.5 py-2 text-sm transition focus:border-(--color-primary) focus:outline-none focus:ring-1 focus:ring-(--color-primary)"
                />
              </label>
              <Button type="submit" variant="primary" size="sm" disabled={mfaPending || mfaCode.length !== 6}>
                {mfaPending ? "Enabling..." : "Enable"}
              </Button>
            </form>
          </div>
        )}

        {mfaEnabled && (
          <form onSubmit={handleMfaDisable} className="mt-4 flex max-w-sm items-end gap-3">
            <label className="block flex-1">
              <span className="text-sm font-medium text-stone-700">Current code to disable</span>
              <input
                value={mfaCode}
                onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                inputMode="numeric"
                pattern="[0-9]{6}"
                required
                placeholder="••••••"
                className="mt-1 w-full rounded-lg border border-stone-300 px-3.5 py-2 text-sm transition focus:border-(--color-primary) focus:outline-none focus:ring-1 focus:ring-(--color-primary)"
              />
            </label>
            <Button type="submit" variant="outline" size="sm" disabled={mfaPending || mfaCode.length !== 6}>
              {mfaPending ? "Disabling..." : "Disable"}
            </Button>
          </form>
        )}
      </section>

      {/* Active Sessions */}
      <section className="rounded-xl border border-stone-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-stone-900">Active Sessions & Devices</h2>
            <p className="text-xs text-stone-500">
              Manage authorized devices currently logged into your account.
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={async () => {
              await logoutAll()
              router.push(`/${locale}/auth/login`)
            }}
          >
            Sign Out Everywhere
          </Button>
        </div>

        <div className="mt-5 space-y-3">
          {sessionsLoading ? (
            <p className="text-sm text-stone-500 py-4">Loading active sessions...</p>
          ) : sessions.length > 0 ? (
            sessions.map((sess) => (
              <div
                key={sess.id}
                className="flex items-center justify-between rounded-lg border border-stone-200 p-4 transition hover:bg-stone-50/50"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-sm text-stone-900">
                      {sess.user_agent ? sess.user_agent.split(" ")[0] : "Web Browser"}
                    </span>
                    {sess.ip && (
                      <span className="rounded bg-stone-100 px-2 py-0.5 text-xs text-stone-600 font-mono">
                        {sess.ip}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-stone-500">
                    Last active: {new Date(sess.last_seen_at).toLocaleString()}
                  </p>
                </div>

                <Button
                  variant="outline"
                  size="sm"
                  disabled={revokingId === sess.id}
                  onClick={() => handleRevokeSession(sess.id)}
                >
                  {revokingId === sess.id ? "Revoking..." : "Revoke"}
                </Button>
              </div>
            ))
          ) : (
            <p className="text-sm text-stone-500 py-4">No active secondary sessions.</p>
          )}
        </div>
      </section>

      {/* Danger Zone: Account Deletion */}
      <section className="rounded-xl border border-red-200 bg-red-50/40 p-6">
        <h2 className="text-lg font-bold text-red-900">Danger Zone: Delete Account</h2>
        <p className="mt-1 text-xs text-red-700">
          In compliance with the Digital Personal Data Protection (DPDP) framework, deleting your
          account permanently anonymizes your personal identity while retaining your public civic
          contributions for community transparency.
        </p>

        <div className="mt-4">
          <Button
            variant="danger"
            size="sm"
            onClick={() => setShowDeleteModal(true)}
          >
            Delete Account
          </Button>
        </div>
      </section>

      {/* Confirmation Modal */}
      {showDeleteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl space-y-4">
            <h3 className="text-lg font-bold text-stone-900">Confirm Account Deletion</h3>
            <p className="text-sm text-stone-600">
              Are you sure you want to delete your account? This action cannot be undone. All
              sessions will be terminated immediately.
            </p>

            {deleteError && (
              <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{deleteError}</div>
            )}

            <div className="flex justify-end gap-3 pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowDeleteModal(false)}
                disabled={deletePending}
              >
                Cancel
              </Button>
              <Button
                variant="danger"
                size="sm"
                onClick={handleDeleteAccount}
                disabled={deletePending}
              >
                {deletePending ? "Deleting..." : "Permanently Delete"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
