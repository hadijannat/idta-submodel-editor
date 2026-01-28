"""
DPP Builder tool wrapper.

Wraps the DPP Builder service with the unified tool interface
for registry integration and lifecycle management.

Provides Digital Product Passport assembly and validation
for EU ESPR (Ecodesign for Sustainable Products Regulation) compliance.
"""

from __future__ import annotations

import logging
from typing import ClassVar

from fastapi import APIRouter

from app.services.tools.base import BaseTool, ToolMetadata

logger = logging.getLogger(__name__)


class DPPBuilderTool(BaseTool):
    """
    Tool for assembling Digital Product Passports.

    Provides:
    - DPP package creation and management
    - Multi-submodel assembly with role assignment
    - EU ESPR compliance validation
    - Export to AASX/JSON formats
    - Dataspace publication integration
    """

    metadata: ClassVar[ToolMetadata] = ToolMetadata(
        id="dpp-builder",
        name="DPP Builder",
        description="Assemble Digital Product Passports for EU ESPR compliance",
        version="1.0.0",
        category="export",
        wizard_step=8,  # After dataspace connector
        feature_flag="dpp_enabled",
        requires_auth=False,
        dependencies=["export-panel"],  # Requires export capability
    )

    def __init__(self, context):
        super().__init__(context)
        self._builder = None

    async def initialize(self) -> None:
        """Initialize the DPP Builder tool."""
        from app.services.dpp.builder import DPPBuilder
        from app.services.fetcher import TemplateFetcherService
        from app.services.parser import ParserService
        from app.services.hydrator import HydratorService

        # Initialize builder with dependencies
        self._builder = DPPBuilder(
            fetcher=TemplateFetcherService(),
            parser=ParserService(),
            hydrator=HydratorService(),
        )

        await super().initialize()
        logger.info("DPP Builder tool initialized")

    async def shutdown(self) -> None:
        """Shutdown the DPP Builder tool."""
        self._builder = None
        await super().shutdown()
        logger.info("DPP Builder tool shut down")

    async def health_check(self) -> tuple[bool, str | None]:
        """Check if the DPP Builder tool is healthy."""
        if self._builder is None:
            return (False, "DPP Builder service not initialized")

        return (True, None)

    def get_router(self) -> APIRouter | None:
        """Get the DPP Builder API router."""
        from app.routers import dpp

        return dpp.router

    def get_capabilities(self) -> dict:
        """Get DPP Builder capabilities."""
        from app.config import get_settings

        settings = get_settings()

        return {
            "package_management": True,
            "submodel_assembly": True,
            "espr_validation": True,
            "json_export": True,
            "aasx_export": True,
            "dataspace_publish": settings.dataspace_enabled,
            "compliance_levels": [
                "full",
                "partial",
                "minimal",
                "non_compliant",
            ],
            "supported_roles": [
                "identification",
                "sustainability",
                "technical",
                "documentation",
            ],
        }


# Auto-discovery marker
tool_class = DPPBuilderTool
