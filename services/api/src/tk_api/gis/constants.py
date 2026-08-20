"""GIS domain constants (kept model-free so the API process never imports the
PostGIS ORM models — ADR-026/027: the SQLite unit schema must not create
geometry tables)."""

BOUNDARY_KINDS = ("ward", "panchayat", "block", "district", "state", "constituency")
