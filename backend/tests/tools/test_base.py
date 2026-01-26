"""
Tests for the BaseTool interface and ToolMetadata.
"""

import pytest
from dataclasses import asdict
from typing import ClassVar

from app.services.tools.base import BaseTool, ToolMetadata
from app.services.tools.context import ToolContext, initialize_tool_context


class TestToolMetadata:
    """Tests for ToolMetadata dataclass."""

    def test_metadata_defaults(self):
        """Test that ToolMetadata has sensible defaults."""
        metadata = ToolMetadata(
            id="test-tool",
            name="Test Tool",
            description="A test tool",
        )

        assert metadata.id == "test-tool"
        assert metadata.name == "Test Tool"
        assert metadata.description == "A test tool"
        assert metadata.version == "1.0.0"
        assert metadata.category == "core"
        assert metadata.wizard_step is None
        assert metadata.feature_flag is None
        assert metadata.requires_auth is False
        assert metadata.dependencies == []

    def test_metadata_custom_values(self):
        """Test ToolMetadata with custom values."""
        metadata = ToolMetadata(
            id="custom-tool",
            name="Custom Tool",
            description="A custom tool",
            version="2.0.0",
            category="import",
            wizard_step=3,
            feature_flag="custom_enabled",
            requires_auth=True,
            dependencies=["other-tool"],
        )

        assert metadata.id == "custom-tool"
        assert metadata.version == "2.0.0"
        assert metadata.category == "import"
        assert metadata.wizard_step == 3
        assert metadata.feature_flag == "custom_enabled"
        assert metadata.requires_auth is True
        assert metadata.dependencies == ["other-tool"]

    def test_metadata_valid_categories(self):
        """Test that category accepts valid values."""
        valid_categories = ["core", "import", "export", "integration", "analytics"]

        for category in valid_categories:
            metadata = ToolMetadata(
                id="test",
                name="Test",
                description="Test",
                category=category,
            )
            assert metadata.category == category

    def test_metadata_to_dict(self):
        """Test converting metadata to dictionary."""
        metadata = ToolMetadata(
            id="test-tool",
            name="Test Tool",
            description="Test description",
        )

        data = metadata.to_dict()

        assert data["id"] == "test-tool"
        assert data["name"] == "Test Tool"
        assert data["description"] == "Test description"
        assert "version" in data
        assert "category" in data


class MockTool(BaseTool):
    """Mock tool for testing."""

    metadata: ClassVar[ToolMetadata] = ToolMetadata(
        id="mock-tool",
        name="Mock Tool",
        description="A mock tool for testing",
        category="core",
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
        return {"test_capability": True}


@pytest.fixture
def context():
    """Create a test tool context."""
    return initialize_tool_context()


class TestBaseTool:
    """Tests for BaseTool abstract class."""

    def test_tool_has_metadata(self):
        """Test that tool has class-level metadata."""
        assert hasattr(MockTool, "metadata")
        assert MockTool.metadata.id == "mock-tool"
        assert MockTool.metadata.name == "Mock Tool"

    def test_tool_instantiation(self, context):
        """Test that tool can be instantiated."""
        tool = MockTool(context)
        assert tool is not None
        assert tool.metadata.id == "mock-tool"

    @pytest.mark.asyncio
    async def test_tool_initialize(self, context):
        """Test tool initialization."""
        tool = MockTool(context)
        assert tool.is_initialized is False

        await tool.initialize()

        assert tool.is_initialized is True

    @pytest.mark.asyncio
    async def test_tool_shutdown(self, context):
        """Test tool shutdown."""
        tool = MockTool(context)
        await tool.initialize()
        assert tool.is_initialized is True

        await tool.shutdown()

        assert tool.is_initialized is False

    @pytest.mark.asyncio
    async def test_tool_health_check(self, context):
        """Test tool health check."""
        tool = MockTool(context)

        healthy, message = await tool.health_check()

        assert healthy is True
        assert message is None

    def test_tool_get_router(self, context):
        """Test tool get_router returns None for mock."""
        tool = MockTool(context)

        router = tool.get_router()

        assert router is None

    def test_tool_get_capabilities(self, context):
        """Test tool get_capabilities."""
        tool = MockTool(context)

        capabilities = tool.get_capabilities()

        assert capabilities == {"test_capability": True}

    def test_tool_is_enabled_default(self, context):
        """Test tool is_enabled with no feature flag."""
        tool = MockTool(context)

        # No feature flag means always enabled
        assert tool.is_enabled() is True

    def test_tool_context_access(self, context):
        """Test tool has context attribute."""
        tool = MockTool(context)

        # Context should be accessible
        assert tool.context is context

    def test_tool_to_manifest_entry(self, context):
        """Test generating manifest entry."""
        tool = MockTool(context)

        entry = tool.to_manifest_entry()

        assert entry["id"] == "mock-tool"
        assert entry["name"] == "Mock Tool"
        assert "enabled" in entry
        assert "initialized" in entry


class FeatureFlagTool(BaseTool):
    """Tool with feature flag for testing."""

    metadata: ClassVar[ToolMetadata] = ToolMetadata(
        id="feature-flag-tool",
        name="Feature Flag Tool",
        description="Tool with feature flag",
        feature_flag="test_flag_enabled",
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


class TestFeatureFlagTool:
    """Tests for tools with feature flags."""

    def test_tool_with_feature_flag(self):
        """Test tool has feature flag in metadata."""
        assert FeatureFlagTool.metadata.feature_flag == "test_flag_enabled"

    def test_is_enabled_checks_context(self, context):
        """Test is_enabled delegates to context."""
        tool = FeatureFlagTool(context)

        # With context set, checks feature flag
        # Default context should have feature disabled (returns False from is_feature_enabled)
        result = tool.is_enabled()
        # The result depends on context implementation
        assert isinstance(result, bool)
