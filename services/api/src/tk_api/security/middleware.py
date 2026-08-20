"""Enhanced security middleware (Phase 28).

Provides:
- SSRF protection for outbound requests
- Enhanced security headers (CSP, HSTS, etc.)
- Request size limits
- Input validation at middleware level
- Abuse detection at request level
"""

from __future__ import annotations

import logging
from typing import ClassVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("tk_api.security.middleware")

# Enhanced security headers
_ENHANCED_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(self), payment=()",
    "X-XSS-Protection": "1; mode=block",
    "Cache-Control": "no-store, no-cache, must-revalidate",
    "Pragma": "no-cache",
}

# CSP header for API responses
_CSP_HEADER = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"

# Paths that skip strict CSP
_CSP_SKIP_PATHS = {"/docs", "/openapi.json", "/redoc"}


class EnhancedSecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add comprehensive security headers to all responses."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)

        # Apply security headers
        for name, value in _ENHANCED_SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)

        # Apply CSP for non-documentation paths
        if not any(request.url.path.startswith(p) for p in _CSP_SKIP_PATHS):
            response.headers.setdefault("Content-Security-Policy", _CSP_HEADER)

        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Enforce request body size limits to prevent abuse."""

    # Default limits by content type
    DEFAULT_LIMITS: ClassVar[dict[str, int]] = {
        "application/json": 1_048_576,  # 1MB
        "multipart/form-data": 10_485_760,  # 10MB
        "application/x-www-form-urlencoded": 524_288,  # 512KB
    }

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        content_type = request.headers.get("content-type", "")

        # Skip for GET/DELETE without body
        if request.method in ("GET", "DELETE", "HEAD", "OPTIONS"):
            return await call_next(request)

        # Check content length
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                limit = self.DEFAULT_LIMITS.get(content_type.split(";")[0], 1_048_576)
                if size > limit:
                    from tk_api.core.errors import problem_response

                    return problem_response(
                        413,
                        kind="payload_too_large",
                        detail=f"Request body exceeds maximum size of {limit} bytes",
                    )
            except ValueError:
                pass

        return await call_next(request)


class SSRFProtectionMiddleware(BaseHTTPMiddleware):
    """SSRF protection middleware.

    Provides the validate_url utility for SSRF checking.
    The dispatch is a pass-through; actual SSRF validation happens at call sites.
    """

    # Blocked hostname patterns
    BLOCKED_HOSTNAMES: ClassVar[set[str]] = {
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "metadata.google.internal",
        "169.254.169.254",  # AWS/GCP metadata
        "metadata.aws.internal",
    }

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        return await call_next(request)

    @classmethod
    def validate_url(cls, url: str) -> bool:
        """Validate that a URL is safe for server-side fetching."""
        from urllib.parse import urlparse

        try:
            parsed = urlparse(url)
        except Exception:
            return False

        # Only allow http/https
        if parsed.scheme not in ("http", "https"):
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        # Block known internal hostnames
        if hostname.lower() in cls.BLOCKED_HOSTNAMES:
            return False

        # Block .local domains
        if hostname.endswith(".local"):
            return False

        # Block IP addresses in private ranges
        import ipaddress

        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                return False
        except ValueError:
            # Not an IP, that's fine
            pass

        return True


class AbuseDetectionMiddleware(BaseHTTPMiddleware):
    """Detect and block abusive requests at the middleware level."""

    # Paths that require abuse monitoring
    MONITORED_PATHS: ClassVar[set[str]] = {
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/otp",
        "/api/v1/reports",
        "/api/v1/cases",
        "/api/v1/communication",
    }

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        # Check if this path requires monitoring
        path = request.url.path
        if not any(path.startswith(p) for p in self.MONITORED_PATHS):
            return await call_next(request)

        # Get client IP
        forwarded = request.headers.get("x-forwarded-for")
        client_ip = (
            forwarded.split(",")[0].strip()
            if forwarded
            else (request.client.host if request.client else "unknown")
        )

        # Check IP blocks (in-memory check for performance)
        # In production, this would use Redis for distributed blocking
        if (
            hasattr(request.app.state, "_blocked_ips")
            and client_ip in request.app.state._blocked_ips
        ):
            from tk_api.core.errors import problem_response

            return problem_response(
                403,
                kind="access_blocked",
                detail="Your access has been temporarily restricted.",
            )

        response = await call_next(request)

        # Track rate limiting headers
        if hasattr(request.state, "rate_limit_remaining"):
            response.headers["X-RateLimit-Remaining"] = str(request.state.rate_limit_remaining)

        return response
