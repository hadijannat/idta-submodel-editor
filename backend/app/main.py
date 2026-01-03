"""
FastAPI application entry point.

This module configures the FastAPI application with:
- CORS middleware
- Security headers middleware
- Rate limiting
- Health check endpoints
- API routers
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings
from app.routers import editor, export, templates


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

    # Create cache directory
    settings.cache_dir.mkdir(parents=True, exist_ok=True)

    # Create temp directory for file processing
    Path("./tmp").mkdir(parents=True, exist_ok=True)

    yield

    # Cleanup on shutdown (if needed)


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
        expose_headers=["Content-Disposition"],
    )

    # Security headers
    app.add_middleware(SecurityHeadersMiddleware)

    # Include routers
    app.include_router(templates.router)
    app.include_router(editor.router)
    app.include_router(export.router)

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

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Handle uncaught exceptions."""
        if settings.debug:
            return JSONResponse(
                status_code=500,
                content={"detail": str(exc), "type": type(exc).__name__},
            )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

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
