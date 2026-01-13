"""Distributed Tracing Configuration.

Implements OpenTelemetry distributed tracing for request correlation across services.
This enables tracking requests from API → Worker → Provider for debugging in production.

Features:
- Trace ID propagation across services
- Span creation for each operation
- Integration with Jaeger, Zipkin, or other OTLP-compatible backends
- Automatic instrumentation for FastAPI, SQLAlchemy, Redis
"""


from contextvars import ContextVar
from typing import Optional

from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import Span, Tracer
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from .config import settings

import logging

logger = logging.getLogger(__name__)

current_span_var: ContextVar[Optional[Span]] = ContextVar('current_span', default=None)


def setup_tracing() -> Optional[TracerProvider]:
    """Setup OpenTelemetry tracing.

    Configures:
    - Resource attributes (service name, version, environment)
    - Span exporter (OTLP or Console based on configuration)
    - Automatic instrumentation for FastAPI, SQLAlchemy, Redis

    Returns:
        TracerProvider instance if tracing is enabled, None otherwise
    """
    if not getattr(settings, 'TRACING_ENABLED', False):
        logger.info("Distributed tracing is disabled")
        return None

    try:
        resource = Resource.create({
            "service.name": settings.APP_NAME.lower().replace(" ", "-"),
            "service.version": settings.APP_VERSION,
            "service.namespace": settings.ENVIRONMENT,
            "deployment.environment": settings.ENVIRONMENT,
        })

        tracer_provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(tracer_provider)

        if getattr(settings, 'TRACING_EXPORTER', 'console').lower() == 'otlp':
            otlp_endpoint = getattr(
                settings, 'TRACING_OTLP_ENDPOINT', 'http://localhost:4318/v1/traces'
            )
            span_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            logger.info(
                "Tracing configured with OTLP exporter",
                extra={'endpoint': otlp_endpoint}
            )
        else:
            span_exporter = ConsoleSpanExporter()
            logger.info("Tracing configured with console exporter")

        span_processor = BatchSpanProcessor(span_exporter)
        tracer_provider.add_span_processor(span_processor)

        try:
            FastAPIInstrumentor().instrument()
            logger.debug("FastAPI instrumentation enabled")
        except Exception as e:
            logger.warning(f"Failed to instrument FastAPI: {e}")

        try:
            SQLAlchemyInstrumentor().instrument()
            logger.debug("SQLAlchemy instrumentation enabled")
        except Exception as e:
            logger.warning(f"Failed to instrument SQLAlchemy: {e}")

        try:
            RedisInstrumentor().instrument()
            logger.debug("Redis instrumentation enabled")
        except Exception as e:
            logger.warning(f"Failed to instrument Redis: {e}")

        logger.info(
            "Distributed tracing initialized",
            extra={
                'exporter': getattr(settings, 'TRACING_EXPORTER', 'console'),
                'environment': settings.ENVIRONMENT
            }
        )

        return tracer_provider

    except Exception as e:
        logger.error(
            f"Failed to setup tracing: {e}",
            exc_info=True
        )
        return None


def get_tracer(name: str) -> Tracer:
    """Get a tracer instance for the given name.

    Args:
        name: Name of the tracer (typically module name)

    Returns:
        Tracer instance
    """
    return trace.get_tracer(name)


def get_current_span() -> Optional[Span]:
    """Get the current active span from context.

    Returns:
        Current span if available, None otherwise
    """
    return current_span_var.get()


def set_current_span(span: Optional[Span]) -> None:
    """Set the current active span in context.

    Args:
        span: Span to set as current
    """
    current_span_var.set(span)


def get_trace_context() -> dict:
    """Extract trace context for propagation.

    Returns:
        Dictionary with trace context headers (traceparent, tracestate)
    """
    carrier = {}
    inject_trace_context(carrier)
    return carrier


def inject_trace_context(carrier: dict) -> None:
    """Inject trace context into a carrier dictionary.

    Args:
        carrier: Dictionary to inject trace context into
    """
    try:
        propagator = TraceContextTextMapPropagator()
        propagator.inject(carrier)
    except Exception:
        pass


def extract_trace_context(carrier: dict) -> Optional[otel_context.Context]:
    """Extract trace context from a carrier dictionary.

    Args:
        carrier: Dictionary containing trace context headers

    Returns:
        OpenTelemetry Context if valid trace context found, None otherwise
    """
    if not carrier:
        return None

    try:
        propagator = TraceContextTextMapPropagator()
        context = propagator.extract(carrier)
        span = trace.get_current_span(context)
        if span and span.get_span_context().is_valid:
            return context
        return None
    except Exception:
        return None


def get_trace_id() -> Optional[str]:
    """Get the current trace ID as a hex string.

    Returns:
        Trace ID as hex string, or None if no active trace
    """
    span = trace.get_current_span()
    if span:
        span_context = span.get_span_context()
        if span_context.is_valid:
            return format(span_context.trace_id, '032x')
    return None


def get_span_id() -> Optional[str]:
    """Get the current span ID as a hex string.

    Returns:
        Span ID as hex string, or None if no active span
    """
    span = trace.get_current_span()
    if span:
        span_context = span.get_span_context()
        if span_context.is_valid:
            return format(span_context.span_id, '016x')
    return None
