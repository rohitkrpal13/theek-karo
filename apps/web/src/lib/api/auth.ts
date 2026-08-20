import { api } from "@/lib/api"

export interface UserSummary {
  id: string
  email: string | null
  phone: string | null
  username: string | null
  display_name: string
  contact_masked: string | null
  roles: string[]
  permissions: string[]
  locale: string
  status: string
  trust_score: number
  bio?: string | null
  profile_image_url?: string | null
  location_pref?: string | null
}

export interface AuthTokens {
  access_token: string
  expires_in: number
  token_type: string
  refresh_token: string
  user: UserSummary
}

export interface MfaChallengeResponse {
  mfa_required: true
  challenge_token: string
  expires_in: number
  user: { id: string; roles: string[]; mfa_enabled: boolean }
}

export type LoginResponse = AuthTokens | MfaChallengeResponse

export interface MfaStatus {
  enabled: boolean
  required_by_role: boolean
  setup_required: boolean
}

export interface MfaSetupResult {
  secret: string
  otpauth_uri: string
  digits: number
  period: number
}

export interface RegisterPayload {
  contact: string
  display_name: string
  password?: string
  username?: string
  consent: boolean
  terms_version?: string
  locale?: string
  location_pref?: string
}

export interface RegisterResponse {
  status: string
  contact_masked: string
  expires_in: number
  dev_verification_token?: string
  dev_otp_code?: string
}

export interface UserSessionItem {
  id: string
  client_id: string
  ip: string | null
  user_agent: string | null
  created_at: string
  last_seen_at: string
}

export const authApi = {
  register: (payload: RegisterPayload) =>
    api.post<RegisterResponse>("/auth/register", payload),

  verifyEmail: (token: string) =>
    api.post<AuthTokens>("/auth/verify-email", { token }),

  resendVerification: (email: string) =>
    api.post<{ status: string; message: string; dev_verification_token?: string }>(
      "/auth/resend-verification",
      { email },
    ),

  login: (contact: string, password: string) =>
    api.post<LoginResponse>("/auth/login", { contact, password }),

  loginOtp: (contact: string) =>
    api.post<{ status: string; contact_masked: string }>("/auth/login-otp", { contact }),

  verifyOtp: (contact: string, code: string) =>
    api.post<LoginResponse>("/auth/verify-otp", { contact, code }),

  resendOtp: (contact: string) =>
    api.post<{ status: string; contact_masked: string }>("/auth/resend-otp", { contact }),

  verifyMfa: (challengeToken: string, code: string) =>
    api.post<AuthTokens>("/auth/mfa/verify", { challenge_token: challengeToken, code }),

  getMfaStatus: () => api.get<MfaStatus>("/auth/mfa/status"),

  setupMfa: () => api.post<MfaSetupResult>("/auth/mfa/setup"),

  enableMfa: (code: string) => api.post<{ status: string; mfa_enabled: boolean }>("/auth/mfa/enable", { code }),

  disableMfa: (code: string) => api.post<{ status: string; mfa_enabled: boolean }>("/auth/mfa/disable", { code }),

  forgotPassword: (email: string) =>
    api.post<{ status: string; message: string; dev_reset_token?: string }>(
      "/auth/forgot-password",
      { email },
    ),

  resetPassword: (token: string, new_password: string) =>
    api.post<{ status: string }>("/auth/reset-password", { token, new_password }),

  changePassword: (
    current_password: string,
    new_password: string,
    revoke_other_sessions = true,
  ) =>
    api.post<{ status: string }>("/auth/change-password", {
      current_password,
      new_password,
      revoke_other_sessions,
    }),

  getGoogleAuthUrl: (redirectUri: string, state?: string) =>
    api.get<{ url: string; state: string }>("/auth/oauth/google/url", {
      params: { redirect_uri: redirectUri, state },
    }),

  googleCallback: (code: string, state: string, redirectUri: string) =>
    api.post<AuthTokens>("/auth/oauth/google/callback", {
      code,
      state,
      redirect_uri: redirectUri,
    }),

  getSessions: () =>
    api.get<{ items: UserSessionItem[] }>("/auth/sessions"),

  revokeSession: (sessionId: string) =>
    api.delete<{ status: string }>(`/auth/sessions/${sessionId}`),

  logout: (refreshToken: string) =>
    api.post<{ status: string }>("/auth/logout", { refresh_token: refreshToken }),

  logoutAll: () =>
    api.post<{ status: string }>("/auth/logout-all"),

  deleteAccount: () =>
    api.delete<{ status: string }>("/users/me"),

  updateProfile: (data: {
    display_name?: string
    username?: string
    bio?: string
    profile_image_url?: string
    location_pref?: string
    locale?: string
  }) => api.patch<UserSummary>("/users/me", data),
}
