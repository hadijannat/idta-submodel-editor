"""
Capability checking utilities for tools.

Provides functions for validating tool dependencies, checking external
service availability, and reporting tool capabilities.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.tools.base import BaseTool
    from app.services.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class DependencyStatus(Enum):
    """Status of a dependency check."""

    SATISFIED = "satisfied"
    MISSING = "missing"
    DISABLED = "disabled"
    UNHEALTHY = "unhealthy"


@dataclass
class DependencyCheckResult:
    """Result of checking a single dependency."""

    dependency_id: str
    status: DependencyStatus
    message: str | None = None

    def is_satisfied(self) -> bool:
        """Check if the dependency is satisfied."""
        return self.status == DependencyStatus.SATISFIED


@dataclass
class CapabilityReport:
    """Report of a tool's capabilities and dependencies."""

    tool_id: str
    enabled: bool
    initialized: bool
    healthy: bool
    health_message: str | None
    dependencies: list[DependencyCheckResult] = field(default_factory=list)
    capabilities: dict = field(default_factory=dict)

    def all_dependencies_satisfied(self) -> bool:
        """Check if all dependencies are satisfied."""
        return all(dep.is_satisfied() for dep in self.dependencies)

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "tool_id": self.tool_id,
            "enabled": self.enabled,
            "initialized": self.initialized,
            "healthy": self.healthy,
            "health_message": self.health_message,
            "dependencies": [
                {
                    "id": dep.dependency_id,
                    "status": dep.status.value,
                    "message": dep.message,
                }
                for dep in self.dependencies
            ],
            "capabilities": self.capabilities,
            "all_dependencies_satisfied": self.all_dependencies_satisfied(),
        }


def check_tool_dependency(
    registry: "ToolRegistry",
    dependency_id: str,
) -> DependencyCheckResult:
    """
    Check if a tool dependency is satisfied.

    Args:
        registry: The tool registry
        dependency_id: ID of the dependency tool

    Returns:
        DependencyCheckResult with the status
    """
    tool = registry.get(dependency_id)

    if tool is None:
        return DependencyCheckResult(
            dependency_id=dependency_id,
            status=DependencyStatus.MISSING,
            message=f"Tool '{dependency_id}' is not registered",
        )

    if not tool.is_enabled():
        return DependencyCheckResult(
            dependency_id=dependency_id,
            status=DependencyStatus.DISABLED,
            message=f"Tool '{dependency_id}' is disabled",
        )

    if not tool.is_initialized:
        return DependencyCheckResult(
            dependency_id=dependency_id,
            status=DependencyStatus.UNHEALTHY,
            message=f"Tool '{dependency_id}' is not initialized",
        )

    return DependencyCheckResult(
        dependency_id=dependency_id,
        status=DependencyStatus.SATISFIED,
    )


def check_all_dependencies(
    registry: "ToolRegistry",
    tool: "BaseTool",
) -> list[DependencyCheckResult]:
    """
    Check all dependencies for a tool.

    Args:
        registry: The tool registry
        tool: The tool to check dependencies for

    Returns:
        List of DependencyCheckResults
    """
    results: list[DependencyCheckResult] = []

    for dep_id in tool.metadata.dependencies:
        result = check_tool_dependency(registry, dep_id)
        results.append(result)

    return results


async def generate_capability_report(
    registry: "ToolRegistry",
    tool: "BaseTool",
) -> CapabilityReport:
    """
    Generate a comprehensive capability report for a tool.

    Args:
        registry: The tool registry
        tool: The tool to report on

    Returns:
        CapabilityReport with full status information
    """
    # Check health
    healthy = False
    health_message = None
    if tool.is_initialized:
        try:
            healthy, health_message = await tool.health_check()
        except Exception as e:
            health_message = str(e)

    # Check dependencies
    dependencies = check_all_dependencies(registry, tool)

    # Get capabilities
    capabilities = tool.get_capabilities()

    return CapabilityReport(
        tool_id=tool.metadata.id,
        enabled=tool.is_enabled(),
        initialized=tool.is_initialized,
        healthy=healthy,
        health_message=health_message,
        dependencies=dependencies,
        capabilities=capabilities,
    )


async def generate_all_capability_reports(
    registry: "ToolRegistry",
) -> dict[str, CapabilityReport]:
    """
    Generate capability reports for all registered tools.

    Args:
        registry: The tool registry

    Returns:
        Dictionary mapping tool IDs to their capability reports
    """
    reports: dict[str, CapabilityReport] = {}

    for tool in registry.get_all():
        report = await generate_capability_report(registry, tool)
        reports[tool.metadata.id] = report

    return reports


def validate_dependency_graph(registry: "ToolRegistry") -> list[str]:
    """
    Validate the dependency graph for circular dependencies.

    Args:
        registry: The tool registry

    Returns:
        List of error messages (empty if valid)
    """
    errors: list[str] = []
    visited: set[str] = set()
    rec_stack: set[str] = set()

    def has_cycle(tool_id: str, path: list[str]) -> bool:
        """DFS to detect cycles."""
        if tool_id in rec_stack:
            cycle_path = " -> ".join(path + [tool_id])
            errors.append(f"Circular dependency detected: {cycle_path}")
            return True

        if tool_id in visited:
            return False

        visited.add(tool_id)
        rec_stack.add(tool_id)

        tool = registry.get(tool_id)
        if tool is not None:
            for dep_id in tool.metadata.dependencies:
                if has_cycle(dep_id, path + [tool_id]):
                    return True

        rec_stack.remove(tool_id)
        return False

    for tool in registry.get_all():
        if tool.metadata.id not in visited:
            has_cycle(tool.metadata.id, [])

    return errors


def get_initialization_order(registry: "ToolRegistry") -> list[str]:
    """
    Get the correct initialization order for tools based on dependencies.

    Uses topological sort to ensure dependencies are initialized first.

    Args:
        registry: The tool registry

    Returns:
        List of tool IDs in initialization order
    """
    # Check for cycles first
    errors = validate_dependency_graph(registry)
    if errors:
        logger.error("Cannot determine initialization order: %s", errors)
        return []

    visited: set[str] = set()
    order: list[str] = []

    def visit(tool_id: str) -> None:
        if tool_id in visited:
            return

        tool = registry.get(tool_id)
        if tool is None:
            return

        visited.add(tool_id)

        for dep_id in tool.metadata.dependencies:
            visit(dep_id)

        order.append(tool_id)

    for tool in registry.get_all():
        visit(tool.metadata.id)

    return order
