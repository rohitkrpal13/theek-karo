"use client"

import Link from "next/link"
import { useParams, useRouter } from "next/navigation"
import { useState } from "react"

import { authApi, type AuthTokens, type MfaChallengeResponse } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { useT } from "@/lib/i18n-client"
import { useRef } from "react"

type LoginMode = "password" | "otp"

export function LoginForm() {
  const t = useT()
  const router = useRouter()
  const params = useParams<{ locale?: string }>()
  const locale = params.locale ?? "en"
  const { login } = useAuth()
  const cooldownTimer = useRef<number | null>(null)

  const [mode, setMode] = useState<LoginMode>("password")
  const [contact, setContact] = useState("")
  const [password, setPassword] = useState("")
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [oauthLoading, setOauthLoading] = useState(false)
  // OTP login: contact -> request code -> verify code
  const [otpSent, setOtpSent] = useState(false)
  const [otpCode, setOtpCode] = useState("")
  const [otpCooldown, setOtpCooldown] = useState(0)
  // MFA challenge step (Phase 16): after a valid password, users with TOTP
  // enabled must supply a 6-digit authenticator code before receiving tokens.
  const [challengeToken, setChallengeToken] = useState<string | null>(null)
  const [mfaCode, setMfaCode] = useState("")

  function applyTokens(body: AuthTokens) {
    login(body.access_token, body.user)
    router.push(`/${locale}/`)
  }

  /** Shared MFA handling for both password and OTP logins. */
  function handleChallenge(body: MfaChallengeResponse) {
    setChallengeToken(body.challenge_token)
  }

  function startResendCooldown() {
    if (cooldownTimer.current) window.clearInterval(cooldownTimer.current)
    setOtpCooldown(30)
    cooldownTimer.current = window.setInterval(() => {
      setOtpCooldown((c) => Math.max(0, c - 1))
    }, 1000)
  }

  async function submitPassword(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setPending(true)
    try {
      const body = await authApi.login(contact, password)
      if ("mfa_required" in body) handleChallenge(body)
      else applyTokens(body)
    } catch (e) {
      setError(e instanceof Error ? e.message : t("auth.error.invalid"))
    } finally {
      setPending(false)
    }
  }

  async function sendLoginOtp(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setPending(true)
    try {
      await authApi.loginOtp(contact)
      setOtpSent(true)
      startResendCooldown()
    } catch (e) {
      setError(e instanceof Error ? e.message : t("auth.error.general"))
    } finally {
      setPending(false)
    }
  }

  async function submitOtp(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setPending(true)
    try {
      const body = await authApi.verifyOtp(contact, otpCode)
      if ("mfa_required" in body) handleChallenge(body)
      else applyTokens(body)
    } catch (e) {
      setError(e instanceof Error ? e.message : t("auth.error.general"))
    } finally {
      setPending(false)
    }
  }

  async function resendOtp() {
    setError(null)
    setPending(true)
    try {
      await authApi.resendOtp(contact)
      startResendCooldown()
    } catch (e) {
      setError(e instanceof Error ? e.message : t("auth.error.general"))
    } finally {
      setPending(false)
    }
  }

  async function submitMfa(event: React.FormEvent) {
    event.preventDefault()
    if (!challengeToken) return
    setError(null)
    setPending(true)
    try {
      const body = await authApi.verifyMfa(challengeToken, mfaCode)
      applyTokens(body)
    } catch (e) {
      setError(e instanceof Error ? e.message : t("auth.error.general"))
    } finally {
      setPending(false)
    }
  }

  async function handleGoogleLogin() {
    setOauthLoading(true)
    try {
      const redirectUri = `${window.location.origin}/${locale}/auth/callback`
      const res = await authApi.getGoogleAuthUrl(redirectUri)
      if (res.url) {
        window.location.href = res.url
      }
    } catch {
      setError(t("auth.google.failed"))
      setOauthLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <button
        type="button"
        onClick={handleGoogleLogin}
        disabled={oauthLoading || pending}
        className="flex w-full items-center justify-center gap-3 rounded-lg border border-stone-300 bg-white px-4 py-2.5 font-medium text-stone-700 shadow-sm transition hover:bg-stone-50 disabled:opacity-60"
      >
        <svg className="h-5 w-5" viewBox="0 0 24 24">
          <path
            fill="#4285F4"
            d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
          />
          <path
            fill="#34A853"
            d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
          />
          <path
            fill="#FBBC05"
            d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
          />
          <path
            fill="#EA4335"
            d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
          />
        </svg>
        <span>{oauthLoading ? t("auth.google.connecting") : t("auth.google.continue")}</span>
      </button>

      <div className="relative flex items-center justify-center">
        <div className="w-full border-t border-stone-200" />
        <span className="absolute bg-white px-3 text-xs font-medium uppercase text-stone-400">
          {t("auth.orPassword")}
        </span>
      </div>

      <div
        role="tablist"
        aria-label="Sign in method"
        className="grid grid-cols-2 rounded-lg border border-stone-200 p-1"
      >
        <button
          type="button"
          role="tab"
          aria-selected={mode === "password"}
          onClick={() => setMode("password")}
          className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
            mode === "password" ? "bg-(--color-primary) text-white" : "text-stone-600 hover:bg-stone-100"
          }`}
        >
          {t("auth.tab.password")}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === "otp"}
          onClick={() => setMode("otp")}
          className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
            mode === "otp" ? "bg-(--color-primary) text-white" : "text-stone-600 hover:bg-stone-100"
          }`}
        >
          {t("auth.tab.otp")}
        </button>
      </div>

      {mode === "password" ? (
        <form onSubmit={submitPassword} className="space-y-4" aria-label="Log in with password">
          <label className="block">
            <span className="text-sm font-medium text-stone-700">{t("auth.contact")}</span>
            <input
              value={contact}
              onChange={(e) => setContact(e.target.value)}
              required
              autoComplete="username"
              placeholder={t("auth.contact.placeholder")}
              className="mt-1 w-full rounded-lg border border-stone-300 px-3.5 py-2.5 text-sm transition focus:border-(--color-primary) focus:outline-none focus:ring-1 focus:ring-(--color-primary)"
            />
          </label>

          <label className="block">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-stone-700">{t("auth.password")}</span>
              <Link
                href={`/${locale}/forgot-password`}
                className="text-xs font-medium text-(--color-primary) hover:underline"
              >
                Forgot password?
              </Link>
            </div>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              placeholder="••••••••"
              className="mt-1 w-full rounded-lg border border-stone-300 px-3.5 py-2.5 text-sm transition focus:border-(--color-primary) focus:outline-none focus:ring-1 focus:ring-(--color-primary)"
            />
          </label>

          {error && (
            <div role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700 border border-red-200">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={pending}
            className="w-full rounded-lg bg-(--color-primary) px-4 py-2.5 font-semibold text-white shadow-sm transition hover:bg-(--color-primary-strong) disabled:opacity-60"
          >
            {pending ? "Signing in..." : t("auth.login")}
          </button>

          <p className="text-center text-sm text-stone-600">
            {t("auth.noAccount")}{" "}
            <Link href={`/${locale}/auth/register`} className="font-semibold text-(--color-primary) hover:underline">
              {t("auth.register")}
            </Link>
          </p>
        </form>
      ) : (
        <form
          onSubmit={otpSent ? submitOtp : sendLoginOtp}
          className="space-y-4"
          aria-label="Log in with a one-time code"
        >
          {!otpSent ? (
            <>
              <label className="block">
                <span className="text-sm font-medium text-stone-700">{t("auth.contact")}</span>
                <input
                  value={contact}
                  onChange={(e) => setContact(e.target.value)}
                  required
                  autoComplete="username"
                  placeholder={t("auth.contact.placeholder")}
                  className="mt-1 w-full rounded-lg border border-stone-300 px-3.5 py-2.5 text-sm transition focus:border-(--color-primary) focus:outline-none focus:ring-1 focus:ring-(--color-primary)"
                />
              </label>
              {error && (
                <div role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700 border border-red-200">
                  {error}
                </div>
              )}
              <button
                type="submit"
                disabled={pending}
                className="w-full rounded-lg bg-(--color-primary) px-4 py-2.5 font-semibold text-white shadow-sm transition hover:bg-(--color-primary-strong) disabled:opacity-60"
              >
                {pending ? "Sending..." : t("auth.sendOtp")}
              </button>
            </>
          ) : (
            <>
              <div className="rounded-lg border border-blue-100 bg-blue-50/70 p-3 text-sm text-blue-900">
                {t("auth.otpSent", { contact })}{" "}
                <button
                  type="button"
                  onClick={resendOtp}
                  disabled={pending || otpCooldown > 0}
                  className="font-medium text-(--color-primary) underline disabled:text-stone-400 disabled:no-underline"
                >
                  {otpCooldown > 0 ? `${otpCooldown}s` : t("auth.resendOtp")}
                </button>
              </div>
              <label className="block">
                <span className="text-sm font-medium text-stone-700">{t("auth.otp")}</span>
                <input
                  value={otpCode}
                  onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  pattern="[0-9]{6}"
                  required
                  placeholder="••••••"
                  className="mt-1 w-full rounded-lg border border-stone-300 px-3.5 py-2.5 text-center font-mono text-lg tracking-widest transition focus:border-(--color-primary) focus:outline-none focus:ring-1 focus:ring-(--color-primary)"
                />
              </label>
              {error && (
                <div role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700 border border-red-200">
                  {error}
                </div>
              )}
              <button
                type="submit"
                disabled={pending || otpCode.length !== 6}
                className="w-full rounded-lg bg-(--color-primary) px-4 py-2.5 font-semibold text-white shadow-sm transition hover:bg-(--color-primary-strong) disabled:opacity-60"
              >
                {pending ? "Verifying..." : t("auth.verify.andSignIn")}
              </button>
              <button
                type="button"
                onClick={() => {
                  setOtpSent(false)
                  setOtpCode("")
                }}
                className="w-full text-center text-sm text-stone-600 hover:underline"
              >
                Back
              </button>
            </>
          )}

          <p className="text-center text-sm text-stone-600">
            {t("auth.noAccount")}{" "}
            <Link href={`/${locale}/auth/register`} className="font-semibold text-(--color-primary) hover:underline">
              {t("auth.register")}
            </Link>
          </p>
        </form>
      )}

      {challengeToken && (
        <form onSubmit={submitMfa} className="space-y-4" aria-label="Two-factor authentication">
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
            {t("auth.mfa.hint")}
          </div>
          <label className="block">
            <span className="text-sm font-medium text-stone-700">Authenticator code</span>
            <input
              value={mfaCode}
              onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              inputMode="numeric"
              autoComplete="one-time-code"
              pattern="[0-9]{6}"
              required
              placeholder="••••••"
              className="mt-1 w-full rounded-lg border border-stone-300 px-3.5 py-2.5 text-sm transition focus:border-(--color-primary) focus:outline-none focus:ring-1 focus:ring-(--color-primary)"
            />
          </label>
          <button
            type="submit"
            disabled={pending || mfaCode.length !== 6}
            className="w-full rounded-lg bg-(--color-primary) px-4 py-2.5 font-semibold text-white shadow-sm transition hover:bg-(--color-primary-strong) disabled:opacity-60"
          >
            {pending ? "Verifying..." : t("auth.verify")}
          </button>
          <button
            type="button"
            onClick={() => setChallengeToken(null)}
            className="w-full text-center text-sm text-stone-600 hover:underline"
          >
            Back
          </button>
        </form>
      )}
    </div>
  )
}