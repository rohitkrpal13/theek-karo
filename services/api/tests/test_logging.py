"""Correlation id and access-log behavior."""

import json
import logging

from tk_api.core.logging import JsonFormatter


def test_request_id_echoed(client) -> None:  # type: ignore[no-untyped-def]
    response = client.get("/api/v1/version", headers={"X-Request-Id": "abc123"})
    assert response.headers["X-Request-Id"] == "abc123"


def test_request_id_generated_when_absent(client) -> None:  # type: ignore[no-untyped-def]
    response = client.get("/api/v1/version")
    assert response.headers["X-Request-Id"]


def test_access_log_extra_fields(client, caplog) -> None:  # type: ignore[no-untyped-def]
    access_logger = logging.getLogger("tk_api.access")
    access_logger.setLevel(logging.INFO)
    caplog.clear()
    client.get("/api/v1/version")
    records = [r for r in caplog.records if r.name == "tk_api.access"]
    assert len(records) == 1
    record = records[0]
    assert record.msg == "request"
    fields = record.extra_fields
    assert fields["method"] == "GET"
    assert fields["path"] == "/api/v1/version"
    assert fields["status"] == 200
    assert isinstance(fields["duration_ms"], float)


def test_json_formatter_emits_valid_json() -> None:
    record = logging.LogRecord("tk_api.test", logging.INFO, __file__, 1, "test message", None, None)
    record.extra_fields = {"request_id": "r1", "duration_ms": 1.5}  # set by ExtraFieldFilter
    payload = json.loads(JsonFormatter().format(record))
    assert payload["level"] == "INFO"
    assert payload["logger"] == "tk_api.test"
    assert payload["msg"] == "test message"
    assert payload["request_id"] == "r1"
    assert payload["duration_ms"] == 1.5
    assert "ts" in payload
