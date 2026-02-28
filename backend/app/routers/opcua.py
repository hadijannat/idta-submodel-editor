"""
OPC UA Bridge API endpoints.

Provides bidirectional import/export between OPC UA NodeSet2.xml
and AAS (Asset Administration Shell) structures.
"""

from __future__ import annotations

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from app.config import get_settings
from app.dependencies import get_current_user, get_fetcher, get_parser
from app.errors import APIError, ErrorCode
from app.services.fetcher import TemplateFetcherService
from app.services.opcua.exporter import NodeSetExporter
from app.services.opcua.importer import NodeSetImporter
from app.services.opcua.type_mapper import (
    OPCUA_TO_AAS_TYPE_MAP,
    AAS_TO_OPCUA_TYPE_MAP,
    NODECLASS_TO_AAS_MAP,
    AAS_TO_NODECLASS_MAP,
)
from app.services.parser import ParserService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/opcua", tags=["opcua"])
PYDANTIC_PROTECTED_NAMESPACES = ("model_validate", "model_dump")


# ============================================================================
# NodeSet → AAS Import
# ============================================================================


class NodeSetImportRequest(BaseModel):
    """Request to import a NodeSet2.xml file."""

    content: str = Field(description="NodeSet2 XML content")
    root_node_id: str | None = Field(
        default=None, description="Optional NodeId to use as template root"
    )


class NodeSetImportResponse(BaseModel):
    """Response from NodeSet import."""

    success: bool
    template: dict | None = Field(default=None, description="Generated AAS template")
    ui_schema: dict | None = Field(default=None, description="Generated UI schema")
    warnings: list[str] = Field(default_factory=list)
    node_count: int = Field(default=0, description="Number of nodes processed")
    source_namespace: str | None = Field(default=None)


@router.post("/import", response_model=NodeSetImportResponse)
async def import_nodeset(
    request: NodeSetImportRequest,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> NodeSetImportResponse:
    """
    Import OPC UA NodeSet2.xml and convert to AAS structure.

    Converts OPC UA information model to:
    - AAS template structure (SubmodelElements)
    - UI schema for form rendering

    This enables editing OPC UA data structures using the IDTA editor.
    """
    settings = get_settings()
    if not settings.opcua_bridge_enabled:
        raise APIError(
            code=ErrorCode.FEATURE_DISABLED,
            message="OPC UA Bridge is disabled",
        )

    try:
        importer = NodeSetImporter()
        result = importer.import_nodeset(
            request.content, root_node_id=request.root_node_id
        )

        if not result.success:
            raise APIError(
                code=ErrorCode.BAD_REQUEST,
                message="NodeSet import failed",
                detail={"warnings": result.warnings},
            )

        return NodeSetImportResponse(
            success=result.success,
            template=result.template,
            ui_schema=result.ui_schema,
            warnings=result.warnings,
            node_count=result.node_count,
            source_namespace=result.source_namespace,
        )

    except APIError:
        raise
    except Exception as e:
        logger.exception("NodeSet import failed")
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to import NodeSet",
            detail={"error": str(e)},
        )


@router.post("/import/file", response_model=NodeSetImportResponse)
async def import_nodeset_file(
    file: Annotated[UploadFile, File(description="NodeSet2.xml file")],
    root_node_id: Annotated[
        str | None, Form(description="Optional root NodeId")
    ] = None,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> NodeSetImportResponse:
    """
    Import OPC UA NodeSet2.xml from an uploaded file.

    Supports .xml files in OPC UA NodeSet2 format.
    """
    settings = get_settings()
    if not settings.opcua_bridge_enabled:
        raise APIError(
            code=ErrorCode.FEATURE_DISABLED,
            message="OPC UA Bridge is disabled",
        )

    # Validate file extension
    filename = file.filename or ""
    if not filename.endswith(".xml"):
        raise APIError(
            code=ErrorCode.BAD_REQUEST,
            message="Unsupported file format. Use .xml (NodeSet2 format)",
        )

    try:
        content = await file.read()
        importer = NodeSetImporter()
        result = importer.import_nodeset(content, root_node_id=root_node_id)

        if not result.success:
            raise APIError(
                code=ErrorCode.BAD_REQUEST,
                message="NodeSet import failed",
                detail={"warnings": result.warnings},
            )

        return NodeSetImportResponse(
            success=result.success,
            template=result.template,
            ui_schema=result.ui_schema,
            warnings=result.warnings,
            node_count=result.node_count,
            source_namespace=result.source_namespace,
        )

    except APIError:
        raise
    except Exception as e:
        logger.exception("NodeSet file import failed")
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to import NodeSet file",
            detail={"error": str(e)},
        )


# ============================================================================
# AAS → NodeSet Export
# ============================================================================


class NodeSetExportRequest(BaseModel):
    """Request to export AAS template as NodeSet."""

    model_config = ConfigDict(protected_namespaces=PYDANTIC_PROTECTED_NAMESPACES)

    template_name: str = Field(description="AAS template name")
    template_status: Literal["published", "deprecated"] = Field(default="published")
    template_version: str | None = Field(default=None)
    namespace_uri: str | None = Field(
        default=None, description="Custom namespace URI for generated model"
    )
    model_version: str = Field(
        default="1.0.0", description="Version for generated NodeSet model"
    )


class NodeSetExportResponse(BaseModel):
    """Response from NodeSet export."""

    success: bool
    nodeset_xml: str | None = Field(default=None, description="Generated NodeSet XML")
    warnings: list[str] = Field(default_factory=list)
    node_count: int = Field(default=0, description="Number of nodes generated")
    namespace_uri: str | None = Field(default=None)


@router.post("/export", response_model=NodeSetExportResponse)
async def export_to_nodeset(
    request: NodeSetExportRequest,
    fetcher: Annotated[TemplateFetcherService, Depends(get_fetcher)],
    parser: Annotated[ParserService, Depends(get_parser)],
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> NodeSetExportResponse:
    """
    Export an AAS template as OPC UA NodeSet2.xml.

    Converts IDTA submodel template to OPC UA information model.
    This enables integrating AAS structures with OPC UA systems.
    """
    settings = get_settings()
    if not settings.opcua_bridge_enabled:
        raise APIError(
            code=ErrorCode.FEATURE_DISABLED,
            message="OPC UA Bridge is disabled",
        )

    try:
        # Fetch the template
        template_content = await fetcher.get_template(
            request.template_name,
            status=request.template_status,
            version=request.template_version,
        )

        if template_content is None:
            raise APIError(
                code=ErrorCode.NOT_FOUND,
                message=f"Template '{request.template_name}' not found",
            )

        # Parse to get UI schema
        ui_schema = await parser.parse(template_content)

        # Export to NodeSet
        exporter = NodeSetExporter(namespace_uri=request.namespace_uri)
        result = exporter.export_template(ui_schema, version=request.model_version)

        if not result.success:
            raise APIError(
                code=ErrorCode.BAD_REQUEST,
                message="NodeSet export failed",
                detail={"warnings": result.warnings},
            )

        return NodeSetExportResponse(
            success=result.success,
            nodeset_xml=result.nodeset_xml,
            warnings=result.warnings,
            node_count=result.node_count,
            namespace_uri=result.namespace_uri,
        )

    except APIError:
        raise
    except Exception as e:
        logger.exception("NodeSet export failed")
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to export to NodeSet",
            detail={"error": str(e)},
        )


@router.post("/export/download")
async def download_nodeset(
    request: NodeSetExportRequest,
    fetcher: Annotated[TemplateFetcherService, Depends(get_fetcher)],
    parser: Annotated[ParserService, Depends(get_parser)],
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> Response:
    """
    Export and download AAS template as NodeSet2.xml file.
    """
    settings = get_settings()
    if not settings.opcua_bridge_enabled:
        raise APIError(
            code=ErrorCode.FEATURE_DISABLED,
            message="OPC UA Bridge is disabled",
        )

    try:
        # Fetch the template
        template_content = await fetcher.get_template(
            request.template_name,
            status=request.template_status,
            version=request.template_version,
        )

        if template_content is None:
            raise APIError(
                code=ErrorCode.NOT_FOUND,
                message=f"Template '{request.template_name}' not found",
            )

        # Parse to get UI schema
        ui_schema = await parser.parse(template_content)

        # Export to NodeSet
        exporter = NodeSetExporter(namespace_uri=request.namespace_uri)
        result = exporter.export_template(ui_schema, version=request.model_version)

        if not result.success or not result.nodeset_xml:
            raise APIError(
                code=ErrorCode.BAD_REQUEST,
                message="NodeSet export failed",
                detail={"warnings": result.warnings},
            )

        filename = f"{request.template_name}_NodeSet2.xml"

        return Response(
            content=result.nodeset_xml.encode("utf-8"),
            media_type="application/xml",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except APIError:
        raise
    except Exception as e:
        logger.exception("NodeSet download failed")
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to export NodeSet file",
            detail={"error": str(e)},
        )


# ============================================================================
# Direct Schema Conversion (without template lookup)
# ============================================================================


class DirectExportRequest(BaseModel):
    """Request to export UI schema directly to NodeSet."""

    model_config = ConfigDict(protected_namespaces=PYDANTIC_PROTECTED_NAMESPACES)

    ui_schema: dict = Field(description="UI schema to export")
    namespace_uri: str | None = Field(default=None)
    model_version: str = Field(default="1.0.0")


@router.post("/export/direct", response_model=NodeSetExportResponse)
async def export_schema_to_nodeset(
    request: DirectExportRequest,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> NodeSetExportResponse:
    """
    Export a UI schema directly to NodeSet2.xml format.

    Use this endpoint when you have the schema already loaded
    and don't need to fetch from templates.
    """
    settings = get_settings()
    if not settings.opcua_bridge_enabled:
        raise APIError(
            code=ErrorCode.FEATURE_DISABLED,
            message="OPC UA Bridge is disabled",
        )

    try:
        exporter = NodeSetExporter(namespace_uri=request.namespace_uri)
        result = exporter.export_template(
            request.ui_schema, version=request.model_version
        )

        return NodeSetExportResponse(
            success=result.success,
            nodeset_xml=result.nodeset_xml,
            warnings=result.warnings,
            node_count=result.node_count,
            namespace_uri=result.namespace_uri,
        )

    except Exception as e:
        logger.exception("Direct NodeSet export failed")
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to export schema to NodeSet",
            detail={"error": str(e)},
        )


# ============================================================================
# Utilities
# ============================================================================


@router.get("/type-mappings")
async def get_type_mappings(
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> dict:
    """
    Get the OPC UA ↔ AAS type mappings.

    Returns the mapping between OPC UA built-in types
    and AAS DataTypeDefXsd values.
    """
    return {
        "opcua_to_aas": OPCUA_TO_AAS_TYPE_MAP,
        "aas_to_opcua": AAS_TO_OPCUA_TYPE_MAP,
        "nodeclass_to_aas": NODECLASS_TO_AAS_MAP,
        "aas_to_nodeclass": AAS_TO_NODECLASS_MAP,
    }


@router.get("/supported-types")
async def get_supported_types(
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> dict:
    """
    Get list of supported OPC UA types and their AAS equivalents.
    """
    return {
        "opcua_types": list(OPCUA_TO_AAS_TYPE_MAP.keys()),
        "aas_types": list(AAS_TO_OPCUA_TYPE_MAP.keys()),
        "import_supported": [
            "UAObjectType",
            "UAObject",
            "UAVariable",
            "UAMethod",
        ],
        "export_supported": [
            "Submodel",
            "SubmodelElementCollection",
            "SubmodelElementList",
            "Property",
            "MultiLanguageProperty",
        ],
    }
