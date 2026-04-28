"""
PCF (Product Carbon Footprint) tools wrapper.

Wraps the existing PCF service with the unified tool interface
for registry integration and lifecycle management.
"""

from __future__ import annotations

import logging
from typing import ClassVar

from fastapi import APIRouter

from app.services.tools.base import BaseTool, ToolMetadata

logger = logging.getLogger(__name__)


class PCFTool(BaseTool):
    """
    Tool for Product Carbon Footprint calculation and validation.

    Provides:
    - CO₂e calculation with emission factor database
    - IDTA 02023 compliance validation
    - Activity list injection for PCF submodels
    - Emission factor lookup
    """

    metadata: ClassVar[ToolMetadata] = ToolMetadata(
        id="pcf-tools",
        name="PCF Tools",
        description="Carbon Footprint Calculator & Validator for IDTA 02023 compliance",
        version="1.0.0",
        category="analytics",
        wizard_step=None,  # Integrated into step 5 when PCF template detected
        feature_flag=None,  # Always enabled
        requires_auth=False,
        dependencies=[],
        ui_entry="utility",
        frontend_component="pcf-tools",
        standalone=True,
        requires_template=True,
    )

    async def initialize(self) -> None:
        """Initialize the PCF tool."""
        # PCF tools are stateless, no initialization needed
        await super().initialize()
        logger.info("PCF tool initialized")

    async def shutdown(self) -> None:
        """Shutdown the PCF tool."""
        await super().shutdown()
        logger.info("PCF tool shut down")

    async def health_check(self) -> tuple[bool, str | None]:
        """Check if the PCF tool is healthy."""
        try:
            # Verify emission factors database is loadable
            from app.services.pcf.emission_factors import get_emission_factors_metadata

            metadata = get_emission_factors_metadata()
            if metadata.get("count", 0) <= 0:
                return (False, "Emission factors database is empty")
            return (True, None)
        except Exception as e:
            return (False, f"Health check failed: {e}")

    def get_router(self) -> APIRouter | None:
        """Get the PCF API router."""
        from app.routers import pcf

        return pcf.router

    def get_capabilities(self) -> dict:
        """Get PCF capabilities."""
        try:
            from app.services.pcf.emission_factors import get_emission_factors_metadata

            metadata = get_emission_factors_metadata()
            factor_count = int(metadata.get("count", 0))
        except Exception:
            factor_count = 0

        return {
            "co2e_calculation": True,
            "idta_02023_validation": True,
            "activity_list_injection": True,
            "emission_factor_count": factor_count,
        }


# Auto-discovery marker
tool_class = PCFTool
