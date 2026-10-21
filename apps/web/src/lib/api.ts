/** Typed client for the tk_api (API.md conventions, RFC 9457 errors).
 * Modern 2026 edition: retry, timeout, offline detection, dedup, correlation.
 */

export interface ApiErrorBody {
  type?: string
  title?: string
  status?: number
  detail?: string
  errors?: Array<{ field?: string; reason?: string }>
  instance?: string
  request_id?: string
}

export class ApiError extends Error {
  status: number
  body: ApiErrorBody
  requestId?: string

  constructor(status: number, body: ApiErrorBody) {
    super(body.detail ?? body.title ?? `HTTP ${status}`)
    this.name = "ApiError"
    this.status = status
    this.body = body
    this.requestId = body.request_id
  }

  get isAuthError(): boolean {
    return this.status === 401 || this.status === 403
  }
  get isRateLimited(): boolean {
    return this.status === 429
  }
  get isServerError(): boolean {
    return this.status >= 500
  }
  get isNotFound(): boolean {
    return this.status === 404
  }
  get fieldErrors(): Record<string, string> {
    const out: Record<string, string> = {}
    for (const e of this.body.errors ?? []) {
      if (e.field) out[e.field] = e.reason ?? "invalid"
    }
    return out
  }
  toUserMessage(): string {
    if (this.body.detail) return this.body.detail
    if (this.body.title) return this.body.title
    if (this.status === 429) return "Too many requests. Please wait and try again."
    if (this.status >= 500) return "Server is temporarily unavailable. Please retry."
    if (this.status === 401) return "Please sign in to continue."
    if (this.status === 403) return "You don't have permission for this action."
    return `Request failed (${this.status})`
  }
}

const TOKEN_KEY = "tk_access_token"
const REFRESH_KEY = "tk_refresh_token"

export function getToken(): string | null {
  if (typeof window === "undefined") return null
  return window.localStorage.getItem(TOKEN_KEY)
}
export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null
  return window.localStorage.getItem(REFRESH_KEY)
}
export function setToken(token: string | null): void {
  if (typeof window === "undefined") return
  if (token) window.localStorage.setItem(TOKEN_KEY, token)
  else window.localStorage.removeItem(TOKEN_KEY)
}
export function setRefreshToken(token: string | null): void {
  if (typeof window === "undefined") return
  if (token) window.localStorage.setItem(REFRESH_KEY, token)
  else window.localStorage.removeItem(REFRESH_KEY)
}
export function clearAuthTokens(): void {
  setToken(null)
  setRefreshToken(null)
}

export interface RequestOptions {
  headers?: Record<string, string>
  signal?: AbortSignal
  params?: Record<string, string | number | boolean | null | undefined>
  timeoutMs?: number
  retries?: number
  idempotencyKey?: string
  skipAuth?: boolean
}

export function buildQueryString(
  params?: Record<string, string | number | boolean | null | undefined>,
): string {
  if (!params) return ""
  const searchParams = new URLSearchParams()
  for (const [key, val] of Object.entries(params)) {
    if (val !== undefined && val !== null && val !== "") {
      searchParams.append(key, String(val))
    }
  }
  const qs = searchParams.toString()
  return qs ? `?${qs}` : ""
}

// --- correlation + dedup + offline helpers ---
function correlationId(): string {
  try {
    return crypto.randomUUID()
  } catch {
    return Math.random().toString(36).slice(2)
  }
}

const inFlight = new Map<string, Promise<unknown>>()

function dedupeKey(method: string, url: string, body?: unknown): string {
  return `${method}:${url}:${body ? JSON.stringify(body) : ""}`
}

function isOnline(): boolean {
  if (typeof navigator === "undefined") return true
  return navigator.onLine
}

async function sleep(ms: number): Promise<void> {
  await new Promise((r) => setTimeout(r, ms))
}

async function requestWithTimeout(
  input: RequestInfo | URL,
  init: RequestInit & { timeoutMs?: number },
): Promise<Response> {
  const ms = init.timeoutMs ?? 15000
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(new DOMException("Timeout", "TimeoutError")), ms)
  const signal = init.signal
    ? signalAny([init.signal, controller.signal])
    : controller.signal
  try {
    return await fetch(input, { ...init, signal })
  } finally {
    clearTimeout(timer)
  }
}

function signalAny(signals: AbortSignal[]): AbortSignal {
  const c = new AbortController()
  for (const s of signals) {
    if (s.aborted) {
      c.abort(s.reason)
      break
    }
    s.addEventListener("abort", () => c.abort(s.reason), { once: true })
  }
  return c.signal
}

// --- core request with retry, refresh, dedup ---
let refreshPromise: Promise<boolean> | null = null

async function tryRefresh(): Promise<boolean> {
  if (refreshPromise) return refreshPromise
  const refreshToken = getRefreshToken()
  if (!refreshToken) return false
  refreshPromise = (async () => {
    try {
      const res = await fetch("/api/v1/auth/refresh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      })
      if (!res.ok) {
        clearAuthTokens()
        return false
      }
      const data = (await res.json()) as { access_token?: string; refresh_token?: string }
      if (data.access_token) setToken(data.access_token)
      if (data.refresh_token) setRefreshToken(data.refresh_token)
      return true
    } catch {
      return false
    } finally {
      refreshPromise = null
    }
  })()
  return refreshPromise
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  options?: RequestOptions,
): Promise<T> {
  const headers: Record<string, string> = { ...options?.headers }
  if (!options?.skipAuth) {
    const token = getToken()
    if (token) headers.Authorization = `Bearer ${token}`
  }
  if (body !== undefined) headers["Content-Type"] = "application/json"
  headers["X-Correlation-ID"] = correlationId()
  headers["X-Request-ID"] = headers["X-Correlation-ID"]
  if (options?.idempotencyKey) headers["Idempotency-Key"] = options.idempotencyKey

  const url = `/api/v1${path}${buildQueryString(options?.params)}`

  // offline fast-fail for mutations
  if (!isOnline() && method !== "GET") {
    throw new ApiError(0, {
      title: "Offline",
      detail: "You appear to be offline. Please check your connection and retry.",
      status: 0,
      type: "https://api.theekkar.in/errors/offline",
    })
  }

  const key = dedupeKey(method, url, body)
  // GET dedup within 1s window
  if (method === "GET" && inFlight.has(key)) {
    return inFlight.get(key) as Promise<T>
  }

  const maxRetries = options?.retries ?? (method === "GET" ? 2 : 0)

  const exec = async (attempt: number): Promise<T> => {
    let response: Response
    try {
      response = await requestWithTimeout(url, {
        method,
        headers,
        body: body !== undefined ? JSON.stringify(body) : undefined,
        signal: options?.signal,
        timeoutMs: options?.timeoutMs,
      })
    } catch (err) {
      const isAbort =
        err instanceof DOMException && (err.name === "AbortError" || err.name === "TimeoutError")
      if (isAbort && options?.signal?.aborted) throw err
      if (isAbort) {
        throw new ApiError(0, {
          title: "Timeout",
          detail: "Request timed out. Please retry.",
          status: 0,
        })
      }
      if (attempt < maxRetries) {
        await sleep(300 * Math.pow(2, attempt))
        return exec(attempt + 1)
      }
      throw new ApiError(0, {
        title: "Network error",
        detail: "Network unavailable. Please check connection.",
        status: 0,
      })
    }

    // handle 401 with refresh once
    if (response.status === 401 && !options?.skipAuth && getRefreshToken()) {
      const refreshed = await tryRefresh()
      if (refreshed) {
        const newToken = getToken()
        if (newToken) headers.Authorization = `Bearer ${newToken}`
        // retry once without further refresh loop
        const retryRes = await requestWithTimeout(url, {
          method,
          headers,
          body: body !== undefined ? JSON.stringify(body) : undefined,
          signal: options?.signal,
          timeoutMs: options?.timeoutMs,
        })
        response = retryRes
      }
    }

    if (!response.ok) {
      let parsed: ApiErrorBody = {}
      try {
        parsed = (await (response as unknown as { json: () => Promise<ApiErrorBody> }).json()) as ApiErrorBody
      } catch {
        parsed = { title: (response as unknown as { statusText?: string }).statusText ?? "Error", status: response.status }
      }
      // enrich with header request id (mock-safe)
      const rid =
        (response.headers as unknown as { get?: (k: string) => string | null })?.get?.("x-correlation-id") ??
        (response.headers as unknown as { get?: (k: string) => string | null })?.get?.("x-request-id") ??
        null
      if (rid && !parsed.request_id) parsed.request_id = rid

      // retry on 5xx / 429 with backoff for GET
      if (
        attempt < maxRetries &&
        (response.status >= 500 || response.status === 429) &&
        method === "GET"
      ) {
        const ra = (response.headers as unknown as { get?: (k: string) => string | null })?.get?.("retry-after")
        const waitMs = ra ? Number(ra) * 1000 : 400 * Math.pow(2, attempt)
        await sleep(Math.min(waitMs, 5000))
        return exec(attempt + 1)
      }

      throw new ApiError(response.status, parsed)
    }
    if (response.status === 204) return undefined as T
    // handle empty body gracefully — compatible with both real fetch and vitest mocks
    try {
      if (typeof (response as unknown as { text?: () => Promise<string> }).text === "function") {
        const text = await (response as unknown as { text: () => Promise<string> }).text()
        if (!text) return undefined as T
        try {
          return JSON.parse(text) as T
        } catch {
          return text as unknown as T
        }
      }
      // mock fallback: has json but no text
      if (typeof (response as unknown as { json?: () => Promise<T> }).json === "function") {
        return (await (response as unknown as { json: () => Promise<T> }).json()) as T
      }
      return undefined as T
    } catch {
      return undefined as T
    }
  }

  const promise = exec(0).finally(() => {
    if (method === "GET") setTimeout(() => inFlight.delete(key), 400)
  })
  if (method === "GET") inFlight.set(key, promise)
  return promise
}

export const api = {
  get: <T>(path: string, options?: RequestOptions) => request<T>("GET", path, undefined, options),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>("POST", path, body, options),
  patch: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>("PATCH", path, body, options),
  put: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>("PUT", path, body, options),
  delete: <T>(path: string, options?: RequestOptions) =>
    request<T>("DELETE", path, undefined, options),
  // helpers
  isOnline,
  clearAuthTokens,
}

export { geographyApi } from "@/lib/api/geography"
export { institutionsApi } from "@/lib/api/institutions"
export { civicApi } from "@/lib/api/civic"
export { reportsApi } from "@/lib/api/reports"
export { searchApi } from "@/lib/api/search"
export { gisApi } from "@/lib/api/gis"
export { govdataApi } from "@/lib/api/govdata"
export { aiApi } from "@/lib/api/ai"
export { analyticsApi } from "@/lib/api/analytics"
export {
  authApi,
  type AuthTokens,
  type LoginResponse,
  type MfaChallengeResponse,
  type MfaStatus,
  type MfaSetupResult,
  type RegisterPayload,
  type RegisterResponse,
  type UserSessionItem,
  type UserSummary,
} from "@/lib/api/auth"
export { communityApi } from "@/lib/api/community"
export { dataTrustApi } from "@/lib/api/data-trust"
export { publicDataApi } from "@/lib/api/public-data"
export type {
  DataConflict,
  DataQualitySummary,
  DataTrustDashboard,
  DisputeRecord,
  EvidenceRecord,
  MetricDefinition,
  ProvenanceChain,
  VerificationRecord,
} from "@/lib/api/data-trust"
export type {
  ExplorerRecord,
  PublicDataset,
  PublicDatasetDetail,
} from "@/lib/api/public-data"
export type {
  Badge,
  BadgeProgress,
  CommunityGroup,
  Initiative,
  Observation,
  VolunteerOpportunity,
  VolunteerProfile,
} from "@/lib/api/community"
export { intelligenceApi } from "@/lib/api/intelligence"
export { realtimeApi, openLiveStream } from "@/lib/api/realtime"
export type {
  AnomalyItem,
  ClusterItem,
  DashboardSection,
  DataGapItem,
  ForecastRun,
  FreshnessItem,
  ImprovementItem,
  IntelligenceDashboardResponse,
  IntelligenceReport,
  IntelligenceReportDetail,
  ModelVersionItem,
  RecurringIssueItem,
  ResolutionIntelligenceResponse,
  SignalAction,
  SignalDetail,
  SignalRead,
  TrendAnalysisItem,
  TrendAnalysisResponse,
} from "@/lib/api/intelligence"
