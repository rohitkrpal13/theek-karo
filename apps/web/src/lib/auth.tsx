"use client"

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react"

import { api, ApiError, authApi, setToken } from "@/lib/api"
import type { UserSummary } from "@/lib/api/auth"

export type SessionUser = UserSummary

export interface AuthState {
  user: SessionUser | null
  loading: boolean
  roles: string[]
  permissions: string[]
  hasRole: (role: string) => boolean
  hasPermission: (permission: string) => boolean
  login: (accessToken: string, user: SessionUser) => void
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
    try {
      const me = await api.get<SessionUser>("/users/me")
      setUser(me)
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) setToken(null)
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    api
      .get<SessionUser>("/users/me")
      .then((me) => {
        if (!cancelled) setUser(me)
      })
      .catch((error) => {
        if (error instanceof ApiError && error.status === 401) setToken(null)
        if (!cancelled) setUser(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const login = useCallback((accessToken: string, nextUser: SessionUser) => {
    setToken(accessToken)
    setUser(nextUser)
  }, [])

  const logout = useCallback(async () => {
    try {
      // Best-effort server notification
      setToken(null)
      setUser(null)
    } catch {
      setToken(null)
      setUser(null)
    }
  }, [])

  const logoutAll = useCallback(async () => {
    try {
      await authApi.logoutAll()
    } finally {
      setToken(null)
      setUser(null)
    }
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
    [
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
    ],
  )

  return <authContext.Provider value={value}>{children}</authContext.Provider>
}

export function useAuth(): AuthState {
  return useContext(authContext)
}