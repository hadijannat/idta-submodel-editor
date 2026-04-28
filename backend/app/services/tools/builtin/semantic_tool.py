"""
Semantic dictionary lookup tool wrapper.

Wraps the existing semantic service with the unified tool interface
for registry integration and lifecycle management.
"""

from __future__ import annotations

import logging
from typing import ClassVar

from fastapi import APIRouter

from app.services.tools.base import BaseTool, ToolMetadata

logger = logging.getLogger(__name__)


class SemanticTool(BaseTool):
    """
    Tool for semantic dictionary lookup (ECLASS, IEC CDD).

    Provides:
    - Search across ECLASS and IEC CDD dictionaries
    - Resolve semantic IDs to concept descriptions
    - Offline indices for fast lookup
    - Optional online ECLASS webservice with mTLS
    """

    metadata: ClassVar[ToolMetadata] = ToolMetadata(
        id="semantic",
        name="Semantic Lookup",
        description="Search and resolve semantic dictionary entries (ECLASS, IEC CDD)",
        version="1.0.0",
        category="core",
        wizard_step=None,  # Utility tool, not a wizard step
        feature_flag="semantic_enabled",
        requires_auth=False,
        dependencies=[],
        ui_entry="field_action",
        frontend_component=None,
        standalone=False,
        requires_template=True,
    )

    def __init__(self, context):
        super().__init__(context)
        self._service = None

    async def initialize(self) -> None:
        """Initialize the Semantic tool."""
        if not self.is_enabled():
            logger.info("Semantic tool is disabled, skipping initialization")
            return

        from app.services.semantic.service import SemanticService

        self._service = SemanticService()

        await super().initialize()
        logger.info("Semantic tool initialized")

    async def shutdown(self) -> None:
        """Shutdown the Semantic tool."""
        self._service = None
        await super().shutdown()
        logger.info("Semantic tool shut down")

    async def health_check(self) -> tuple[bool, str | None]:
        """
        Check if the Semantic tool is healthy.

        Verifies at least one provider is available.
        """
        if not self.is_enabled():
            return (True, "Tool is disabled")

        if self._service is None:
            return (False, "Service not initialized")

        try:
            providers = self._service.providers_info()
            available = [p for p in providers if p.status == "ready"]
            if not available:
                return (False, "No semantic providers available")
            return (True, None)
        except Exception as e:
            return (False, f"Health check failed: {e}")

    def get_router(self) -> APIRouter | None:
        """Get the Semantic API router."""
        if not self.is_enabled():
            return None

        from app.routers import semantic

        return semantic.router

    def get_capabilities(self) -> dict:
        """Get Semantic capabilities."""
        from app.config import get_settings

        settings = get_settings()

        return {
            "eclass_offline_enabled": settings.semantic_eclass_offline_enabled,
            "iec_cdd_offline_enabled": settings.semantic_iec_cdd_offline_enabled,
            "eclass_online_enabled": settings.semantic_eclass_online_enabled,
            "cache_ttl_seconds": settings.semantic_cache_ttl_seconds,
        }


# Auto-discovery marker
tool_class = SemanticTool
