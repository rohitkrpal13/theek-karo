import { api, type RequestOptions } from "@/lib/api"

export type ResolutionDecision =
  | "verified"
  | "more_evidence_required"
  | "rejected"
  | "partially_verified"

export interface ResolutionEvidenceItem {
  kind: "before" | "after" | "document" | "other"
  media_object_id?: string | null
  notes?: string | null
  document_kind?: string | null
  before_after?: "before" | "after" | "neutral" | null
  captured_at?: string | null
  checksum?: string | null
  visibility?: "public" | "internal"
}

export interface ResolutionSubmission {
  id: string
  case_id: string
  submitted_by: string | null
  notes: string | null
  responsible_party: string | null
  explanation: string | null
  resolution_date: string | null
  reference_numbers: Record<string, unknown> | null
  status: string
  evidence: ResolutionEvidenceItem[]
  reviewed_by: string | null
  reviewed_at: string | null
  created_at: string
}

export interface ResolutionReview {
  id: string
  decision: ResolutionDecision
  submission_status: string
}

export const resolutionsApi = {
  submit: (
    payload: {
      case_id: string
      notes?: string | null
      responsible_party?: string | null
      explanation?: string | null
      resolution_date?: string | null
      reference_numbers?: Record<string, unknown> | null
      evidence: ResolutionEvidenceItem[]
    },
    options?: RequestOptions,
  ): Promise<ResolutionSubmission> =>
    api.post<ResolutionSubmission>("/resolutions", payload, options),

  list: (
    params?: { case_id?: string; status?: string },
    options?: RequestOptions,
  ): Promise<{ items: ResolutionSubmission[]; count: number }> =>
    api.get<{ items: ResolutionSubmission[]; count: number }>("/resolutions", {
      ...options,
      params,
    }),

  get: (id: string, options?: RequestOptions): Promise<ResolutionSubmission> =>
    api.get<ResolutionSubmission>(`/resolutions/${id}`, options),

  review: (
    id: string,
    payload: {
      decision: ResolutionDecision
      reason?: string | null
      ai_assessment?: Record<string, unknown> | null
    },
    options?: RequestOptions,
  ): Promise<ResolutionReview> =>
    api.post<ResolutionReview>(`/resolutions/${id}/review`, payload, options),

  addEvidence: (
    id: string,
    items: ResolutionEvidenceItem[],
    options?: RequestOptions,
  ): Promise<{ count: number; version_no: number | null }> =>
    api.post<{ count: number; version_no: number | null }>(
      `/resolutions/${id}/evidence`,
      { items },
      options,
    ),
}