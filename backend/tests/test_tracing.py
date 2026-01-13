"""Tests for Distributed Tracing.

Tests for OpenTelemetry tracing configuration and utilities.
"""

import pytest
from unittest.mock import MagicMock, patch, Mock
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags

from app.core.tracing import (
    setup_tracing,
    get_tracer,
    get_current_span,
    set_current_span,
    get_trace_context,
    inject_trace_context,
    extract_trace_context,
    get_trace_id,
    get_span_id,
)


class TestTracing:
    """Test suite for tracing functionality"""

    def test_setup_tracing_disabled(self, monkeypatch):
        """Test setup_tracing when tracing is disabled"""
        from app.core.config import settings
        
        # Mock settings to disable tracing
        with patch.object(settings, 'TRACING_ENABLED', False):
            result = setup_tracing()
            assert result is None

    @pytest.mark.asyncio
    async def test_setup_tracing_enabled_console(self, monkeypatch):
        """Test setup_tracing when tracing is enabled with console exporter"""
        from app.core.config import settings
        
        with patch.object(settings, 'TRACING_ENABLED', True):
            with patch.object(settings, 'TRACING_EXPORTER', 'console'):
                with patch('app.core.tracing.TracerProvider') as mock_provider:
                    with patch('app.core.tracing.Resource') as mock_resource:
                        with patch('app.core.tracing.ConsoleSpanExporter') as mock_exporter:
                            with patch('app.core.tracing.BatchSpanProcessor') as mock_processor:
                                with patch('app.core.tracing.FastAPIInstrumentor') as mock_fastapi:
                                    with patch('app.core.tracing.SQLAlchemyInstrumentor') as mock_sqlalchemy:
                                        with patch('app.core.tracing.RedisInstrumentor') as mock_redis:
                                            mock_provider_instance = MagicMock()
                                            mock_provider.return_value = mock_provider_instance
                                            
                                            result = setup_tracing()
                                            assert result is not None

    @pytest.mark.asyncio
    async def test_setup_tracing_enabled_otlp(self, monkeypatch):
        """Test setup_tracing when tracing is enabled with OTLP exporter"""
        from app.core.config import settings
        
        with patch.object(settings, 'TRACING_ENABLED', True):
            with patch.object(settings, 'TRACING_EXPORTER', 'otlp'):
                with patch.object(settings, 'TRACING_OTLP_ENDPOINT', 'http://localhost:4318/v1/traces'):
                    with patch('app.core.tracing.TracerProvider') as mock_provider:
                        with patch('app.core.tracing.Resource') as mock_resource:
                            with patch('app.core.tracing.OTLPSpanExporter') as mock_exporter:
                                with patch('app.core.tracing.BatchSpanProcessor') as mock_processor:
                                    mock_provider_instance = MagicMock()
                                    mock_provider.return_value = mock_provider_instance
                                    
                                    result = setup_tracing()
                                    assert result is not None

    @pytest.mark.asyncio
    async def test_setup_tracing_instrumentation_errors(self, monkeypatch):
        """Test setup_tracing when instrumentation fails"""
        from app.core.config import settings
        
        with patch.object(settings, 'TRACING_ENABLED', True):
            with patch.object(settings, 'TRACING_EXPORTER', 'console'):
                with patch('app.core.tracing.TracerProvider') as mock_provider:
                    with patch('app.core.tracing.Resource') as mock_resource:
                        with patch('app.core.tracing.ConsoleSpanExporter') as mock_exporter:
                            with patch('app.core.tracing.BatchSpanProcessor') as mock_processor:
                                with patch('app.core.tracing.FastAPIInstrumentor') as mock_fastapi:
                                    with patch('app.core.tracing.SQLAlchemyInstrumentor') as mock_sqlalchemy:
                                        with patch('app.core.tracing.RedisInstrumentor') as mock_redis:
                                            # Make instrumentation raise errors
                                            mock_fastapi.return_value.instrument.side_effect = Exception("FastAPI error")
                                            mock_sqlalchemy.return_value.instrument.side_effect = Exception("SQLAlchemy error")
                                            mock_redis.return_value.instrument.side_effect = Exception("Redis error")
                                            
                                            mock_provider_instance = MagicMock()
                                            mock_provider.return_value = mock_provider_instance
                                            
                                            # Should not raise, just log warnings
                                            result = setup_tracing()
                                            assert result is not None

    @pytest.mark.asyncio
    async def test_setup_tracing_exception(self, monkeypatch):
        """Test setup_tracing when an exception occurs"""
        from app.core.config import settings
        
        with patch.object(settings, 'TRACING_ENABLED', True):
            with patch('app.core.tracing.TracerProvider', side_effect=Exception("Setup error")):
                result = setup_tracing()
                assert result is None

    def test_get_tracer(self):
        """Test getting a tracer instance"""
        tracer = get_tracer("test_module")
        assert tracer is not None

    def test_get_current_span_none(self):
        """Test getting current span when none is set"""
        # Clear any existing span
        set_current_span(None)
        span = get_current_span()
        assert span is None

    def test_set_and_get_current_span(self):
        """Test setting and getting current span"""
        mock_span = MagicMock()
        set_current_span(mock_span)
        span = get_current_span()
        assert span == mock_span

    def test_get_trace_context(self):
        """Test getting trace context"""
        context = get_trace_context()
        assert isinstance(context, dict)

    def test_inject_trace_context(self):
        """Test injecting trace context into carrier"""
        carrier = {}
        inject_trace_context(carrier)
        # Should not raise exception
        assert isinstance(carrier, dict)

    def test_inject_trace_context_exception(self, monkeypatch):
        """Test injecting trace context when exception occurs"""
        carrier = {}
        
        with patch('app.core.tracing.TraceContextTextMapPropagator') as mock_propagator:
            mock_propagator.return_value.inject.side_effect = Exception("Inject error")
            # Should catch exception and not raise
            inject_trace_context(carrier)
            assert isinstance(carrier, dict)

    def test_extract_trace_context_empty(self):
        """Test extracting trace context from empty carrier"""
        carrier = {}
        context = extract_trace_context(carrier)
        assert context is None

    def test_extract_trace_context_valid(self, monkeypatch):
        """Test extracting trace context from valid carrier"""
        from opentelemetry import trace, context as otel_context
        
        carrier = {"traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"}
        
        with patch('app.core.tracing.TraceContextTextMapPropagator') as mock_propagator:
            mock_context = MagicMock()
            mock_propagator.return_value.extract.return_value = mock_context
            
            with patch('app.core.tracing.trace.get_current_span') as mock_get_span:
                mock_span = MagicMock()
                mock_span_context = MagicMock()
                mock_span_context.is_valid = True
                mock_span.get_span_context.return_value = mock_span_context
                mock_get_span.return_value = mock_span
                
                result = extract_trace_context(carrier)
                assert result is not None

    def test_extract_trace_context_invalid(self, monkeypatch):
        """Test extracting trace context when span is invalid"""
        carrier = {"traceparent": "invalid"}
        
        with patch('app.core.tracing.TraceContextTextMapPropagator') as mock_propagator:
            mock_context = MagicMock()
            mock_propagator.return_value.extract.return_value = mock_context
            
            with patch('app.core.tracing.trace.get_current_span') as mock_get_span:
                mock_span = MagicMock()
                mock_span_context = MagicMock()
                mock_span_context.is_valid = False
                mock_span.get_span_context.return_value = mock_span_context
                mock_get_span.return_value = mock_span
                
                result = extract_trace_context(carrier)
                assert result is None

    def test_extract_trace_context_exception(self, monkeypatch):
        """Test extracting trace context when exception occurs"""
        carrier = {"traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"}
        
        with patch('app.core.tracing.TraceContextTextMapPropagator') as mock_propagator:
            mock_propagator.return_value.extract.side_effect = Exception("Extract error")
            result = extract_trace_context(carrier)
            assert result is None

    def test_get_trace_id_no_span(self, monkeypatch):
        """Test getting trace ID when no active span"""
        with patch('app.core.tracing.trace.get_current_span', return_value=None):
            trace_id = get_trace_id()
            assert trace_id is None

    def test_get_trace_id_invalid_span(self, monkeypatch):
        """Test getting trace ID when span context is invalid"""
        mock_span = MagicMock()
        mock_span_context = MagicMock()
        mock_span_context.is_valid = False
        mock_span.get_span_context.return_value = mock_span_context
        
        with patch('app.core.tracing.trace.get_current_span', return_value=mock_span):
            trace_id = get_trace_id()
            assert trace_id is None

    def test_get_trace_id_valid(self, monkeypatch):
        """Test getting trace ID from valid span"""
        mock_span = MagicMock()
        mock_span_context = MagicMock()
        mock_span_context.is_valid = True
        mock_span_context.trace_id = 0x4bf92f3577b34da6a3ce929d0e0e4736
        mock_span.get_span_context.return_value = mock_span_context
        
        with patch('app.core.tracing.trace.get_current_span', return_value=mock_span):
            trace_id = get_trace_id()
            assert trace_id is not None
            assert isinstance(trace_id, str)
            assert len(trace_id) == 32  # 32 hex characters

    def test_get_span_id_no_span(self, monkeypatch):
        """Test getting span ID when no active span"""
        with patch('app.core.tracing.trace.get_current_span', return_value=None):
            span_id = get_span_id()
            assert span_id is None

    def test_get_span_id_invalid_span(self, monkeypatch):
        """Test getting span ID when span context is invalid"""
        mock_span = MagicMock()
        mock_span_context = MagicMock()
        mock_span_context.is_valid = False
        mock_span.get_span_context.return_value = mock_span_context
        
        with patch('app.core.tracing.trace.get_current_span', return_value=mock_span):
            span_id = get_span_id()
            assert span_id is None

    def test_get_span_id_valid(self, monkeypatch):
        """Test getting span ID from valid span"""
        mock_span = MagicMock()
        mock_span_context = MagicMock()
        mock_span_context.is_valid = True
        mock_span_context.span_id = 0x00f067aa0ba902b7
        mock_span.get_span_context.return_value = mock_span_context
        
        with patch('app.core.tracing.trace.get_current_span', return_value=mock_span):
            span_id = get_span_id()
            assert span_id is not None
            assert isinstance(span_id, str)
            assert len(span_id) == 16  # 16 hex characters
