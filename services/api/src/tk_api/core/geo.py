"""Spatial column typing shared by Postgres (PostGIS) and SQLite unit tests.

ADR-027: geometry behaviour is exercised only on Postgres. The unit-test schema is
SQLite, which has no spatial types, so :class:`LocationPoint` swaps the mapped
type per dialect (see ``load_dialect_impl``): Postgres gets a GeoAlchemy2
``Geometry(POINT, 4326)`` column (with its auto-created GIST index), SQLite gets a
plain ``Text`` column storing the GeoJSON serialization.

GeoAlchemy2's own bind/result processors are deliberately *not* relied on: a
TypeDecorator wrapping ``Geometry`` bypasses them (WKBElement reaches the driver
and fails), so this module converts between GeoJSON dicts and hex EWKB strings
itself on Postgres.
"""

from __future__ import annotations

import json
import struct
from typing import Any

from sqlalchemy import String
from sqlalchemy.types import TypeDecorator

try:  # geoalchemy2 is a package dependency; keep the import guarded for cheap tooling
    from geoalchemy2 import Geometry, WKBElement
except ImportError:  # pragma: no cover
    Geometry = None  # type: ignore[assignment, misc]
    WKBElement = None  # type: ignore[assignment, misc]

_WKB_POINT = 1
_EWKB_SRID_FLAG = 0x20000000


def _point_to_ewkb_hex(lon: float, lat: float, srid: int) -> str:
    return struct.pack(
        "<BIIdd", 1, _WKB_POINT | _EWKB_SRID_FLAG, srid, float(lon), float(lat)
    ).hex()


def _wkb_to_coords(data: bytes) -> tuple[float, float]:
    byte_order = data[0]
    endian = "<" if byte_order == 1 else ">"
    (wkb_type,) = struct.unpack(endian + "I", data[1:5])
    offset = 5
    if wkb_type & _EWKB_SRID_FLAG:
        offset += 4  # skip the SRID int32
    (lon, lat) = struct.unpack(endian + "dd", data[offset : offset + 16])
    return lon, lat


def _hex_to_geojson(raw: str | bytes | Any) -> dict[str, Any]:
    if isinstance(raw, WKBElement):
        data: bytes = raw.data
    elif isinstance(raw, str):
        data = bytes.fromhex(raw)
    elif isinstance(raw, (bytes, memoryview)):
        data = bytes(raw)
    else:
        raise TypeError(f"unexpected location value: {type(raw)!r}")
    lon, lat = _wkb_to_coords(data)
    return {"type": "Point", "coordinates": [lon, lat]}


class LocationPoint(TypeDecorator[Any]):
    """A POINT(4326) on Postgres; a GeoJSON string on SQLite."""

    cache_ok = True
    impl = String(4096)
    # geoalchemy2's admin hooks inspect ``spatial_index`` on the column type;
    # spatial indexes are managed explicitly by migrations, so expose False
    # instead of proxying to the String impl (which has no such attribute).
    spatial_index = False

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect is None:
            # geoalchemy2's spatial-management introspection calls
            # load_dialect_impl(None); fall back to the base impl
            return self.impl
        if self._is_postgres(dialect):
            return dialect.type_descriptor(Geometry(geometry_type="POINT", srid=4326))
        return dialect.type_descriptor(String(4096))

    @staticmethod
    def _is_postgres(dialect: Any) -> bool:
        try:
            return bool(dialect.name == "postgresql")
        except (AttributeError, TypeError):
            return False

    def bind_processor(self, dialect: Any) -> Any:
        if not self._is_postgres(dialect):
            return lambda value: json.dumps(value) if value is not None else None
        return self._bind_hex

    def _bind_hex(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, WKBElement):
            return value.data.hex() if isinstance(value.data, bytes) else value.data
        if isinstance(value, str):
            return value  # already hex EWKB
        lon, lat = value["coordinates"]
        return _point_to_ewkb_hex(lon, lat, 4326)

    def result_processor(self, dialect: Any, coltype: Any) -> Any:
        if not self._is_postgres(dialect):
            return lambda value: json.loads(value) if value else None
        return _hex_to_geojson

    def copy(self, **kw: Any) -> LocationPoint:
        return LocationPoint()
