"""Tests for PCF emission factors search API endpoint."""

import pytest
from fastapi import FastAPI
from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from app.errors import APIError, ErrorCode, ErrorResponse
from app.middleware.correlation import get_correlation_id
from app.routers.pcf import router

@pytest.fixture
def client():
    """Create test client with PCF router."""
    app = FastAPI()
    app.include_router(router)

    @app.exception_handler(APIError)
    async def api_error_handler(request: Request, exc: APIError):
        correlation_id = getattr(request.state, "correlation_id", get_correlation_id()) or "unknown"
        response = exc.to_response(correlation_id)
        return JSONResponse(
            status_code=exc.status_code,
            content=response.model_dump(mode="json"),
            headers={"X-Correlation-ID": correlation_id},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
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

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        correlation_id = getattr(request.state, "correlation_id", get_correlation_id()) or "unknown"
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

    with TestClient(app) as test_client:
        yield test_client


class TestEmissionFactorsSearchEndpoint:
    """Tests for GET /api/pcf/factors/search endpoint."""

    def test_search_returns_matching_factors(self, client):
        """Search should return factors matching the query."""
        response = client.get(
            "/api/pcf/factors/search", params={"query": "electricity"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert all("electricity" in f["name"].lower() for f in data)

    def test_search_with_empty_query_returns_all(self, client):
        """Empty query should return all factors up to limit."""
        response = client.get("/api/pcf/factors/search", params={"query": ""})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_search_respects_limit(self, client):
        """Search should respect the limit parameter."""
        response = client.get(
            "/api/pcf/factors/search", params={"query": "", "limit": 3}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 3

    def test_search_returns_correct_structure(self, client):
        """Each factor should have the expected fields."""
        response = client.get(
            "/api/pcf/factors/search", params={"query": "steel"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0

        factor = data[0]
        assert "id" in factor
        assert "name" in factor
        assert "factor_value" in factor
        assert "factor_unit" in factor
        assert "source" in factor

    def test_search_no_match_returns_empty_list(self, client):
        """Search with no matches should return empty list."""
        response = client.get(
            "/api/pcf/factors/search", params={"query": "xyznonexistent123"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_search_is_case_insensitive(self, client):
        """Search should be case insensitive."""
        response_lower = client.get(
            "/api/pcf/factors/search", params={"query": "electricity"}
        )
        response_upper = client.get(
            "/api/pcf/factors/search", params={"query": "ELECTRICITY"}
        )
        assert response_lower.status_code == 200
        assert response_upper.status_code == 200
        assert len(response_lower.json()) == len(response_upper.json())


class TestEmissionFactorByIdEndpoint:
    """Tests for GET /api/pcf/factors/{factor_id} endpoint."""

    def test_get_existing_factor(self, client):
        """Should return factor when ID exists."""
        # First search to get a valid ID
        search_response = client.get(
            "/api/pcf/factors/search", params={"query": "", "limit": 1}
        )
        factors = search_response.json()
        if factors:
            factor_id = factors[0]["id"]
            response = client.get(f"/api/pcf/factors/{factor_id}")
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == factor_id

    def test_get_nonexistent_factor_returns_404(self, client):
        """Should return 404 for non-existent ID."""
        response = client.get("/api/pcf/factors/nonexistent-id-12345")
        assert response.status_code == 404
