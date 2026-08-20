import { render, screen, fireEvent } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { MapExplore, type MapEntity } from "./MapExplore"

describe("MapExplore component", () => {
  const mockEntities: MapEntity[] = [
    {
      id: "inst-1",
      kind: "institution",
      title: "Government High School",
      subtitle: "Active · School",
      operational_status: "operational",
      lon: 75.7873,
      lat: 26.9124,
    },
    {
      id: "rep-1",
      kind: "report",
      title: "Water pipeline rupture",
      subtitle: "Ticket #TK-001",
      status: "submitted",
      severity: "high",
      ticket_no: "TK-001",
      lon: 75.7880,
      lat: 26.9130,
    },
  ]

  it("renders map with items and allows switching to list view", () => {
    render(<MapExplore entities={mockEntities} />)

    expect(screen.getByRole("status")).toHaveTextContent("2")
    expect(screen.getByRole("status")).toHaveTextContent("items in viewport")

    // Switch to List View
    const listBtn = screen.getByRole("button", { name: /List View/i })
    fireEvent.click(listBtn)

    expect(screen.getByText("Government High School")).toBeInTheDocument()
    expect(screen.getByText("Water pipeline rupture")).toBeInTheDocument()
  })

  it("displays marker popup details when an entity is selected", () => {
    const onSelect = vi.fn()
    render(
      <MapExplore
        entities={mockEntities}
        selectedEntity={mockEntities[0]}
        onSelectEntity={onSelect}
      />
    )

    expect(screen.getByText("Public Institution")).toBeInTheDocument()
    expect(screen.getByText("Government High School")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /View Twin/i })).toBeInTheDocument()
  })

  it("renders accessible map legend with symbols", () => {
    render(<MapExplore entities={mockEntities} />)

    expect(screen.getByText(/Map Legend:/i)).toBeInTheDocument()
    expect(screen.getByText(/Public Institution/i)).toBeInTheDocument()
    expect(screen.getByText(/Critical \/ High Severity/i)).toBeInTheDocument()
  })
})
