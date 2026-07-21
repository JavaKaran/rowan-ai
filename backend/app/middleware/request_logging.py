import os
import time

from asgi_correlation_id import correlation_id
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import structlog

from app.core import get_logger

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if os.getenv("LOG_REQUESTS", "true").lower() != "true":
            return await call_next(request)

        structlog.contextvars.clear_contextvars()
        start_time = time.perf_counter()
        request_id = correlation_id.get()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        logger.info(
            "request.started",
            method=request.method,
            path=request.url.path,
            client_host=request.client.host if request.client else None,
        )

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.exception(
                "request.failed",
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
            )
            structlog.contextvars.clear_contextvars()
            raise

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info(
            "request.completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        structlog.contextvars.clear_contextvars()
        return response
