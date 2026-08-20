"use client"

import Link from "next/link"
import { useParams, useRouter, useSearchParams } from "next/navigation"
import { useEffect, useState } from "react"

import { authApi } from "@/lib/api"
import { useAuth } from "@/lib/auth"

export default function VerifyEmailPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const params = useParams<{ locale?: string }>()
  const locale = params.locale ?? "en"
  const { login } = useAuth()

  const urlToken = searchParams.get("token") || ""
  const [token, setToken] = useState(urlToken)
  const [loading, setLoading] = useState(Boolean(urlToken))
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  async function executeVerification(verificationToken: string) {
    if (!verificationToken.trim()) return
    try {
      const res = await authApi.verifyEmail(verificationToken.trim())
      login(res.access_token, res.user)
      setSuccess(true)
      setTimeout(() => {
        router.push(`/${locale}/`)
      }, 2000)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Verification failed. Token may be invalid or expired.")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!urlToken) return
    let cancelled = false
    ;(async () => {
      try {
        const res = await authApi.verifyEmail(urlToken.trim())
        if (cancelled) return
        login(res.access_token, res.user)
        setSuccess(true)
        setTimeout(() => {
          router.push(`/${locale}/`)
        }, 2000)
      } catch (e) {
        if (cancelled) return
        setError(e instanceof Error ? e.message : "Verification failed. Token may be invalid or expired.")
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [urlToken, locale, login, router])

  return (
    <div className="mx-auto max-w-md space-y-6">
      <div className="text-center">
        <h1 className="text-2xl font-bold text-stone-900">Email Verification</h1>
        <p className="mt-1 text-sm text-stone-600">
          Activating your citizen account on Theek Karo.
        </p>
      </div>

      <div className="rounded-xl border border-stone-200 bg-white p-6 shadow-sm">
        {loading && (
          <div className="py-8 text-center space-y-3">
            <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-(--color-primary) border-t-transparent" />
            <p className="text-sm font-medium text-stone-600">Verifying your email address...</p>
          </div>
        )}

        {success && (
          <div className="py-6 text-center space-y-3">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-green-100 text-green-600">
              <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h2 className="text-lg font-semibold text-stone-900">Email Verified Successfully!</h2>
            <p className="text-sm text-stone-600">Redirecting to home page...</p>
          </div>
        )}

        {!loading && !success && (
          <form
            onSubmit={(e) => {
              e.preventDefault()
              setLoading(true)
              setError(null)
              void executeVerification(token)
            }}
            className="space-y-4"
          >
            {error && (
              <div role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700 border border-red-200">
                {error}
              </div>
            )}

            <label className="block">
              <span className="text-sm font-medium text-stone-700">Verification Token</span>
              <input
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="Enter token from your email"
                required
                className="mt-1 w-full rounded-lg border border-stone-300 px-3.5 py-2.5 text-sm transition focus:border-(--color-primary) focus:outline-none focus:ring-1 focus:ring-(--color-primary)"
              />
            </label>

            <button
              type="submit"
              disabled={loading || !token.trim()}
              className="w-full rounded-lg bg-(--color-primary) px-4 py-2.5 font-semibold text-white shadow-sm transition hover:bg-(--color-primary-strong) disabled:opacity-60"
            >
              Verify Email
            </button>

            <p className="text-center text-sm text-stone-600 pt-2">
              Need a new link?{" "}
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
