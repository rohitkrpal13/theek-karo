"""OpenTelemetry bootstrap.

Enables tracing and metrics only when ``TK_OTEL_ENABLED`` is true (dev default: off,
no-op SDK keeps overhead ~zero). Endpoint from ``TK_OTEL_ENDPOINT`` (OTLP/HTTP).
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from tk_api import __version__
from tk_api.core.config import Settings

logger = logging.getLogger("tk_api.otel")

_configured = False


def setup_otel(app: FastAPI, settings: Settings) -> None:
    """Idempotent; call once per process lifetime (lifespan startup)."""
    global _configured
    if _configured:
        return
    if not settings.otel_enabled:
        logger.info("OpenTelemetry disabled (TK_OTEL_ENABLED=false)")
        _configured = True
        return

    resource = Resource.create({"service.name": "tk-api", "service.version": __version__})

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{settings.otel_endpoint}/v1/traces"))
    )
    trace.set_tracer_provider(tracer_provider)

    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=f"{settings.otel_endpoint}/v1/metrics"),
        export_interval_millis=30_000,
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app, tracer_provider=tracer_provider)
    except Exception:
        logger.exception("Failed to instrument FastAPI; continuing without OTel")

    logger.info("OpenTelemetry enabled; endpoint=%s", settings.otel_endpoint)
    _configured = True
