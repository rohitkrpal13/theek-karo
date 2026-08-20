import "@testing-library/jest-dom/vitest"
import { vi } from "vitest"

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
