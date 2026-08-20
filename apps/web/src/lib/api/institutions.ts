import { api, type RequestOptions } from "@/lib/api"
import type {
  Institution,
  InstitutionDetail,
  InstitutionType,
  PageResponse,
} from "@/lib/types"

export interface ListInstitutionsParams {
  type_id?: string
  geography_id?: string
  operational_status?: string
  verification_state?: string
  q?: string
  page?: number
  limit?: number
}

export interface CreateInstitutionPayload {
  type_id: string
  name: string
  official_id?: string | null
  description?: string | null
  geography_id?: string | null
  location_lat?: number | null
  location_lon?: number | null
  operational_status?: "operational" | "closed" | "under_construction" | "relocated"
  verification_state?: "unverified" | "official" | "community_verified"
  confidence_score?: number
  source_id?: string | null
}

export interface UpdateInstitutionPayload {
  name?: string
  description?: string | null
  operational_status?: "operational" | "closed" | "under_construction" | "relocated"
  verification_state?: "unverified" | "official" | "community_verified"
  confidence_score?: number
}

export const institutionsApi = {
  listTypes: (options?: RequestOptions): Promise<InstitutionType[]> =>
    api.get<InstitutionType[]>("/institutions/types", options),

  list: (
    params?: ListInstitutionsParams,
    options?: RequestOptions,
  ): Promise<PageResponse<Institution>> =>
    api.get<PageResponse<Institution>>("/institutions", {
      ...options,
      params: {
        type_id: params?.type_id,
        geography_id: params?.geography_id,
        operational_status: params?.operational_status,
        verification_state: params?.verification_state,
        q: params?.q,
        page: params?.page,
        limit: params?.limit,
      },
    }),

  get: (id: string, options?: RequestOptions): Promise<InstitutionDetail> =>
    api.get<InstitutionDetail>(`/institutions/${id}`, options),

  create: (
    payload: CreateInstitutionPayload,
    options?: RequestOptions,
  ): Promise<Institution> =>
    api.post<Institution>("/institutions", payload, options),

  update: (
    id: string,
    payload: UpdateInstitutionPayload,
    options?: RequestOptions,
  ): Promise<Institution> =>
    api.patch<Institution>(`/institutions/${id}`, payload, options),
}
