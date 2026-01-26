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

        cache_dir = self._context.get_cache_dir("magic-import")
        self._job_manager = JobManager(cache_dir=cache_dir)

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
            from app.services.magic_import.llm.factory import get_llm_provider

            provider = get_llm_provider()
            if provider is None:
                return (False, "No LLM provider configured")

            # Check if API key is set for cloud providers
            from app.config import get_settings

            settings = get_settings()
            llm_provider = settings.magic_import_llm_provider

            if llm_provider == "openai" and not settings.openai_api_key:
                return (False, "OpenAI API key not configured")
            elif llm_provider == "anthropic" and not settings.anthropic_api_key:
                return (False, "Anthropic API key not configured")

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

        settings = get_settings()

        return {
            "llm_provider": settings.magic_import_llm_provider,
            "llm_model": settings.magic_import_llm_model,
            "ocr_enabled": settings.magic_import_ocr_enabled,
            "max_pdf_size_mb": settings.magic_import_max_pdf_size_mb,
            "confidence_threshold": settings.magic_import_confidence_threshold,
            "supported_formats": ["pdf"],
        }


# Auto-discovery marker
tool_class = MagicImportTool
