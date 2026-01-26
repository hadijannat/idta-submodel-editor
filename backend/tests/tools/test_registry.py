"""Tests for the tool registry dependency handling."""

import pytest

from app.config import Settings
from app.services.tools.base import BaseTool, ToolMetadata
from app.services.tools.context import ToolContext
from app.services.tools.registry import ToolRegistry


class MissingDepTool(BaseTool):
    """Tool that depends on a missing tool."""

    metadata = ToolMetadata(
        id="missing-dep-tool",
        name="Missing Dep Tool",
        description="Depends on a missing tool",
        dependencies=["does-not-exist"],
    )


class DisabledDepTool(BaseTool):
    """Tool that is disabled via feature flag."""

    metadata = ToolMetadata(
        id="disabled-dep",
        name="Disabled Dep",
        description="Disabled dependency",
        feature_flag="magic_import_enabled",
    )


class DependsOnDisabledTool(BaseTool):
    """Tool that depends on a disabled tool."""

    metadata = ToolMetadata(
        id="depends-on-disabled",
        name="Depends On Disabled",
        description="Depends on a disabled tool",
        dependencies=["disabled-dep"],
    )


class FailingTool(BaseTool):
    """Tool that fails during initialization."""

    metadata = ToolMetadata(
        id="failing-tool",
        name="Failing Tool",
        description="Fails on initialize",
    )

    async def initialize(self) -> None:
        raise RuntimeError("boom")


class DependsOnFailingTool(BaseTool):
    """Tool that depends on a failing tool."""

    metadata = ToolMetadata(
        id="depends-on-failing",
        name="Depends On Failing",
        description="Depends on a failing tool",
        dependencies=["failing-tool"],
    )


@pytest.mark.asyncio
async def test_initialize_all_skips_missing_dependency():
    context = ToolContext(Settings())
    registry = ToolRegistry(context=context)
    registry.register(MissingDepTool)

    results = await registry.initialize_all()

    assert results["missing-dep-tool"] is False


@pytest.mark.asyncio
async def test_initialize_all_skips_disabled_dependency():
    settings = Settings(magic_import_enabled=False)
    context = ToolContext(settings)
    registry = ToolRegistry(context=context)
    registry.register(DisabledDepTool)
    registry.register(DependsOnDisabledTool)

    results = await registry.initialize_all()

    assert results["disabled-dep"] is True  # disabled tools are skipped as OK
    assert results["depends-on-disabled"] is False


@pytest.mark.asyncio
async def test_initialize_all_skips_failed_dependency():
    context = ToolContext(Settings())
    registry = ToolRegistry(context=context)
    registry.register(FailingTool)
    registry.register(DependsOnFailingTool)

    results = await registry.initialize_all()

    assert results["failing-tool"] is False
    assert results["depends-on-failing"] is False
