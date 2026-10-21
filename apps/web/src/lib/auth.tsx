"use client"

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react"

import {
  api,
  ApiError,
  clearAuthTokens,
  getToken,
  setRefreshToken,
  setToken,
} from "@/lib/api"
import type { UserSummary } from "@/lib/api/auth"

export type SessionUser = UserSummary

export interface AuthState {
  user: SessionUser | null
  loading: boolean
  roles: string[]
  permissions: string[]
  hasRole: (role: string) => boolean
  hasPermission: (permission: string) => boolean
  // supports both legacy (access, user) and modern (access, refresh, user)
  login: (accessToken: string, userOrRefresh: string | SessionUser, maybeUser?: SessionUser) => void
  logout: () => Promise<void>
  logoutAll: () => Promise<void>
  refresh: () => Promise<void>
}

const authContext = createContext<AuthState>({
  user: null,
  loading: true,
  roles: [],
  permissions: [],
  hasRole: () => false,
  hasPermission: () => false,
  login: () => undefined,
  logout: async () => undefined,
  logoutAll: async () => undefined,
  refresh: async () => undefined,
})

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    const token = getToken()
    if (!token) {
      setUser(null)
      setLoading(false)
      return
    }
    try {
      const me = await api.get<SessionUser>("/users/me")
      setUser(me)
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        // token expired — api client already attempted refresh via refresh_token;
        // if still 401, clear and stay logged out.
        clearAuthTokens()
      }
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    const token = getToken()
    if (!token) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- initial auth check
      setLoading(false)
      return
    }
    api
      .get<SessionUser>("/users/me")
      .then((me) => {
        if (!cancelled) setUser(me)
      })
      .catch((error) => {
        if (error instanceof ApiError && error.status === 401) clearAuthTokens()
        if (!cancelled) setUser(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  // cross-tab sync
  useEffect(() => {
    const onStorage = (e: StorageEvent): void => {
      if (e.key === "tk_access_token" && e.newValue === null) setUser(null)
    }
    window.addEventListener("storage", onStorage)
    return () => window.removeEventListener("storage", onStorage)
  }, [])

  const login = useCallback(
    (accessToken: string, userOrRefresh: string | SessionUser, maybeUser?: SessionUser) => {
      // flexible overload: login(access, user) OR login(access, refresh, user)
      let refreshToken: string | null = null
      let nextUser: SessionUser
      if (typeof userOrRefresh === "string") {
        refreshToken = userOrRefresh
        nextUser = maybeUser as SessionUser
      } else {
        nextUser = userOrRefresh
        // try to infer refresh from maybeUser if passed as third?
        if (maybeUser && typeof (maybeUser as unknown as string) === "string") {
          refreshToken = maybeUser as unknown as string
        }
      }
      setToken(accessToken)
      if (refreshToken) setRefreshToken(refreshToken)
      setUser(nextUser)
    },
    [],
  )

  const logout = useCallback(async () => {
    const hadToken = Boolean(getToken())
    clearAuthTokens()
    setUser(null)
    if (hadToken) {
      try {
        await api.post("/auth/logout", {}).catch(() => {})
      } catch {}
    }
  }, [])

  const logoutAll = useCallback(async () => {
    clearAuthTokens()
    setUser(null)
    try {
      await api.post("/auth/logout-all", {}).catch(() => {})
    } catch {}
  }, [])

  const roles = useMemo(() => user?.roles ?? [], [user])
  const permissions = useMemo(() => user?.permissions ?? [], [user])

  const hasRole = useCallback(
    (role: string) => roles.includes("super_admin") || roles.includes(role),
    [roles],
  )

  const hasPermission = useCallback(
    (permission: string) =>
      permissions.includes("*") ||
      permissions.includes(permission) ||
      roles.includes("super_admin"),
    [permissions, roles],
  )

  const value = useMemo(
    () => ({
      user,
      loading,
      roles,
      permissions,
      hasRole,
      hasPermission,
      login,
      logout,
      logoutAll,
      refresh,
    }),
    [user, loading, roles, permissions, hasRole, hasPermission, login, logout, logoutAll, refresh],
  )

  return <authContext.Provider value={value}>{children}</authContext.Provider>
}

export function useAuth(): AuthState {
  return useContext(authContext)
}

export function RequireAuth({
  children,
  fallback,
  role,
  permission,
}: {
  children: React.ReactNode
  fallback?: React.ReactNode
  role?: string
  permission?: string
}): React.ReactNode {
  const { user, loading, hasRole, hasPermission } = useAuth()
  if (loading) return <p className="p-4 text-sm text-(--color-ink-muted)">Loading…</p>
  if (!user) return fallback ?? <p className="p-4 text-sm">Please sign in.</p>
  if (role && !hasRole(role)) return fallback ?? <p className="p-4 text-sm">Forbidden.</p>
  if (permission && !hasPermission(permission)) return fallback ?? <p className="p-4 text-sm">Forbidden.</p>
  return children
}
