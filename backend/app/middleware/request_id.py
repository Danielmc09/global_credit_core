import time

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ..core.constants import ErrorMessages, HttpHeaders
from ..core.logging import get_logger, set_request_id

logger = get_logger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to add request_id to all requests for traceability.

    The request_id is:
    1. Generated for each request
    2. Stored in context var (accessible in all logs)
    3. Returned in response headers
    """

    async def dispatch(self, request: Request, call_next):
        """Process request and add request ID tracking.
        
        Args:
            request: The incoming HTTP request
            call_next: The next middleware/route handler in the chain
            
        Returns:
            Response with request ID and process time headers
        """
        # Generate and set request ID
        request_id = set_request_id()

        # Log request
        logger.info(
            "Request started",
            extra={
                'method': request.method,
                'path': request.url.path,
                'client': request.client.host if request.client else 'unknown'
            }
        )

        # Process request
        start_time = time.time()

        try:
            response = await call_next(request)

            # Calculate processing time
            process_time = time.time() - start_time

            # Add custom headers
            response.headers[HttpHeaders.REQUEST_ID] = request_id
            response.headers[HttpHeaders.PROCESS_TIME] = str(process_time)

            # Log response
            logger.info(
                "Request completed",
                extra={
                    'status_code': response.status_code,
                    'process_time': process_time
                }
            )

            return response

        except Exception as e:
            process_time = time.time() - start_time

            logger.error(
                "Request failed",
                extra={
                    'error': str(e),
                    'process_time': process_time
                },
                exc_info=True
            )

            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": ErrorMessages.INTERNAL_SERVER_ERROR,
                    "request_id": request_id
                },
                headers={HttpHeaders.REQUEST_ID: request_id}
            )
