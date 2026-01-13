"""Structured JSON Logging Configuration.

Implements structured logging with request_id tracking for observability (Requirement 4.3).
All logs are output in JSON format for easy parsing and analysis in production.
"""

import logging
import sys
from contextvars import ContextVar

from pythonjsonlogger import jsonlogger

from ..utils import generate_request_id
from .config import settings

request_id_var: ContextVar[str] = ContextVar('request_id', default='no-request-id')

try:
    from .tracing import get_trace_id, get_span_id
except ImportError:
    def get_trace_id() -> str | None:
        return None

    def get_span_id() -> str | None:
        return None


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter that includes request_id and standard fields."""

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)

        log_record['timestamp'] = record.created
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        log_record['request_id'] = request_id_var.get()

        trace_id = get_trace_id()
        span_id = get_span_id()
        if trace_id:
            log_record['trace_id'] = trace_id
        if span_id:
            log_record['span_id'] = span_id

        log_record['file'] = record.filename
        log_record['line'] = record.lineno
        log_record['function'] = record.funcName

        log_record['process_id'] = record.process
        log_record['thread_id'] = record.thread


def setup_logging():
    """Setup structured JSON logging for the application."""
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, settings.LOG_LEVEL))
    logger.handlers = []

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, settings.LOG_LEVEL))

    formatter = CustomJsonFormatter(
        '%(timestamp)s %(level)s %(name)s %(message)s',
        timestamp=True
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)

    logger.info(
        "Logging configured",
        extra={
            'log_level': settings.LOG_LEVEL,
            'environment': settings.ENVIRONMENT
        }
    )

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name.

    Args:
        name: Logger name (typically __name__ of the module)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def set_request_id(request_id: str | None = None):
    """Set the request ID for the current context.

    Args:
        request_id: Request ID to set (generates one if not provided)
    """
    if request_id is None:
        request_id = generate_request_id()
    request_id_var.set(request_id)
    return request_id


def get_request_id() -> str:
    """Get the current request ID.

    Returns:
        Current request ID
    """
    return request_id_var.get()
