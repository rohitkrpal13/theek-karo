"""Structured JSON logging with request correlation ids.

Log records are emitted as single-line JSON: timestamp, level, logger, message and
structured extras (request_id, duration_ms, ...). A contextvar carries the request id
so worker tasks and nested calls can correlate with the originating HTTP request.
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        request_id = request_id_var.get()
        if request_id:
            payload["request_id"] = request_id
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        for key, value in getattr(record, "extra_fields", {}).items():
            payload[key] = value
        return json.dumps(payload, ensure_ascii=False, default=str)


class ExtraFieldFilter(logging.Filter):
    """Stash structured extras from log() calls into the record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.extra_fields = getattr(record, "extra_fields", {})
        return True


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(ExtraFieldFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy.engine"):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = True
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def log_extra(**fields: Any) -> dict[str, Any]:
    """Return kwargs for log() calls carrying structured extras for the JSON formatter.

    Usage: ``logger.info("msg", **log_extra(key=value))``
    Produces: ``extra={"extra_fields": {"key": value}}`` consumed by ExtraFieldFilter.
    """
    return {"extra": {"extra_fields": fields}}
