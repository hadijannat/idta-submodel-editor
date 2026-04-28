"""
OPC UA Bridge tool wrapper.

Wraps the OPC UA Bridge service with the unified tool interface
for registry integration and lifecycle management.

Provides bidirectional import/export between OPC UA NodeSet2.xml
and AAS (Asset Administration Shell) structures.
"""

from __future__ import annotations

import logging
from typing import ClassVar

from fastapi import APIRouter

from app.services.tools.base import BaseTool, ToolMetadata

logger = logging.getLogger(__name__)


class OPCUABridgeTool(BaseTool):
    """
    Tool for OPC UA ↔ AAS bridging.

    Provides:
    - OPC UA → AAS: Import NodeSet2.xml files
    - AAS → OPC UA: Export to NodeSet2.xml
    - Type mapping between OPC UA and AAS
    """

    metadata: ClassVar[ToolMetadata] = ToolMetadata(
        id="opcua-bridge",
        name="OPC UA Bridge",
        description="Import/export between OPC UA NodeSet and AAS formats",
        version="1.0.0",
        category="integration",
        wizard_step=None,  # Utility tool
        feature_flag="opcua_bridge_enabled",
        requires_auth=False,
        dependencies=[],
        ui_entry="api_only",
        frontend_component=None,
        standalone=False,
    )

    def __init__(self, context):
        super().__init__(context)
        self._importer = None
        self._exporter = None

    async def initialize(self) -> None:
        """Initialize the OPC UA Bridge tool."""
        from app.services.opcua.importer import NodeSetImporter
        from app.services.opcua.exporter import NodeSetExporter
        from app.config import get_settings

        settings = get_settings()

        self._importer = NodeSetImporter()
        self._exporter = NodeSetExporter(
            namespace_uri=settings.opcua_default_namespace
        )

        await super().initialize()
        logger.info("OPC UA Bridge tool initialized")

    async def shutdown(self) -> None:
        """Shutdown the OPC UA Bridge tool."""
        self._importer = None
        self._exporter = None
        await super().shutdown()
        logger.info("OPC UA Bridge tool shut down")

    async def health_check(self) -> tuple[bool, str | None]:
        """Check if the OPC UA Bridge tool is healthy."""
        if self._importer is None or self._exporter is None:
            return (False, "OPC UA Bridge not initialized")

        return (True, None)

    def get_router(self) -> APIRouter | None:
        """Get the OPC UA Bridge API router."""
        from app.routers import opcua

        return opcua.router

    def get_capabilities(self) -> dict:
        """Get OPC UA Bridge capabilities."""
        return {
            "import_nodeset": True,
            "export_nodeset": True,
            "supported_opcua_types": [
                "Boolean",
                "SByte",
                "Byte",
                "Int16",
                "UInt16",
                "Int32",
                "UInt32",
                "Int64",
                "UInt64",
                "Float",
                "Double",
                "String",
                "DateTime",
                "ByteString",
                "LocalizedText",
            ],
            "supported_node_classes": [
                "ObjectType",
                "Object",
                "Variable",
                "Method",
            ],
            "i4aas_companion_spec": True,
        }


# Auto-discovery marker
tool_class = OPCUABridgeTool
