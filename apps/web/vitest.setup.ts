import "@testing-library/jest-dom/vitest"
import { vi } from "vitest"

// jsdom lacks matchMedia / IntersectionObserver; provide minimal stubs
if (typeof window !== "undefined" && !window.matchMedia) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  })
}
if (typeof window !== "undefined" && !("IntersectionObserver" in window)) {
  class MockIO {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  }
  Object.defineProperty(window, "IntersectionObserver", {
    writable: true,
    configurable: true,
    value: MockIO,
  })
  // also global for direct `new IntersectionObserver` in modules
  // @ts-expect-error — global fallback for jsdom
  globalThis.IntersectionObserver = MockIO
}

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
  }),
  useParams: () => ({ locale: "en", id: "123" }),
  usePathname: () => "/en",
  useSearchParams: () => new URLSearchParams(),
}))
