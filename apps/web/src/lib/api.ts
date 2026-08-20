/** Typed client for the tk_api (API.md conventions, RFC 9457 errors). */

export interface ApiErrorBody {
  type?: string
  title?: string
  status?: number
  detail?: string
  errors?: Array<{ field?: string; reason?: string }>
}

export class ApiError extends Error {
  status: number
  body: ApiErrorBody

  constructor(status: number, body: ApiErrorBody) {
    super(body.detail ?? body.title ?? `HTTP ${status}`)
    this.name = "ApiError"
    this.status = status
    this.body = body
  }
}

const TOKEN_KEY = "tk_access_token"

export function getToken(): string | null {
  if (typeof window === "undefined") return null
  return window.localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string | null): void {
  if (typeof window === "undefined") return
  if (token) window.localStorage.setItem(TOKEN_KEY, token)
  else window.localStorage.removeItem(TOKEN_KEY)
}

export interface RequestOptions {
  headers?: Record<string, string>
  signal?: AbortSignal
  params?: Record<string, string | number | boolean | null | undefined>
}

export function buildQueryString(params?: Record<string, string | number | boolean | null | undefined>): string {
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

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  options?: RequestOptions,
): Promise<T> {
  const headers: Record<string, string> = { ...options?.headers }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  if (body !== undefined) headers["Content-Type"] = "application/json"

  const url = `/api/v1${path}${buildQueryString(options?.params)}`

  const response = await fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal: options?.signal,
  })

  if (!response.ok) {
    let parsed: ApiErrorBody = {}
    try {
      parsed = (await response.json()) as ApiErrorBody
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(response.status, parsed)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const api = {
  get: <T>(path: string, options?: RequestOptions) => request<T>("GET", path, undefined, options),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>("POST", path, body, options),
  patch: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>("PATCH", path, body, options),
  put: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>("PUT", path, body, options),
  delete: <T>(path: string, options?: RequestOptions) => request<T>("DELETE", path, undefined, options),
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