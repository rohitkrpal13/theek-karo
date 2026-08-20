import { api, type RequestOptions } from "@/lib/api"

export type DepartmentStatus = "active" | "inactive"

export interface DepartmentType {
  id: string
  code: string
  name_key: string
  is_active: boolean
  created_at: string
}

export interface Department {
  id: string
  slug: string
  name: string
  department_type_id: string
  parent_department_id: string | null
  jurisdiction_geography_id: string | null
  description: string | null
  official_contact: string | null
  official_email: string | null
  official_phone: string | null
  status: DepartmentStatus
  metadata: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface DepartmentListItem {
  id: string
  slug: string
  name: string
  department_type_id: string
  parent_department_id: string | null
  jurisdiction_geography_id: string | null
  description: string | null
  status: DepartmentStatus
  metadata: Record<string, unknown>
}

export interface DepartmentMember {
  id: string
  user_id: string
  department_id: string
  role_in_department: string
  scope_geography_id: string | null
  is_active: boolean
  created_at: string
}

export interface MyDepartment {
  department_id: string
  department_name: string | null
  department_slug: string | null
  role_in_department: string
  scope_geography_id: string | null
  is_active: boolean
}

export type VerificationState = "pending" | "verified" | "suspended" | "revoked"

export interface OrganizationVerification {
  id: string
  user_id: string
  organization_name: string
  department_id: string | null
  institution_id: string | null
  verification_state: VerificationState
  submitted_email: string | null
  submitted_reason: string | null
  verified_by: string | null
  verified_at: string | null
  scope_note: string | null
  created_at: string
}

export const departmentsApi = {
  listTypes: (options?: RequestOptions): Promise<DepartmentType[]> =>
    api.get<DepartmentType[]>("/departments/types", options),

  createType: (
    payload: { code: string; name_key: string; is_active?: boolean },
    options?: RequestOptions,
  ): Promise<DepartmentType> =>
    api.post<DepartmentType>("/departments/types", payload, options),

  list: (
    params?: { include_inactive?: boolean; department_type_id?: string; q?: string },
    options?: RequestOptions,
  ): Promise<DepartmentListItem[]> =>
    api.get<DepartmentListItem[]>("/departments", { ...options, params }),

  get: (id: string, options?: RequestOptions): Promise<Department> =>
    api.get<Department>(`/departments/${id}`, options),

  create: (
    payload: {
      slug: string
      name: string
      department_type_id: string
      parent_department_id?: string | null
      jurisdiction_geography_id?: string | null
      description?: string | null
      official_contact?: string | null
      official_email?: string | null
      official_phone?: string | null
      metadata?: Record<string, unknown>
    },
    options?: RequestOptions,
  ): Promise<{ id: string; slug: string }> =>
    api.post<{ id: string; slug: string }>("/departments", payload, options),

  my: (options?: RequestOptions): Promise<MyDepartment[]> =>
    api.get<MyDepartment[]>("/departments/me", options),

  listMembers: (departmentId: string, options?: RequestOptions): Promise<DepartmentMember[]> =>
    api.get<DepartmentMember[]>(`/departments/${departmentId}/members`, options),

  addMember: (
    departmentId: string,
    payload: { user_id: string; role_in_department?: string; scope_geography_id?: string | null },
    options?: RequestOptions,
  ): Promise<{ id: string; user_id: string }> =>
    api.post<{ id: string; user_id: string }>(
      `/departments/${departmentId}/members`,
      payload,
      options,
    ),

  listVerifications: (
    params?: { state?: VerificationState },
    options?: RequestOptions,
  ): Promise<OrganizationVerification[]> =>
    api.get<OrganizationVerification[]>("/departments/verifications", { ...options, params }),

  requestVerification: (
    payload: {
      organization_name: string
      department_id?: string | null
      institution_id?: string | null
      submitted_email?: string | null
      submitted_reason?: string | null
    },
    options?: RequestOptions,
  ): Promise<OrganizationVerification> =>
    api.post<OrganizationVerification>("/departments/verifications", payload, options),

  reviewVerification: (
    verificationId: string,
    payload: { state: VerificationState; scope_note?: string | null },
    options?: RequestOptions,
  ): Promise<OrganizationVerification> =>
    api.post<OrganizationVerification>(
      `/departments/verifications/${verificationId}/review`,
      payload,
      options,
    ),
}