import { NextResponse, type NextRequest } from "next/server";

export const LOCALES = ["en","hi","bn","te","mr","ta","gu","kn","ml","or","pa","as","ur","mai","sd"] as const;
export type Locale = (typeof LOCALES)[number];
export const DEFAULT_LOCALE: Locale = "hi";

/**
 * Locale routing (Next 16 proxy = the old middleware slot).
 * - "/"                    → 307 to "/en"
 * - "/hi|/en/..."          → pass through (path prefix stays in the URL)
 * - other locales/unknown  → 307 to "/en"
 */
export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const first = pathname.split("/")[1] ?? "";

  if (!first) {
    const url = request.nextUrl.clone();
    url.pathname = `/${DEFAULT_LOCALE}`;
    return NextResponse.redirect(url);
  }
  if ((LOCALES as readonly string[]).includes(first)) {
    return NextResponse.next();
  }
  const url = request.nextUrl.clone();
  url.pathname = `/${DEFAULT_LOCALE}${pathname}`;
  return NextResponse.redirect(url);
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|manifest.webmanifest|sw.js|icons/|api/).*)",
  ],
};