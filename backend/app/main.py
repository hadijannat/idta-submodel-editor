"""
FastAPI application entry point.

This module configures the FastAPI application with:
- CORS middleware
- Security headers middleware
- Correlation ID middleware
- Rate limiting
- Health check endpoints
- API routers
- Standardized error handling
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from prometheus_fastapi_instrumentator import Instrumentator

from app.config import get_settings
from app.errors import APIError, ErrorCode, ErrorResponse
from app.metrics import set_app_info
from app.middleware.correlation import CorrelationIdMiddleware, get_correlation_id
from app.routers import editor, export, templates, semantic, mapper, pcf, magic_import, dataspace, tools
from app.services.tools.registry import initialize_registry, shutdown_registry

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Only add HSTS in production
        if get_settings().env == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    settings = get_settings()

    # Set application info for Prometheus metrics
    set_app_info(version="1.0.0", environment=settings.env)

    # Create cache directory
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    settings.semantic_index_dir.mkdir(parents=True, exist_ok=True)
    settings.mapper_cache_dir.mkdir(parents=True, exist_ok=True)
    settings.magic_import_cache_dir.mkdir(parents=True, exist_ok=True)

    # Create dataspace cache directory if feature is enabled
    if settings.dataspace_enabled:
        settings.dataspace_cache_dir.mkdir(parents=True, exist_ok=True)

    # Create temp directory for file processing
    Path("./tmp").mkdir(parents=True, exist_ok=True)

    # Initialize tool registry
    # This discovers and initializes all builtin tools
    logger.info("Initializing tool registry...")
    registry = await initialize_registry()
    logger.info(
        "Tool registry initialized with %d tools",
        len(registry.get_all()),
    )

    yield

    # Cleanup on shutdown
    logger.info("Shutting down tool registry...")
    await shutdown_registry()
    logger.info("Tool registry shut down")


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="IDTA Submodel Template Editor",
        description=(
            "Universal metamodel-driven editor for IDTA submodel templates. "
            "Supports any IDTA template without code modifications."
        ),
        version="1.0.0",
        docs_url="/api/docs" if settings.env != "production" else None,
        redoc_url="/api/redoc" if settings.env != "production" else None,
        openapi_url="/api/openapi.json" if settings.env != "production" else None,
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition", "X-Correlation-ID"],
    )

    # Security headers
    app.add_middleware(SecurityHeadersMiddleware)

    # Correlation ID middleware (must be added after security headers to run first)
    app.add_middleware(CorrelationIdMiddleware)

    # Include routers
    app.include_router(templates.router)
    app.include_router(editor.router)
    app.include_router(export.router)
    app.include_router(semantic.router)
    app.include_router(mapper.router)
    app.include_router(pcf.router)
    app.include_router(magic_import.router)
    app.include_router(tools.router)

    # Conditionally include dataspace router based on feature flag
    if settings.dataspace_enabled:
        app.include_router(dataspace.router)

    # Health check endpoints
    @app.get("/health", tags=["health"])
    async def health_check():
        """Basic health check."""
        return {"status": "healthy", "version": "1.0.0"}

    @app.get("/health/liveness", tags=["health"])
    async def liveness_check():
        """Kubernetes liveness probe."""
        return {"status": "alive"}

    @app.get("/health/readiness", tags=["health"])
    async def readiness_check():
        """Kubernetes readiness probe."""
        # Check if cache directory is accessible
        if not settings.cache_dir.exists():
            return JSONResponse(
                status_code=503,
                content={"status": "not ready", "reason": "Cache directory unavailable"},
            )
        return {"status": "ready"}

    @app.get("/health/startup", tags=["health"])
    async def startup_check():
        """Kubernetes startup probe."""
        return {"status": "started"}

    @app.get("/api/settings", tags=["settings"])
    async def get_public_settings():
        """Return public settings needed by the frontend."""
        return {
            "mnestix_enabled": settings.mnestix_enabled,
            "mnestix_url": settings.mnestix_url if settings.mnestix_enabled else None,
            "basyx_registry_url": settings.basyx_registry_url if settings.mnestix_enabled else None,
            "dataspace_enabled": settings.dataspace_enabled,
        }

    # Exception handler for APIError (structured errors)
    @app.exception_handler(APIError)
    async def api_error_handler(request: Request, exc: APIError):
        """Handle structured API errors."""
        correlation_id = getattr(request.state, "correlation_id", get_correlation_id()) or "unknown"
        response = exc.to_response(correlation_id)
        return JSONResponse(
            status_code=exc.status_code,
            content=response.model_dump(mode="json"),
            headers={"X-Correlation-ID": correlation_id},
        )

    # Exception handler for RequestValidationError (Pydantic validation)
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Convert Pydantic validation errors to standardized error response."""
        correlation_id = getattr(request.state, "correlation_id", get_correlation_id()) or "unknown"
        response = ErrorResponse(
            code=ErrorCode.VALIDATION_FAILED,
            message="Request validation failed",
            detail={"errors": exc.errors()},
            correlation_id=correlation_id,
        )
        return JSONResponse(
            status_code=422,
            content=response.model_dump(mode="json"),
            headers={"X-Correlation-ID": correlation_id},
        )

    # Exception handler for HTTPException (convert to ErrorResponse format)
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Convert HTTPException to standardized error response."""
        correlation_id = getattr(request.state, "correlation_id", get_correlation_id()) or "unknown"

        # Map HTTP status codes to error codes
        code_map = {
            400: ErrorCode.BAD_REQUEST,
            404: ErrorCode.RESOURCE_NOT_FOUND,
            409: ErrorCode.RESOURCE_CONFLICT,
            413: ErrorCode.FILE_TOO_LARGE,
            422: ErrorCode.VALIDATION_FAILED,
            429: ErrorCode.UPSTREAM_RATE_LIMITED,
            502: ErrorCode.UPSTREAM_ERROR,
            503: ErrorCode.UPSTREAM_UNAVAILABLE,
        }
        error_code = code_map.get(exc.status_code, ErrorCode.INTERNAL_ERROR)

        response = ErrorResponse(
            code=error_code,
            message=exc.detail if isinstance(exc.detail, str) else str(exc.detail),
            detail=exc.detail if isinstance(exc.detail, dict) else None,
            correlation_id=correlation_id,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=response.model_dump(mode="json"),
            headers={"X-Correlation-ID": correlation_id},
        )

    # Global exception handler for uncaught exceptions
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Handle uncaught exceptions with standardized error response."""
        correlation_id = getattr(request.state, "correlation_id", get_correlation_id()) or "unknown"

        # Log the full exception for debugging
        logger.exception(
            "Unhandled exception [correlation_id=%s]: %s",
            correlation_id,
            str(exc),
        )

        # Build error response
        if settings.debug:
            response = ErrorResponse(
                code=ErrorCode.INTERNAL_ERROR,
                message=str(exc),
                detail={"type": type(exc).__name__},
                correlation_id=correlation_id,
            )
        else:
            response = ErrorResponse(
                code=ErrorCode.INTERNAL_ERROR,
                message="Internal server error",
                correlation_id=correlation_id,
            )

        return JSONResponse(
            status_code=500,
            content=response.model_dump(mode="json"),
            headers={"X-Correlation-ID": correlation_id},
        )

    # Add Prometheus instrumentation
    # Exposes /metrics endpoint for scraping
    Instrumentator().instrument(app).expose(app, endpoint="/metrics", tags=["metrics"])

    return app


app = create_application()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.env == "development",
        workers=1 if settings.env == "development" else settings.workers,
    )
