"use client"

import Link from "next/link"
import { useParams, useRouter } from "next/navigation"
import { useRef, useState } from "react"

import { authApi } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { useT } from "@/lib/i18n-client"

type ContactKind = "email" | "phone"

const IS_DEV = process.env.NEXT_PUBLIC_APP_ENV !== "production"

export function RegisterForm() {
  const t = useT()
  const router = useRouter()
  const params = useParams<{ locale?: string }>()
  const locale = params.locale ?? "en"
  const { login } = useAuth()

  const [contactKind, setContactKind] = useState<ContactKind>("phone")
  const [contact, setContact] = useState("")
  const [displayName, setDisplayName] = useState("")
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [consent, setConsent] = useState(false)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [verifyPending, setVerifyPending] = useState<{
    contact: string
    masked: string
    isEmail: boolean
    devToken?: string
    devCode?: string
  } | null>(null)
  const [otpCode, setOtpCode] = useState("")
  const [otpCooldown, setOtpCooldown] = useState(0)
  const cooldownTimer = useRef<number | null>(null)
  const [oauthLoading, setOauthLoading] = useState(false)

  function startResendCooldown() {
    if (cooldownTimer.current) window.clearInterval(cooldownTimer.current)
    setOtpCooldown(30)
    cooldownTimer.current = window.setInterval(() => {
      setOtpCooldown((c) => Math.max(0, c - 1))
    }, 1000)
  }

  async function handleGoogleRegister() {
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

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    if (!consent) {
      setError(t("auth.error.consent"))
      return
    }
    setPending(true)
    try {
      const body = await authApi.register({
        contact,
        display_name: displayName,
        username: username.trim() || undefined,
        password,
        consent: true,
        terms_version: "2026-v1",
        locale,
      })
      const isEmail = contactKind === "email"
      setVerifyPending({
        contact,
        masked: body.contact_masked,
        isEmail,
        devToken: body.dev_verification_token,
        devCode: body.dev_otp_code,
      })
      if (!isEmail) startResendCooldown()
    } catch (e) {
      setError(e instanceof Error ? e.message : t("auth.error.general"))
    } finally {
      setPending(false)
    }
  }

  async function onVerifyOtp(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setPending(true)
    try {
      const contact = verifyPending?.contact ?? ""
      const body = await authApi.verifyOtp(contact, otpCode)
      if ("mfa_required" in body) {
        setError(t("auth.error.general"))
        return
      }
      login(body.access_token, body.user)
      router.push(`/${locale}/`)
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
      await authApi.resendOtp(verifyPending?.contact ?? contact)
      startResendCooldown()
    } catch (e) {
      setError(e instanceof Error ? e.message : t("auth.error.general"))
    } finally {
      setPending(false)
    }
  }

  if (verifyPending) {
    return (
      <div className="space-y-5">
        <div className="rounded-xl border border-blue-100 bg-blue-50/70 p-4 text-sm text-blue-900">
          <h3 className="font-semibold text-blue-950">
            {verifyPending.isEmail ? t("auth.checkEmail") : t("auth.checkPhone")}
          </h3>
          <p className="mt-1 text-blue-800">
            {verifyPending.isEmail
              ? t("auth.verifySteps", { contact: verifyPending.masked })
              : t("auth.code.sentTo", { contact: verifyPending.masked })}
          </p>
        </div>

        {IS_DEV && verifyPending.devToken && (
          <div className="rounded-lg bg-amber-50 p-3 text-xs text-amber-900 border border-amber-200">
            <span className="font-semibold">Dev Verification Link:</span>{" "}
            <Link
              href={`/${locale}/verify-email?token=${verifyPending.devToken}`}
              className="text-amber-800 underline font-mono break-all"
            >
              Verify Now ({verifyPending.devToken.slice(0, 12)}...)
            </Link>
          </div>
        )}

        {!verifyPending.isEmail && (
          <form onSubmit={onVerifyOtp} className="space-y-4">
            {IS_DEV && verifyPending.devCode && (
              <p className="rounded bg-amber-50 p-2 text-xs text-amber-900 font-mono">
                Dev OTP: {verifyPending.devCode}
              </p>
            )}
            <label className="block">
              <span className="text-sm font-medium text-stone-700">{t("auth.otp")}</span>
              <input
                value={otpCode}
                onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                inputMode="numeric"
                autoComplete="one-time-code"
                pattern="[0-9]{6}"
                required
                className="mt-1 w-full rounded-lg border border-stone-300 px-3.5 py-2.5 text-center font-mono text-lg tracking-widest transition focus:border-(--color-primary) focus:outline-none focus:ring-1 focus:ring-(--color-primary)"
              />
            </label>
            {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
            <button
              type="submit"
              disabled={pending || otpCode.length !== 6}
              className="w-full rounded-lg bg-(--color-primary) px-4 py-2.5 font-semibold text-white shadow-sm transition hover:bg-(--color-primary-strong) disabled:opacity-60"
            >
              {pending ? "Verifying..." : t("auth.verify.andSignIn")}
            </button>
            <button
              type="button"
              onClick={resendOtp}
              disabled={pending || otpCooldown > 0}
              className="w-full text-center text-sm text-(--color-primary) hover:underline disabled:text-stone-400 disabled:no-underline"
            >
              {otpCooldown > 0 ? `${t("auth.resendOtp")} (${otpCooldown}s)` : t("auth.resendOtp")}
            </button>
          </form>
        )}

        <p className="text-center text-sm text-stone-600">
          {t("auth.hasAccount")}{" "}
          <Link href={`/${locale}/auth/login`} className="font-semibold text-(--color-primary) hover:underline">
            {t("auth.login")}
          </Link>
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <button
        type="button"
        onClick={handleGoogleRegister}
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
        <span>{oauthLoading ? t("auth.google.connecting") : t("auth.google.signup")}</span>
      </button>

      <div className="relative flex items-center justify-center">
        <div className="w-full border-t border-stone-200" />
        <span className="absolute bg-white px-3 text-xs font-medium uppercase text-stone-400">
          {contactKind === "email" ? t("auth.orEmail") : t("auth.orPhone")}
        </span>
      </div>

      <div
        role="tablist"
        aria-label="Registration method"
        className="grid grid-cols-2 rounded-lg border border-stone-200 p-1"
      >
        <button
          type="button"
          role="tab"
          aria-selected={contactKind === "phone"}
          onClick={() => setContactKind("phone")}
          className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
            contactKind === "phone" ? "bg-(--color-primary) text-white" : "text-stone-600 hover:bg-stone-100"
          }`}
        >
          {t("auth.phone")}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={contactKind === "email"}
          onClick={() => setContactKind("email")}
          className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
            contactKind === "email" ? "bg-(--color-primary) text-white" : "text-stone-600 hover:bg-stone-100"
          }`}
        >
          {t("auth.email")}
        </button>
      </div>

      <form onSubmit={onSubmit} className="space-y-4" aria-label="Register">
        <label className="block">
          <span className="text-sm font-medium text-stone-700">{t("auth.name")}</span>
          <input
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            required
            placeholder="e.g. Priya Patel"
            className="mt-1 w-full rounded-lg border border-stone-300 px-3.5 py-2.5 text-sm transition focus:border-(--color-primary) focus:outline-none focus:ring-1 focus:ring-(--color-primary)"
          />
        </label>

        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="text-sm font-medium text-stone-700">{t("auth.contact")}</span>
            <input
              type={contactKind === "email" ? "email" : "tel"}
              value={contact}
              onChange={(e) => setContact(e.target.value)}
              required
              autoComplete={contactKind === "email" ? "email" : "tel"}
              placeholder={contactKind === "email" ? "priya@example.com" : "+919876543210"}
              className="mt-1 w-full rounded-lg border border-stone-300 px-3.5 py-2.5 text-sm transition focus:border-(--color-primary) focus:outline-none focus:ring-1 focus:ring-(--color-primary)"
            />
          </label>

          <label className="block">
            <span className="text-sm font-medium text-stone-700">
              {t("auth.username")} <span className="text-xs text-stone-400">({t("auth.username.optional")})</span>
            </span>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ""))}
              maxLength={30}
              placeholder="priya_patel"
              className="mt-1 w-full rounded-lg border border-stone-300 px-3.5 py-2.5 text-sm transition focus:border-(--color-primary) focus:outline-none focus:ring-1 focus:ring-(--color-primary)"
            />
          </label>
        </div>

        <label className="block">
          <span className="text-sm font-medium text-stone-700">{t("auth.password")}</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={8}
            required
            autoComplete="new-password"
            placeholder={t("auth.password.hint")}
            className="mt-1 w-full rounded-lg border border-stone-300 px-3.5 py-2.5 text-sm transition focus:border-(--color-primary) focus:outline-none focus:ring-1 focus:ring-(--color-primary)"
          />
        </label>

        <label className="flex items-start gap-3 text-sm text-stone-600">
          <input
            type="checkbox"
            checked={consent}
            onChange={(e) => setConsent(e.target.checked)}
            className="mt-1 h-4 w-4 rounded border-stone-300 text-(--color-primary) focus:ring-(--color-primary)"
          />
          <span>
            I agree to the{" "}
            <Link href={`/${locale}/terms`} className="text-(--color-primary) hover:underline font-medium">
              Terms of Service
            </Link>{" "}
            and{" "}
            <Link href={`/${locale}/privacy`} className="text-(--color-primary) hover:underline font-medium">
              Privacy Policy (DPDP Act)
            </Link>
            .
          </span>
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
          {pending ? "Creating Account..." : t("auth.createAccount")}
        </button>

        <p className="text-center text-sm text-stone-600">
          {t("auth.hasAccount")}{" "}
          <Link href={`/${locale}/auth/login`} className="font-semibold text-(--color-primary) hover:underline">
            {t("auth.login")}
          </Link>
        </p>
      </form>
    </div>
  )
}