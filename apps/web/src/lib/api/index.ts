export { api, ApiError, getToken, setToken, buildQueryString } from "@/lib/api"
export type { ApiErrorBody, RequestOptions } from "@/lib/api"

export { geographyApi } from "@/lib/api/geography"
export type { ListGeographyParams } from "@/lib/api/geography"

export { institutionsApi } from "@/lib/api/institutions"
export type {
  ListInstitutionsParams,
  CreateInstitutionPayload,
  UpdateInstitutionPayload,
} from "@/lib/api/institutions"

export { civicApi } from "@/lib/api/civic"

export { reportsApi } from "@/lib/api/reports"
export type { ListReportsParams, SubmitReportPayload } from "@/lib/api/reports"

export { searchApi } from "@/lib/api/search"
export { gisApi } from "@/lib/api/gis"
export type { MapInstitutionsParams, MapReportsParams } from "@/lib/api/gis"

export { govdataApi } from "@/lib/api/govdata"
export type {
  CreateDataSourcePayload,
  TriggerImportPayload,
  ReviewEntityMatchPayload,
} from "@/lib/api/govdata"

export { aiApi } from "@/lib/api/ai"
export { analyticsApi } from "@/lib/api/analytics"

export { communityApi } from "@/lib/api/community"
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
