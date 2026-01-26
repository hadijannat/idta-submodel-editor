"""
Export Panel tool wrapper.

Wraps the existing export functionality with the unified tool interface
for registry integration and lifecycle management.
"""

from __future__ import annotations

import logging
from typing import ClassVar

from fastapi import APIRouter

from app.services.tools.base import BaseTool, ToolMetadata

logger = logging.getLogger(__name__)


class ExportTool(BaseTool):
    """
    Tool for exporting submodels to various formats.

    Provides:
    - AASX package export (conformant to IDTA specs)
    - JSON export (AAS JSON serialization)
    - PDF export (human-readable documentation)
    - Export verification against aas-test-engines
    """

    metadata: ClassVar[ToolMetadata] = ToolMetadata(
        id="export-panel",
        name="Export Panel",
        description="Export submodels to AASX, JSON, and PDF formats",
        version="1.0.0",
        category="export",
        wizard_step=6,
        feature_flag=None,  # Always enabled
        requires_auth=False,
        dependencies=[],
    )

    def __init__(self, context):
        super().__init__(context)
        self._hydrator = None
        self._pdf_service = None

    async def initialize(self) -> None:
        """Initialize the Export tool."""
        from app.services.hydrator import HydratorService, PDFExportService
        from app.config import get_settings

        self._hydrator = HydratorService()

        settings = get_settings()
        if settings.pdf_enabled:
            try:
                self._pdf_service = PDFExportService()
            except ImportError:
                logger.warning("PDF export dependencies not available")
                self._pdf_service = None

        await super().initialize()
        logger.info("Export tool initialized")

    async def shutdown(self) -> None:
        """Shutdown the Export tool."""
        self._hydrator = None
        self._pdf_service = None
        await super().shutdown()
        logger.info("Export tool shut down")

    async def health_check(self) -> tuple[bool, str | None]:
        """Check if the Export tool is healthy."""
        if self._hydrator is None:
            return (False, "Hydrator service not initialized")

        return (True, None)

    def get_router(self) -> APIRouter | None:
        """Get the Export API router."""
        from app.routers import export

        return export.router

    def get_capabilities(self) -> dict:
        """Get Export capabilities."""
        from app.config import get_settings

        settings = get_settings()

        return {
            "aasx_export": True,
            "json_export": True,
            "pdf_export": settings.pdf_enabled and self._pdf_service is not None,
            "verification": True,
        }


# Auto-discovery marker
tool_class = ExportTool
