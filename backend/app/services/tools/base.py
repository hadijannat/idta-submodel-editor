# Copyright (c) 2024-2025 Hadi Jannatabadi <h.jannatabadi@iat.rwth-aachen.de>
# SPDX-License-Identifier: MIT
"""
Base tool interface for the IDTA Submodel Editor.

Defines the abstract base class that all tools must implement, along with
the metadata structure for tool registration and discovery.
"""

from abc import ABC
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar, Literal

from fastapi import APIRouter

if TYPE_CHECKING:
    from app.services.tools.registry import ToolRegistry
    from app.services.tools.context import ToolContext


ToolCategory = Literal["core", "import", "export", "integration", "analytics"]
ToolUiEntry = Literal["wizard", "utility", "field_action", "api_only"]


@dataclass
class ToolMetadata:
    """
    Metadata describing a tool for registration and discovery.

    Attributes:
        id: Unique identifier for the tool (e.g., "magic-import")
        name: Human-readable display name
        description: Brief description of the tool's purpose
        version: Semantic version of the tool
        category: Classification for grouping tools in the UI
        wizard_step: Position in the wizard flow (None for utility tools)
        feature_flag: Config key that enables/disables this tool
        requires_auth: Whether authentication is required to use this tool
        dependencies: List of other tool IDs that must be available
        ui_entry: Where this tool should appear in the frontend
        frontend_component: Registered frontend component ID, if launchable
        standalone: Whether the tool can be opened without field-specific context
        requires_template: Whether the tool needs a selected template/schema
    """

    id: str
    name: str
    description: str
    version: str = "1.0.0"
    category: ToolCategory = "core"
    wizard_step: int | None = None
    feature_flag: str | None = None
    requires_auth: bool = False
    dependencies: list[str] = field(default_factory=list)
    ui_entry: ToolUiEntry | None = None
    frontend_component: str | None = None
    standalone: bool | None = None
    requires_template: bool = False

    @property
    def resolved_ui_entry(self) -> ToolUiEntry:
        """Return explicit UI placement, or infer a conservative default."""
        if self.ui_entry is not None:
            return self.ui_entry
        if self.wizard_step is not None:
            return "wizard"
        return "utility"

    @property
    def resolved_standalone(self) -> bool:
        """Return whether this tool is launchable as an independent panel."""
        if self.standalone is not None:
            return self.standalone
        return self.resolved_ui_entry in {"wizard", "utility"}

    @property
    def resolved_frontend_component(self) -> str | None:
        """Return the frontend component ID expected by the tool registry."""
        if self.frontend_component is not None:
            return self.frontend_component
        if self.resolved_ui_entry in {"wizard", "utility"}:
            return self.id
        return None

    def to_dict(self) -> dict:
        """Convert metadata to a dictionary for API responses."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "category": self.category,
            "wizard_step": self.wizard_step,
            "feature_flag": self.feature_flag,
            "requires_auth": self.requires_auth,
            "dependencies": self.dependencies,
            "ui_entry": self.resolved_ui_entry,
            "frontend_component": self.resolved_frontend_component,
            "standalone": self.resolved_standalone,
            "requires_template": self.requires_template,
        }


class BaseTool(ABC):
    """
    Abstract base class for all tools in the IDTA Submodel Editor.

    Tools encapsulate feature-specific functionality and integrate with the
    core pipeline through a standardized interface. Each tool provides:
    - Metadata for registration and discovery
    - Lifecycle hooks (initialize, shutdown)
    - Health checking
    - Optional FastAPI router for endpoints
    - Capability reporting

    Example:
        class MagicImportTool(BaseTool):
            metadata = ToolMetadata(
                id="magic-import",
                name="Magic Import",
                category="import",
                wizard_step=4,
                feature_flag="magic_import_enabled",
            )

            async def initialize(self) -> None:
                self._service = MagicImportService(...)

            async def health_check(self) -> tuple[bool, str | None]:
                return await self._service.check_llm_provider()

            def get_router(self) -> APIRouter | None:
                return magic_import_router
    """

    metadata: ClassVar[ToolMetadata]
    """Class-level metadata describing the tool."""

    def __init__(self, context: "ToolContext"):
        """
        Initialize the tool with shared context.

        Args:
            context: Shared tool context providing access to core services
        """
        self._context = context
        self._initialized = False

    @property
    def context(self) -> "ToolContext":
        """Get the shared tool context."""
        return self._context

    @property
    def is_initialized(self) -> bool:
        """Check if the tool has been initialized."""
        return self._initialized

    async def initialize(self) -> None:
        """
        Initialize the tool.

        Called once during application startup. Implementations should
        set up any resources, connections, or internal state needed.

        Override this method to add custom initialization logic.
        """
        self._initialized = True

    async def shutdown(self) -> None:
        """
        Shutdown the tool and clean up resources.

        Called during application shutdown. Implementations should
        release any resources, close connections, etc.

        Override this method to add custom cleanup logic.
        """
        self._initialized = False

    async def health_check(self) -> tuple[bool, str | None]:
        """
        Check if the tool is healthy and operational.

        Returns:
            Tuple of (is_healthy, error_message).
            If healthy, returns (True, None).
            If unhealthy, returns (False, "reason for failure").
        """
        return (True, None)

    def get_router(self) -> APIRouter | None:
        """
        Get the FastAPI router for this tool's endpoints.

        Returns:
            An APIRouter instance if the tool has endpoints, None otherwise.
        """
        return None

    def get_capabilities(self) -> dict:
        """
        Get the capabilities/features provided by this tool.

        Returns:
            Dictionary describing the tool's capabilities.
            Used by the frontend to determine available features.
        """
        return {}

    def is_enabled(self) -> bool:
        """
        Check if this tool is enabled based on configuration.

        If the tool has a feature_flag, checks the config setting.
        Tools without a feature_flag are always enabled.

        Returns:
            True if the tool is enabled, False otherwise.
        """
        flag = self.metadata.feature_flag
        if flag is None:
            return True
        return self._context.is_feature_enabled(flag)

    def get_disabled_reason(self, registry: "ToolRegistry | None" = None) -> str | None:
        """
        Return a human-readable reason why this tool is disabled.

        Args:
            registry: Optional registry for dependency-aware diagnostics.

        Returns:
            A short disabled reason when unavailable, otherwise None.
        """
        if self.is_enabled():
            # Enabled tools can still be unusable due to missing dependencies.
            if registry is not None:
                for dependency in self.metadata.dependencies:
                    dependency_tool = registry.get(dependency)
                    if dependency_tool is None:
                        return f"Dependency '{dependency}' is not installed."
                    if not dependency_tool.is_enabled():
                        return f"Dependency '{dependency}' is disabled."
                    if not dependency_tool.is_initialized:
                        return f"Dependency '{dependency}' is not initialized."
            return None

        if self.metadata.feature_flag:
            return (
                f"Feature flag '{self.metadata.feature_flag}' is disabled."
            )
        return "Tool is disabled by configuration."

    def to_manifest_entry(self) -> dict:
        """
        Convert the tool to a manifest entry for API responses.

        Returns:
            Dictionary with tool metadata and runtime status.
        """
        return {
            **self.metadata.to_dict(),
            "enabled": self.is_enabled(),
            "initialized": self.is_initialized,
        }
