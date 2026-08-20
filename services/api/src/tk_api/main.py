"""Theek Karo API application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tk_api import __version__
from tk_api.ai.gateway import build_gateway
from tk_api.api.middleware import CorrelationMiddleware
from tk_api.api.routers import health
from tk_api.api.security import SecurityHeadersMiddleware
from tk_api.api.v1 import api_v1_router
from tk_api.auth.authorization import configure_mfa_enforcement
from tk_api.auth.otp import build_otp_sender, build_store
from tk_api.core.config import Settings, get_settings
from tk_api.core.db import create_engine
from tk_api.core.errors import register_exception_handlers
from tk_api.core.idempotency import build_idempotency_store
from tk_api.core.logging import configure_logging
from tk_api.core.login_throttle import LoginThrottle
from tk_api.core.metrics import MetricsMiddleware
from tk_api.core.otel import setup_otel
from tk_api.core.rate_limit import RateLimiter, register_rate_limit_handler, try_redis
from tk_api.media.storage import build_storage
from tk_api.notifications.providers import build_providers
from tk_api.security.middleware import (
    AbuseDetectionMiddleware,
    EnhancedSecurityHeadersMiddleware,
    RequestSizeLimitMiddleware,
    SSRFProtectionMiddleware,
)


def create_app(settings: Settings | None = None, engine=None) -> FastAPI:  # type: ignore[no-untyped-def]
    resolved = settings or get_settings()
    configure_logging(resolved.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.engine = engine or create_engine(
            resolved.database_url,
            pool_size=resolved.db_pool_size,
            max_overflow=resolved.db_max_overflow,
            pool_recycle=resolved.db_pool_recycle_seconds,
        )
        redis_client = await try_redis(resolved)
        if "limiter" not in app.state:
            app.state.limiter = RateLimiter(redis_client)
        if "login_throttle" not in app.state:
            app.state.login_throttle = LoginThrottle(redis_client)
        if "otp_store" not in app.state:
            app.state.otp_store = build_store(resolved, redis_client)
        if "otp_sender" not in app.state:
            app.state.otp_sender = build_otp_sender(resolved)
        if "email_provider" not in app.state:
            app.state.email_provider = build_providers(resolved).get("email")
        if "idempotency_store" not in app.state:
            app.state.idempotency_store = build_idempotency_store(resolved, redis_client)
        if "storage" not in app.state:
            app.state.storage = build_storage(resolved)
        if "ai_gateway" not in app.state:
            app.state.ai_gateway = build_gateway(resolved)
        setup_otel(app, resolved)
        yield
        the_engine = getattr(app.state, "engine", None)
        if the_engine is not None and engine is None:
            await the_engine.dispose()

    app = FastAPI(
        title="Theek Karo API",
        version=__version__,
        description="Civic intelligence platform API.",
        lifespan=lifespan,
    )
    app.state.settings = resolved
    configure_mfa_enforcement(resolved.mfa_enforce_privileged, set(resolved.mfa_required_roles))

    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(CorrelationMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(EnhancedSecurityHeadersMiddleware)
    app.add_middleware(RequestSizeLimitMiddleware)
    app.add_middleware(SSRFProtectionMiddleware)
    app.add_middleware(AbuseDetectionMiddleware)
    app.add_middleware(MetricsMiddleware)

    register_exception_handlers(app)
    from tk_api.api.routers.metrics import metrics_router
    from tk_api.publicdata.public_router import public_router

    app.include_router(metrics_router, include_in_schema=False)
    register_rate_limit_handler(app)

    app.include_router(health.router)
    app.include_router(api_v1_router)
    app.include_router(public_router)
    return app


app = create_app()
