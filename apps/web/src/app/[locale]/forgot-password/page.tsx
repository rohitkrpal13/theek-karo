"use client"

import Link from "next/link"
import { useParams } from "next/navigation"
import { useState } from "react"

import { authApi } from "@/lib/api"

export default function ForgotPasswordPage() {
  const params = useParams<{ locale?: string }>()
  const locale = params.locale ?? "en"

  const [email, setEmail] = useState("")
  const [loading, setLoading] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [devToken, setDevToken] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const res = await authApi.forgotPassword(email.trim())
      setSubmitted(true)
      if (res.dev_reset_token) {
        setDevToken(res.dev_reset_token)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send reset link")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto max-w-md space-y-6">
      <div className="text-center">
        <h1 className="text-2xl font-bold text-stone-900">Forgot Password</h1>
        <p className="mt-1 text-sm text-stone-600">
          Enter your registered email address to receive reset instructions.
        </p>
      </div>

      <div className="rounded-xl border border-stone-200 bg-white p-6 shadow-sm">
        {submitted ? (
          <div className="space-y-4 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-blue-100 text-blue-600">
              <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                />
              </svg>
            </div>
            <h2 className="text-lg font-semibold text-stone-900">Check Your Inbox</h2>
            <p className="text-sm text-stone-600">
              If an active account exists for <strong>{email}</strong>, we have sent a secure password
              reset link.
            </p>

            {devToken && (
              <div className="rounded-lg bg-amber-50 p-3 text-xs text-amber-900 border border-amber-200 text-left">
                <span className="font-semibold">Dev Reset Link:</span>{" "}
                <Link
                  href={`/${locale}/reset-password?token=${devToken}`}
                  className="text-amber-800 underline font-mono break-all"
                >
                  Reset Password Now
                </Link>
              </div>
            )}

            <div className="pt-2">
              <Link
                href={`/${locale}/auth/login`}
                className="text-sm font-semibold text-(--color-primary) hover:underline"
              >
                Return to Sign In
              </Link>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700 border border-red-200">
                {error}
              </div>
            )}

            <label className="block">
              <span className="text-sm font-medium text-stone-700">Email Address</span>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="you@example.com"
                className="mt-1 w-full rounded-lg border border-stone-300 px-3.5 py-2.5 text-sm transition focus:border-(--color-primary) focus:outline-none focus:ring-1 focus:ring-(--color-primary)"
              />
            </label>

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-(--color-primary) px-4 py-2.5 font-semibold text-white shadow-sm transition hover:bg-(--color-primary-strong) disabled:opacity-60"
            >
              {loading ? "Sending..." : "Send Reset Link"}
            </button>

            <p className="text-center text-sm text-stone-600 pt-2">
              Remember your password?{" "}
              <Link href={`/${locale}/auth/login`} className="text-(--color-primary) font-semibold hover:underline">
                Sign In
              </Link>
            </p>
          </form>
        )}
      </div>
    </div>
  )
}
