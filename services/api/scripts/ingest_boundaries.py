"""Boundary ingestion ETL CLI (ADR-006/032).

Usage:
  # fetch the canonical open dataset (geoBoundaries India ADM1, CC-BY) and load states
  uv run python scripts/ingest_boundaries.py --download-adm1 --kind state \
      --version-label IND-ADM1-2026.05

  # or load any licensed GeoJSON FeatureCollection
  uv run python scripts/ingest_boundaries.py --input file.geojson --kind district \
      --version-label RJ-DIST-2026 --parent-kind state

Idempotent by version label: re-running the same label swaps in the replacement
rows (the old version's boundaries are replaced; history remains in
``gis_boundary_versions``). Boundaries are data, never hand-drawn; every row
carries source + version FKs (ADR-006).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import urllib.request
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.core.config import Settings
from tk_api.core.db import create_engine, create_session_factory
from tk_api.gis.constants import BOUNDARY_KINDS
from tk_api.gis.etl import (
    EtlError,
    geojson_to_text,
    parse_places,
    parse_records,
    validate_source_metadata,
)
from tk_api.provenance.models import ExternalSource

GEOBOUNDARIES_URL = (
    "https://media.githubusercontent.com/media/wmgeolab/geoBoundaries/main/releaseData/"
    "gbOpen/IND/ADM1/geoBoundaries-IND-ADM1_simplified.geojson"
)


def _download(url: str, dest: str) -> None:
    print(f"downloading {url}")
    # Ops-only ETL CLI: url is the hardcoded GEOBOUNDARIES_URL constant or a
    # local file path from --input — never user-controlled network input.
    with urllib.request.urlopen(url, timeout=90) as response:  # nosemgrep
        data = response.read()
    with open(dest, "wb") as handle:
        handle.write(data)
    print(f"saved {dest} ({len(data) / 1e6:.1f} MB)")


async def _version_swap(session: AsyncSession, *, label: str, source_id: Any) -> Any:
    """Return the id of the CURRENT version row, replacing any previous one."""
    existing = (
        await session.execute(
            text("SELECT id FROM gis_boundary_versions WHERE label = :label").bindparams(
                label=label
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        await session.execute(
            text("DELETE FROM gis_boundaries WHERE version_id = :vid").bindparams(vid=existing)
        )
        await session.execute(
            text("DELETE FROM gis_boundary_versions WHERE id = :vid").bindparams(vid=existing)
        )
        await session.flush()
    return (
        await session.execute(
            text(
                "INSERT INTO gis_boundary_versions (id, label, source_id, valid_from, created_at) "
                "VALUES (gen_random_uuid(), :label, :source_id, :valid_from, now()) RETURNING id"
            ).bindparams(label=label, source_id=source_id, valid_from=datetime.now(UTC))
        )
    ).scalar_one()


async def _link_parents(session: AsyncSession, *, parent_kind: str | None, version_id: Any) -> int:
    """Parent wiring by CENTROID CONTAINMENT: each child of this version gets
    the parent-kind boundary that covers its centroid (robust even when the
    dataset carries no parent refs, e.g. geoBoundaries ADM2)."""
    if parent_kind is None:
        return 0
    result = await session.execute(
        text(
            "UPDATE gis_boundaries child "
            "SET parent_id = (SELECT p.id FROM gis_boundaries p "
            "WHERE p.boundary_kind = :parent_kind "
            "AND ST_Covers(p.geom, ST_Centroid(child.geom)) "
            "ORDER BY ST_Area(p.geom) ASC LIMIT 1) "
            "WHERE child.version_id = :vid AND child.parent_id IS NULL"
        ).bindparams(parent_kind=parent_kind, vid=version_id)
    )
    return int(result.rowcount or 0)  # type: ignore[union-attr] - scripts are outside the src mypy gate


async def ingest(
    database_url: str,
    *,
    kind: str,
    feature_collection: dict[str, Any],
    meta: dict[str, Any],
    version_label: str,
    parent_kind: str | None,
) -> dict[str, Any]:
    validate_source_metadata(meta)

    engine = create_engine(database_url)
    try:
        factory = create_session_factory(engine)
        async with factory() as session:
            if kind == "_places_":
                return await _ingest_places(
                    session, feature_collection=feature_collection, meta=meta
                )
            records = parse_records(feature_collection, kind)
            source = await session.scalar(
                select(ExternalSource).where(ExternalSource.url == meta["url"])
            )
            if source is None:
                source = ExternalSource(
                    name=meta["name"],
                    publisher=meta["publisher"],
                    url=meta["url"],
                    license=meta.get("license"),
                    geo_applicability=meta.get("geo_applicability", {}),
                )
                session.add(source)
                await session.flush()

            version_id = await _version_swap(session, label=version_label, source_id=source.id)
            for record in records:
                await session.execute(
                    text(
                        "INSERT INTO gis_boundaries "
                        "(id, boundary_kind, name, name_local, geom, parent_id, source_id, "
                        " version_id, valid_from, created_at, updated_at) "
                        "VALUES (gen_random_uuid(), :kind, :name, :name_local, "
                        " ST_GeomFromGeoJSON(:geom), :parent_id, :source_id, :version_id, "
                        " :valid_from, now(), now())"
                    ).bindparams(
                        kind=kind,
                        name=record.name,
                        name_local=json.dumps(record.name_local) if record.name_local else None,
                        geom=geojson_to_text(record.geometry),
                        parent_id=None,
                        source_id=source.id,
                        version_id=version_id,
                        valid_from=datetime.now(UTC),
                    )
                )
            linked = await _link_parents(session, parent_kind=parent_kind, version_id=version_id)
            await session.commit()
            return {
                "ingested": len(records),
                "version": version_label,
                "parent_linked": linked,
            }
    finally:
        await engine.dispose()


async def _ingest_places(
    session: AsyncSession,
    *,
    feature_collection: dict[str, Any],
    meta: dict[str, Any],
) -> dict[str, Any]:
    """Point records → gis_places (directory data: schools etc.). Replace-per-
    source idempotency (the table has no version column by design)."""
    records = parse_places(feature_collection, "place")
    source = await session.scalar(select(ExternalSource).where(ExternalSource.url == meta["url"]))
    if source is None:
        source = ExternalSource(
            name=meta["name"],
            publisher=meta["publisher"],
            url=meta["url"],
            license=meta.get("license"),
            geo_applicability=meta.get("geo_applicability", {}),
        )
        session.add(source)
        await session.flush()
    # replace any existing rows from this source
    await session.execute(
        text("DELETE FROM gis_places WHERE source_id = :sid").bindparams(sid=source.id)
    )
    for record in records:
        await session.execute(
            text(
                "INSERT INTO gis_places (id, name, name_local, kind, geom, boundary_id, "
                "source_id, created_at) VALUES (gen_random_uuid(), :name, :nl, :kind, "
                "ST_GeomFromGeoJSON(:geom), "
                "(SELECT b.id FROM gis_boundaries b WHERE ST_Covers(b.geom, "
                "ST_GeomFromGeoJSON(:geom)) ORDER BY "
                "array_position(ARRAY['state','district','block','panchayat','ward',"
                "'constituency'], b.boundary_kind) DESC LIMIT 1), :sid, now())"
            ).bindparams(
                name=record.name,
                nl=json.dumps(record.name_local) if record.name_local else None,
                kind=record.kind,
                geom=geojson_to_text(record.geometry),
                sid=source.id,
            )
        )
    await session.commit()
    return {"places_ingested": len(records), "source": source.name}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--kind", required=False, choices=BOUNDARY_KINDS)
    parser.add_argument("--version-label", required=True)
    parser.add_argument("--input", default=None, help="local GeoJSON FeatureCollection file")
    parser.add_argument(
        "--download-adm1", action="store_true", help="fetch geoBoundaries India ADM1 (states)"
    )
    parser.add_argument("--parent-kind", default=None, choices=BOUNDARY_KINDS)
    parser.add_argument(
        "--places",
        action="store_true",
        help="ingest a POINT GeoJSON into gis_places (directory data)",
    )
    parser.add_argument("--source-url", default=None)
    parser.add_argument("--source-name", default="geoBoundaries India ADM1")
    parser.add_argument("--publisher", default="geoBoundaries")
    parser.add_argument("--license", default="CC-BY-4.0")
    args = parser.parse_args()

    if not args.places and not args.kind:
        parser.error("--kind is required unless --places is used")
    if args.download_adm1:
        dest = f"/tmp/{args.version_label}.geojson"
        _download(GEOBOUNDARIES_URL, dest)
        args.input = dest
    if not args.input:
        parser.error("--input (or --download-adm1) is required")
    with open(args.input, encoding="utf-8") as handle:
        feature_collection = json.load(handle)

    meta = {
        "name": args.source_name,
        "publisher": args.publisher,
        "url": args.source_url or GEOBOUNDARIES_URL,
        "license": args.license,
        "geo_applicability": {"country": "IND"},
    }
    url = args.database_url or Settings().database_url
    try:
        result = asyncio.run(
            ingest(
                url,
                kind="_places_" if args.places else args.kind,
                feature_collection=feature_collection,
                meta=meta,
                version_label=args.version_label,
                parent_kind=args.parent_kind,
            )
        )
        print(f"INGEST OK: {result}")
        return 0
    except (EtlError, ValueError, KeyError) as exc:
        print(f"INGEST FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
