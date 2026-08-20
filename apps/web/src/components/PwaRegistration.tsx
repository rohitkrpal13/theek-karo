"use client"

import { useEffect } from "react"

export function PwaRegistration() {
  useEffect(() => {
    if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) return
    if (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1") {
      return // dev: keep hot reload clean; production registers below
    }
    navigator.serviceWorker.register("/sw.js").catch(() => undefined)
  }, [])
  return null
}