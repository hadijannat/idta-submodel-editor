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


class AlphaWizardTool(BaseTool):
    """Tool sharing wizard step with test-tool for tie-break validation."""

    metadata: ClassVar[ToolMetadata] = ToolMetadata(
        id="alpha-tool",
        name="Alpha Tool",
        description="A first wizard tool",
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
        return {"alpha": True}


class DisabledIntegrationTool(BaseTool):
    """Tool disabled by default feature flag for filter tests."""

    metadata: ClassVar[ToolMetadata] = ToolMetadata(
        id="disabled-integration",
        name="Disabled Integration",
        description="Integration tool behind dataspace flag",
        category="integration",
        feature_flag="dataspace_enabled",
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
        return {"integration": True}


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
    registry.register(AlphaWizardTool)
    registry.register(DisabledIntegrationTool)
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
        assert "ui_entry" in tool
        assert "frontend_component" in tool
        assert "standalone" in tool
        assert "requires_template" in tool

    def test_list_tools_enabled_only_filters_disabled_tools(self, test_client):
        response = test_client.get("/api/tools?enabled_only=true")

        assert response.status_code == 200
        ids = [tool["id"] for tool in response.json()]
        assert "disabled-integration" not in ids

    def test_list_tools_filters_by_category(self, test_client):
        response = test_client.get("/api/tools?category=integration")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "disabled-integration"
        assert data[0]["category"] == "integration"


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
        assert "schema_version" in tool
        assert "disabled_reason" in tool
        assert "ui_entry" in tool
        assert "frontend_component" in tool
        assert "standalone" in tool
        assert "requires_template" in tool

    def test_manifest_is_sorted_stably(self, test_client):
        response = test_client.get("/api/tools/manifest")
        assert response.status_code == 200

        ids = [item["id"] for item in response.json()]
        assert ids == ["alpha-tool", "test-tool", "late-tool", "disabled-integration"]

    def test_manifest_sanitizes_initialization_failure(
        self,
        test_client,
        mock_registry,
    ):
        tool = mock_registry.get("test-tool")
        assert tool is not None
        tool.set_initialization_error("/tmp/cache/token failed")

        response = test_client.get("/api/tools/manifest")
        assert response.status_code == 200

        entry = next(item for item in response.json() if item["id"] == "test-tool")
        assert entry["disabled_reason"] == (
            "Initialization failed. Check backend logs for details."
        )
        assert "/tmp/cache/token" not in entry["disabled_reason"]


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
