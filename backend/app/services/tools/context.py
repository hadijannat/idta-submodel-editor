"""
Shared context for tools in the IDTA Submodel Editor.

Provides tools with access to core services (fetcher, parser, hydrator,
validator) and shared utilities like cache directories and feature flags.
"""

from __future__ import annotations

from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING

from app.config import Settings, get_settings

if TYPE_CHECKING:
    from app.services.fetcher import TemplateFetcherService
    from app.services.hydrator import HydratorService
    from app.services.parser import ParserService
    from app.services.validation import ValidationService


class ToolContext:
    """
    Shared context providing tools with access to core services.

    This class provides a centralized way for tools to access:
    - Core pipeline services (fetcher, parser, hydrator, validator)
    - Cache directory management
    - Feature flag checking
    - Configuration settings

    The context is created once and shared across all tools during
    the application lifecycle.

    Example:
        context = ToolContext()

        # Access core services
        schema = await context.parser.parse(template)

        # Get tool-specific cache directory
        cache_dir = context.get_cache_dir("magic-import")

        # Check feature flags
        if context.is_feature_enabled("dataspace_enabled"):
            ...
    """

    def __init__(self, settings: Settings | None = None):
        """
        Initialize the tool context.

        Args:
            settings: Application settings. If None, uses get_settings().
        """
        self._settings = settings or get_settings()
        self._fetcher: TemplateFetcherService | None = None
        self._parser: ParserService | None = None
        self._hydrator: HydratorService | None = None
        self._validator: ValidationService | None = None

    @property
    def settings(self) -> Settings:
        """Get application settings."""
        return self._settings

    @cached_property
    def fetcher(self) -> "TemplateFetcherService":
        """
        Get the template fetcher service.

        Lazy-loaded on first access to avoid circular imports.
        """
        if self._fetcher is None:
            from app.services.fetcher import TemplateFetcherService

            self._fetcher = TemplateFetcherService(
                github_token=self._settings.github_token,
                cache_dir=self._settings.cache_dir,
                cache_ttl_hours=self._settings.cache_ttl_hours,
            )
        return self._fetcher

    @cached_property
    def parser(self) -> "ParserService":
        """
        Get the parser service.

        Lazy-loaded on first access to avoid circular imports.
        """
        if self._parser is None:
            from app.services.parser import ParserService

            self._parser = ParserService()
        return self._parser

    @cached_property
    def hydrator(self) -> "HydratorService":
        """
        Get the hydrator service.

        Lazy-loaded on first access to avoid circular imports.
        """
        if self._hydrator is None:
            from app.services.hydrator import HydratorService

            self._hydrator = HydratorService()
        return self._hydrator

    @cached_property
    def validator(self) -> "ValidationService":
        """
        Get the validation service.

        Lazy-loaded on first access to avoid circular imports.
        """
        if self._validator is None:
            from app.services.validation import ValidationService

            self._validator = ValidationService()
        return self._validator

    def get_cache_dir(self, tool_id: str) -> Path:
        """
        Get a cache directory for a specific tool.

        Creates the directory if it doesn't exist.

        Args:
            tool_id: The tool's unique identifier

        Returns:
            Path to the tool's cache directory
        """
        cache_dir = self._settings.cache_dir / "tools" / tool_id
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    def is_feature_enabled(self, flag: str) -> bool:
        """
        Check if a feature flag is enabled.

        Looks up the flag name as an attribute on settings.
        If the attribute doesn't exist, returns True (enabled by default).

        Args:
            flag: Name of the feature flag (e.g., "magic_import_enabled")

        Returns:
            True if the feature is enabled, False otherwise
        """
        from app.services import settings_service

        return settings_service.get_effective_feature_flag(flag, settings=self._settings)

    def get_setting(self, name: str, default: object = None) -> object:
        """
        Get a configuration setting by name.

        Args:
            name: Name of the setting
            default: Default value if setting doesn't exist

        Returns:
            The setting value or the default
        """
        return getattr(self._settings, name, default)


# Global context instance (initialized during app startup)
_context: ToolContext | None = None


def get_tool_context() -> ToolContext:
    """
    Get the global tool context.

    Returns:
        The shared ToolContext instance

    Raises:
        RuntimeError: If the context hasn't been initialized
    """
    global _context
    if _context is None:
        _context = ToolContext()
    return _context


def initialize_tool_context(settings: Settings | None = None) -> ToolContext:
    """
    Initialize the global tool context.

    Called during application startup to create the shared context.

    Args:
        settings: Optional settings instance

    Returns:
        The initialized ToolContext
    """
    global _context
    _context = ToolContext(settings)
    return _context
