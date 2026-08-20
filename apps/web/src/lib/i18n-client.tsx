"use client"

import { createContext, useCallback, useContext } from "react"

import { DICTIONARIES, en, type Locale, type TFunction } from "./i18n"

export const localeContext = createContext<Locale>("en")

export function useLocale(): Locale {
  return useContext(localeContext)
}

export function useT(): TFunction {
  const locale = useContext(localeContext)
  return useCallback(
    (key: keyof typeof en, params?: Record<string, string>) => {
      let text: string = DICTIONARIES[locale][key] || en[key]
      if (params) {
        for (const [name, value] of Object.entries(params)) {
          text = text.replaceAll(`{${name}}`, value)
        }
      }
      return text
    },
    [locale],
  )
}
