import { api, type RequestOptions } from "@/lib/api"
import type { SearchDomain, SearchResponse } from "@/lib/types"

export const searchApi = {
  search: (
    q: string,
    domain: SearchDomain = "all",
    limit = 20,
    options?: RequestOptions,
  ): Promise<SearchResponse> =>
    api.get<SearchResponse>("/search", {
      ...options,
      params: { q, domain, limit },
    }),
}
