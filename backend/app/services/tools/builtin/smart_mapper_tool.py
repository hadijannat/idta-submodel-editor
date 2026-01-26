"""
Smart Mapper tool wrapper.

Wraps the existing mapper service with the unified tool interface
for registry integration and lifecycle management.
"""

from __future__ import annotations

import logging
from typing import ClassVar

from fastapi import APIRouter

from app.services.tools.base import BaseTool, ToolMetadata

logger = logging.getLogger(__name__)


class SmartMapperTool(BaseTool):
    """
    Tool for CSV/XLSX bulk import with intelligent column mapping.

    Provides:
    - CSV/XLSX file parsing with column profiling
    - Semantic-aware auto-mapping suggestions
    - Transformation options for data normalization
    - Recipe persistence for reusable mappings
    """

    metadata: ClassVar[ToolMetadata] = ToolMetadata(
        id="smart-mapper",
        name="Smart Mapper",
        description="Import and map CSV/XLSX data to template fields",
        version="1.0.0",
        category="import",
        wizard_step=3,
        feature_flag=None,  # Always enabled
        requires_auth=False,
        dependencies=[],
    )

    def __init__(self, context):
        super().__init__(context)
        self._service = None

    async def initialize(self) -> None:
        """Initialize the Smart Mapper tool."""
        from app.services.mapper.service import MapperService
        from app.dependencies import (
            get_fetcher,
            get_parser,
            get_hydrator,
            get_pdf_service,
            get_semantic_service,
        )

        self._service = MapperService(
            fetcher=get_fetcher(),
            parser=get_parser(),
            hydrator=get_hydrator(),
            pdf_service=get_pdf_service(),
            semantic_service=get_semantic_service(),
        )

        await super().initialize()
        logger.info("Smart Mapper tool initialized")

    async def shutdown(self) -> None:
        """Shutdown the Smart Mapper tool."""
        self._service = None
        await super().shutdown()
        logger.info("Smart Mapper tool shut down")

    async def health_check(self) -> tuple[bool, str | None]:
        """Check if the Smart Mapper tool is healthy."""
        if self._service is None:
            return (False, "Service not initialized")

        # Check cache directory is accessible
        from app.config import get_settings

        settings = get_settings()
        if not settings.mapper_cache_dir.exists():
            return (False, "Mapper cache directory not accessible")

        return (True, None)

    def get_router(self) -> APIRouter | None:
        """Get the Smart Mapper API router."""
        from app.routers import mapper

        return mapper.router

    def get_capabilities(self) -> dict:
        """Get Smart Mapper capabilities."""
        return {
            "supported_formats": ["csv", "xlsx", "xls"],
            "auto_mapping": True,
            "recipe_persistence": True,
            "semantic_matching": True,
        }


# Auto-discovery marker
tool_class = SmartMapperTool
