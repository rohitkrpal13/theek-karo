/**
 * Public Data Portal API client — typed methods for /api/v1/public-data/.
 * Public-facing read-only endpoints accessed through the shared `api` client.
 */

import { api, type RequestOptions } from "@/lib/api"

export interface PublicDataset {
  slug: string;
  name: string;
  name_hi: string | null;
  description: string | null;
  category: string | null;
  publisher: string | null;
  source: string | null;
  license: string | null;
  update_frequency: string | null;
  derived: boolean;
  version: string;
  record_count: number | null;
  last_updated_at: string | null;
  freshness: string;
  status: string;
}

export interface PublicDatasetListResponse {
  items: PublicDataset[];
}

export type ExplorerRecord = Record<string, unknown> & {
  id?: string;
};

export interface PublicDataRecordsResponse {
  items: ExplorerRecord[];
  total?: number;
  next_cursor?: string | null;
}

export interface PublicDatasetDetail extends PublicDataset {
  description: string | null;
  methodology?: string | null;
}

export const publicDataApi = {
  listDatasets: (
    params: { category?: string; limit?: number; offset?: number } = {},
    options?: RequestOptions
  ): Promise<PublicDatasetListResponse> =>
    api.get<PublicDatasetListResponse>("/public-data/datasets", { ...options, params }),

  getDataset: (
    slug: string,
    options?: RequestOptions
  ): Promise<PublicDatasetDetail> =>
    api.get<PublicDatasetDetail>(`/public-data/datasets/${slug}`, options),

  listRecords: (
    slug: string,
    params: {
      status?: string;
      date_from?: string;
      date_to?: string;
      limit?: number;
      cursor?: string;
    } = {},
    options?: RequestOptions
  ): Promise<PublicDataRecordsResponse> =>
    api.get<PublicDataRecordsResponse>(`/public-data/datasets/${slug}/records`, {
      ...options,
      params,
    }),
}