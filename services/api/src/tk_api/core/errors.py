"""RFC 9457 problem+json error model and exception handlers.

Every non-2xx response is a ProblemDetails document:
type, title, status, detail, instance, and optional structured errors.
Handlers must never leak stack traces or internals (SECURITY.md §4).
"""

from __future__ import annotations

from typing import cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ExceptionHandler

_PROBLEM_BASE = "https://api.theekkar.in/errors"


class ApiError(Exception):
    """Domain error mapped to an RFC 9457 problem response (status, kind, message)."""

    def __init__(self, message: str, status: int = 400, kind: str = "error") -> None:
        super().__init__(message)
        self.status = status
        self.kind = kind


class NotFoundError(ApiError):
    def __init__(self, message: str = "Resource not found", kind: str = "not_found") -> None:
        super().__init__(message, status=404, kind=kind)


class UnauthorizedError(ApiError):
    def __init__(
        self, message: str = "Authentication required", kind: str = "unauthorized"
    ) -> None:
        super().__init__(message, status=401, kind=kind)


class ForbiddenError(ApiError):
    def __init__(self, message: str = "Permission denied", kind: str = "forbidden") -> None:
        super().__init__(message, status=403, kind=kind)


class ConflictError(ApiError):
    def __init__(self, message: str = "Resource conflict", kind: str = "conflict") -> None:
        super().__init__(message, status=409, kind=kind)


class ValidationError(ApiError):
    def __init__(self, message: str = "Validation failed", kind: str = "validation_error") -> None:
        super().__init__(message, status=422, kind=kind)


class RateLimitError(ApiError):
    def __init__(
        self, message: str = "Rate limit exceeded", kind: str = "rate_limit_exceeded"
    ) -> None:
        super().__init__(message, status=429, kind=kind)


class DatabaseError(ApiError):
    def __init__(
        self, message: str = "A database error occurred", kind: str = "database_error"
    ) -> None:
        super().__init__(message, status=500, kind=kind)


class FieldProblem(BaseModel):
    field: str
    reason: str


class ProblemDetails(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
    request_id: str | None = None
    errors: list[FieldProblem] | None = None


_STATUS_TITLES: dict[int, str] = {
    400: "Bad request",
    401: "Unauthenticated",
    403: "Forbidden",
    404: "Not found",
    405: "Method not allowed",
    409: "Conflict",
    422: "Validation error",
    429: "Rate limit exceeded",
    500: "Internal server error",
    503: "Service unavailable",
}


def _slugify(title: str) -> str:
    return title.lower().replace(" ", "-")


def _problem(
    status: int,
    *,
    title: str | None = None,
    detail: str | None = None,
    instance: str | None = None,
    errors: list[FieldProblem] | None = None,
    problem_type: str | None = None,
) -> JSONResponse:
    from tk_api.core.logging import request_id_var

    resolved_title = title or _STATUS_TITLES.get(status, "Error")
    body = ProblemDetails(
        type=problem_type or f"{_PROBLEM_BASE}/{_slugify(resolved_title)}",
        title=resolved_title,
        status=status,
        detail=detail,
        instance=instance,
        request_id=request_id_var.get(),
        errors=errors,
    )
    headers = {"Content-Type": "application/problem+json"}
    if req_id := request_id_var.get():
        headers["X-Correlation-ID"] = req_id
    return JSONResponse(
        status_code=status,
        content=body.model_dump(exclude_none=True),
        headers=headers,
    )


def problem_response(
    status: int,
    *,
    kind: str | None = None,
    detail: str | None = None,
    title: str | None = None,
) -> JSONResponse:
    """Build an RFC 9457 problem+json response with the platform problem type."""
    from tk_api.core.logging import request_id_var

    resolved_title = title or _STATUS_TITLES.get(status, "Error")
    body = ProblemDetails(
        type=f"{_PROBLEM_BASE}/{kind}" if kind else f"{_PROBLEM_BASE}/{_slugify(resolved_title)}",
        title=resolved_title,
        status=status,
        detail=detail,
        instance=None,
        request_id=request_id_var.get(),
    )
    headers = {"Content-Type": "application/problem+json"}
    if req_id := request_id_var.get():
        headers["X-Correlation-ID"] = req_id
    return JSONResponse(
        status_code=status,
        content=body.model_dump(exclude_none=True),
        headers=headers,
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return _problem(
        exc.status_code,
        detail=str(exc.detail) if exc.detail else None,
        instance=str(request.url.path),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors: list[FieldProblem] = []
    for err in exc.errors():
        loc = ".".join(str(part) for part in err.get("loc", []) if part != "body")
        errors.append(FieldProblem(field=loc or "body", reason=str(err.get("msg", "invalid"))))
    return _problem(
        422, detail="Request failed validation", instance=str(request.url.path), errors=errors
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    import logging

    from tk_api.core.logging import log_extra, request_id_var

    logging.getLogger("tk_api").error(
        "Unhandled exception",
        exc_info=exc,
        **log_extra(path=str(request.url.path), request_id=request_id_var.get()),
    )
    return _problem(500, instance=str(request.url.path))


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return _problem(
        exc.status,
        title=_STATUS_TITLES.get(exc.status, "Error"),
        detail=str(exc),
        instance=str(request.url.path),
        problem_type=f"{_PROBLEM_BASE}/{exc.kind}",
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(
        StarletteHTTPException, cast(ExceptionHandler, http_exception_handler)
    )
    app.add_exception_handler(
        RequestValidationError, cast(ExceptionHandler, validation_exception_handler)
    )
    app.add_exception_handler(ApiError, cast(ExceptionHandler, api_error_handler))
    app.add_exception_handler(Exception, cast(ExceptionHandler, unhandled_exception_handler))
