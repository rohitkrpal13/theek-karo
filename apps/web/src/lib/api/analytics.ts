import { api, type RequestOptions } from "@/lib/api"
import type {
  AiOpsAnalyticsResponse,
  AnalyticsFilterParams,
  CategoryAnalyticsResponse,
  DataQualityScorecardResponse,
  ExportRequest,
  ExportResponse,
  GeographicAnalyticsResponse,
  InstitutionAnalyticsResponse,
  MetricDefinition,
  ModerationAnalyticsResponse,
  OverviewAnalyticsResponse,
  ReportTrendsResponse,
  ResolutionAnalyticsResponse,
  VerificationAndBacklogResponse,
} from "@/lib/types"

function toQueryString(params?: AnalyticsFilterParams): string {
  if (!params) return ""
  const query = new URLSearchParams()
  if (params.geography_id) query.set("geography_id", params.geography_id)
  if (params.category_slug) query.set("category_slug", params.category_slug)
  if (params.issue_type_slug) query.set("issue_type_slug", params.issue_type_slug)
  if (params.status) query.set("status", params.status)
  if (params.severity) query.set("severity", params.severity)
  if (params.institution_id) query.set("institution_id", params.institution_id)
  if (params.date_preset) query.set("date_preset", params.date_preset)
  if (params.start_date) query.set("start_date", params.start_date)
  if (params.end_date) query.set("end_date", params.end_date)
  if (params.interval) query.set("interval", params.interval)
  if (params.timezone) query.set("timezone", params.timezone)
  const qs = query.toString()
  return qs ? `?${qs}` : ""
}

export const analyticsApi = {
  /**
   * Retrieve high-level KPI cards and civic health summary.
   */
  getOverview(params?: AnalyticsFilterParams, options?: RequestOptions): Promise<OverviewAnalyticsResponse> {
    const qs = toQueryString(params)
    return api.get<OverviewAnalyticsResponse>(`/analytics/overview${qs}`, options)
  },

  /**
   * Retrieve time series trends of reports over time.
   */
  getTrends(params?: AnalyticsFilterParams, options?: RequestOptions): Promise<ReportTrendsResponse> {
    const qs = toQueryString(params)
    return api.get<ReportTrendsResponse>(`/analytics/trends${qs}`, options)
  },

  /**
   * Retrieve category breakdown and nested issue types.
   */
  getCategories(params?: AnalyticsFilterParams, options?: RequestOptions): Promise<CategoryAnalyticsResponse> {
    const qs = toQueryString(params)
    return api.get<CategoryAnalyticsResponse>(`/analytics/categories${qs}`, options)
  },

  /**
   * Retrieve resolution metrics, durations, and rates.
   */
  getResolution(params?: AnalyticsFilterParams, options?: RequestOptions): Promise<ResolutionAnalyticsResponse> {
    const qs = toQueryString(params)
    return api.get<ResolutionAnalyticsResponse>(`/analytics/resolution${qs}`, options)
  },

  /**
   * Retrieve verification backlog velocity and aging buckets.
   */
  getVerification(params?: AnalyticsFilterParams, options?: RequestOptions): Promise<VerificationAndBacklogResponse> {
    const qs = toQueryString(params)
    return api.get<VerificationAndBacklogResponse>(`/analytics/verification${qs}`, options)
  },

  /**
   * Retrieve geographic drilldown summary.
   */
  getGeography(params?: AnalyticsFilterParams, options?: RequestOptions): Promise<GeographicAnalyticsResponse> {
    const qs = toQueryString(params)
    return api.get<GeographicAnalyticsResponse>(`/analytics/geography${qs}`, options)
  },

  /**
   * Retrieve institution-specific analytics.
   */
  getInstitutionAnalytics(institutionId: string, options?: RequestOptions): Promise<InstitutionAnalyticsResponse> {
    return api.get<InstitutionAnalyticsResponse>(`/analytics/institutions/${institutionId}`, options)
  },

  /**
   * Admin/Analyst: Retrieve government data source health scorecard.
   */
  getDataQuality(options?: RequestOptions): Promise<DataQualityScorecardResponse> {
    return api.get<DataQualityScorecardResponse>("/analytics/data-quality", options)
  },

  /**
   * Admin: Retrieve AI token, cost, and latency telemetry.
   */
  getAiOps(options?: RequestOptions): Promise<AiOpsAnalyticsResponse> {
    return api.get<AiOpsAnalyticsResponse>("/analytics/ai-ops", options)
  },

  /**
   * Moderator/Admin: Retrieve moderation queue size and aging.
   */
  getModeration(options?: RequestOptions): Promise<ModerationAnalyticsResponse> {
    return api.get<ModerationAnalyticsResponse>("/analytics/moderation", options)
  },

  /**
   * Export analytics records in CSV or JSON.
   */
  exportData(request: ExportRequest, options?: RequestOptions): Promise<ExportResponse> {
    return api.post<ExportResponse>("/analytics/export", request, options)
  },

  /**
   * Retrieve metric registry catalog definitions.
   */
  getCatalog(options?: RequestOptions): Promise<{ metrics: MetricDefinition[]; count: number }> {
    return api.get<{ metrics: MetricDefinition[]; count: number }>("/analytics/catalog", options)
  },
}
