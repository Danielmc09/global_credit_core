"""Payload Size Validation Middleware.

Validates request payload sizes to prevent DoS attacks.
Rejects requests with payloads exceeding configured limits.
"""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ..core.config import settings
from ..core.logging import get_logger

logger = get_logger(__name__)


class PayloadSizeMiddleware(BaseHTTPMiddleware):
    """Middleware to validate request payload sizes and prevent DoS attacks.

    Checks Content-Length header and rejects requests that exceed
    the configured maximum payload size.

    Methods with potential request bodies: POST, PUT, PATCH
    """

    def __init__(self, app, max_size_bytes: int | None = None):
        """Initialize middleware with optional custom max size.

        Args:
            app: The ASGI application
            max_size_bytes: Optional custom max size in bytes.
                          If None, uses settings.MAX_PAYLOAD_SIZE_MB
        """
        super().__init__(app)
        if max_size_bytes is None:
            self.max_size_bytes = settings.MAX_PAYLOAD_SIZE_MB * 1024 * 1024
        else:
            self.max_size_bytes = max_size_bytes


    async def dispatch(self, request: Request, call_next):
        """Validate payload size before processing request.

        For methods that can have request bodies (POST, PUT, PATCH),
        checks Content-Length header and rejects if too large.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            HTTP response
        """
        if request.method in ("POST", "PUT", "PATCH"):
            content_length = request.headers.get("content-length")

            if content_length:
                try:
                    content_length_int = int(content_length)

                    if content_length_int > self.max_size_bytes:
                        logger.warning(
                            "Request payload too large (rejected by middleware)",
                            extra={
                                'method': request.method,
                                'path': request.url.path,
                                'content_length': content_length_int,
                                'max_size_bytes': self.max_size_bytes,
                                'client': request.client.host if request.client else 'unknown'
                            }
                        )

                        return JSONResponse(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            content={
                                "error": f"Request payload exceeds maximum size of {settings.MAX_PAYLOAD_SIZE_MB}MB",
                                "detail": f"Maximum allowed size: {settings.MAX_PAYLOAD_SIZE_MB}MB ({self.max_size_bytes} bytes), received: {content_length_int} bytes"
                            }
                        )
                except ValueError:
                    logger.debug(
                        "Invalid Content-Length header format",
                        extra={
                            'method': request.method,
                            'path': request.url.path,
                            'content_length': content_length
                        }
                    )

        return await call_next(request)
