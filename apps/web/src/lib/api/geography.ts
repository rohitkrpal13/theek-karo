import { api, type RequestOptions } from "@/lib/api"
import type {
  Geography,
  GeographyDetail,
  GeographyHierarchyNode,
  GeographyType,
  PageResponse,
} from "@/lib/types"

export interface ListGeographyParams {
  type_id?: string
  parent_id?: string
  country_code?: string
  page?: number
  limit?: number
}

export const geographyApi = {
  listTypes: (options?: RequestOptions): Promise<GeographyType[]> =>
    api.get<GeographyType[]>("/geography/types", options),

  list: (
    params?: ListGeographyParams,
    options?: RequestOptions,
  ): Promise<PageResponse<Geography>> =>
    api.get<PageResponse<Geography>>("/geography", {
      ...options,
      params: {
        type_id: params?.type_id,
        parent_id: params?.parent_id,
        country_code: params?.country_code,
        page: params?.page,
        limit: params?.limit,
      },
    }),

  get: (id: string, options?: RequestOptions): Promise<GeographyDetail> =>
    api.get<GeographyDetail>(`/geography/${id}`, options),

  getChildren: (id: string, options?: RequestOptions): Promise<Geography[]> =>
    api.get<Geography[]>(`/geography/${id}/children`, options),

  getAncestors: (
    id: string,
    options?: RequestOptions,
  ): Promise<GeographyHierarchyNode[]> =>
    api.get<GeographyHierarchyNode[]>(`/geography/${id}/ancestors`, options),

  search: (
    q: string,
    typeId?: string,
    limit?: number,
    options?: RequestOptions,
  ): Promise<Geography[]> =>
    api.get<Geography[]>("/geography/search", {
      ...options,
      params: { q, type_id: typeId, limit },
    }),
}
