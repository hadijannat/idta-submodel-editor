"""
Standardized error handling for the IDTA Submodel Editor API.

Provides:
- ErrorCode enum for consistent error categorization
- APIError exception for raising structured errors
- ErrorResponse model for consistent API error responses
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ErrorCode(str, Enum):
    """Standardized error codes for API responses."""

    # Validation errors
    VALIDATION_FAILED = "VALIDATION_FAILED"
    INVALID_FILE_TYPE = "INVALID_FILE_TYPE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    INVALID_MAGIC_BYTES = "INVALID_MAGIC_BYTES"

    # Resource errors
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    RESOURCE_CONFLICT = "RESOURCE_CONFLICT"

    # Upstream/external service errors
    UPSTREAM_UNAVAILABLE = "UPSTREAM_UNAVAILABLE"
    UPSTREAM_RATE_LIMITED = "UPSTREAM_RATE_LIMITED"
    UPSTREAM_ERROR = "UPSTREAM_ERROR"

    # Feature/configuration errors
    FEATURE_DISABLED = "FEATURE_DISABLED"

    # Generic errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    BAD_REQUEST = "BAD_REQUEST"


# Mapping of error codes to default HTTP status codes
ERROR_CODE_STATUS: dict[ErrorCode, int] = {
    ErrorCode.VALIDATION_FAILED: 422,
    ErrorCode.INVALID_FILE_TYPE: 400,
    ErrorCode.FILE_TOO_LARGE: 413,
    ErrorCode.INVALID_MAGIC_BYTES: 400,
    ErrorCode.RESOURCE_NOT_FOUND: 404,
    ErrorCode.RESOURCE_CONFLICT: 409,
    ErrorCode.UPSTREAM_UNAVAILABLE: 503,
    ErrorCode.UPSTREAM_RATE_LIMITED: 429,
    ErrorCode.UPSTREAM_ERROR: 502,
    ErrorCode.FEATURE_DISABLED: 503,
    ErrorCode.INTERNAL_ERROR: 500,
    ErrorCode.BAD_REQUEST: 400,
}


class ErrorResponse(BaseModel):
    """Standardized API error response model."""

    code: ErrorCode = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    detail: dict[str, Any] | None = Field(
        default=None, description="Additional error context"
    )
    correlation_id: str = Field(..., description="Request correlation ID for tracing")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Error timestamp in UTC",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "code": "RESOURCE_NOT_FOUND",
                    "message": "Template not found",
                    "detail": {"template_name": "IDTA-02006"},
                    "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
                    "timestamp": "2024-01-15T10:30:00Z",
                }
            ]
        }
    }


class APIError(Exception):
    """
    Structured API error exception.

    Raise this exception from route handlers to return a standardized
    error response with proper error codes and correlation ID tracking.

    Example:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Template not found",
            detail={"template_name": template_name},
        )
    """

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        detail: dict[str, Any] | None = None,
        status_code: int | None = None,
    ):
        """
        Initialize an API error.

        Args:
            code: The error code (from ErrorCode enum)
            message: Human-readable error message
            detail: Optional additional context as a dictionary
            status_code: Optional HTTP status code override (defaults based on code)
        """
        self.code = code
        self.message = message
        self.detail = detail
        self.status_code = status_code or ERROR_CODE_STATUS.get(code, 500)
        super().__init__(message)

    def to_response(self, correlation_id: str) -> ErrorResponse:
        """Convert to ErrorResponse with the given correlation ID."""
        return ErrorResponse(
            code=self.code,
            message=self.message,
            detail=self.detail,
            correlation_id=correlation_id,
        )
