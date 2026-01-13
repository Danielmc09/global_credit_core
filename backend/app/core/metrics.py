"""Prometheus Metrics.

This module defines and exports Prometheus metrics for monitoring the application.
Metrics include counters, gauges, histograms, and summaries for tracking:
- API requests and responses
- Application processing
- Database operations
- External provider calls
- Worker performance
"""

import functools

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    Info,
    Summary,
    generate_latest,
)

# ========================================
# Application Metrics
# ========================================

# Application creation metrics
applications_created_total = Counter(
    'applications_created_total',
    'Total number of credit applications created',
    ['country']
)

applications_processed_total = Counter(
    'applications_processed_total',
    'Total number of applications processed by workers',
    ['country', 'status']
)

# Application status metrics
applications_by_status = Gauge(
    'applications_by_status',
    'Current number of applications by status',
    ['status']
)

applications_by_country = Gauge(
    'applications_by_country',
    'Current number of applications by country',
    ['country']
)

# ========================================
# API Metrics
# ========================================

# HTTP request metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)

http_requests_in_progress = Gauge(
    'http_requests_in_progress',
    'Number of HTTP requests currently being processed',
    ['method', 'endpoint']
)

# ========================================
# Worker Metrics
# ========================================

# Worker processing metrics
worker_tasks_total = Counter(
    'worker_tasks_total',
    'Total number of worker tasks processed',
    ['task_name', 'status']
)

worker_task_duration_seconds = Histogram(
    'worker_task_duration_seconds',
    'Worker task duration in seconds',
    ['task_name'],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0)
)

worker_tasks_in_progress = Gauge(
    'worker_tasks_in_progress',
    'Number of worker tasks currently being processed'
)


def track_inprogress_decorator(gauge: Gauge):
    """Create a decorator that tracks in-progress tasks using a Prometheus Gauge.

    This decorator increments the gauge when a task starts and decrements it when it finishes.
    It preserves the async nature of the decorated function so ARQ can recognize it as a coroutine.

    Args:
        gauge: Prometheus Gauge to use for tracking

    Returns:
        Decorator function that can be used with @ syntax
    """
    def decorator(func):
        """Decorator that wraps an async function to track in-progress status."""
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            """Wrapper that tracks in-progress status."""
            gauge.inc()
            try:
                return await func(*args, **kwargs)
            finally:
                gauge.dec()

        return wrapper

    return decorator


worker_tasks_in_progress.track_inprogress = lambda: track_inprogress_decorator(worker_tasks_in_progress)

worker_queue_size = Gauge(
    'worker_queue_size',
    'Number of tasks in the worker queue'
)

# ========================================
# Database Metrics
# ========================================

# Database query metrics
db_queries_total = Counter(
    'db_queries_total',
    'Total number of database queries',
    ['operation']
)

db_query_duration_seconds = Histogram(
    'db_query_duration_seconds',
    'Database query duration in seconds',
    ['operation'],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0)
)

db_connections_active = Gauge(
    'db_connections_active',
    'Number of active database connections'
)

db_connections_idle = Gauge(
    'db_connections_idle',
    'Number of idle database connections in the pool'
)

# ========================================
# External Provider Metrics
# ========================================

# Banking provider metrics
provider_requests_total = Counter(
    'provider_requests_total',
    'Total requests to banking data providers',
    ['country', 'provider', 'status']
)

provider_request_duration_seconds = Histogram(
    'provider_request_duration_seconds',
    'Banking provider request duration in seconds',
    ['country', 'provider'],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0)
)

provider_circuit_breaker_state = Gauge(
    'provider_circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=open, 2=half-open)',
    ['country', 'provider']
)

# ========================================
# Business Metrics
# ========================================

# Risk assessment metrics
risk_score_distribution = Histogram(
    'risk_score_distribution',
    'Distribution of risk scores',
    ['country'],
    buckets=(10, 20, 30, 40, 50, 60, 70, 80, 90, 100)
)

approval_rate = Gauge(
    'approval_rate',
    'Approval rate by country (percentage)',
    ['country']
)

rejection_reasons = Counter(
    'rejection_reasons_total',
    'Total rejections by reason',
    ['country', 'reason']
)

# Loan amount metrics
requested_amount_total = Summary(
    'requested_amount_total',
    'Summary of requested loan amounts',
    ['country']
)

approved_amount_total = Summary(
    'approved_amount_total',
    'Summary of approved loan amounts',
    ['country']
)

# ========================================
# Cache Metrics
# ========================================

cache_hits_total = Counter(
    'cache_hits_total',
    'Total number of cache hits',
    ['cache_key_type']
)

cache_misses_total = Counter(
    'cache_misses_total',
    'Total number of cache misses',
    ['cache_key_type']
)

cache_hit_rate = Gauge(
    'cache_hit_rate',
    'Cache hit rate (percentage)',
    ['cache_key_type']
)

cache_errors_total = Counter(
    'cache_errors_total',
    'Total number of cache errors',
    ['operation', 'error_type']
)

cache_connection_status = Gauge(
    'cache_connection_status',
    'Cache connection status (1=connected, 0=disconnected)'
)

cache_operations_total = Counter(
    'cache_operations_total',
    'Total number of cache operations',
    ['operation', 'status']
)

# ========================================
# WebSocket Metrics
# ========================================

websocket_connections_active = Gauge(
    'websocket_connections_active',
    'Number of active WebSocket connections'
)

websocket_messages_sent_total = Counter(
    'websocket_messages_sent_total',
    'Total WebSocket messages sent',
    ['message_type']
)

# ========================================
# Application Info
# ========================================

app_info = Info(
    'app',
    'Application information'
)

def set_app_info(version: str, environment: str):
    """Set application information for Prometheus.

    Call this during app startup.
    """
    app_info.info({
        'version': version,
        'environment': environment,
        'service': 'global-credit-core'
    })


# ========================================
# Utility Functions
# ========================================

def get_metrics():
    """Get current Prometheus metrics in text format.

    Use this for the /metrics endpoint.
    """
    return generate_latest()


def get_content_type():
    """Get the content type for Prometheus metrics."""
    return CONTENT_TYPE_LATEST
