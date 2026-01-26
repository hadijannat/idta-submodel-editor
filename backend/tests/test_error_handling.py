"""Tests for standardized error handling and correlation ID middleware."""

import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.errors import APIError, ErrorCode, ErrorResponse, ERROR_CODE_STATUS
from app.main import app
from app.middleware.correlation import (
    CorrelationIdMiddleware,
    get_correlation_id,
    generate_correlation_id,
    correlation_id_ctx,
)


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


class TestErrorCode:
    """Tests for ErrorCode enum."""

    def test_error_codes_are_strings(self):
        """Verify error codes are string enums."""
        assert ErrorCode.VALIDATION_FAILED == "VALIDATION_FAILED"
        assert ErrorCode.RESOURCE_NOT_FOUND == "RESOURCE_NOT_FOUND"
        assert ErrorCode.INTERNAL_ERROR == "INTERNAL_ERROR"

    def test_all_error_codes_have_status_mapping(self):
        """Verify all error codes have a default HTTP status code."""
        for code in ErrorCode:
            assert code in ERROR_CODE_STATUS, f"Missing status mapping for {code}"


class TestAPIError:
    """Tests for APIError exception."""

    def test_api_error_basic(self):
        """Test basic APIError creation."""
        error = APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Template not found",
        )
        assert error.code == ErrorCode.RESOURCE_NOT_FOUND
        assert error.message == "Template not found"
        assert error.detail is None
        assert error.status_code == 404

    def test_api_error_with_detail(self):
        """Test APIError with additional detail."""
        error = APIError(
            code=ErrorCode.VALIDATION_FAILED,
            message="Invalid input",
            detail={"field": "name", "error": "required"},
        )
        assert error.detail == {"field": "name", "error": "required"}

    def test_api_error_custom_status_code(self):
        """Test APIError with custom status code override."""
        error = APIError(
            code=ErrorCode.BAD_REQUEST,
            message="Custom error",
            status_code=418,  # I'm a teapot
        )
        assert error.status_code == 418

    def test_api_error_to_response(self):
        """Test converting APIError to ErrorResponse."""
        error = APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Template not found",
            detail={"template_name": "test"},
        )
        correlation_id = "test-correlation-id"
        response = error.to_response(correlation_id)

        assert isinstance(response, ErrorResponse)
        assert response.code == ErrorCode.RESOURCE_NOT_FOUND
        assert response.message == "Template not found"
        assert response.detail == {"template_name": "test"}
        assert response.correlation_id == correlation_id


class TestErrorResponse:
    """Tests for ErrorResponse model."""

    def test_error_response_serialization(self):
        """Test ErrorResponse JSON serialization."""
        response = ErrorResponse(
            code=ErrorCode.VALIDATION_FAILED,
            message="Invalid input",
            detail={"field": "name"},
            correlation_id="test-id",
        )
        data = response.model_dump(mode="json")

        assert data["code"] == "VALIDATION_FAILED"
        assert data["message"] == "Invalid input"
        assert data["detail"] == {"field": "name"}
        assert data["correlation_id"] == "test-id"
        assert "timestamp" in data


class TestCorrelationIdMiddleware:
    """Tests for correlation ID middleware."""

    def test_correlation_id_generated(self, client):
        """Test that correlation ID is generated for requests."""
        response = client.get("/health")
        assert "X-Correlation-ID" in response.headers
        # Should be valid UUID4
        uuid.UUID(response.headers["X-Correlation-ID"])

    def test_correlation_id_propagated(self, client):
        """Test that provided correlation ID is propagated."""
        custom_id = "my-custom-correlation-id"
        response = client.get(
            "/health",
            headers={"X-Correlation-ID": custom_id},
        )
        assert response.headers["X-Correlation-ID"] == custom_id

    def test_request_id_header_accepted(self, client):
        """Test that X-Request-ID header is also accepted."""
        custom_id = "request-id-test"
        response = client.get(
            "/health",
            headers={"X-Request-ID": custom_id},
        )
        assert response.headers["X-Correlation-ID"] == custom_id

    def test_generate_correlation_id_is_uuid4(self):
        """Test that generated correlation IDs are valid UUID4."""
        correlation_id = generate_correlation_id()
        parsed = uuid.UUID(correlation_id)
        assert parsed.version == 4


class TestErrorHandlerIntegration:
    """Integration tests for error handlers."""

    def test_404_returns_error_response_format(self, client):
        """Test that 404 errors return ErrorResponse format."""
        response = client.get("/api/templates/nonexistent-template")
        assert response.status_code == 404

        data = response.json()
        assert "code" in data
        assert "message" in data
        assert "correlation_id" in data
        assert "timestamp" in data

    def test_error_response_includes_correlation_id(self, client):
        """Test that error responses include correlation ID."""
        custom_id = "error-test-correlation-id"
        response = client.get(
            "/api/templates/nonexistent-template",
            headers={"X-Correlation-ID": custom_id},
        )

        data = response.json()
        assert data["correlation_id"] == custom_id
        assert response.headers["X-Correlation-ID"] == custom_id

    def test_validation_error_format(self, client):
        """Test that validation errors return proper format."""
        # This should trigger a validation error (invalid limit type)
        response = client.get("/api/magic-import/jobs?limit=invalid")
        assert response.status_code == 422

        data = response.json()
        assert "code" in data
        assert "correlation_id" in data


class TestContextVar:
    """Tests for correlation ID context variable."""

    def test_get_correlation_id_outside_request(self):
        """Test get_correlation_id returns empty string outside request."""
        assert get_correlation_id() == ""

    def test_context_var_isolation(self):
        """Test that context variable is properly isolated."""
        token = correlation_id_ctx.set("test-value")
        try:
            assert get_correlation_id() == "test-value"
        finally:
            correlation_id_ctx.reset(token)
        assert get_correlation_id() == ""
