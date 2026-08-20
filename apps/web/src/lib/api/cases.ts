import { api, type RequestOptions } from "@/lib/api"

export type CaseStatus =
  | "submitted"
  | "under_review"
  | "needs_information"
  | "verified"
  | "assigned"
  | "acknowledged"
  | "action_planned"
  | "in_progress"
  | "waiting_for_information"
  | "resolution_submitted"
  | "resolution_under_review"
  | "resolution_rejected"
  | "partially_resolved"
  | "resolved"
  | "closed"
  | "reopened"
  | "rejected"
  | "duplicate"

export type CaseSeverity = "low" | "medium" | "high" | "critical"
export type SlaStatus = "not_started" | "within_sla" | "at_risk" | "breached" | "paused" | "exempt"

export interface CaseDetail {
  id: string
  case_no: string
  report_id: string
  status: CaseStatus
  primary_department_id: string | null
  assigned_geography_id: string | null
  severity: CaseSeverity | null
  priority: CaseSeverity
  sla_policy_id: string | null
  sla_started_at: string | null
  sla_due_at: string | null
  created_at: string
  updated_at: string
  closed_at: string | null
  reopened_at: string | null
  resolution_verified_at: string | null
  internal: { sla_status: SlaStatus } | null
  responses: CaseResponse[]
  actions: CaseAction[]
  escalations: CaseEscalation[]
}

export interface CaseEscalation {
  id: string
  level: number
  status: string
  reason: string | null
  escalated_by_system: boolean
  created_at: string
}

export interface CaseTimelineEntry {
  type: "status_change" | "response"
  at: string
  from_status?: CaseStatus
  to_status?: CaseStatus
  reason?: string | null
  actor_id?: string | null
  kind?: "acknowledgement" | "public_response" | "progress_update"
  body?: string
  department_id?: string | null
}

export interface CaseTimeline {
  case_no: string
  status: CaseStatus
  items: CaseTimelineEntry[]
}

export interface CaseResponse {
  id: string
  kind: "acknowledgement" | "public_response" | "internal_note" | "progress_update"
  visibility: "public" | "internal"
  body: string
  created_at: string
}

export interface CaseAction {
  id: string
  case_id: string
  title: string
  description: string | null
  responsible_team: string | null
  target_date: string | null
  status: "planned" | "in_progress" | "completed" | "cancelled" | "blocked"
  notes: string | null
  created_at: string
}

export interface SlaInstanceRead {
  case_id: string
  status: SlaStatus
  started_at: string | null
  target_resolution_at: string | null
  paused_seconds: number | null
  breached_at: string | null
  remaining_hours: number | null
}

export interface ReopenRequest {
  id: string
  case_id: string
  requested_by: string | null
  reason: string
  evidence: string | null
  status: "pending" | "approved" | "rejected"
  reviewed_by: string | null
  review_note: string | null
  created_at: string
}

export const casesApi = {
  list: (
    params?: {
      status?: CaseStatus
      department_id?: string
      q?: string
      limit?: number
      offset?: number
    },
    options?: RequestOptions,
  ): Promise<{ items: CaseDetail[]; count: number }> =>
    api.get<{ items: CaseDetail[]; count: number }>("/cases", { ...options, params }),

  get: (id: string, options?: RequestOptions): Promise<CaseDetail> =>
    api.get<CaseDetail>(`/cases/${id}`, options),

  create: (
    payload: {
      report_id: string
      department_id?: string | null
      severity?: CaseSeverity | null
      priority?: CaseSeverity
    },
    options?: RequestOptions,
  ): Promise<CaseDetail> => api.post<CaseDetail>("/cases", payload, options),

  transition: (
    id: string,
    payload: { to_status: CaseStatus; reason?: string | null },
    options?: RequestOptions,
  ): Promise<CaseDetail> => api.post<CaseDetail>(`/cases/${id}/transition`, payload, options),

  assign: (
    id: string,
    payload: {
      department_id: string
      assignee_user_id?: string | null
      geography_id?: string | null
      reason?: string | null
    },
    options?: RequestOptions,
  ): Promise<{ id: string; primary_department_id: string | null }> =>
    api.post<{ id: string; primary_department_id: string | null }>(
      `/cases/${id}/assign`,
      payload,
      options,
    ),

  respond: (
    id: string,
    payload: {
      kind: "acknowledgement" | "public_response" | "internal_note" | "progress_update"
      visibility?: "public" | "internal"
      body: string
    },
    options?: RequestOptions,
  ): Promise<CaseResponse> => api.post<CaseResponse>(`/cases/${id}/respond`, payload, options),

  timeline: (id: string, options?: RequestOptions): Promise<CaseTimeline> =>
    api.get<CaseTimeline>(`/cases/${id}/timeline`, options),

  createAction: (
    id: string,
    payload: {
      title: string
      description?: string | null
      responsible_team?: string | null
      target_date?: string | null
    },
    options?: RequestOptions,
  ): Promise<CaseAction> => api.post<CaseAction>(`/cases/${id}/actions`, payload, options),

  updateAction: (
    id: string,
    actionId: string,
    payload: { status?: string; notes?: string | null },
    options?: RequestOptions,
  ): Promise<CaseAction> =>
    api.patch<CaseAction>(`/cases/${id}/actions/${actionId}`, payload, options),

  getSla: (id: string, options?: RequestOptions): Promise<SlaInstanceRead> =>
    api.get<SlaInstanceRead>(`/cases/${id}/sla`, options),

  pauseSla: (
    id: string,
    payload: { reason: string; expected_resume_condition?: string | null },
    options?: RequestOptions,
  ): Promise<{ id: string; status: "paused" }> =>
    api.post<{ id: string; status: "paused" }>(`/cases/${id}/sla/pause`, payload, options),

  resumeSla: (id: string, options?: RequestOptions): Promise<{ id: string; status: "within_sla" }> =>
    api.post<{ id: string; status: "within_sla" }>(`/cases/${id}/sla/resume`, {}, options),

  escalate: (
    id: string,
    payload: { level: number; reason: string },
    options?: RequestOptions,
  ): Promise<{ id: string; level: number }> =>
    api.post<{ id: string; level: number }>(`/cases/${id}/escalate`, payload, options),

  requestReopen: (
    id: string,
    payload: { reason: string; evidence?: string | null },
    options?: RequestOptions,
  ): Promise<{ id: string; status: string }> =>
    api.post<{ id: string; status: string }>(`/cases/${id}/reopen-requests`, payload, options),

  reviewReopen: (
    id: string,
    requestId: string,
    payload: { decision: "approved" | "rejected"; note?: string | null },
    options?: RequestOptions,
  ): Promise<{ id: string; status: string }> =>
    api.post<{ id: string; status: string }>(
      `/cases/${id}/reopen-requests/${requestId}/review`,
      payload,
      options,
    ),
}