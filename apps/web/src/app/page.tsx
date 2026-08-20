import { redirect } from "next/navigation"

/** Root path is handled by the locale proxy (→ DEFAULT_LOCALE). This page is
 *  a safety net so a crawler or direct hit never sees boilerplate content. */
export default function Home() {
  redirect("/hi")
}