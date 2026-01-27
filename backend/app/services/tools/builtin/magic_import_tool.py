"""
Magic Import tool wrapper.

Wraps the existing magic_import service with the unified tool interface
for registry integration and lifecycle management.
"""

from __future__ import annotations

import logging
from typing import ClassVar

from fastapi import APIRouter

from app.services.tools.base import BaseTool, ToolMetadata

logger = logging.getLogger(__name__)


class MagicImportTool(BaseTool):
    """
    Tool for extracting data from PDF datasheets using LLM-powered extraction.

    Magic Import uses:
    - PDF indexing with text extraction and OCR fallback
    - Schema-aware target field resolution
    - Multi-provider LLM extraction (OpenAI, Anthropic, Local)
    - Evidence localization for source highlighting
    - Confidence scoring for human review
    """

    metadata: ClassVar[ToolMetadata] = ToolMetadata(
        id="magic-import",
        name="Magic Import",
        description="Extract fields from PDF datasheets using LLM-powered extraction",
        version="1.0.0",
        category="import",
        wizard_step=4,
        feature_flag="magic_import_enabled",
        requires_auth=False,
        dependencies=[],
    )

    def __init__(self, context):
        super().__init__(context)
        self._job_manager = None

    async def initialize(self) -> None:
        """Initialize the Magic Import tool."""
        if not self.is_enabled():
            logger.info("Magic Import tool is disabled, skipping initialization")
            return

        from app.services.magic_import.job_manager import JobManager

        self._job_manager = JobManager()

        await super().initialize()
        logger.info("Magic Import tool initialized")

    async def shutdown(self) -> None:
        """Shutdown the Magic Import tool."""
        self._job_manager = None
        await super().shutdown()
        logger.info("Magic Import tool shut down")

    async def health_check(self) -> tuple[bool, str | None]:
        """
        Check if the Magic Import tool is healthy.

        Verifies:
        - LLM provider is configured and accessible
        - Cache directory is writable
        """
        if not self.is_enabled():
            return (True, "Tool is disabled")

        # Check LLM provider availability
        try:
            from app.services.magic_import.llm.factory import get_provider
            from app.services import settings_service

            provider = get_provider()
            if not provider.is_available():
                llm_provider = settings_service.get_effective_provider()
                return (False, f"{llm_provider.title()} not configured")

            return (True, None)

        except Exception as e:
            return (False, f"Health check failed: {e}")

    def get_router(self) -> APIRouter | None:
        """Get the Magic Import API router."""
        if not self.is_enabled():
            return None

        from app.routers import magic_import

        return magic_import.router

    def get_capabilities(self) -> dict:
        """Get Magic Import capabilities."""
        from app.config import get_settings
        from app.services import settings_service

        settings = get_settings()
        llm_settings = (
            settings_service.load_llm_settings()
            if settings_service.has_llm_settings()
            else None
        )
        active_provider = settings_service.get_effective_provider()
        active_model = settings_service.get_effective_model(active_provider)
        confidence_threshold = (
            llm_settings.confidence_threshold
            if llm_settings is not None
            else settings.magic_import_confidence_threshold
        )
        ocr_enabled = (
            llm_settings.ocr_enabled
            if llm_settings is not None
            else settings.magic_import_ocr_enabled
        )

        return {
            "llm_provider": active_provider,
            "llm_model": active_model,
            "ocr_enabled": ocr_enabled,
            "max_pdf_size_mb": settings.magic_import_max_pdf_size_mb,
            "confidence_threshold": confidence_threshold,
            "supported_formats": ["pdf"],
        }


# Auto-discovery marker
tool_class = MagicImportTool
