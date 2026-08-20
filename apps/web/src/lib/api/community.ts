import { api, type RequestOptions } from "@/lib/api"

export interface InitiativeMemberPublic {
  id: string
  display_name: string
  username: string
}

export interface Initiative {
  id: string
  slug: string
  title: string
  description: string
  category_id: string | null
  geography_id: string | null
  status: string
  goal: string | null
  expected_activities: string[]
  duration_days: number | null
  participation_rules: Record<string, unknown>
  evidence_requirements: Record<string, unknown>
  results: Record<string, unknown> | null
  participant_count: number
  observation_count: number
  accepted_evidence_count: number
  initiator: InitiativeMemberPublic | null
  starts_at: string | null
  ends_at: string | null
  created_at: string
  updated_at: string
  is_member: boolean
  is_organizer: boolean
  is_following: boolean
}

export interface Observation {
  id: string
  kind: string
  notes: string | null
  media_object_id: string | null
  status: string
  created_at: string
  user: InitiativeMemberPublic
}

export interface VolunteerProfile {
  user_id: string
  languages: string[]
  interests: string[]
  categories: string[]
  areas: string[]
  skills: string[]
  availability: Record<string, unknown>
}

export interface VolunteerOpportunity {
  id: string
  initiative_id: string | null
  title: string
  description: string
  location_label: string | null
  geography_id: string | null
  skills: string[]
  participants_needed: number
  participants_count: number
  status: string
  created_by: InitiativeMemberPublic | null
  created_at: string
  my_status: string | null
}

export interface CommunityGroup {
  id: string
  name: string
  slug: string
  description: string | null
  category_id: string | null
  geography_id: string | null
  rules: Record<string, unknown>
  status: string
  owner: InitiativeMemberPublic | null
  member_count: number
  my_role: string | null
  created_at: string
}

export interface Badge {
  code: string
  name: string
  name_hi: string | null
  description: string | null
  criteria: { metric: string; min: number }
}

export interface BadgeProgress {
  metrics: Record<string, number>
  earned: Array<Badge & { current: number; earned: boolean }>
  in_progress: Array<Badge & { current: number; earned: boolean }>
}

export const communityApi = {
  // Initiatives
  listInitiatives: (
    params: {
      status?: string
      category_id?: string
      geography_id?: string
      limit?: number
      offset?: number
    } = {},
    options?: RequestOptions,
  ): Promise<{ items: Initiative[]; count: number }> =>
    api.get<{ items: Initiative[]; count: number }>("/community/initiatives", {
      ...options,
      params,
    }),

  getInitiative: (id: string, options?: RequestOptions): Promise<Initiative> =>
    api.get<Initiative>(`/community/initiatives/${id}`, options),

  createInitiative: (
    payload: Record<string, unknown>,
    options?: RequestOptions,
  ): Promise<Initiative> =>
    api.post<Initiative>("/community/initiatives", payload, options),

  updateInitiative: (
    id: string,
    payload: Record<string, unknown>,
    options?: RequestOptions,
  ): Promise<Initiative> =>
    api.patch<Initiative>(`/community/initiatives/${id}`, payload, options),

  submitInitiative: (id: string, options?: RequestOptions): Promise<Initiative> =>
    api.post<Initiative>(`/community/initiatives/${id}/submit`, {}, options),

  reviewInitiative: (
    id: string,
    decision: "approve" | "reject",
    note?: string,
    options?: RequestOptions,
  ): Promise<Initiative> =>
    api.post<Initiative>(
      `/community/initiatives/${id}/review`,
      { decision, note },
      options,
    ),

  joinInitiative: (id: string, options?: RequestOptions): Promise<Initiative> =>
    api.post<Initiative>(`/community/initiatives/${id}/join`, {}, options),

  leaveInitiative: (id: string, options?: RequestOptions): Promise<Initiative> =>
    api.post<Initiative>(`/community/initiatives/${id}/leave`, {}, options),

  listObservations: (id: string, options?: RequestOptions): Promise<{ items: Observation[]; count: number }> =>
    api.get<{ items: Observation[]; count: number }>(
      `/community/initiatives/${id}/observations`,
      options,
    ),

  addObservation: (
    id: string,
    payload: { kind: string; notes?: string; media_object_id?: string },
    options?: RequestOptions,
  ): Promise<Observation> =>
    api.post<Observation>(`/community/initiatives/${id}/observations`, payload, options),

  reviewObservation: (
    id: string,
    observationId: string,
    decision: "accept" | "reject",
    options?: RequestOptions,
  ): Promise<{ id: string; status: string }> =>
    api.post<{ id: string; status: string }>(
      `/community/initiatives/${id}/observations/${observationId}/review`,
      { decision },
      options,
    ),

  completeInitiative: (
    id: string,
    results: Record<string, unknown>,
    options?: RequestOptions,
  ): Promise<Initiative> =>
    api.post<Initiative>(`/community/initiatives/${id}/complete`, { results }, options),

  followInitiative: (id: string, options?: RequestOptions): Promise<{ status: string }> =>
    api.post<{ status: string }>(`/community/follows/initiative/${id}`, {}, options),

  unfollowInitiative: (id: string, options?: RequestOptions): Promise<{ status: string }> =>
    api.delete<{ status: string }>(`/community/follows/initiative/${id}`, options),

  // Volunteers
  getVolunteerProfile: (options?: RequestOptions): Promise<VolunteerProfile> =>
    api.get<VolunteerProfile>("/community/volunteer/profile", options),

  updateVolunteerProfile: (
    payload: Partial<VolunteerProfile>,
    options?: RequestOptions,
  ): Promise<VolunteerProfile> =>
    api.put<VolunteerProfile>("/community/volunteer/profile", payload, options),

  listOpportunities: (
    params: { status?: string; geography_id?: string; limit?: number; offset?: number } = {},
    options?: RequestOptions,
  ): Promise<{ items: VolunteerOpportunity[]; count: number }> =>
    api.get<{ items: VolunteerOpportunity[]; count: number }>("/community/volunteer/opportunities", {
      ...options,
      params,
    }),

  createOpportunity: (
    payload: Record<string, unknown>,
    options?: RequestOptions,
  ): Promise<VolunteerOpportunity> =>
    api.post<VolunteerOpportunity>("/community/volunteer/opportunities", payload, options),

  getOpportunity: (id: string, options?: RequestOptions): Promise<VolunteerOpportunity> =>
    api.get<VolunteerOpportunity>(`/community/volunteer/opportunities/${id}`, options),

  joinOpportunity: (id: string, options?: RequestOptions): Promise<VolunteerOpportunity> =>
    api.post<VolunteerOpportunity>(
      `/community/volunteer/opportunities/${id}/join`,
      {},
      options,
    ),

  withdrawOpportunity: (id: string, options?: RequestOptions): Promise<VolunteerOpportunity> =>
    api.post<VolunteerOpportunity>(
      `/community/volunteer/opportunities/${id}/withdraw`,
      {},
      options,
    ),

  // Groups
  listGroups: (
    params: { status?: string; geography_id?: string; limit?: number; offset?: number } = {},
    options?: RequestOptions,
  ): Promise<{ items: CommunityGroup[]; count: number }> =>
    api.get<{ items: CommunityGroup[]; count: number }>("/community/groups", {
      ...options,
      params,
    }),

  getGroup: (id: string, options?: RequestOptions): Promise<CommunityGroup> =>
    api.get<CommunityGroup>(`/community/groups/${id}`, options),

  createGroup: (
    payload: { name: string; description?: string; category_id?: string; geography_id?: string; rules?: Record<string, unknown> },
    options?: RequestOptions,
  ): Promise<CommunityGroup> =>
    api.post<CommunityGroup>("/community/groups", payload, options),

  reviewGroup: (
    id: string,
    decision: "approve" | "reject",
    note?: string,
    options?: RequestOptions,
  ): Promise<CommunityGroup> =>
    api.post<CommunityGroup>(`/community/groups/${id}/review`, { decision, note }, options),

  joinGroup: (id: string, options?: RequestOptions): Promise<CommunityGroup> =>
    api.post<CommunityGroup>(`/community/groups/${id}/join`, {}, options),

  leaveGroup: (id: string, options?: RequestOptions): Promise<CommunityGroup> =>
    api.post<CommunityGroup>(`/community/groups/${id}/leave`, {}, options),

  manageGroupMember: (
    id: string,
    targetUserId: string,
    action: "add" | "remove" | "ban" | "promote" | "demote",
    options?: RequestOptions,
  ): Promise<CommunityGroup> =>
    api.post<CommunityGroup>(`/community/groups/${id}/members/${targetUserId}`, { action }, options),

  // Badges
  listBadges: (options?: RequestOptions): Promise<{ items: Badge[] }> =>
    api.get<{ items: Badge[] }>("/community/badges", options),

  myBadges: (options?: RequestOptions): Promise<BadgeProgress> =>
    api.get<BadgeProgress>("/community/badges/me", options),
}
