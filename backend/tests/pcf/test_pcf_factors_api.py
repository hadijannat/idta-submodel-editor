"""
Tests for PCF emission factors search API endpoint.
"""

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from app.routers.pcf import router

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def client():
    """Create test client with PCF router."""
    app = FastAPI()
    app.include_router(router)
    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://testserver")
    try:
        yield client
    finally:
        await client.aclose()


class TestEmissionFactorsSearchEndpoint:
    """Tests for GET /api/pcf/factors/search endpoint."""

    async def test_search_returns_matching_factors(self, client):
        """Search should return factors matching the query."""
        response = await client.get(
            "/api/pcf/factors/search", params={"query": "electricity"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert all("electricity" in f["name"].lower() for f in data)

    async def test_search_with_empty_query_returns_all(self, client):
        """Empty query should return all factors up to limit."""
        response = await client.get("/api/pcf/factors/search", params={"query": ""})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    async def test_search_respects_limit(self, client):
        """Search should respect the limit parameter."""
        response = await client.get(
            "/api/pcf/factors/search", params={"query": "", "limit": 3}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 3

    async def test_search_returns_correct_structure(self, client):
        """Each factor should have the expected fields."""
        response = await client.get(
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

    async def test_search_no_match_returns_empty_list(self, client):
        """Search with no matches should return empty list."""
        response = await client.get(
            "/api/pcf/factors/search", params={"query": "xyznonexistent123"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data == []

    async def test_search_is_case_insensitive(self, client):
        """Search should be case insensitive."""
        response_lower = await client.get(
            "/api/pcf/factors/search", params={"query": "electricity"}
        )
        response_upper = await client.get(
            "/api/pcf/factors/search", params={"query": "ELECTRICITY"}
        )
        assert response_lower.status_code == 200
        assert response_upper.status_code == 200
        assert len(response_lower.json()) == len(response_upper.json())


class TestEmissionFactorByIdEndpoint:
    """Tests for GET /api/pcf/factors/{factor_id} endpoint."""

    async def test_get_existing_factor(self, client):
        """Should return factor when ID exists."""
        # First search to get a valid ID
        search_response = await client.get(
            "/api/pcf/factors/search", params={"query": "", "limit": 1}
        )
        factors = search_response.json()
        if factors:
            factor_id = factors[0]["id"]
            response = await client.get(f"/api/pcf/factors/{factor_id}")
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == factor_id

    async def test_get_nonexistent_factor_returns_404(self, client):
        """Should return 404 for non-existent ID."""
        response = await client.get("/api/pcf/factors/nonexistent-id-12345")
        assert response.status_code == 404
