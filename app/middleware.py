"""
Request middleware for structured logging and correlation IDs.
"""

import uuid
import time
import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Adds correlation IDs and structured logging to every request.
    """

    async def dispatch(self, request: Request, call_next):
        # Generate correlation ID
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        start_time = time.time()

        # Log request
        logger.info(
            "request_started",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else "unknown",
        )

        try:
            response: Response = await call_next(request)

            # Log response
            duration = round((time.time() - start_time) * 1000, 2)
            logger.info(
                "request_completed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration,
            )

            # Add correlation headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time-Ms"] = str(duration)

            return response

        except Exception as e:
            duration = round((time.time() - start_time) * 1000, 2)
            logger.error(
                "request_failed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                error=str(e),
                duration_ms=duration,
            )
            raise
