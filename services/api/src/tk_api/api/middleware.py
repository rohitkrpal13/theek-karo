"""Request correlation and access-log middleware."""

from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from tk_api.core.logging import log_extra, request_id_var

logger = logging.getLogger("tk_api.access")

_REQUEST_HEADER = "X-Request-Id"
_CORRELATION_HEADER = "X-Correlation-Id"
_RESPONSE_HEADER = "X-Request-Id"

_SKIP_PATHS = {"/health", "/ready", "/healthz", "/readyz"}


class CorrelationMiddleware(BaseHTTPMiddleware):
    """Tag every request with a correlation id and emit one structured access log line."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = (
            request.headers.get(_REQUEST_HEADER)
            or request.headers.get(_CORRELATION_HEADER)
            or uuid.uuid4().hex
        )
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            duration_ms = (time.perf_counter() - start) * 1000.0
            request_id_var.reset(token)
        response.headers[_RESPONSE_HEADER] = request_id
        response.headers[_CORRELATION_HEADER] = request_id
        if request.url.path not in _SKIP_PATHS:
            logger.info(
                "request",
                **log_extra(
                    request_id=request_id,
                    method=request.method,
                    path=request.url.path,
                    status=response.status_code,
                    duration_ms=round(duration_ms, 2),
                ),
            )
        return response
