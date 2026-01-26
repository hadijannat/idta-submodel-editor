"""
Tests for the ToolRegistry.
"""

import pytest
from typing import ClassVar

from app.services.tools.base import BaseTool, ToolMetadata
from app.services.tools.registry import ToolRegistry
from app.services.tools.context import initialize_tool_context


class MockToolA(BaseTool):
    """Mock tool A for testing."""

    metadata: ClassVar[ToolMetadata] = ToolMetadata(
        id="mock-tool-a",
        name="Mock Tool A",
        description="First mock tool",
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
        return {"a": True}


class MockToolB(BaseTool):
    """Mock tool B for testing."""

    metadata: ClassVar[ToolMetadata] = ToolMetadata(
        id="mock-tool-b",
        name="Mock Tool B",
        description="Second mock tool",
        category="import",
        wizard_step=2,
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
        return {"b": True}


class FailingTool(BaseTool):
    """Tool that fails health check."""

    metadata: ClassVar[ToolMetadata] = ToolMetadata(
        id="failing-tool",
        name="Failing Tool",
        description="Tool that fails",
        category="core",
    )

    async def initialize(self) -> None:
        raise Exception("Init failed")

    async def shutdown(self) -> None:
        await super().shutdown()

    async def health_check(self) -> tuple[bool, str | None]:
        return False, "Health check failed"

    def get_router(self):
        return None

    def get_capabilities(self) -> dict:
        return {}


class UtilityTool(BaseTool):
    """Utility tool without wizard step."""

    metadata: ClassVar[ToolMetadata] = ToolMetadata(
        id="utility-tool",
        name="Utility Tool",
        description="A utility tool",
        category="core",
        wizard_step=None,
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
        return {}


@pytest.fixture
def context():
    """Create a test tool context."""
    return initialize_tool_context()


class TestToolRegistry:
    """Tests for ToolRegistry class."""

    def test_registry_instantiation(self, context):
        """Test registry can be instantiated."""
        registry = ToolRegistry(context)

        assert registry is not None
        assert len(registry._tools) == 0

    def test_register_tool(self, context):
        """Test registering a single tool."""
        registry = ToolRegistry(context)

        tool = registry.register(MockToolA)

        assert tool is not None
        assert tool.metadata.id == "mock-tool-a"
        assert "mock-tool-a" in registry._tools

    def test_register_multiple_tools(self, context):
        """Test registering multiple tools."""
        registry = ToolRegistry(context)

        tool_a = registry.register(MockToolA)
        tool_b = registry.register(MockToolB)

        assert tool_a.metadata.id == "mock-tool-a"
        assert tool_b.metadata.id == "mock-tool-b"
        assert len(registry._tools) == 2

    def test_register_same_tool_twice(self, context):
        """Test registering same tool twice replaces it."""
        registry = ToolRegistry(context)

        registry.register(MockToolA)
        registry.register(MockToolA)

        # Should only have one instance
        assert len(registry._tools) == 1

    def test_get_tool(self, context):
        """Test getting a tool by ID."""
        registry = ToolRegistry(context)
        registry.register(MockToolA)

        tool = registry.get("mock-tool-a")

        assert tool is not None
        assert tool.metadata.name == "Mock Tool A"

    def test_get_nonexistent_tool(self, context):
        """Test getting a tool that doesn't exist."""
        registry = ToolRegistry(context)

        tool = registry.get("nonexistent")

        assert tool is None

    def test_get_all_tools(self, context):
        """Test getting all registered tools."""
        registry = ToolRegistry(context)
        registry.register(MockToolA)
        registry.register(MockToolB)

        tools = registry.get_all()

        assert len(tools) == 2
        ids = [t.metadata.id for t in tools]
        assert "mock-tool-a" in ids
        assert "mock-tool-b" in ids

    def test_get_enabled_tools(self, context):
        """Test getting only enabled tools."""
        registry = ToolRegistry(context)
        registry.register(MockToolA)
        registry.register(MockToolB)

        enabled = registry.get_enabled()

        # Both should be enabled by default (no feature flags)
        assert len(enabled) == 2

    def test_get_tool_manifest(self, context):
        """Test getting tool manifest for frontend."""
        registry = ToolRegistry(context)
        registry.register(MockToolA)

        manifest = registry.get_tool_manifest()

        assert len(manifest) == 1
        entry = manifest[0]
        assert entry["id"] == "mock-tool-a"
        assert entry["name"] == "Mock Tool A"
        assert "enabled" in entry
        assert "initialized" in entry


class TestToolRegistryLifecycle:
    """Tests for registry initialization and shutdown."""

    @pytest.mark.asyncio
    async def test_initialize_all_tools(self, context):
        """Test initializing all registered tools."""
        registry = ToolRegistry(context)
        registry.register(MockToolA)
        registry.register(MockToolB)

        results = await registry.initialize_all()

        assert results["mock-tool-a"] is True
        assert results["mock-tool-b"] is True

    @pytest.mark.asyncio
    async def test_initialize_failing_tool(self, context):
        """Test that failing tool doesn't crash registry."""
        registry = ToolRegistry(context)
        registry.register(MockToolA)
        registry.register(FailingTool)

        results = await registry.initialize_all()

        assert results["mock-tool-a"] is True
        assert results["failing-tool"] is False

    @pytest.mark.asyncio
    async def test_shutdown_all_tools(self, context):
        """Test shutting down all registered tools."""
        registry = ToolRegistry(context)
        registry.register(MockToolA)
        registry.register(MockToolB)

        await registry.initialize_all()
        await registry.shutdown_all()

        # Should complete without error
        assert True

    @pytest.mark.asyncio
    async def test_health_check_all_tools(self, context):
        """Test health checking all tools."""
        registry = ToolRegistry(context)
        registry.register(MockToolA)

        await registry.initialize_all()
        health = await registry.health_check_all()

        assert "mock-tool-a" in health
        assert health["mock-tool-a"]["healthy"] is True


class TestToolRegistryAutoDiscovery:
    """Tests for tool auto-discovery."""

    def test_discover_builtin_tools(self, context):
        """Test discovering builtin tools."""
        registry = ToolRegistry(context)

        count = registry.discover_tools("app.services.tools.builtin")

        # Should find at least the tools we created
        assert count >= 1

    def test_discover_nonexistent_package(self, context):
        """Test discovering from nonexistent package."""
        registry = ToolRegistry(context)

        count = registry.discover_tools("nonexistent.package")

        # Should return 0, not crash
        assert count == 0

    def test_discover_registers_tools(self, context):
        """Test that discovery actually registers tools."""
        registry = ToolRegistry(context)

        registry.discover_tools("app.services.tools.builtin")

        # Should have some tools registered
        assert len(registry._tools) > 0


class TestToolRegistryRouters:
    """Tests for router aggregation."""

    def test_get_all_routers_empty(self, context):
        """Test getting routers when no tools registered."""
        registry = ToolRegistry(context)

        routers = registry.get_all_routers()

        assert routers == []

    def test_get_all_routers_excludes_none(self, context):
        """Test that None routers are excluded."""
        registry = ToolRegistry(context)
        registry.register(MockToolA)  # Returns None router

        routers = registry.get_all_routers()

        # MockToolA returns None, so should be empty
        assert len(routers) == 0
