import { t, type Locale } from "@/lib/i18n"

const GUIDELINE_KEYS = [
  "Be constructive and evidence-based: support claims with observations, photos or public sources.",
  "No harassment, personal attacks or targeted abuse of any person or group.",
  "No doxxing: never share personal contact details, home addresses or private information.",
  "No spam, promotional content or malicious links.",
  "No fabricated evidence. Community observations are not the same as platform verification.",
  "No impersonation of officials, institutions or other users.",
  "No political campaigning or partisan persuasion on the platform.",
  "Respect privacy: support for a report is a community signal, not proof.",
]

export default async function GuidelinesPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params
  const lang = locale as Locale

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-(--color-primary-strong)">{t(lang, "community.guidelines.link")}</h1>
        <p className="text-sm text-stone-500">{t(lang, "community.guidelines.short")}</p>
      </div>
      <div className="rounded-lg border border-stone-200 bg-white p-6 shadow-sm">
        <ol className="list-decimal space-y-3 pl-5 text-sm text-stone-700">
          {GUIDELINE_KEYS.map((rule, i) => (
            <li key={i}>{rule}</li>
          ))}
        </ol>
      </div>
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
        Civic principles: non-partisan, evidence-based, privacy-respecting, safe and inclusive.
        Community discussion never replaces official or platform verification.
      </div>
    </div>
  )
}
