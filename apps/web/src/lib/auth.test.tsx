import { renderHook, act } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { AuthProvider, useAuth } from "@/lib/auth"
import type { SessionUser } from "@/lib/auth"

describe("AuthProvider and useAuth", () => {
  it("initializes with unauthenticated guest state", () => {
    const { result } = renderHook(() => useAuth(), {
      wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider>,
    })

    expect(result.current.user).toBeNull()
    expect(result.current.roles).toEqual([])
    expect(result.current.hasRole("citizen")).toBe(false)
    expect(result.current.hasPermission("reports.create")).toBe(false)
  })

  it("evaluates roles and permissions correctly when logged in as citizen", () => {
    const { result } = renderHook(() => useAuth(), {
      wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider>,
    })

    const mockCitizen: SessionUser = {
      id: "usr-1",
      email: "citizen@example.com",
      phone: null,
      username: "citizen_jane",
      display_name: "Citizen Jane",
      contact_masked: "c•••@example.com",
      roles: ["citizen"],
      permissions: ["reports.create", "reports.read_public", "identity.update_self"],
      locale: "hi",
      status: "active",
      trust_score: 1.0,
    }

    act(() => {
      result.current.login("mock-jwt-token", mockCitizen)
    })

    expect(result.current.user?.username).toBe("citizen_jane")
    expect(result.current.hasRole("citizen")).toBe(true)
    expect(result.current.hasRole("admin")).toBe(false)
    expect(result.current.hasPermission("reports.create")).toBe(true)
    expect(result.current.hasPermission("reports.moderate")).toBe(false)
  })

  it("grants all permissions to super_admin wildcard", () => {
    const { result } = renderHook(() => useAuth(), {
      wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider>,
    })

    const mockSuperAdmin: SessionUser = {
      id: "usr-admin",
      email: "root@example.com",
      phone: null,
      username: "super_admin",
      display_name: "Super Administrator",
      contact_masked: "r•••@example.com",
      roles: ["super_admin"],
      permissions: ["*"],
      locale: "en",
      status: "active",
      trust_score: 5.0,
    }

    act(() => {
      result.current.login("admin-jwt-token", mockSuperAdmin)
    })

    expect(result.current.hasRole("super_admin")).toBe(true)
    expect(result.current.hasRole("citizen")).toBe(true) // Super admin possesses role override
    expect(result.current.hasPermission("reports.create")).toBe(true)
    expect(result.current.hasPermission("system.manage")).toBe(true)
    expect(result.current.hasPermission("any.unlisted.permission")).toBe(true)
  })

  it("clears user and session on logout", () => {
    const { result } = renderHook(() => useAuth(), {
      wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider>,
    })

    act(() => {
      result.current.login("jwt-token", {
        id: "u-1",
        email: "a@example.com",
        phone: null,
        username: "user_a",
        display_name: "User A",
        contact_masked: "a•••@example.com",
        roles: ["citizen"],
        permissions: ["reports.create"],
        locale: "en",
        status: "active",
        trust_score: 0.0,
      })
    })

    expect(result.current.user).not.toBeNull()

    act(() => {
      void result.current.logout()
    })

    expect(result.current.user).toBeNull()
    expect(result.current.roles).toEqual([])
  })
})
