"""Boundary ingestion ETL — pure, dialect-safe parts (ADR-006/032).

GeoJSON FeatureCollection → validated ingestion records. Geometry is kept as
the original GeoJSON and bound through ``ST_GeomFromGeoJSON`` at insert time
(Postgres only), so this module stays unit-testable on SQLite.

Rules (ADR-006): every record needs a provenance pair — an ``external_sources``
row (name/publisher/url/license) and a ``gis_boundary_versions`` label that is
the idempotency key: re-ingesting the same label **replaces** the previous
version's rows. Boundaries are data from licensed sources, never hand-drawn.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from tk_api.gis.constants import BOUNDARY_KINDS

GEOJSON_TYPES = {"MultiPolygon", "Polygon"}


class EtlError(ValueError):
    pass


@dataclass
class IngestRecord:
    name: str
    kind: str
    geometry: dict[str, Any]
    name_local: dict[str, str] | None
    external_id: str | None


def validate_source_metadata(meta: dict[str, Any]) -> None:
    missing = [field for field in ("name", "publisher", "url") if not meta.get(field)]
    if missing:
        raise EtlError(f"source metadata missing: {', '.join(missing)}")
    if not isinstance(meta.get("license"), str) or not meta["license"]:
        raise EtlError("source metadata requires a license")


def parse_records(feature_collection: dict[str, Any], kind: str) -> list[IngestRecord]:
    """Parse a GeoJSON FeatureCollection into validated ingestion records."""
    if kind not in BOUNDARY_KINDS:
        raise EtlError(f"unknown boundary kind: {kind} (allowed: {', '.join(BOUNDARY_KINDS)})")
    if feature_collection.get("type") != "FeatureCollection":
        raise EtlError("input must be a GeoJSON FeatureCollection")
    records: list[IngestRecord] = []
    for index, feature in enumerate(feature_collection.get("features", [])):
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            raise EtlError(f"feature #{index} is not a GeoJSON Feature")
        geometry = feature.get("geometry")
        if not isinstance(geometry, dict) or geometry.get("type") not in GEOJSON_TYPES:
            raise EtlError(f"feature #{index} geometry must be Polygon or MultiPolygon")
        properties = feature.get("properties") or {}
        name = properties.get("shapeName") or properties.get("name") or properties.get("osm_name")
        if not isinstance(name, str) or not name.strip():
            raise EtlError(f"feature #{index} has no name in properties")
        name_local = _localized_name(properties)
        external_id = (
            properties.get("shapeISO") or properties.get("shapeID") or properties.get("osm_id")
        )
        records.append(
            IngestRecord(
                name=name.strip(),
                kind=kind,
                geometry=geometry,
                name_local=name_local,
                external_id=str(external_id) if external_id else None,
            )
        )
    if not records:
        raise EtlError("no features found in feature collection")
    return records


def _localized_name(properties: dict[str, Any]) -> dict[str, str] | None:
    """GeoBoundaries carries ``shapeName`` (EN); some excerpts add hi/ta names."""
    localized: dict[str, str] = {}
    for key in ("name_hi", "name_ta", "name_te", "name_bn", "name_en"):
        value = properties.get(key)
        if isinstance(value, str) and value.strip():
            localized[key.replace("name_", "")] = value.strip()
    return localized or None


def parse_places(feature_collection: dict[str, Any], kind: str) -> list[IngestRecord]:
    """Parse a GeoJSON FeatureCollection of POINTS into place records (dev
    fixtures and licensed directory datasets land in gis_places)."""
    if feature_collection.get("type") != "FeatureCollection":
        raise EtlError("input must be a GeoJSON FeatureCollection")
    records: list[IngestRecord] = []
    for index, feature in enumerate(feature_collection.get("features", [])):
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            raise EtlError(f"feature #{index} is not a GeoJSON Feature")
        geometry = feature.get("geometry")
        if not isinstance(geometry, dict) or geometry.get("type") != "Point":
            raise EtlError(f"feature #{index} geometry must be Point")
        properties = feature.get("properties") or {}
        name = properties.get("shapeName") or properties.get("name")
        if not isinstance(name, str) or not name.strip():
            raise EtlError(f"feature #{index} has no name in properties")
        records.append(
            IngestRecord(
                name=name.strip(),
                kind=kind,
                geometry=geometry,
                name_local=_localized_name(properties),
                external_id=properties.get("shapeID") or properties.get("id"),
            )
        )
    if not records:
        raise EtlError("no features found in feature collection")
    return records


def geojson_to_text(geometry: dict[str, Any]) -> str:
    """JSON text suitable for ST_GeomFromGeoJSON."""
    return json.dumps(geometry)


def stable_source_name(name: str, kind: str) -> str:
    return f"{name} ({kind})"
