# Copyright (c) 2024-2025 Hadi Jannatabadi <h.jannatabadi@iat.rwth-aachen.de>
# SPDX-License-Identifier: MIT
"""
Tool registry for the IDTA Submodel Editor.

Provides auto-discovery, lifecycle management, and router aggregation
for all registered tools.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from typing import TYPE_CHECKING

from fastapi import APIRouter

from app.services.tools.base import BaseTool
from app.services.tools.context import ToolContext, initialize_tool_context

if TYPE_CHECKING:
    from types import ModuleType

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Registry for managing tools in the IDTA Submodel Editor.

    The registry handles:
    - Tool registration and lookup
    - Auto-discovery of tools from packages
    - Lifecycle management (initialize, shutdown)
    - Router aggregation for API endpoints
    - Manifest generation for frontend consumption

    Example:
        registry = ToolRegistry()

        # Auto-discover and register builtin tools
        registry.discover_tools("app.services.tools.builtin")

        # Initialize all tools
        results = await registry.initialize_all()

        # Get routers for mounting
        for router in registry.get_all_routers():
            app.include_router(router)

        # Shutdown on app close
        await registry.shutdown_all()
    """

    MANIFEST_SCHEMA_VERSION = "1.1.0"

    def __init__(self, context: ToolContext | None = None):
        """
        Initialize the tool registry.

        Args:
            context: Shared tool context. If None, a new context is created.
        """
        self._context = context or initialize_tool_context()
        self._tools: dict[str, BaseTool] = {}
        self._initialization_order: list[str] = []
        self._manifest_cache: list[dict] | None = None

    @property
    def context(self) -> ToolContext:
        """Get the shared tool context."""
        return self._context

    def register(self, tool_class: type[BaseTool]) -> BaseTool:
        """
        Register a tool class with the registry.

        Creates an instance of the tool and adds it to the registry.
        If a tool with the same ID is already registered, it is replaced.

        Args:
            tool_class: The tool class to register

        Returns:
            The registered tool instance
        """
        tool = tool_class(self._context)
        tool_id = tool.metadata.id

        if tool_id in self._tools:
            logger.warning("Replacing existing tool: %s", tool_id)
        else:
            logger.info("Registering tool: %s", tool_id)

        self._tools[tool_id] = tool
        self._invalidate_manifest_cache()
        return tool

    def unregister(self, tool_id: str) -> bool:
        """
        Unregister a tool from the registry.

        Args:
            tool_id: ID of the tool to unregister

        Returns:
            True if the tool was found and removed, False otherwise
        """
        if tool_id in self._tools:
            del self._tools[tool_id]
            if tool_id in self._initialization_order:
                self._initialization_order.remove(tool_id)
            self._invalidate_manifest_cache()
            logger.info("Unregistered tool: %s", tool_id)
            return True
        return False

    def get(self, tool_id: str) -> BaseTool | None:
        """
        Get a tool by ID.

        Args:
            tool_id: ID of the tool to get

        Returns:
            The tool instance, or None if not found
        """
        return self._tools.get(tool_id)

    def get_all(self) -> list[BaseTool]:
        """
        Get all registered tools.

        Returns:
            List of all tool instances
        """
        return list(self._tools.values())

    def get_enabled(self) -> list[BaseTool]:
        """
        Get all enabled tools.

        Returns:
            List of enabled tool instances
        """
        return [tool for tool in self._tools.values() if tool.is_enabled()]

    def discover_tools(self, package_name: str) -> int:
        """
        Auto-discover and register tools from a Python package.

        Scans the package for modules containing a `tool_class` attribute
        that is a subclass of BaseTool. Each discovered tool is registered.

        Args:
            package_name: Fully qualified package name to scan

        Returns:
            Number of tools discovered and registered
        """
        count = 0

        try:
            package = importlib.import_module(package_name)
        except ImportError as e:
            logger.warning("Failed to import package %s: %s", package_name, e)
            return 0

        package_path = getattr(package, "__path__", None)
        if package_path is None:
            logger.warning("Package %s has no __path__", package_name)
            return 0

        for finder, module_name, is_pkg in pkgutil.iter_modules(package_path):
            if is_pkg:
                # Recursively discover tools in subpackages
                count += self.discover_tools(f"{package_name}.{module_name}")
                continue

            if module_name.startswith("_"):
                continue

            try:
                module = importlib.import_module(f"{package_name}.{module_name}")
                tool_class = self._find_tool_class(module)

                if tool_class is not None:
                    self.register(tool_class)
                    count += 1
                    logger.debug(
                        "Discovered tool %s in %s.%s",
                        tool_class.metadata.id,
                        package_name,
                        module_name,
                    )

            except Exception as e:
                logger.warning(
                    "Failed to load tool from %s.%s: %s",
                    package_name,
                    module_name,
                    e,
                )

        logger.info("Discovered %d tools in %s", count, package_name)
        return count

    def _find_tool_class(self, module: "ModuleType") -> type[BaseTool] | None:
        """
        Find a tool class in a module.

        Looks for:
        1. A `tool_class` attribute
        2. Any class that is a subclass of BaseTool (but not BaseTool itself)

        Args:
            module: The module to search

        Returns:
            The tool class, or None if not found
        """
        # Check for explicit tool_class attribute
        if hasattr(module, "tool_class"):
            candidate = getattr(module, "tool_class")
            if isinstance(candidate, type) and issubclass(candidate, BaseTool):
                return candidate

        # Scan for BaseTool subclasses
        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue

            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, BaseTool)
                and attr is not BaseTool
                and hasattr(attr, "metadata")
            ):
                return attr

        return None

    async def initialize_all(self) -> dict[str, bool]:
        """
        Initialize all registered tools.

        Tools are initialized in dependency order. If a tool has dependencies,
        those tools are initialized first.

        Returns:
            Dictionary mapping tool IDs to initialization success (True/False)
        """
        results: dict[str, bool] = {}
        pending = set(self._tools.keys())
        initialized = set()

        while pending:
            made_progress = False

            for tool_id in list(pending):
                tool = self._tools[tool_id]

                # Check if tool is enabled
                if not tool.is_enabled():
                    logger.info("Skipping disabled tool: %s", tool_id)
                    pending.remove(tool_id)
                    results[tool_id] = True
                    continue

                # Check dependency availability and status
                deps = tool.metadata.dependencies
                missing_or_disabled = [
                    dep_id
                    for dep_id in deps
                    if (self._tools.get(dep_id) is None)
                    or not self._tools[dep_id].is_enabled()
                ]
                failed_deps = [
                    dep_id for dep_id in deps if results.get(dep_id) is False
                ]

                if missing_or_disabled:
                    logger.warning(
                        "Skipping tool %s due to missing/disabled dependencies: %s",
                        tool_id,
                        missing_or_disabled,
                    )
                    pending.remove(tool_id)
                    results[tool_id] = False
                    made_progress = True
                    continue

                if failed_deps:
                    logger.warning(
                        "Skipping tool %s due to failed dependencies: %s",
                        tool_id,
                        failed_deps,
                    )
                    pending.remove(tool_id)
                    results[tool_id] = False
                    made_progress = True
                    continue

                # Check if dependencies are satisfied
                if not all(dep in initialized for dep in deps):
                    continue

                # Initialize the tool
                try:
                    await tool.initialize()
                    initialized.add(tool_id)
                    self._initialization_order.append(tool_id)
                    results[tool_id] = True
                    logger.info("Initialized tool: %s", tool_id)
                except Exception as e:
                    results[tool_id] = False
                    logger.error("Failed to initialize tool %s: %s", tool_id, e)

                pending.remove(tool_id)
                made_progress = True

            if not made_progress and pending:
                # Circular dependency or missing dependency
                logger.error(
                    "Cannot initialize remaining tools due to unmet dependencies: %s",
                    pending,
                )
                for tool_id in pending:
                    results[tool_id] = False
                break

        # Invalidate manifest cache since initialized state changed
        self._invalidate_manifest_cache()
        return results

    async def shutdown_all(self) -> None:
        """
        Shutdown all initialized tools.

        Tools are shut down in reverse initialization order.
        """
        for tool_id in reversed(self._initialization_order):
            tool = self._tools.get(tool_id)
            if tool is None:
                continue

            try:
                await tool.shutdown()
                logger.info("Shut down tool: %s", tool_id)
            except Exception as e:
                logger.error("Error shutting down tool %s: %s", tool_id, e)

        self._initialization_order.clear()
        # Invalidate manifest cache since initialized state changed
        self._invalidate_manifest_cache()

    def get_all_routers(self) -> list[APIRouter]:
        """
        Get all routers from enabled tools.

        Returns:
            List of FastAPI routers to mount
        """
        routers: list[APIRouter] = []

        for tool in self.get_enabled():
            router = tool.get_router()
            if router is not None:
                routers.append(router)

        return routers

    def _invalidate_manifest_cache(self) -> None:
        """Invalidate the cached manifest when tools change."""
        self._manifest_cache = None

    def get_tool_manifest(self) -> list[dict]:
        """
        Get the manifest of all tools for API responses.

        The manifest is cached and only rebuilt when tools are
        registered or unregistered.

        Returns:
            List of tool manifest entries
        """
        if self._manifest_cache is None:
            entries = []
            for tool in self._tools.values():
                entry = tool.to_manifest_entry()
                entry["schema_version"] = self.MANIFEST_SCHEMA_VERSION
                entry["disabled_reason"] = tool.get_disabled_reason(self)
                entries.append(entry)
            # Keep manifest ordering stable for frontend and tests.
            entries.sort(
                key=lambda entry: (
                    entry.get("wizard_step") is None,
                    entry.get("wizard_step") if entry.get("wizard_step") is not None else 999,
                    entry.get("id", ""),
                )
            )
            self._manifest_cache = entries
        return self._manifest_cache

    async def health_check_all(self) -> dict[str, dict]:
        """
        Run health checks on all enabled tools.

        Returns:
            Dictionary mapping tool IDs to health status.
            Each status contains "healthy" (bool) and "message" (str | None).
        """
        results: dict[str, dict] = {}

        for tool in self.get_enabled():
            if not tool.is_initialized:
                results[tool.metadata.id] = {
                    "healthy": False,
                    "message": "Tool not initialized",
                }
                continue

            try:
                healthy, message = await tool.health_check()
                results[tool.metadata.id] = {
                    "healthy": healthy,
                    "message": message,
                }
            except Exception as e:
                results[tool.metadata.id] = {
                    "healthy": False,
                    "message": str(e),
                }

        return results


# Global registry instance
_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """
    Get the global tool registry.

    Returns:
        The shared ToolRegistry instance

    Raises:
        RuntimeError: If the registry hasn't been initialized
    """
    global _registry
    if _registry is None:
        raise RuntimeError(
            "Tool registry not initialized. "
            "Call initialize_registry() during app startup."
        )
    return _registry


async def initialize_registry() -> ToolRegistry:
    """
    Initialize the global tool registry.

    Called during application startup. Discovers and initializes all
    builtin tools.

    Returns:
        The initialized ToolRegistry
    """
    global _registry
    if _registry is None:
        _registry = ToolRegistry()

    # Discover builtin tools if not already populated
    if not _registry.get_all():
        _registry.discover_tools("app.services.tools.builtin")

    # Validate dependency graph before initialization
    try:
        from app.services.tools.capabilities import validate_dependency_graph

        errors = validate_dependency_graph(_registry)
        if errors:
            logger.error("Tool dependency graph validation errors: %s", errors)
    except Exception as e:
        logger.warning("Failed to validate tool dependency graph: %s", e)

    # Initialize all discovered tools
    await _registry.initialize_all()

    return _registry


async def shutdown_registry() -> None:
    """
    Shutdown the global tool registry.

    Called during application shutdown.
    """
    global _registry
    if _registry is not None:
        await _registry.shutdown_all()
        _registry = None
