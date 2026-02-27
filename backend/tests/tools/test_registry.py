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


class StepTenTool(BaseTool):
    metadata = ToolMetadata(
        id="step-10",
        name="Step Ten",
        description="Wizard step ten",
        wizard_step=10,
    )


class StepThreeTool(BaseTool):
    metadata = ToolMetadata(
        id="step-3",
        name="Step Three",
        description="Wizard step three",
        wizard_step=3,
    )


class UtilityZTool(BaseTool):
    metadata = ToolMetadata(
        id="utility-z",
        name="Utility Z",
        description="Utility tool",
        wizard_step=None,
    )


class UtilityATool(BaseTool):
    metadata = ToolMetadata(
        id="utility-a",
        name="Utility A",
        description="Utility tool",
        wizard_step=None,
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


def test_manifest_order_is_stable_and_sorted():
    context = ToolContext(Settings())
    registry = ToolRegistry(context=context)
    # Register in unsorted order to verify explicit sort contract.
    registry.register(UtilityZTool)
    registry.register(StepTenTool)
    registry.register(UtilityATool)
    registry.register(StepThreeTool)

    manifest = registry.get_tool_manifest()
    ids = [entry["id"] for entry in manifest]

    assert ids == ["step-3", "step-10", "utility-a", "utility-z"]


def test_manifest_cache_invalidates_on_new_registration():
    context = ToolContext(Settings())
    registry = ToolRegistry(context=context)
    registry.register(StepTenTool)
    first_manifest = registry.get_tool_manifest()
    assert [entry["id"] for entry in first_manifest] == ["step-10"]

    registry.register(StepThreeTool)
    second_manifest = registry.get_tool_manifest()
    assert [entry["id"] for entry in second_manifest] == ["step-3", "step-10"]
