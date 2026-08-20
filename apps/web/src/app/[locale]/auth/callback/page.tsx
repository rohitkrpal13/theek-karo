"use client"

import { useParams, useRouter, useSearchParams } from "next/navigation"
import { useEffect, useState } from "react"

import { authApi } from "@/lib/api"
import { useAuth } from "@/lib/auth"

export default function AuthCallbackPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const params = useParams<{ locale?: string }>()
  const locale = params.locale ?? "en"
  const { login } = useAuth()

  const [error, setError] = useState<string | null>(null)

  const code = searchParams.get("code")
  const state = searchParams.get("state") || ""
  const missingCode = code === null

  useEffect(() => {
    if (!code) return

    const redirectUri = `${window.location.origin}/${locale}/auth/callback`
    authApi
      .googleCallback(code, state, redirectUri)
      .then((res) => {
        login(res.access_token, res.user)
        router.push(`/${locale}/`)
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "OAuth authentication failed.")
      })
  }, [code, state, locale, login, router])

  return (
    <div className="mx-auto max-w-md space-y-6 py-12 text-center">
      {error || missingCode ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-6 space-y-4">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-red-100 text-red-600">
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>
          <h2 className="text-lg font-semibold text-red-900">Sign-in Error</h2>
          <p className="text-sm text-red-700">
            {error ?? "No authorization code received from provider."}
          </p>
          <button
            onClick={() => router.push(`/${locale}/auth/login`)}
            className="rounded-lg bg-red-700 px-4 py-2 text-sm font-semibold text-white hover:bg-red-800"
          >
            Back to Login
          </button>
        </div>
      ) : (
        <div className="rounded-xl border border-stone-200 bg-white p-8 space-y-4 shadow-sm">
          <div className="mx-auto h-10 w-10 animate-spin rounded-full border-3 border-(--color-primary) border-t-transparent" />
          <h2 className="text-lg font-semibold text-stone-900">Completing Sign-In</h2>
          <p className="text-sm text-stone-600">Authenticating your profile securely...</p>
        </div>
      )}
    </div>
  )
}
