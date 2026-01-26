"""
Tool registry API endpoints.

Provides endpoints for listing tools, checking health, and getting
tool-specific information.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.services.tools.registry import ToolRegistry, get_tool_registry
from app.services.tools.capabilities import (
    generate_capability_report,
    generate_all_capability_reports,
)


router = APIRouter(prefix="/api/tools", tags=["tools"])


# --- Response Models ---


class ToolMetadataResponse(BaseModel):
    """Tool metadata for API responses."""

    id: str
    name: str
    description: str
    version: str
    category: str
    wizard_step: int | None
    feature_flag: str | None
    requires_auth: bool
    dependencies: list[str]
    enabled: bool
    initialized: bool


class ToolHealthResponse(BaseModel):
    """Health status for a single tool."""

    tool_id: str
    healthy: bool
    message: str | None


class ToolsHealthResponse(BaseModel):
    """Health status for all tools."""

    tools: dict[str, ToolHealthResponse]
    all_healthy: bool


class DependencyResponse(BaseModel):
    """Dependency check result."""

    id: str
    status: str
    message: str | None


class CapabilityReportResponse(BaseModel):
    """Full capability report for a tool."""

    tool_id: str
    enabled: bool
    initialized: bool
    healthy: bool
    health_message: str | None
    dependencies: list[DependencyResponse]
    capabilities: dict
    all_dependencies_satisfied: bool


# --- Dependency Injection ---


def get_registry() -> ToolRegistry:
    """Get the tool registry dependency."""
    return get_tool_registry()


# --- Endpoints ---


@router.get("", response_model=list[ToolMetadataResponse])
async def list_tools(
    registry: Annotated[ToolRegistry, Depends(get_registry)],
    enabled_only: bool = False,
    category: str | None = None,
) -> list[ToolMetadataResponse]:
    """
    List all registered tools.

    Args:
        enabled_only: If true, only return enabled tools
        category: Filter by category (core, import, export, integration, analytics)

    Returns:
        List of tool metadata
    """
    if enabled_only:
        tools = registry.get_enabled()
    else:
        tools = registry.get_all()

    result = []
    for tool in tools:
        if category and tool.metadata.category != category:
            continue

        result.append(
            ToolMetadataResponse(
                id=tool.metadata.id,
                name=tool.metadata.name,
                description=tool.metadata.description,
                version=tool.metadata.version,
                category=tool.metadata.category,
                wizard_step=tool.metadata.wizard_step,
                feature_flag=tool.metadata.feature_flag,
                requires_auth=tool.metadata.requires_auth,
                dependencies=tool.metadata.dependencies,
                enabled=tool.is_enabled(),
                initialized=tool.is_initialized,
            )
        )

    # Sort by wizard_step (None values at end)
    result.sort(key=lambda t: (t.wizard_step is None, t.wizard_step or 0))

    return result


@router.get("/health", response_model=ToolsHealthResponse)
async def check_tools_health(
    registry: Annotated[ToolRegistry, Depends(get_registry)],
) -> ToolsHealthResponse:
    """
    Check health of all enabled tools.

    Returns:
        Health status for each tool and overall health
    """
    health_results = await registry.health_check_all()

    tools: dict[str, ToolHealthResponse] = {}
    all_healthy = True

    for tool_id, status_info in health_results.items():
        tools[tool_id] = ToolHealthResponse(
            tool_id=tool_id,
            healthy=status_info["healthy"],
            message=status_info["message"],
        )
        if not status_info["healthy"]:
            all_healthy = False

    return ToolsHealthResponse(
        tools=tools,
        all_healthy=all_healthy,
    )


@router.get("/manifest")
async def get_tool_manifest(
    registry: Annotated[ToolRegistry, Depends(get_registry)],
) -> list[dict]:
    """
    Get the full tool manifest for frontend consumption.

    Returns a list of all tools with their metadata and runtime status.
    This is the primary endpoint used by the frontend to discover
    available tools and their wizard positions.

    Returns:
        List of tool manifest entries
    """
    return registry.get_tool_manifest()


@router.get("/{tool_id}", response_model=CapabilityReportResponse)
async def get_tool(
    tool_id: str,
    registry: Annotated[ToolRegistry, Depends(get_registry)],
) -> CapabilityReportResponse:
    """
    Get detailed information about a specific tool.

    Args:
        tool_id: The tool's unique identifier

    Returns:
        Full capability report including health and dependencies
    """
    tool = registry.get(tool_id)

    if tool is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool '{tool_id}' not found",
        )

    report = await generate_capability_report(registry, tool)

    return CapabilityReportResponse(
        tool_id=report.tool_id,
        enabled=report.enabled,
        initialized=report.initialized,
        healthy=report.healthy,
        health_message=report.health_message,
        dependencies=[
            DependencyResponse(
                id=dep.dependency_id,
                status=dep.status.value,
                message=dep.message,
            )
            for dep in report.dependencies
        ],
        capabilities=report.capabilities,
        all_dependencies_satisfied=report.all_dependencies_satisfied(),
    )


@router.get("/{tool_id}/health", response_model=ToolHealthResponse)
async def check_tool_health(
    tool_id: str,
    registry: Annotated[ToolRegistry, Depends(get_registry)],
) -> ToolHealthResponse:
    """
    Check health of a specific tool.

    Args:
        tool_id: The tool's unique identifier

    Returns:
        Health status for the tool
    """
    tool = registry.get(tool_id)

    if tool is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool '{tool_id}' not found",
        )

    if not tool.is_initialized:
        return ToolHealthResponse(
            tool_id=tool_id,
            healthy=False,
            message="Tool not initialized",
        )

    try:
        healthy, message = await tool.health_check()
        return ToolHealthResponse(
            tool_id=tool_id,
            healthy=healthy,
            message=message,
        )
    except Exception as e:
        return ToolHealthResponse(
            tool_id=tool_id,
            healthy=False,
            message=str(e),
        )


@router.get("/{tool_id}/capabilities")
async def get_tool_capabilities(
    tool_id: str,
    registry: Annotated[ToolRegistry, Depends(get_registry)],
) -> dict:
    """
    Get capabilities provided by a specific tool.

    Args:
        tool_id: The tool's unique identifier

    Returns:
        Dictionary of capabilities
    """
    tool = registry.get(tool_id)

    if tool is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool '{tool_id}' not found",
        )

    return tool.get_capabilities()
