import { api, type RequestOptions } from "@/lib/api"
import type {
  BBoxQuery,
  GeocodeResponse,
  MapInstitutionItem,
  MapNearbyResponse,
  MapReportItem,
  MapSummary,
} from "@/lib/types"

export interface MapInstitutionsParams extends BBoxQuery {
  type_id?: string
  operational_status?: string
  limit?: number
}

export interface MapReportsParams extends BBoxQuery {
  category_slug?: string
  status?: string
  severity?: string
  limit?: number
}

export const gisApi = {
  mapInstitutions: (
    params: MapInstitutionsParams,
    options?: RequestOptions,
  ): Promise<MapInstitutionItem[]> =>
    api.get<MapInstitutionItem[]>("/gis/map/institutions", {
      ...options,
      params: {
        min_lon: params.min_lon,
        min_lat: params.min_lat,
        max_lon: params.max_lon,
        max_lat: params.max_lat,
        type_id: params.type_id,
        operational_status: params.operational_status,
        limit: params.limit ?? 100,
      },
    }),

  mapReports: (
    params: MapReportsParams,
    options?: RequestOptions,
  ): Promise<MapReportItem[]> =>
    api.get<MapReportItem[]>("/gis/map/reports", {
      ...options,
      params: {
        min_lon: params.min_lon,
        min_lat: params.min_lat,
        max_lon: params.max_lon,
        max_lat: params.max_lat,
        category_slug: params.category_slug,
        status: params.status,
        severity: params.severity,
        limit: params.limit ?? 100,
      },
    }),

  mapNearby: (
    lat: number,
    lng: number,
    radius_m = 5000,
    domain = "all",
    category_slug?: string,
    limit = 50,
    options?: RequestOptions,
  ): Promise<MapNearbyResponse> =>
    api.get<MapNearbyResponse>("/gis/map/nearby", {
      ...options,
      params: {
        lat,
        lng,
        radius_m,
        domain,
        category_slug,
        limit,
      },
    }),

  mapSummary: (
    params?: { geography_id?: string; boundary_id?: string },
    options?: RequestOptions,
  ): Promise<MapSummary> =>
    api.get<MapSummary>("/gis/map/summary", {
      ...options,
      params: {
        geography_id: params?.geography_id,
        boundary_id: params?.boundary_id,
      },
    }),

  forwardGeocode: (
    q: string,
    limit = 10,
    options?: RequestOptions,
  ): Promise<GeocodeResponse> =>
    api.get<GeocodeResponse>("/gis/geocode/forward", {
      ...options,
      params: { q, limit },
    }),

  reverseGeocode: (
    lat: number,
    lng: number,
    options?: RequestOptions,
  ): Promise<{
    boundary_ids: string[]
    finest: { id: string; boundary_kind: string; name: string } | null
    hint: string | null
  }> =>
    api.get("/gis/reverse-geocode", {
      ...options,
      params: { lat, lng },
    }),

  listBoundaries: (
    kind?: string,
    parentId?: string,
    options?: RequestOptions,
  ): Promise<{ items: Array<{ id: string; boundary_kind: string; name: string; parent_id: string | null }>; count: number }> =>
    api.get("/gis/boundaries", {
      ...options,
      params: { kind, parent_id: parentId },
    }),

  getBoundary: (
    boundaryId: string,
    options?: RequestOptions,
  ): Promise<{
    id: string
    boundary_kind: string
    name: string
    geometry: unknown
    provenance: Record<string, unknown>
  }> =>
    api.get(`/gis/boundaries/${boundaryId}`, options),
}
