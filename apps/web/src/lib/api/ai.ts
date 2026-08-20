import { api, type RequestOptions } from "@/lib/api"
import type {
  AiFeedbackCreate,
  AiUsageStats,
  CivicChatRequest,
  CivicChatResponse,
  DuplicateAnalysisOutput,
  InstitutionSummaryOutput,
  ReportClassificationOutput,
  TranslationRequest,
  TranslationResponse,
} from "@/lib/types"

export const aiApi = {
  chat: (payload: CivicChatRequest, options?: RequestOptions): Promise<CivicChatResponse> =>
    api.post<CivicChatResponse>("/ai/chat", payload, options),

  classifyReport: (
    payload: { title: string; description: string; fields?: Record<string, unknown> },
    options?: RequestOptions,
  ): Promise<ReportClassificationOutput> =>
    api.post<ReportClassificationOutput>("/ai/classify-report", payload, options),

  checkDuplicate: (
    payload: {
      target_title: string
      target_description: string
      candidate_title: string
      candidate_description: string
      candidate_status?: string
      candidate_ticket_no?: string
      distance_m?: number
    },
    options?: RequestOptions,
  ): Promise<DuplicateAnalysisOutput> =>
    api.post<DuplicateAnalysisOutput>("/ai/duplicate-check", payload, options),

  getInstitutionSummary: (
    institutionId: string,
    options?: RequestOptions,
  ): Promise<InstitutionSummaryOutput> =>
    api.get<InstitutionSummaryOutput>(`/ai/institutions/${institutionId}/summary`, options),

  translate: (
    payload: TranslationRequest,
    options?: RequestOptions,
  ): Promise<TranslationResponse> =>
    api.post<TranslationResponse>("/ai/translate", payload, options),

  submitFeedback: (
    payload: AiFeedbackCreate,
    options?: RequestOptions,
  ): Promise<{ status: string; id: string }> =>
    api.post<{ status: string; id: string }>("/ai/feedback", payload, options),

  getUsageStats: (options?: RequestOptions): Promise<AiUsageStats> =>
    api.get<AiUsageStats>("/ai/admin/usage", options),

  listTools: (options?: RequestOptions): Promise<{ tools: Array<{ name: string; description: string }> }> =>
    api.get<{ tools: Array<{ name: string; description: string }> }>("/ai/tools", options),

  // Conversation History (Phase 8)
  listConversations: (
    options?: RequestOptions,
  ): Promise<{ conversations: Array<{ id: string; title: string; created_at: string; updated_at: string }>; count: number }> =>
    api.get<{ conversations: Array<{ id: string; title: string; created_at: string; updated_at: string }>; count: number }>("/ai/conversations", options),

  getConversationMessages: (
    conversationId: string,
    options?: RequestOptions,
  ): Promise<{ messages: Array<{ id: string; role: string; content: string; created_at: string }>; count: number }> =>
    api.get<{ messages: Array<{ id: string; role: string; content: string; created_at: string }>; count: number }>(
      `/ai/conversations/${conversationId}/messages`,
      options,
    ),

  createConversation: (
    payload: { title?: string; session_id?: string },
    options?: RequestOptions,
  ): Promise<{ id: string; title: string; created_at: string }> =>
    api.post<{ id: string; title: string; created_at: string }>("/ai/conversations", payload, options),

  saveConversationMessage: (
    conversationId: string,
    payload: { role: string; content: string },
    options?: RequestOptions,
  ): Promise<{ id: string; role: string; content: string; created_at: string }> =>
    api.post<{ id: string; role: string; content: string; created_at: string }>(
      `/ai/conversations/${conversationId}/messages`,
      payload,
      options,
    ),

  // Triage (Phase 9)
  triageReport: (
    reportId: string,
    options?: RequestOptions,
  ): Promise<Record<string, unknown>> =>
    api.post<Record<string, unknown>>(`/ai/triage/${reportId}`, {}, options),

  // Moderation (Phase 9)
  moderateContent: (
    payload: { content: string; content_type?: string; content_id?: string },
    options?: RequestOptions,
  ): Promise<Record<string, unknown>> =>
    api.post<Record<string, unknown>>("/ai/moderate", payload, options),
}
