"""
Tests for the tools API router.
"""

import pytest
from fastapi.testclient import TestClient
from typing import ClassVar

from app.services.tools.base import BaseTool, ToolMetadata
from app.services.tools.registry import ToolRegistry
from app.services.tools.context import initialize_tool_context


class MockTool(BaseTool):
    """Mock tool for router testing."""

    metadata: ClassVar[ToolMetadata] = ToolMetadata(
        id="test-tool",
        name="Test Tool",
        description="A test tool for API testing",
        category="core",
        wizard_step=1,
    )

    async def initialize(self) -> None:
        await super().initialize()

    async def shutdown(self) -> None:
        await super().shutdown()

    async def health_check(self) -> tuple[bool, str | None]:
        return True, None

    def get_router(self):
        return None

    def get_capabilities(self) -> dict:
        return {"test": True}


class LateWizardTool(BaseTool):
    """Additional tool to verify manifest ordering."""

    metadata: ClassVar[ToolMetadata] = ToolMetadata(
        id="late-tool",
        name="Late Tool",
        description="A later wizard tool",
        category="core",
        wizard_step=9,
    )

    async def initialize(self) -> None:
        await super().initialize()

    async def shutdown(self) -> None:
        await super().shutdown()

    async def health_check(self) -> tuple[bool, str | None]:
        return True, None

    def get_router(self):
        return None

    def get_capabilities(self) -> dict:
        return {"late": True}


@pytest.fixture
def context():
    """Create a test tool context."""
    return initialize_tool_context()


@pytest.fixture
def mock_registry(context):
    """Create a mock registry with test tools."""
    registry = ToolRegistry(context)
    registry.register(LateWizardTool)
    registry.register(MockTool)
    return registry


@pytest.fixture
def test_client(mock_registry):
    """Create a test client with mocked registry."""
    from fastapi import FastAPI
    from app.routers.tools import router, get_registry

    app = FastAPI()
    app.include_router(router)

    # Override the local dependency function
    app.dependency_overrides[get_registry] = lambda: mock_registry

    return TestClient(app)


class TestToolsListEndpoint:
    """Tests for GET /api/tools endpoint."""

    def test_list_all_tools(self, test_client):
        """Test listing all tools."""
        response = test_client.get("/api/tools")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_list_tools_structure(self, test_client):
        """Test tool list response structure."""
        response = test_client.get("/api/tools")

        data = response.json()
        tool = data[0]

        assert "id" in tool
        assert "name" in tool
        assert "description" in tool
        assert "category" in tool
        assert "enabled" in tool


class TestToolsManifestEndpoint:
    """Tests for GET /api/tools/manifest endpoint."""

    def test_get_manifest(self, test_client):
        """Test getting tool manifest."""
        response = test_client.get("/api/tools/manifest")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_manifest_includes_all_metadata(self, test_client):
        """Test manifest includes full metadata."""
        response = test_client.get("/api/tools/manifest")

        data = response.json()
        tool = data[0]

        # Check key expected fields
        assert "id" in tool
        assert "name" in tool
        assert "description" in tool
        assert "version" in tool
        assert "category" in tool
        assert "enabled" in tool
        assert "initialized" in tool

    def test_manifest_is_sorted_stably(self, test_client):
        response = test_client.get("/api/tools/manifest")
        assert response.status_code == 200

        ids = [item["id"] for item in response.json()]
        assert ids == ["test-tool", "late-tool"]


class TestToolDetailEndpoint:
    """Tests for GET /api/tools/{tool_id} endpoint."""

    def test_get_tool_by_id(self, test_client):
        """Test getting a specific tool."""
        response = test_client.get("/api/tools/test-tool")

        assert response.status_code == 200
        data = response.json()
        assert data["tool_id"] == "test-tool"

    def test_get_nonexistent_tool(self, test_client):
        """Test getting a tool that doesn't exist."""
        response = test_client.get("/api/tools/nonexistent-tool")

        assert response.status_code == 404


class TestToolCapabilitiesEndpoint:
    """Tests for GET /api/tools/{tool_id}/capabilities endpoint."""

    def test_get_tool_capabilities(self, test_client):
        """Test getting tool capabilities."""
        response = test_client.get("/api/tools/test-tool/capabilities")

        assert response.status_code == 200
        data = response.json()
        assert data == {"test": True}

    def test_capabilities_nonexistent_tool(self, test_client):
        """Test capabilities for nonexistent tool."""
        response = test_client.get("/api/tools/nonexistent-tool/capabilities")

        assert response.status_code == 404
