"""Tests for built-in tool lifecycle and health wiring."""

import pytest

from app.config import Settings
from app.schemas.semantic import SemanticProviderInfo
from app.services.tools.builtin.pcf_tool import PCFTool
from app.services.tools.builtin.semantic_tool import SemanticTool
from app.services.tools.builtin.template_ops_tool import TemplateOpsTool
from app.services.tools.context import ToolContext


class _SemanticServiceStub:
    def providers_info(self) -> list[SemanticProviderInfo]:
        return [
            SemanticProviderInfo(
                id="offline",
                label="Offline",
                status="ready",
            )
        ]


@pytest.fixture
def context() -> ToolContext:
    return ToolContext(Settings())


@pytest.mark.asyncio
async def test_semantic_tool_health_uses_provider_status(context: ToolContext):
    tool = SemanticTool(context)
    tool._service = _SemanticServiceStub()

    healthy, message = await tool.health_check()

    assert healthy is True
    assert message is None


@pytest.mark.asyncio
async def test_pcf_tool_health_uses_emission_factor_metadata(context: ToolContext):
    tool = PCFTool(context)
    await tool.initialize()

    healthy, message = await tool.health_check()

    assert healthy is True
    assert message is None
    assert tool.get_capabilities()["emission_factor_count"] > 0


@pytest.mark.asyncio
async def test_template_ops_marks_lifecycle_initialized(context: ToolContext):
    tool = TemplateOpsTool(context)

    await tool.initialize()
    assert tool.is_initialized is True

    await tool.shutdown()
    assert tool.is_initialized is False
