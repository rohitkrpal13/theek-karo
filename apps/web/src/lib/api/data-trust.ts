/**
 * Data Trust API client — typed methods for /api/v1/data-trust/ endpoints.
 * Uses the shared authenticated `api` client (attaches Bearer token, RFC 9457 errors).
 */

import { api, type RequestOptions } from "@/lib/api"

// ---------------------------------------------------------------------------
// Evidence Registry
// ---------------------------------------------------------------------------

export interface EvidenceRecord {
  id: string;
  evidence_type: string;
  title: string | null;
  description: string | null;
  source_type: string;
  source_id: string | null;
  uploader_id: string | null;
  media_id: string | null;
  entity_type: string | null;
  entity_id: string | null;
  checksum_sha256: string | null;
  file_size_bytes: number | null;
  mime_type: string | null;
  status: string;
  verification_status: string;
  verification_count: number;
  language: string | null;
  created_at: string | null;
}

export interface EvidenceListResponse {
  items: EvidenceRecord[];
  total: number;
}

// ---------------------------------------------------------------------------
// Verification Records
// ---------------------------------------------------------------------------

export interface VerificationRecord {
  id: string;
  entity_type: string;
  entity_id: string;
  reviewer_id: string | null;
  reviewer_type: string;
  decision: string;
  method: string;
  evidence_refs: unknown[];
  explanation: string | null;
  confidence: number | null;
  ai_model: string | null;
  created_at: string | null;
}

// ---------------------------------------------------------------------------
// Data Quality
// ---------------------------------------------------------------------------

export interface DataQualityResult {
  id: string;
  entity_type: string;
  entity_id: string;
  dimension: string;
  score: number;
  status: string;
  overall_status: string;
  details: Record<string, unknown> | null;
  created_at: string | null;
}

export interface DataQualitySummary {
  entity_type: string;
  entity_id: string;
  overall_status: string;
  dimensions: DataQualityResult[];
}

// ---------------------------------------------------------------------------
// Data Conflicts
// ---------------------------------------------------------------------------

export interface DataConflict {
  id: string;
  entity_type: string;
  entity_id: string;
  field_name: string;
  source_a_value: unknown;
  source_b_value: unknown;
  source_a_timestamp: string | null;
  source_b_timestamp: string | null;
  status: string;
  resolved_value: unknown;
  resolution_note: string | null;
  severity: string;
  created_at: string | null;
}

// ---------------------------------------------------------------------------
// Disputes
// ---------------------------------------------------------------------------

export interface DisputeRecord {
  id: string;
  dispute_target_type: string;
  dispute_target_id: string;
  filed_by: string;
  reason: string;
  explanation: string | null;
  status: string;
  decision: string | null;
  public_banner: boolean;
  created_at: string | null;
}

// ---------------------------------------------------------------------------
// Provenance
// ---------------------------------------------------------------------------

export interface ProvenanceChain {
  entity_type: string;
  entity_id: string;
  evidence: EvidenceRecord[];
  verifications: VerificationRecord[];
  change_history: {
    field_name: string;
    old_value: unknown;
    new_value: unknown;
    change_source: string;
    created_at: string | null;
  }[];
  quality: DataQualitySummary;
  disputes: DisputeRecord[];
  limitations: string[];
}

// ---------------------------------------------------------------------------
// Change History
// ---------------------------------------------------------------------------

export interface ChangeHistoryEntry {
  field_name: string;
  old_value: unknown;
  new_value: unknown;
  change_source: string;
  changed_by: string | null;
  reason: string | null;
  created_at: string | null;
}

// ---------------------------------------------------------------------------
// Metric Definitions
// ---------------------------------------------------------------------------

export interface MetricDefinition {
  id: string;
  metric_id: string;
  name: string;
  name_hi: string | null;
  description: string;
  formula: string;
  definition: string | null;
  source: string | null;
  category: string | null;
  version: string;
  visibility: string;
  coverage: string | null;
  limitations: string | null;
  status: string;
  created_at: string | null;
}

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------

export interface DataTrustDashboard {
  total_sources: number;
  active_sources: number;
  failed_sources: number;
  stale_sources: number;
  total_datasets: number;
  total_conflicts: number;
  open_conflicts: number;
  total_disputes: number;
  open_disputes: number;
  total_evidence: number;
  verified_evidence: number;
  total_verifications: number;
  quarantined_records: number;
}

export const dataTrustApi = {
  // Evidence
  registerEvidence: (data: {
    evidence_type: string;
    title?: string;
    description?: string;
    source_type?: string;
    source_id?: string;
    media_id?: string;
    entity_type?: string;
    entity_id?: string;
    location?: Record<string, unknown>;
    language?: string;
    original_text?: string;
  }, options?: RequestOptions): Promise<EvidenceRecord> =>
    api.post<EvidenceRecord>("/data-trust/evidence", data, options),

  listEvidence: (params: {
    entity_type?: string;
    entity_id?: string;
    source_type?: string;
    status?: string;
    limit?: number;
    offset?: number;
  } = {}, options?: RequestOptions): Promise<EvidenceListResponse> =>
    api.get<EvidenceListResponse>("/data-trust/evidence", { ...options, params }),

  getEvidence: (evidenceId: string, options?: RequestOptions): Promise<EvidenceRecord> =>
    api.get<EvidenceRecord>(`/data-trust/evidence/${evidenceId}`, options),

  // Verifications
  createVerification: (data: {
    entity_type: string;
    entity_id: string;
    decision: string;
    method: string;
    evidence_refs?: string[];
    explanation?: string;
    confidence?: number;
    ai_model?: string;
    ai_model_version?: string;
    ai_reasoning?: string;
  }, options?: RequestOptions): Promise<VerificationRecord> =>
    api.post<VerificationRecord>("/data-trust/verifications", data, options),

  listVerifications: (params: {
    entity_type?: string;
    entity_id?: string;
    decision?: string;
    limit?: number;
    offset?: number;
  } = {}, options?: RequestOptions): Promise<{ items: VerificationRecord[]; total: number }> =>
    api.get("/data-trust/verifications", { ...options, params }),

  // Quality
  getQualitySummary: (
    entityType: string,
    entityId: string,
    options?: RequestOptions
  ): Promise<DataQualitySummary> =>
    api.get<DataQualitySummary>(`/data-trust/quality/${entityType}/${entityId}`, options),

  // Conflicts
  listConflicts: (params: {
    entity_type?: string;
    entity_id?: string;
    status?: string;
    limit?: number;
    offset?: number;
  } = {}, options?: RequestOptions): Promise<{ items: DataConflict[]; total: number }> =>
    api.get("/data-trust/conflicts", { ...options, params }),

  // Disputes
  fileDispute: (data: {
    dispute_target_type: string;
    dispute_target_id: string;
    reason: string;
    explanation?: string;
    evidence_refs?: string[];
  }, options?: RequestOptions): Promise<DisputeRecord> =>
    api.post<DisputeRecord>("/data-trust/disputes", data, options),

  listDisputes: (params: {
    target_type?: string;
    status?: string;
    limit?: number;
    offset?: number;
  } = {}, options?: RequestOptions): Promise<{ items: DisputeRecord[]; total: number }> =>
    api.get("/data-trust/disputes", { ...options, params }),

  // Provenance & history
  getProvenance: (
    entityType: string,
    entityId: string,
    options?: RequestOptions
  ): Promise<ProvenanceChain> =>
    api.get<ProvenanceChain>(`/data-trust/provenance/${entityType}/${entityId}`, options),

  getChangeHistory: (
    entityType: string,
    entityId: string,
    limit = 50,
    options?: RequestOptions
  ): Promise<{ items: ChangeHistoryEntry[] }> =>
    api.get(`/data-trust/history/${entityType}/${entityId}`, {
      ...options,
      params: { limit },
    }),

  // Metrics
  listMetrics: (params: {
    category?: string;
    visibility?: string;
    limit?: number;
  } = {}, options?: RequestOptions): Promise<{ items: MetricDefinition[] }> =>
    api.get("/data-trust/metrics", { ...options, params }),

  // Dashboard
  getDashboard: (options?: RequestOptions): Promise<DataTrustDashboard> =>
    api.get<DataTrustDashboard>("/data-trust/dashboard", options),
}