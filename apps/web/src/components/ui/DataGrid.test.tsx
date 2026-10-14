import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { DataGrid, type Column } from "@/components/ui/DataGrid"

type Row = { id: string; name: string; status: string }

const columns: Column<Row>[] = [
  { key: "id", header: "ID", width: "80px" },
  { key: "name", header: "Name", sortable: true, accessor: (r) => r.name },
  { key: "status", header: "Status", render: (r) => <span>{r.status}</span> },
]

describe("DataGrid", () => {
  it("renders rows", () => {
    const data: Row[] = [
      { id: "1", name: "Alpha", status: "ok" },
      { id: "2", name: "Beta", status: "fail" },
    ]
    render(<DataGrid data={data} columns={columns} getRowId={(r) => r.id} />)
    expect(screen.getByText("Alpha")).toBeInTheDocument()
    expect(screen.getByText("Beta")).toBeInTheDocument()
  })

  it("shows empty state", () => {
    render(<DataGrid data={[]} columns={columns} emptyTitle="No data here" />)
    expect(screen.getByText("No data here")).toBeInTheDocument()
  })

  it("shows loading", () => {
    render(<DataGrid data={[]} columns={columns} loading />)
    // skeleton has aria-hidden but loading renders skeletons
    expect(document.body.innerHTML).toContain("animate-pulse")
  })
})
