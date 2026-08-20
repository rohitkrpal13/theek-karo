import { api, type RequestOptions } from "@/lib/api"
import type {
  Campaign,
  Category,
  CategoryDetail,
  CursorResponse,
  IssueType,
} from "@/lib/types"

export const civicApi = {
  listCategories: (
    includeInactive = false,
    options?: RequestOptions,
  ): Promise<{ items: Category[] }> =>
    api.get<{ items: Category[] }>("/civic/categories", {
      ...options,
      params: includeInactive ? { include_inactive: true } : undefined,
    }),

  getCategory: (slug: string, options?: RequestOptions): Promise<Category> =>
    api.get<Category>(`/civic/categories/${slug}`, options),

  getCategoryDetail: (
    slugOrId: string,
    options?: RequestOptions,
  ): Promise<CategoryDetail> =>
    api.get<CategoryDetail>(`/civic/categories/${slugOrId}/detail`, options),

  listIssueTypes: (
    categorySlug?: string,
    options?: RequestOptions,
  ): Promise<IssueType[]> =>
    api.get<IssueType[]>("/civic/issue-types", {
      ...options,
      params: categorySlug ? { category_slug: categorySlug } : undefined,
    }),

  getIssueType: (id: string, options?: RequestOptions): Promise<IssueType> =>
    api.get<IssueType>(`/civic/issue-types/${id}`, options),

  listCampaigns: (
    status?: string,
    boundaryId?: string,
    cursor?: string,
    limit?: number,
    options?: RequestOptions,
  ): Promise<CursorResponse<Campaign>> =>
    api.get<CursorResponse<Campaign>>("/civic/campaigns", {
      ...options,
      params: { status, boundary_id: boundaryId, cursor, limit },
    }),
}
