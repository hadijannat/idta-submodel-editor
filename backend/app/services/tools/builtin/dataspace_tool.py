"""
Dataspace Connector tool wrapper.

Wraps the existing dataspace service with the unified tool interface
for registry integration and lifecycle management.
"""

from __future__ import annotations

import logging
from typing import ClassVar

from fastapi import APIRouter

from app.services.tools.base import BaseTool, ToolMetadata

logger = logging.getLogger(__name__)


class DataspaceConnectorTool(BaseTool):
    """
    Tool for Manufacturing-X / Catena-X dataspace integration.

    Provides:
    - Connection lifecycle management (create/connect/disconnect)
    - Submodel publication to BaSyx/DTR/EDC
    - ODRL policy management with Catena-X profile
    - Health monitoring of dataspace components
    """

    metadata: ClassVar[ToolMetadata] = ToolMetadata(
        id="dataspace-connector",
        name="Dataspace Connector",
        description="Publish submodels to Manufacturing-X/Catena-X dataspaces",
        version="1.0.0",
        category="integration",
        wizard_step=7,
        feature_flag="dataspace_enabled",
        requires_auth=False,
        dependencies=[],
    )

    def __init__(self, context):
        super().__init__(context)
        self._connection_manager = None

    async def initialize(self) -> None:
        """Initialize the Dataspace Connector tool."""
        if not self.is_enabled():
            logger.info("Dataspace Connector tool is disabled, skipping initialization")
            return

        from app.services.dataspace.connection_manager import ConnectionManager

        cache_dir = self._context.get_cache_dir("dataspace")
        self._connection_manager = ConnectionManager(cache_dir=cache_dir)

        await super().initialize()
        logger.info("Dataspace Connector tool initialized")

    async def shutdown(self) -> None:
        """Shutdown the Dataspace Connector tool."""
        self._connection_manager = None
        await super().shutdown()
        logger.info("Dataspace Connector tool shut down")

    async def health_check(self) -> tuple[bool, str | None]:
        """
        Check if the Dataspace Connector tool is healthy.

        Verifies basic configuration is in place.
        """
        if not self.is_enabled():
            return (True, "Tool is disabled")

        from app.config import get_settings

        settings = get_settings()

        # Check basic configuration
        if not settings.basyx_aas_server_url:
            return (False, "BaSyx AAS Server URL not configured")

        return (True, None)

    def get_router(self) -> APIRouter | None:
        """Get the Dataspace Connector API router."""
        if not self.is_enabled():
            return None

        from app.routers import dataspace

        return dataspace.router

    def get_capabilities(self) -> dict:
        """Get Dataspace Connector capabilities."""
        from app.config import get_settings

        settings = get_settings()

        return {
            "default_environment": settings.dataspace_default_environment,
            "default_edc_mode": settings.dataspace_default_edc_mode,
            "basyx_enabled": bool(settings.basyx_aas_server_url),
            "dtr_enabled": bool(settings.dtr_url),
            "edc_tractus_x_enabled": bool(settings.edc_control_plane_url),
            "edc_aas_extension_enabled": bool(settings.edc_aas_extension_url),
            "vault_enabled": bool(settings.vault_url and settings.vault_token),
            "plc4x_bridge_enabled": settings.plc4x_bridge_enabled,
        }


# Auto-discovery marker
tool_class = DataspaceConnectorTool
