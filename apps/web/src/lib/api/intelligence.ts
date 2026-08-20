import { api, type RequestOptions } from "@/lib/api"

/* ------------------------- Phase 20: Civic Intelligence ------------------ */

export type SignalSeverity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
export type SignalConfidence = "LOW" | "MEDIUM" | "HIGH"
export type SignalVisibility = "PUBLIC" | "COMMUNITY" | "DEPARTMENT" | "ADMIN" | "RESTRICTED"
export type SignalAction =
  | "CONFIRM"
  | "DISMISS"
  | "REQUEST_MORE_DATA"
  | "MONITOR"
  | "ESCALATE"
  | "MARK_RESOLVED"

export interface TrendComparison {
  period_label: string
  start: string | null
  end: string | null
  count: number
  change_count: number | null
  change_pct: number | null
  direction: "increasing" | "decreasing" | "stable" | "insufficient_data"
  denominator: string | null
  coverage_note: string | null
}

export interface TrendSeriesPoint {
  timestamp: string
  value: number
}

export interface TrendAnalysisItem {
  metric: string
  geography_id: string | null
  category_slug: string | null
  interval: string
  observation_period: Record<string, unknown> | null
  comparison: TrendComparison
  series: TrendSeriesPoint[]
  seasonality: Array<Record<string, unknown>>
  limitations: string[]
}

export interface TrendAnalysisResponse {
  items: TrendAnalysisItem[]
  generated_at: string
  methodology_note: string
}

export interface AnomalyItem {
  metric: string
  geography_id: string | null
  category_slug: string | null
  observed_value: number
  expected_low: number | null
  expected_high: number | null
  deviation_pct: number | null
  method: string | null
  explanation: string | null
  status: string
  detected_at: string | null
}

export interface AnomalyResponse {
  anomalies: AnomalyItem[]
  generated_at: string
  note: string
}

export interface ClusterItem {
  cluster_key: string
  label: string | null
  category_slug: string | null
  geography_id: string | null
  geography_name: string | null
  institution_id: string | null
  institution_name: string | null
  report_count: number
  evidence_count: number
  first_seen: string | null
  last_seen: string | null
  report_ids: string[]
  status: string
}

export interface ClusterResponse {
  clusters: ClusterItem[]
  observation_window_days: number
  generated_at: string
  note: string
}

export interface RecurringIssueItem {
  institution_id: string | null
  institution_name: string | null
  geography_id: string | null
  geography_name: string | null
  category_slug: string | null
  issue_type_slug: string | null
  distinct_months: number
  total_reports: number
  first_seen: string | null
  last_seen: string | null
  open_reports: number
}

export interface RecurringIssueResponse {
  items: RecurringIssueItem[]
  window_months: number
  min_distinct_months: number
  generated_at: string
  note: string
}

export interface FreshnessItem {
  scope: string
  label: string
  last_updated_at: string | null
  expected_frequency: string | null
  detail: string | null
}

export interface DataFreshnessResponse {
  items: FreshnessItem[]
  generated_at: string
}

export interface DataGapItem {
  scope: string
  total: number
  with_data: number
  without_data: number
  coverage_pct: number | null
  note: string
}

export interface DataGapResponse {
  items: DataGapItem[]
  generated_at: string
  interpretation_note: string
}

export interface AgingBucketItem {
  bucket_label: string
  count: number
  pct: number
}

export interface ResolutionIntelligenceResponse {
  total_cases: number
  avg_response_hours: number | null
  median_response_hours: number | null
  p90_response_hours: number | null
  avg_resolution_hours: number | null
  median_resolution_hours: number | null
  p90_resolution_hours: number | null
  within_sla_count: number
  at_risk_count: number
  breached_count: number
  sla_compliance_pct: number
  open_count: number
  aging_buckets: AgingBucketItem[]
  reopen_count: number
  followup_signals: number
  verified_resolution_count: number
  community_confirmed_count: number
  limitations: string[]
  generated_at: string
}

export interface ImprovementItem {
  case_no: string | null
  report_id: string | null
  institution_id: string | null
  institution_name: string | null
  title: string | null
  category_slug: string | null
  resolved_at: string | null
  verified_at: string | null
  community_confirmed_at: string | null
  evidence_count: number
  source: string
}

export interface ImprovementResponse {
  items: ImprovementItem[]
  count: number
  generated_at: string
  note: string
}

export interface ForecastPointItem {
  point: string
  low: number
  point_value: number
  high: number
}

export interface ForecastRun {
  id: string
  metric: string
  geography_id: string | null
  category_slug: string | null
  horizon_days: number
  model_version: string | null
  method: string | null
  training_start: string | null
  training_end: string | null
  status: string
  eval_metrics: Record<string, unknown> | null
  error: string | null
  created_at: string
  points: ForecastPointItem[]
}

export interface ForecastListResponse {
  runs: ForecastRun[]
  generated_at: string
  note: string
}

export interface RunForecastPayload {
  metric?: "reports" | "resolved" | "reports_per_week"
  geography_id?: string | null
  category_slug?: string | null
  horizon_days?: number
  interval?: "week" | "month"
}

export interface ModelVersionItem {
  model_name: string
  version: string
  model_type: string
  training_data_ref: string | null
  feature_definition: Record<string, unknown> | null
  evaluation_metrics: Record<string, unknown> | null
  deployed_at: string | null
  status: string
}

export interface ModelRegistryResponse {
  models: ModelVersionItem[]
  generated_at: string
}

export interface SignalRead {
  id: string
  signal_type: string
  title: string
  description: string | null
  category_slug: string | null
  geography_id: string | null
  geography_name: string | null
  institution_id: string | null
  institution_name: string | null
  severity: string
  confidence: string
  status: string
  visibility: string
  evidence_count: number
  source_count: number
  observation_period: Record<string, unknown> | null
  payload: Record<string, unknown> | null
  explanation: Record<string, unknown> | null
  detected_at: string | null
  created_at: string
  review_history: Array<{ action: string; note: string | null; created_at: string }>
}

export interface SignalListResponse {
  items: SignalRead[]
  count: number
  generated_at: string
  note: string
}

export interface SignalEvidenceItem {
  kind: string
  entity_type: string
  entity_id: string | null
  payload: Record<string, unknown> | null
  source: string
  created_at: string
}

export interface SignalSourceItem {
  source_kind: string
  source_name: string
  source_id: string | null
  dataset_version: string | null
  retrieved_at: string | null
  note: string | null
}

export interface SignalDetail extends SignalRead {
  evidence: SignalEvidenceItem[]
  sources: SignalSourceItem[]
  limitations: string[]
}

export interface ManualSignalCreate {
  signal_type: string
  title: string
  description?: string | null
  category_slug?: string | null
  geography_id?: string | null
  institution_id?: string | null
  severity?: SignalSeverity
  confidence?: SignalConfidence
  visibility?: SignalVisibility
}

export interface DashboardSection {
  key: string
  title: string
  data: Record<string, unknown>
  limitations: string[]
}

export interface IntelligenceDashboardResponse {
  generated_at: string
  geography_name: string | null
  sections: DashboardSection[]
  methodology_note: string
}

export interface MapLayerItem {
  layer: string
  geography_id: string | null
  geography_name: string | null
  geography_type: string | null
  value: number
  count: number
  denominator: string | null
  normalized: number | null
  detail: Record<string, unknown>
  caveat: string | null
}

export interface IntelligenceMapResponse {
  layer: string
  explanation: string
  items: MapLayerItem[]
  generated_at: string
  note: string
}

export interface IntelligenceReport {
  id: string
  title: string
  scope: string
  geography_id: string | null
  filters: Record<string, unknown> | null
  status: string
  format: string
  generated_at: string | null
  methodology: Record<string, unknown> | null
  dataset_versions: Record<string, unknown> | null
  model_versions: Record<string, unknown> | null
  created_at: string
}

export interface IntelligenceReportDetail extends IntelligenceReport {
  content: Record<string, unknown> | null
  error: string | null
}

export interface CreateIntelligenceReportPayload {
  title: string
  scope?: string
  geography_id?: string | null
  filters?: Record<string, unknown>
  format?: "json" | "csv"
}

export type IntelligenceParams = {
  geography_id?: string | null
  category_slug?: string | null
  date_preset?: string
  timezone?: string
}

export const intelligenceApi = {
  overview: (params?: IntelligenceParams, options?: RequestOptions): Promise<IntelligenceDashboardResponse> =>
    api.get<IntelligenceDashboardResponse>("/intelligence/overview", { ...options, params }),

  listSignals: (
    params: { signal_type?: string; signal_status?: string; geography_id?: string | null; limit?: number; offset?: number } = {},
    options?: RequestOptions,
  ): Promise<SignalListResponse> =>
    api.get<SignalListResponse>("/intelligence/signals", { ...options, params }),

  getSignal: (id: string, options?: RequestOptions): Promise<SignalDetail> =>
    api.get<SignalDetail>(`/intelligence/signals/${id}`, options),

  createSignal: (payload: ManualSignalCreate, options?: RequestOptions): Promise<SignalRead> =>
    api.post<SignalRead>("/intelligence/signals", payload, options),

  reviewSignal: (id: string, action: { action: SignalAction; note?: string | null }, options?: RequestOptions): Promise<SignalRead> =>
    api.post<SignalRead>(`/intelligence/signals/${id}/review`, action, options),

  trends: (params?: IntelligenceParams, options?: RequestOptions): Promise<TrendAnalysisResponse> =>
    api.get<TrendAnalysisResponse>("/intelligence/trends", { ...options, params }),

  anomalies: (params?: Pick<IntelligenceParams, "geography_id">, options?: RequestOptions): Promise<AnomalyResponse> =>
    api.get<AnomalyResponse>("/intelligence/anomalies", { ...options, params }),

  clusters: (params?: Pick<IntelligenceParams, "geography_id" | "category_slug">, options?: RequestOptions): Promise<ClusterResponse> =>
    api.get<ClusterResponse>("/intelligence/clusters", { ...options, params }),

  recurring: (params?: Pick<IntelligenceParams, "geography_id">, options?: RequestOptions): Promise<RecurringIssueResponse> =>
    api.get<RecurringIssueResponse>("/intelligence/recurring", { ...options, params }),

  resolution: (params?: Pick<IntelligenceParams, "geography_id">, options?: RequestOptions): Promise<ResolutionIntelligenceResponse> =>
    api.get<ResolutionIntelligenceResponse>("/intelligence/resolution", { ...options, params }),

  improvements: (params?: { geography_id?: string | null; limit?: number }, options?: RequestOptions): Promise<ImprovementResponse> =>
    api.get<ImprovementResponse>("/intelligence/improvements", { ...options, params }),

  freshness: (options?: RequestOptions): Promise<DataFreshnessResponse> =>
    api.get<DataFreshnessResponse>("/intelligence/freshness", options),

  dataGaps: (options?: RequestOptions): Promise<DataGapResponse> =>
    api.get<DataGapResponse>("/intelligence/data-gaps", options),

  map: (params?: { layer?: string; geography_type?: string | null; days?: number }, options?: RequestOptions): Promise<IntelligenceMapResponse> =>
    api.get<IntelligenceMapResponse>("/intelligence/map", { ...options, params }),

  listForecasts: (params?: { limit?: number }, options?: RequestOptions): Promise<ForecastListResponse> =>
    api.get<ForecastListResponse>("/intelligence/forecasts", { ...options, params }),

  runForecast: (payload: RunForecastPayload, options?: RequestOptions): Promise<ForecastRun> =>
    api.post<ForecastRun>("/intelligence/forecasts", payload, options),

  listModelVersions: (options?: RequestOptions): Promise<ModelRegistryResponse> =>
    api.get<ModelRegistryResponse>("/intelligence/model-versions", options),

  listReports: (params?: { limit?: number }, options?: RequestOptions): Promise<IntelligenceReport[]> =>
    api.get<IntelligenceReport[]>("/intelligence/reports", { ...options, params }),

  createReport: (payload: CreateIntelligenceReportPayload, options?: RequestOptions): Promise<IntelligenceReport> =>
    api.post<IntelligenceReport>("/intelligence/reports", payload, options),

  getReport: (id: string, options?: RequestOptions): Promise<IntelligenceReportDetail> =>
    api.get<IntelligenceReportDetail>(`/intelligence/reports/${id}`, options),
}
