"use client"

import tokens from "@/theme/tokens"

const languageRegistry = tokens.languages

export default function LanguagesPage() {
  const sample = "ठीक करो — report a problem, follow progress. १२३"
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Language rendering check</h1>
      <p className="max-w-2xl text-sm text-(--color-ink-muted)">
        Every launch language rendered with its script-appropriate font stack (system-first). This page is a
        rendering QA surface for the 15-language registry.
      </p>
      <ol className="space-y-3">
        {languageRegistry.map((language) => (
          <li key={language.code} dir={language.script === "urdu" ? "rtl" : "ltr"} className="flex flex-wrap items-baseline gap-3 rounded-(--radius-md) border border-(--color-line) p-3">
            <span className="w-24 shrink-0 text-(--text-caption) text-(--color-ink-muted)">{language.code}</span>
            <span lang={language.code} className="text-lg">
              {language.native} — {sample}
            </span>
          </li>
        ))}
      </ol>
    </div>
  )
}
