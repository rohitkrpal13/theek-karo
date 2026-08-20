"""GIS unit tests: ETL parsing/validation (dialect-safe) + the SQLite schema
guard (ADR-026/027: GIS geometry tables must never reach unit DBs)."""

from __future__ import annotations

import pytest

from tk_api.core.db import Base
from tk_api.gis.etl import EtlError, parse_places, parse_records, validate_source_metadata

JAIPUR_STATE = {
    "type": "Feature",
    "properties": {
        "shapeName": "Rajasthan",
        "shapeISO": "IN-RJ",
        "name_hi": "राजस्थान",
    },
    "geometry": {
        "type": "Polygon",
        "coordinates": [
            [
                [69.0, 23.0],
                [78.0, 23.0],
                [78.0, 30.0],
                [69.0, 30.0],
                [69.0, 23.0],
            ]
        ],
    },
}

DELHI_STATE = {
    "type": "Feature",
    "properties": {"shapeName": "Delhi", "shapeISO": "IN-DL"},
    "geometry": {
        "type": "MultiPolygon",
        "coordinates": [
            [
                [
                    [76.8, 28.4],
                    [77.3, 28.4],
                    [77.3, 28.9],
                    [76.8, 28.9],
                    [76.8, 28.4],
                ]
            ]
        ],
    },
}


def _collection(*features: dict) -> dict:
    return {"type": "FeatureCollection", "features": list(features)}


class TestParseRecords:
    def test_parses_polygon_and_multipolygon(self) -> None:
        records = parse_records(_collection(JAIPUR_STATE, DELHI_STATE), "state")
        assert [r.name for r in records] == ["Rajasthan", "Delhi"]
        rj = records[0]
        assert rj.kind == "state"
        assert rj.name_local == {"hi": "राजस्थान"}
        assert rj.external_id == "IN-RJ"
        assert rj.geometry["type"] == "Polygon"

    def test_rejects_bad_kind(self) -> None:
        with pytest.raises(EtlError, match="unknown boundary kind"):
            parse_records(_collection(JAIPUR_STATE), "country")

    def test_rejects_non_featurecollection(self) -> None:
        with pytest.raises(EtlError, match="FeatureCollection"):
            parse_records({"type": "Feature", "properties": {}, "geometry": {}}, "state")

    def test_rejects_geometry_types(self) -> None:
        point = dict(JAIPUR_STATE)
        point["geometry"] = {"type": "Point", "coordinates": [75.0, 26.0]}
        with pytest.raises(EtlError, match="geometry must be Polygon or MultiPolygon"):
            parse_records(_collection(point), "state")

    def test_rejects_unnamed_features(self) -> None:
        unnamed = dict(JAIPUR_STATE)
        unnamed["properties"] = {"shapeISO": "IN-RJ"}
        with pytest.raises(EtlError, match="no name"):
            parse_records(_collection(unnamed), "state")

    def test_empty_collection(self) -> None:
        with pytest.raises(EtlError, match="no features"):
            parse_records(_collection(), "state")


class TestSourceMetadata:
    def test_requires_name_publisher_url_license(self) -> None:
        validate_source_metadata(
            {"name": "X", "publisher": "Y", "url": "https://z", "license": "CC-BY-4.0"}
        )
        with pytest.raises(EtlError, match="publisher"):
            validate_source_metadata({"name": "X", "url": "https://z", "license": "CC-BY-4.0"})
        with pytest.raises(EtlError, match="license"):
            validate_source_metadata(
                {"name": "X", "publisher": "Y", "url": "https://z", "license": ""}
            )


class TestParsePlaces:
    def test_point_records_and_links(self) -> None:
        collection = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"shapeName": "GHS Jaipur", "shapeID": "S1"},
                    "geometry": {"type": "Point", "coordinates": [75.7873, 26.9124]},
                }
            ],
        }
        records = parse_places(collection, "place")
        assert len(records) == 1
        assert records[0].name == "GHS Jaipur"
        assert records[0].external_id == "S1"
        assert records[0].geometry["type"] == "Point"

    def test_rejects_non_points_and_nameless(self) -> None:
        bad = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"shapeName": "X"},
                    "geometry": {"type": "Point", "coordinates": [1, 2]},
                }
            ],
        }
        assert parse_places(bad, "place")[0].name == "X"
        with pytest.raises(EtlError, match="geometry must be Point"):
            parse_places(
                {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "properties": {"shapeName": "X"},
                            "geometry": {
                                "type": "Polygon",
                                "coordinates": [[[0, 0], [1, 1], [0, 1], [0, 0]]],
                            },
                        }
                    ],
                },
                "place",
            )
        with pytest.raises(EtlError, match="no name"):
            parse_places(
                {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "properties": {"shapeID": "S"},
                            "geometry": {"type": "Point", "coordinates": [1, 2]},
                        }
                    ],
                },
                "place",
            )


class TestSqliteSchemaGuard:
    def test_gis_tables_never_reach_unit_schema(self) -> None:
        # importing the app (routers → service) must not register geometry tables
        assert "gis_boundaries" not in Base.metadata.tables
        assert "gis_places" not in Base.metadata.tables
