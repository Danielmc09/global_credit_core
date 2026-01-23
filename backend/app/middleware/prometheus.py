"""Prometheus Middleware.

Automatically captures HTTP metrics for all requests.
"""

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from ..core.constants import HttpStatusCodes
from ..infrastructure.monitoring import (
    http_request_duration_seconds,
    http_requests_in_progress,
    http_requests_total,
)
from ..utils import normalize_path


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Middleware to capture Prometheus metrics for HTTP requests.

    Tracks:
    - Total requests by method, endpoint, and status code
    - Request duration histogram
    - Requests currently in progress
    """

    async def dispatch(self, request: Request, call_next):
        """Process request and capture Prometheus metrics.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            HTTP response
        """
        method = request.method
        path = request.url.path
        normalized_path = normalize_path(path)

        http_requests_in_progress.labels(
            method=method,
            endpoint=normalized_path
        ).inc()

        start_time = time.time()

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            status_code = HttpStatusCodes.INTERNAL_SERVER_ERROR
            raise
        finally:
            duration = time.time() - start_time

            http_requests_total.labels(
                method=method,
                endpoint=normalized_path,
                status_code=status_code
            ).inc()

            http_request_duration_seconds.labels(
                method=method,
                endpoint=normalized_path
            ).observe(duration)

            http_requests_in_progress.labels(
                method=method,
                endpoint=normalized_path
            ).dec()

        return response
