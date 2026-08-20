import { api, type RequestOptions } from "@/lib/api"
import type {
  AiIntakeSuggestRequest,
  AiIntakeSuggestResponse,
  Analysis,
  Comment,
  CoordinateSource,
  CursorResponse,
  DuplicateCandidate,
  GeoJsonPoint,
  Report,
  ReportDetail,
  ReportEvidence,
  ReportSeverity,
  ReportStatus,
  ReportVisibility,
  TimelineEntry,
  UploadSlotResponse,
  Verification,
  VerificationListResponse,
} from "@/lib/types"

export interface ListReportsParams {
  category_slug?: string
  campaign_id?: string
  institution_id?: string
  issue_type_id?: string
  status?: ReportStatus
  severity?: ReportSeverity
  visibility?: ReportVisibility
  boundary_id?: string
  cursor?: string
  limit?: number
}

export interface SubmitReportPayload {
  category_slug: string
  campaign_id?: string | null
  institution_id?: string | null
  issue_type_id?: string | null
  title: string
  description: string
  severity?: ReportSeverity
  visibility?: ReportVisibility
  source?: string
  location: GeoJsonPoint
  location_accuracy_m?: number
  coordinate_source?: CoordinateSource | null
  observed_at?: string | null
  address_hint?: string | null
  fields?: Record<string, unknown>
  media_ids?: string[]
}

export interface DraftCreatePayload {
  category_slug?: string
  campaign_id?: string | null
  institution_id?: string | null
  issue_type_id?: string | null
  title?: string
  description?: string
  location?: GeoJsonPoint
  location_accuracy_m?: number
  coordinate_source?: CoordinateSource
  observed_at?: string
  address_hint?: string
  severity?: ReportSeverity
  visibility?: ReportVisibility
  fields?: Record<string, unknown>
}

export interface DraftUpdatePayload {
  category_slug?: string
  campaign_id?: string | null
  institution_id?: string | null
  issue_type_id?: string | null
  title?: string
  description?: string
  location?: GeoJsonPoint
  location_accuracy_m?: number
  coordinate_source?: CoordinateSource
  observed_at?: string
  address_hint?: string
  severity?: ReportSeverity
  visibility?: ReportVisibility
  fields?: Record<string, unknown>
}

export interface VerificationCreatePayload {
  kind: "confirm" | "refute" | "needs_information"
  evidence?: string | null
  notes?: string | null
  location_independent?: boolean
}

export const reportsApi = {
  list: (
    params?: ListReportsParams,
    options?: RequestOptions,
  ): Promise<CursorResponse<Report>> =>
    api.get<CursorResponse<Report>>("/reports", {
      ...options,
      params: {
        category_slug: params?.category_slug,
        campaign_id: params?.campaign_id,
        institution_id: params?.institution_id,
        issue_type_id: params?.issue_type_id,
        status: params?.status,
        severity: params?.severity,
        visibility: params?.visibility,
        boundary_id: params?.boundary_id,
        cursor: params?.cursor,
        limit: params?.limit,
      },
    }),

  get: (id: string, options?: RequestOptions): Promise<ReportDetail> =>
    api.get<ReportDetail>(`/reports/${id}`, options),

  submit: (
    payload: SubmitReportPayload,
    idempotencyKey?: string,
    options?: RequestOptions,
  ): Promise<Report> => {
    const headers = { ...options?.headers }
    if (idempotencyKey) {
      headers["Idempotency-Key"] = idempotencyKey
    }
    return api.post<Report>("/reports", payload, { ...options, headers })
  },

  // Drafts
  createDraft: (payload: DraftCreatePayload, options?: RequestOptions): Promise<Report> =>
    api.post<Report>("/reports/drafts", payload, options),

  listDrafts: (options?: RequestOptions): Promise<{ items: Report[] }> =>
    api.get<{ items: Report[] }>("/reports/drafts", options),

  updateDraft: (
    draftId: string,
    payload: DraftUpdatePayload,
    options?: RequestOptions,
  ): Promise<Report> =>
    api.patch<Report>(`/reports/drafts/${draftId}`, payload, options),

  deleteDraft: (draftId: string, options?: RequestOptions): Promise<void> =>
    api.delete<void>(`/reports/drafts/${draftId}`, options),

  submitDraft: (
    draftId: string,
    overrides?: Partial<SubmitReportPayload>,
    options?: RequestOptions,
  ): Promise<Report> =>
    api.post<Report>(`/reports/drafts/${draftId}/submit`, overrides || {}, options),

  // Evidence Media Pipeline
  requestUploadSlot: (
    reportId: string,
    payload: { mime_type: string; size_bytes: number; kind: string },
    options?: RequestOptions,
  ): Promise<UploadSlotResponse> =>
    api.post<UploadSlotResponse>(`/reports/${reportId}/media/upload-url`, payload, options),

  completeUpload: (
    reportId: string,
    payload: { media_id: string; checksum_sha256?: string },
    options?: RequestOptions,
  ): Promise<ReportEvidence> =>
    api.post<ReportEvidence>(`/reports/${reportId}/media/complete`, payload, options),

  listMedia: (reportId: string, options?: RequestOptions): Promise<{ items: ReportEvidence[] }> =>
    api.get<{ items: ReportEvidence[] }>(`/reports/${reportId}/media`, options),

  deleteMedia: (
    reportId: string,
    evidenceId: string,
    options?: RequestOptions,
  ): Promise<void> =>
    api.delete<void>(`/reports/${reportId}/media/${evidenceId}`, options),

  // Verifications
  listVerifications: (
    id: string,
    options?: RequestOptions,
  ): Promise<VerificationListResponse> =>
    api.get<VerificationListResponse>(`/reports/${id}/verifications`, options),

  verify: (
    id: string,
    payload: VerificationCreatePayload,
    options?: RequestOptions,
  ): Promise<Verification> =>
    api.post<Verification>(`/reports/${id}/verifications`, payload, options),

  // Duplicates & AI Suggestions
  listDuplicates: (
    id: string,
    options?: RequestOptions,
  ): Promise<{ items: DuplicateCandidate[] }> =>
    api.get<{ items: DuplicateCandidate[] }>(`/reports/${id}/duplicates`, options),

  linkDuplicate: (
    id: string,
    candidateReportId: string,
    status: "possible" | "confirmed" | "rejected",
    options?: RequestOptions,
  ): Promise<{ status: string }> =>
    api.post<{ status: string }>(
      `/reports/${id}/duplicates/link`,
      { candidate_report_id: candidateReportId, status },
      options,
    ),

  aiSuggestIntake: (
    payload: AiIntakeSuggestRequest,
    options?: RequestOptions,
  ): Promise<AiIntakeSuggestResponse> =>
    api.post<AiIntakeSuggestResponse>("/reports/ai/suggest", payload, options),

  // Timeline & Collaboration
  getTimeline: (
    id: string,
    options?: RequestOptions,
  ): Promise<{ items: TimelineEntry[] }> =>
    api.get<{ items: TimelineEntry[] }>(`/reports/${id}/timeline`, options),

  listComments: (id: string, options?: RequestOptions): Promise<Comment[]> =>
    api.get<Comment[]>(`/reports/${id}/comments`, options),

  addComment: (
    id: string,
    body: string,
    parentId?: string | null,
    options?: RequestOptions,
  ): Promise<Comment> =>
    api.post<Comment>(
      `/reports/${id}/comments`,
      { body, parent_id: parentId },
      options,
    ),

  follow: (
    id: string,
    notifyLevel: "all" | "status_only" | "none" = "all",
    options?: RequestOptions,
  ): Promise<{ status: string; notify_level: string }> =>
    api.post<{ status: string; notify_level: string }>(
      `/reports/${id}/follow`,
      { notify_level: notifyLevel },
      options,
    ),

  unfollow: (id: string, options?: RequestOptions): Promise<void> =>
    api.delete<void>(`/reports/${id}/follow`, options),

  getAnalysis: (id: string, options?: RequestOptions): Promise<Analysis> =>
    api.get<Analysis>(`/reports/${id}/analysis`, options),
}
