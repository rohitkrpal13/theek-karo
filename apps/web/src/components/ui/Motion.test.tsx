import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { FadeIn, PulseDot, SlideIn } from "@/components/ui/Motion"

describe("Motion primitives", () => {
  it("renders FadeIn children", () => {
    render(<FadeIn>hello fade</FadeIn>)
    expect(screen.getByText("hello fade")).toBeInTheDocument()
  })

  it("renders SlideIn children", () => {
    render(<SlideIn>slide me</SlideIn>)
    expect(screen.getByText("slide me")).toBeInTheDocument()
  })

  it("renders PulseDot", () => {
    const { container } = render(<PulseDot active />)
    expect(container.firstChild).toBeInTheDocument()
  })
})
