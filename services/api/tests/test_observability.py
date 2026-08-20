"""Observability tests (Step 13).

Covers the liveness/readiness probes (``/health``, ``/live``, ``/ready`` and
their aliases) and the structured JSON log formatter: single-line JSON records
that carry the request correlation id.
"""

from __future__ import annotations

import json
import logging

from tk_api.core.logging import JsonFormatter, request_id_var


class TestHealthEndpoints:
    def test_liveness_aliases(self, client) -> None:  # type: ignore[no-untyped-def]
        for path in ("/health", "/healthz", "/live", "/livez"):
            response = client.get(path)
            assert response.status_code == 200, path
            assert response.json() == {"status": "ok"}

    def test_readiness_aliases(self, client) -> None:  # type: ignore[no-untyped-def]
        for path in ("/ready", "/readyz"):
            response = client.get(path)
            assert response.status_code == 200, path
            body = response.json()
            assert body["status"] == "ok"
            assert body["checks"]["database"] == "ok"


class TestJsonLogging:
    def test_formatter_emits_single_line_json_with_request_id(self) -> None:  # type: ignore[no-untyped-def]
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="tk_api.access",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="request",
            args=(),
            exc_info=None,
        )
        record.extra_fields = {"method": "GET", "status": 200, "duration_ms": 3.5}

        token = request_id_var.set("req-abc")
        try:
            line = formatter.format(record)
        finally:
            request_id_var.reset(token)

        parsed = json.loads(line)  # single-line, parseable JSON
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "tk_api.access"
        assert parsed["msg"] == "request"
        assert parsed["request_id"] == "req-abc"
        assert parsed["method"] == "GET"
        assert parsed["status"] == 200
        assert parsed["duration_ms"] == 3.5

    def test_formatter_omits_request_id_when_unset(self) -> None:  # type: ignore[no-untyped-def]
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="tk_api.worker",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="sweep done",
            args=(),
            exc_info=None,
        )
        record.extra_fields = {"purged": 5}
        parsed = json.loads(formatter.format(record))
        assert "request_id" not in parsed
        assert parsed["purged"] == 5
