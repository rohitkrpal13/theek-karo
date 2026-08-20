/** Shared API contract types (matching Phase 5 tk_api schemas). */

export type TrustTier = "official" | "community_verified" | "community" | "ai" | "citizen"

export interface GeoJsonPoint {
  type: "Point"
  coordinates: [number, number]
}

// ---------------------------------------------------------------------------
// Pagination & Response Wrappers
// ---------------------------------------------------------------------------

export interface PageResponse<T> {
  items: T[]
  total: number
  page: number
  limit: number
  pages: number
}

export interface CursorResponse<T> {
  items: T[]
  limit?: number
  next_cursor: string | null
  has_more?: boolean
}

// Backward compatibility alias
export interface Page<T> {
  items: T[]
  next_cursor: string | null
  limit?: number
  has_more?: boolean
}

// ---------------------------------------------------------------------------
// Geography Domain
// ---------------------------------------------------------------------------

export interface GeographyType {
  id: string
  code: string
  name_key: string
  level_order: number
  parent_type_id: string | null
  description: string | null
  is_active: boolean
}

export interface GeographyTranslation {
  id: string
  language_code: string
  name: string
  verified: boolean
}

export interface Geography {
  id: string
  type_id: string
  parent_id: string | null
  code: string
  name: string
  normalized_name: string
  country_code: string
  hierarchy_path: string | null
  source_id: string | null
  is_active: boolean
  translations?: GeographyTranslation[]
}

export interface GeographyHierarchyNode {
  id: string
  name: string
  code: string
  type_id: string
  type_code?: string
  level_order?: number
}

export interface GeographyDetail extends Geography {
  parent?: Geography | null
  ancestors: GeographyHierarchyNode[]
}

// ---------------------------------------------------------------------------
// Institutions Domain
// ---------------------------------------------------------------------------

export interface InstitutionType {
  id: string
  code: string
  name_key: string
  category_id: string | null
  default_schema: Record<string, unknown>
  description: string | null
  is_active: boolean
}

export interface InstitutionAttributeDef {
  id: string
  institution_type_id: string
  attribute_key: string
  data_type: "string" | "integer" | "float" | "boolean" | "json" | "date"
  label_key: string
  unit: string | null
  is_required: boolean
  is_filterable: boolean
  is_public: boolean
}

export interface InstitutionAttributeValue {
  id: string
  attribute_id: string
  attribute_key?: string
  label_key?: string
  value_string: string | null
  value_integer: number | null
  value_float: number | null
  value_boolean: boolean | null
  value_json: Record<string, unknown> | null
  value_date: string | null
  source_id: string | null
  confidence: number
}

export interface InstitutionTranslation {
  id: string
  language_code: string
  name: string
  description: string | null
  address: string | null
  verified: boolean
}

export interface Institution {
  id: string
  type_id: string
  official_id: string | null
  name: string
  slug: string
  description: string | null
  geography_id: string | null
  location_geojson?: GeoJsonPoint | null
  location_lat?: number | null
  location_lon?: number | null
  operational_status: "operational" | "closed" | "under_construction" | "relocated"
  verification_state: "unverified" | "official" | "community_verified"
  confidence_score: number
  source_id: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface InstitutionDetail extends Institution {
  type?: InstitutionType | null
  geography?: Geography | null
  attributes: InstitutionAttributeValue[]
  translations: InstitutionTranslation[]
}

// ---------------------------------------------------------------------------
// Civic Domain (Categories, Issue Types, Campaigns)
// ---------------------------------------------------------------------------

export interface Category {
  id: string
  slug: string
  icon: string
  form_schema: Record<string, unknown>
  verification_policy: Record<string, unknown>
  attachment_rules: Record<string, unknown>
  default_locale_keys: Record<string, string>
  form_schema_version: number
  is_active: boolean
}

export interface CategoryTranslation {
  id: string
  language_code: string
  name: string
  description: string | null
}

export interface IssueType {
  id: string
  category_id: string
  slug: string
  name_key: string
  default_severity: "low" | "medium" | "high" | "critical"
  default_sla_hours: number
  is_active: boolean
}

export interface CategoryDetail extends Category {
  translations: CategoryTranslation[]
  issue_types: IssueType[]
}

export interface CampaignScope {
  state?: string
  district?: string
  city?: string
  boundary_id?: string
}

export interface Campaign {
  id: string
  category_id: string
  slug: string
  title_key: string
  status: "planned" | "live" | "paused" | "closed"
  scope?: CampaignScope | null
  materialized_scope?: unknown
  starts_at?: string | null
  ends_at?: string | null
  created_at?: string
  updated_at?: string
}

// ---------------------------------------------------------------------------
// Reports Domain
// ---------------------------------------------------------------------------

export type ReportSeverity = "low" | "medium" | "high" | "critical"
export type ReportVisibility = "public" | "internal" | "restricted"
export type ReportStatus =
  | "draft"
  | "submitted"
  | "under_verification"
  | "verified"
  | "assigned"
  | "in_progress"
  | "resolution_submitted"
  | "resolution_review"
  | "resolved"
  | "resolution_verified"
  | "community_verified"
  | "needs_information"
  | "reopened"
  | "rejected"
  | "duplicate_merged"
  | "archived"
  | "closed"

export type CoordinateSource =
  | "USER_SELECTED"
  | "DEVICE_LOCATION"
  | "INSTITUTION_LOCATION"
  | "MAP_SELECTED"
  | "IMPORTED"

export interface Report {
  id: string
  ticket_no: string
  category_id: string
  campaign_id: string | null
  institution_id: string | null
  issue_type_id: string | null
  reporter_id: string
  title: string
  description: string
  severity: ReportSeverity
  visibility: ReportVisibility
  source: string
  location: GeoJsonPoint
  location_accuracy_m: number
  coordinate_source?: CoordinateSource | null
  observed_at?: string | null
  address_hint?: string | null
  boundary_id?: string | null
  status: ReportStatus
  info_class: string
  trust_score: number
  duplicate_of: string | null
  merged_by_ai: boolean
  fields: Record<string, unknown>
  evidence?: ReportEvidence[]
  verifications?: Verification[]
  verifications_count?: number
  confirmations_count?: number
  refutations_count?: number
  resolved_at: string | null
  created_at: string
  updated_at: string
}

export interface Verification {
  id: string
  verifier_id: string
  kind: "confirm" | "refute" | "needs_information"
  evidence: string | null
  location_independent: boolean
  trust_score?: number
  status?: ReportStatus
  created_at: string
}

export interface VerificationListResponse {
  items: Verification[]
  confirmations_count: number
  refutations_count: number
  total_count: number
}

// ---------------------------------------------------------------------------
// Phase 12: Civic Analytics, Dashboards & Decision Intelligence
// ---------------------------------------------------------------------------

export interface KpiItem {
  metric_id: string
  name: string
  value: number
  unit: string
  period_label: string
  definition: string
  source: string
  denominator_label?: string | null
  change_pct?: number | null
  trend_direction?: "up" | "down" | "flat" | null
}

export interface OverviewAnalyticsResponse {
  kpis: KpiItem[]
  generated_at: string
  data_coverage_note: string
}

export interface TimeSeriesPoint {
  timestamp: string
  total_count: number
  verified_count: number
  resolved_count: number
  critical_count: number
}

export interface ReportTrendsResponse {
  series: TimeSeriesPoint[]
  total_in_range: number
  interval: string
}

export interface IssueTypeBreakdown {
  slug: string
  name: string
  count: number
  pct: number
}

export interface CategoryAnalyticsItem {
  category_slug: string
  category_name: string
  report_count: number
  verified_count: number
  resolved_count: number
  open_count: number
  pct_of_total: number
  top_issue_types: IssueTypeBreakdown[]
}

export interface CategoryAnalyticsResponse {
  categories: CategoryAnalyticsItem[]
  total_reports: number
}

export interface AgingBucket {
  bucket_label: string
  count: number
  pct: number
}

export interface VerificationAndBacklogResponse {
  total_submitted: number
  under_verification_count: number
  verified_count: number
  needs_info_count: number
  rejected_count: number
  duplicate_count: number
  verification_rate: number
  median_verification_hours: number | null
  aging_buckets: AgingBucket[]
}

export interface ResolutionAnalyticsResponse {
  total_resolved: number
  resolution_rate: number
  verified_resolution_count: number
  community_confirmed_count: number
  closed_count: number
  reopened_count: number
  median_resolution_hours: number | null
  p90_resolution_hours: number | null
  resolution_by_category: Record<string, number>
}

export interface GeographicDrilldownItem {
  geography_id: string
  name: string
  type_name: string
  hierarchy_path?: string | null
  report_count: number
  verified_count: number
  open_count: number
  resolved_count: number
  resolution_rate: number
  institution_count: number
  coverage_pct: number
}

export interface GeographicAnalyticsResponse {
  current_level: string
  current_geography_name?: string | null
  children: GeographicDrilldownItem[]
}

export interface InstitutionAnalyticsResponse {
  institution_id: string
  name: string
  type_name: string
  operational_status: string
  report_count: number
  verified_count: number
  open_count: number
  resolved_count: number
  resolution_rate: number
  top_category?: string | null
  last_reported_at?: string | null
  official_data_updated_at?: string | null
  discrepancies_flagged_count: number
}

export interface DataQualityScorecardResponse {
  total_sources: number
  healthy_sources_count: number
  stale_sources_count: number
  failed_sources_count: number
  total_records_ingested: number
  pending_entity_matches_count: number
  institutions_with_official_data_pct: number
  sources_breakdown: Array<{
    id: string
    name: string
    publisher: string
    status: string
    retrieval_date?: string | null
    confidence_base: number
  }>
}

export interface AiOpsAnalyticsResponse {
  total_requests: number
  total_tokens: number
  estimated_cost_usd: number
  avg_latency_ms: number
  p95_latency_ms: number
  feedback_positivity_pct: number
  task_breakdown: Record<string, number>
  model_breakdown: Record<string, number>
}

export interface ModerationAnalyticsResponse {
  pending_verification_count: number
  flagged_content_count: number
  duplicate_candidates_count: number
  high_priority_count: number
  median_queue_age_hours: number | null
  aging_buckets: AgingBucket[]
}

export interface AnalyticsFilterParams {
  geography_id?: string | null
  category_slug?: string | null
  issue_type_slug?: string | null
  status?: string | null
  severity?: string | null
  institution_id?: string | null
  institution_type_id?: string | null
  date_preset?: "today" | "yesterday" | "7d" | "30d" | "90d" | "year" | "all" | null
  start_date?: string | null
  end_date?: string | null
  interval?: "day" | "week" | "month"
  timezone?: string
}

export interface ExportRequest {
  domain?: "reports" | "institutions" | "kpis" | "discrepancies" | "overview"
  format?: "csv" | "json"
  filters?: object
}

export interface ExportResponse {
  filename: string
  content_type: string
  data: string
  record_count: number
  generated_at: string
}

export interface MetricDefinition {
  metric_id: string
  name: string
  description: string
  formula: string
  dimensions: string[]
  allowed_roles: string[]
  data_sources: string[]
  refresh_frequency: string
  privacy_threshold: number
  unit: string
  is_public: boolean
  version: string
}

// -----------------------------------------------------------------------------
// Phase 11: AI Intelligence, RAG, Assistant & Multilingual Schemas
// -----------------------------------------------------------------------------

export interface CitationItem {
  source_id?: string | null
  dataset_name: string
  dataset_version?: string | null
  publication_date?: string | null
  url?: string | null
  snippet: string
}

export interface RelatedEntityRef {
  id: string
  kind: "institution" | "report" | "geography" | "dataset"
  title: string
  subtitle?: string | null
}

export interface CivicChatRequest {
  message: string
  conversation_id?: string | null
  language?: string
  geography_id?: string | null
  institution_id?: string | null
  report_id?: string | null
}

export interface CivicChatResponse {
  answer: string
  conversation_id: string
  citations: CitationItem[]
  related_entities: RelatedEntityRef[]
  suggested_followups: string[]
  confidence_label: "high" | "moderate" | "low" | "insufficient_evidence"
  model_id: string
  latency_ms: number
}

export interface ReportClassificationOutput {
  category_slug: string
  issue_type_slug?: string | null
  severity: "critical" | "high" | "medium" | "low"
  department_hint?: string | null
  missing_information: string[]
  confidence: number
  rationale: string
}

export interface DuplicateAnalysisOutput {
  is_duplicate: boolean
  similarity_score: number
  duplicate_candidate_id?: string | null
  duplicate_ticket_no?: string | null
  rationale: string
}

export interface InstitutionSummaryOutput {
  institution_name: string
  institution_type: string
  situation_summary: string
  dominant_categories: string[]
  official_freshness: string
  discrepancy_note?: string | null
  citations: CitationItem[]
  confidence: number
}

export interface TranslationRequest {
  text: string
  source_language?: string
  target_language: string
  preserve_identifiers?: boolean
}

export interface TranslationResponse {
  translated_text: string
  source_language: string
  target_language: string
  model_id: string
  confidence: number
}

export interface AiFeedbackCreate {
  ai_output_id?: string | null
  task_kind: string
  rating: 1 | -1
  feedback_text?: string | null
}

export interface AiUsageStats {
  total_runs: number
  total_tokens_in: number
  total_tokens_out: number
  total_cost_usd: number
  avg_latency_ms: number
  by_task: Record<string, number>
  by_model: Record<string, number>
}

// ---------------------------------------------------------------------------
// Phase 10: Government Data, Discrepancies & Provenance
// ---------------------------------------------------------------------------

export type DiscrepancyState =
  | "NO_DISCREPANCY_DETECTED"
  | "POSSIBLE_DISCREPANCY"
  | "CONFLICTING_DATA"
  | "OUTDATED_OFFICIAL_DATA"
  | "INSUFFICIENT_DATA"
  | "UNDER_REVIEW"
  | "RESOLVED"

export interface ProvenanceDetail {
  source_id: string
  source_name: string
  publisher: string
  dataset_identifier?: string | null
  dataset_version?: string | null
  license?: string | null
  source_url?: string | null
  retrieval_date: string
  publication_date?: string | null
  checksum_sha256?: string | null
  transformation_version?: string
}

export interface OfficialDataResponse {
  institution_id: string
  institution_name: string
  institution_type: string
  official_identifier?: string | null
  operational_status: string
  canonical_data: Record<string, string | number | boolean | null>
  provenance?: ProvenanceDetail | null
  last_published?: string | null
  last_retrieved?: string | null
  freshness_label: string
}

export interface DiscrepancyItem {
  id: string
  institution_id: string
  resource_key: string
  discrepancy_state: DiscrepancyState
  official_value?: unknown
  citizen_summary?: string | null
  ai_finding?: string | null
  confidence: number
  rule_code?: string | null
  severity: string
  status: string
  reviewed_at?: string | null
  created_at: string
}

export interface ResourceComparisonItem {
  resource_key: string
  label: string
  official_value?: unknown
  official_source?: string | null
  official_updated_at?: string | null
  citizen_reports_count: number
  citizen_observation_summary?: string | null
  discrepancy_state: DiscrepancyState
  ai_analysis_note?: string | null
}

export interface InstitutionComparisonResponse {
  institution_id: string
  institution_name: string
  institution_type: string
  official_data_coverage_pct: number
  citizen_report_count: number
  overall_discrepancy_state: DiscrepancyState
  comparison_matrix: ResourceComparisonItem[]
  provenance?: ProvenanceDetail | null
  last_reconciled_at: string
}

export interface DataSourceItem {
  id: string
  name: string
  source_type: string
  publisher?: string | null
  url?: string | null
  license?: string | null
  dataset_identifier?: string | null
  version?: string | null
  confidence_base: number
  verification_state: string
  publication_date?: string | null
  retrieval_date: string
  created_at: string
}

export interface ImportJobItem {
  id: string
  dataset_id: string
  run_id: string
  status: string
  started_at: string
  finished_at?: string | null
  rows_total?: number
  rows_imported?: number
  error?: string | null
}

export interface EntityMatchReviewItem {
  id: string
  dataset_id: string
  external_key: string
  raw_data: Record<string, unknown>
  candidate_institution_id?: string | null
  candidate_institution_name?: string | null
  match_confidence: number
  match_status: string
  match_signals?: Record<string, unknown> | null
  review_status: string
  created_at: string
}

export interface DataQualityReport {
  total_datasets: number
  healthy_datasets: number
  stale_datasets: number
  failed_datasets: number
  total_institutions: number
  institutions_with_official_data: number
  official_data_coverage_pct: number
  pending_entity_matches_count: number
  total_discrepancies_flagged: number
}

export interface TimelineEntry {
  id: string
  report_id?: string
  from_status: string | null
  to_status: string
  actor_id: string | null
  reason: string | null
  created_at: string
}

export interface Comment {
  id: string
  report_id: string
  author_id: string
  author_name?: string
  parent_id: string | null
  body: string
  created_at: string
}

export interface ReportEvidence {
  id: string
  report_id: string
  kind: "image" | "video" | "audio" | "document"
  media_object_id?: string | null
  url?: string | null
  thumbnail_url?: string | null
  mime_type?: string | null
  size_bytes?: number | null
  width?: number | null
  height?: number | null
  moderation_status?: string
  verification_status?: string
  created_at: string
}

export interface UploadSlotResponse {
  media_id: string
  object_key: string
  upload_url: string | null
  headers: Record<string, string>
  expires_in_seconds: number
}

export interface DuplicateCandidate {
  candidate_report_id: string
  candidate_ticket_no: string
  candidate_title: string
  similarity_score: number
  confidence: "low" | "medium" | "high"
  status: "possible" | "confirmed" | "rejected"
  suggested_by: string
}

export interface AiIntakeSuggestRequest {
  description: string
  location?: GeoJsonPoint | null
  category_hint?: string | null
}

export interface AiIntakeSuggestResponse {
  category_suggestion: string | null
  issue_type_suggestion: string | null
  title_suggestion: string
  severity_suggestion: ReportSeverity
  confidence: number
  missing_information: string[]
  hazard_alert: string | null
}

export interface ReportDetail extends Report {
  verifications: Verification[]
  verifications_count: number
  confirmations_count: number
  refutations_count: number
  timeline: TimelineEntry[]
  comments: Comment[]
  evidence: ReportEvidence[]
  institution?: Institution | null
}

export interface AiCitation {
  id: string
  annotation_id: string | null
  text: string
  source_id: string
  url: string | null
  snippet: string | null
}

export interface Analysis {
  annotation_id: string
  report_id: string
  info_class: string
  confidence: number
  model_id: string
  created_at: string
  content: {
    summary: string
    entities: unknown[]
    suggested_category: string
    cross_references: string[]
  }
  run: { id: string; provider: string; status: string; latency_ms: number | null }
  citations: AiCitation[]
}

// ---------------------------------------------------------------------------
// Search Domain
// ---------------------------------------------------------------------------

export type SearchDomain = "all" | "reports" | "institutions" | "geography" | "categories"

export interface SearchResultItem {
  domain: "report" | "institution" | "geography" | "category"
  id: string
  title: string
  subtitle: string | null
  snippet: string | null
  url: string
  relevance_score: number
  metadata: Record<string, unknown>
}

export interface SearchResponse {
  query: string
  domain: string
  total: number
  items: SearchResultItem[]
}

// ---------------------------------------------------------------------------
// GIS & Map Intelligence Domain (Phase 9)
// -----------------------------------------------------------------------------

export interface BBoxQuery {
  min_lon: number
  min_lat: number
  max_lon: number
  max_lat: number
}

export interface MapInstitutionItem {
  id: string
  name: string
  type_id: string
  type_code?: string | null
  type_name?: string | null
  location: GeoJsonPoint
  operational_status: string
  geography_id?: string | null
  open_reports_count: number
  resolved_reports_count: number
}

export interface MapReportItem {
  id: string
  ticket_no: string
  title: string
  category_id: string
  category_slug?: string | null
  institution_id?: string | null
  location: GeoJsonPoint
  status: ReportStatus
  severity: ReportSeverity
  trust_score: number
  coordinate_source?: CoordinateSource | null
  observed_at?: string | null
  created_at: string
}

export interface MapSummary {
  geography_id?: string | null
  geography_name?: string | null
  hierarchy_path?: string | null
  boundary_id?: string | null
  boundary_name?: string | null
  institution_count: number
  report_count: number
  open_report_count: number
  resolved_report_count: number
  verified_report_count: number
  category_breakdown: Record<string, number>
  severity_breakdown: Record<string, number>
  status_breakdown: Record<string, number>
  data_coverage_pct: number
}

export interface GeocodeResultItem {
  label: string
  kind: "geography" | "institution" | "landmark" | "coordinate"
  lat: number
  lng: number
  id?: string | null
  hierarchy_hint?: string | null
  confidence: number
}

export interface GeocodeResponse {
  query: string
  results: GeocodeResultItem[]
}

export interface MapNearbyResponse {
  center: { lat: number; lng: number }
  radius_m: number
  institutions: Array<{
    id: string
    name: string
    type_code?: string
    type_name?: string
    operational_status: string
    location: GeoJsonPoint
    distance_m: number
  }>
  reports: Array<{
    id: string
    ticket_no: string
    title: string
    category_slug?: string
    status: string
    severity: string
    trust_score: number
    location: GeoJsonPoint
    distance_m: number
  }>
  total_count: number
}