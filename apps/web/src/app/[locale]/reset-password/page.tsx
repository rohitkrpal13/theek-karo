"use client"

import Link from "next/link"
import { useParams, useRouter, useSearchParams } from "next/navigation"
import { useState } from "react"

import { authApi } from "@/lib/api"

export default function ResetPasswordPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const params = useParams<{ locale?: string }>()
  const locale = params.locale ?? "en"

  const [token, setToken] = useState(searchParams.get("token") || "")
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  async function handleReset(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (newPassword.length < 8) {
      setError("Password must be at least 8 characters long.")
      return
    }
    if (newPassword !== confirmPassword) {
      setError("Passwords do not match.")
      return
    }
    setLoading(true)
    try {
      await authApi.resetPassword(token.trim(), newPassword)
      setSuccess(true)
      setTimeout(() => {
        router.push(`/${locale}/auth/login`)
      }, 2500)
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Password reset failed. The link may be expired or already used.",
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto max-w-md space-y-6">
      <div className="text-center">
        <h1 className="text-2xl font-bold text-stone-900">Set New Password</h1>
        <p className="mt-1 text-sm text-stone-600">
          Create a secure new password for your Theek Karo account.
        </p>
      </div>

      <div className="rounded-xl border border-stone-200 bg-white p-6 shadow-sm">
        {success ? (
          <div className="space-y-4 text-center py-4">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-green-100 text-green-600">
              <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h2 className="text-lg font-semibold text-stone-900">Password Reset Complete</h2>
            <p className="text-sm text-stone-600">
              Your password has been securely updated. Redirecting you to login...
            </p>
          </div>
        ) : (
          <form onSubmit={handleReset} className="space-y-4">
            {error && (
              <div role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700 border border-red-200">
                {error}
              </div>
            )}

            {!searchParams.get("token") && (
              <label className="block">
                <span className="text-sm font-medium text-stone-700">Reset Token</span>
                <input
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  required
                  placeholder="Paste token from email"
                  className="mt-1 w-full rounded-lg border border-stone-300 px-3.5 py-2.5 text-sm transition focus:border-(--color-primary) focus:outline-none focus:ring-1 focus:ring-(--color-primary)"
                />
              </label>
            )}

            <label className="block">
              <span className="text-sm font-medium text-stone-700">New Password</span>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                minLength={8}
                autoComplete="new-password"
                placeholder="At least 8 characters"
                className="mt-1 w-full rounded-lg border border-stone-300 px-3.5 py-2.5 text-sm transition focus:border-(--color-primary) focus:outline-none focus:ring-1 focus:ring-(--color-primary)"
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
                placeholder="Re-enter new password"
                className="mt-1 w-full rounded-lg border border-stone-300 px-3.5 py-2.5 text-sm transition focus:border-(--color-primary) focus:outline-none focus:ring-1 focus:ring-(--color-primary)"
              />
            </label>

            <button
              type="submit"
              disabled={loading || !token.trim()}
              className="w-full rounded-lg bg-(--color-primary) px-4 py-2.5 font-semibold text-white shadow-sm transition hover:bg-(--color-primary-strong) disabled:opacity-60"
            >
              {loading ? "Updating Password..." : "Update Password"}
            </button>

            <p className="text-center text-sm text-stone-600 pt-2">
              <Link href={`/${locale}/auth/login`} className="text-(--color-primary) font-semibold hover:underline">
                Back to Sign In
              </Link>
            </p>
          </form>
        )}
      </div>
    </div>
  )
}
