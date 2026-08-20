import { api, type RequestOptions } from "@/lib/api"
import type {
  DataQualityReport,
  DataSourceItem,
  DiscrepancyItem,
  EntityMatchReviewItem,
  ImportJobItem,
  InstitutionComparisonResponse,
  OfficialDataResponse,
} from "@/lib/types"

export interface CreateDataSourcePayload {
  name: string
  source_type: string
  publisher?: string
  url?: string
  license?: string
  dataset_identifier?: string
  version?: string
  confidence_base?: number
  verification_state?: string
}

export interface TriggerImportPayload {
  dataset_id: string
  dry_run?: boolean
  raw_payload?: Record<string, unknown>
}

export interface ReviewEntityMatchPayload {
  decision: "confirm" | "reject" | "reassign" | "create_new"
  target_institution_id?: string
  notes?: string
}

export const govdataApi = {
  getOfficialData: (
    institutionId: string,
    options?: RequestOptions,
  ): Promise<OfficialDataResponse> =>
    api.get<OfficialDataResponse>(`/institutions/${institutionId}/official-data`, options),

  getDiscrepancies: (
    institutionId: string,
    options?: RequestOptions,
  ): Promise<DiscrepancyItem[]> =>
    api.get<DiscrepancyItem[]>(`/institutions/${institutionId}/discrepancies`, options),

  getComparison: (
    institutionId: string,
    options?: RequestOptions,
  ): Promise<InstitutionComparisonResponse> =>
    api.get<InstitutionComparisonResponse>(`/institutions/${institutionId}/comparison`, options),

  listDataSources: (
    params?: { source_type?: string; limit?: number },
    options?: RequestOptions,
  ): Promise<DataSourceItem[]> =>
    api.get<DataSourceItem[]>("/govdata/sources", {
      ...options,
      params: {
        source_type: params?.source_type,
        limit: params?.limit ?? 50,
      },
    }),

  getDataSource: (
    sourceId: string,
    options?: RequestOptions,
  ): Promise<DataSourceItem> =>
    api.get<DataSourceItem>(`/govdata/sources/${sourceId}`, options),

  createDataSource: (
    payload: CreateDataSourcePayload,
    options?: RequestOptions,
  ): Promise<DataSourceItem> =>
    api.post<DataSourceItem>("/govdata/sources", payload, options),

  triggerImportJob: (
    payload: TriggerImportPayload,
    options?: RequestOptions,
  ): Promise<ImportJobItem> =>
    api.post<ImportJobItem>("/govdata/imports", payload, options),

  listEntityMatches: (
    params?: { dataset_id?: string; review_status?: string; limit?: number },
    options?: RequestOptions,
  ): Promise<EntityMatchReviewItem[]> =>
    api.get<EntityMatchReviewItem[]>("/govdata/entity-matches", {
      ...options,
      params: {
        dataset_id: params?.dataset_id,
        review_status: params?.review_status ?? "pending",
        limit: params?.limit ?? 50,
      },
    }),

  reviewEntityMatch: (
    reviewId: string,
    payload: ReviewEntityMatchPayload,
    options?: RequestOptions,
  ): Promise<EntityMatchReviewItem> =>
    api.post<EntityMatchReviewItem>(`/govdata/entity-matches/${reviewId}/review`, payload, options),

  getDataQualityReport: (
    options?: RequestOptions,
  ): Promise<DataQualityReport> =>
    api.get<DataQualityReport>("/govdata/data-quality", options),
}
