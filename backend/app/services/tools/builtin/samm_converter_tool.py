"""
SAMM Converter tool wrapper.

Wraps the SAMM Converter service with the unified tool interface
for registry integration and lifecycle management.

Provides bidirectional conversion between Catena-X SAMM models
and AAS (Asset Administration Shell) structures.
"""

from __future__ import annotations

import logging
from importlib.util import find_spec
from typing import ClassVar

from fastapi import APIRouter

from app.services.tools.base import BaseTool, ToolMetadata

logger = logging.getLogger(__name__)


class SAMMConverterTool(BaseTool):
    """
    Tool for SAMM ↔ AAS conversion.

    Provides:
    - SAMM → AAS: Import Catena-X Aspect Models
    - AAS → SAMM: Export to Catena-X ecosystem
    - Type mapping between SAMM and AAS
    """

    metadata: ClassVar[ToolMetadata] = ToolMetadata(
        id="samm-converter",
        name="SAMM Converter",
        description="Convert between Catena-X SAMM and AAS formats",
        version="1.0.0",
        category="integration",
        wizard_step=None,  # Utility tool
        feature_flag="samm_enabled",
        requires_auth=False,
        dependencies=[],
        ui_entry="api_only",
        frontend_component=None,
        standalone=False,
    )

    def __init__(self, context):
        super().__init__(context)
        self._converter = None

    async def initialize(self) -> None:
        """Initialize the SAMM Converter tool."""
        from app.services.samm.converter import SAMMConverter
        from app.services.fetcher import TemplateFetcherService
        from app.services.parser import ParserService
        from app.config import get_settings

        settings = get_settings()

        self._converter = SAMMConverter(
            fetcher=TemplateFetcherService(),
            parser=ParserService(),
            namespace=settings.samm_default_namespace,
        )

        await super().initialize()
        logger.info("SAMM Converter tool initialized")

    async def shutdown(self) -> None:
        """Shutdown the SAMM Converter tool."""
        self._converter = None
        await super().shutdown()
        logger.info("SAMM Converter tool shut down")

    async def health_check(self) -> tuple[bool, str | None]:
        """Check if the SAMM Converter tool is healthy."""
        if self._converter is None:
            return (False, "SAMM Converter not initialized")

        return (True, None)

    def get_router(self) -> APIRouter | None:
        """Get the SAMM Converter API router."""
        from app.routers import samm

        return samm.router

    def get_capabilities(self) -> dict:
        """Get SAMM Converter capabilities."""
        rdflib_available = find_spec("rdflib") is not None

        return {
            "import_ttl": True,
            "import_json_ld": True,
            "export_ttl": True,
            "rdflib_available": rdflib_available,
            "supported_samm_versions": ["2.0.0", "2.1.0"],
            "type_mapping": True,
        }


# Auto-discovery marker
tool_class = SAMMConverterTool
