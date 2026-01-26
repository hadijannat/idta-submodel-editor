"""
Correlation ID middleware for request tracing.

Generates or extracts a correlation ID for each request, making it available
throughout the request lifecycle via contextvars for thread-safe access.
"""

import uuid
from contextvars import ContextVar
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Header name for correlation ID (common conventions)
CORRELATION_ID_HEADER = "X-Correlation-ID"
REQUEST_ID_HEADER = "X-Request-ID"  # Alternative header name

# Context variable for thread-safe access to correlation ID
correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="")


def get_correlation_id() -> str:
    """
    Get the current correlation ID from context.

    Returns the correlation ID for the current request, or an empty string
    if called outside of a request context.

    Returns:
        The correlation ID string, or empty string if not in request context.
    """
    return correlation_id_ctx.get()


def generate_correlation_id() -> str:
    """Generate a new UUID4 correlation ID."""
    return str(uuid.uuid4())


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware that manages correlation IDs for request tracing.

    For each request:
    1. Extracts existing correlation ID from X-Correlation-ID or X-Request-ID header
    2. Generates a new UUID4 if no correlation ID is provided
    3. Stores the ID in request.state and contextvars for easy access
    4. Adds X-Correlation-ID header to the response
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        # Extract existing correlation ID from headers, or generate new one
        correlation_id = (
            request.headers.get(CORRELATION_ID_HEADER)
            or request.headers.get(REQUEST_ID_HEADER)
            or generate_correlation_id()
        )

        # Store in request.state for direct access in route handlers
        request.state.correlation_id = correlation_id

        # Store in contextvar for access anywhere in the call stack
        token = correlation_id_ctx.set(correlation_id)

        try:
            # Process the request
            response = await call_next(request)

            # Add correlation ID to response headers
            response.headers[CORRELATION_ID_HEADER] = correlation_id

            return response
        finally:
            # Reset the context variable
            correlation_id_ctx.reset(token)
