"""
SAMM Converter API endpoints.

Provides bidirectional conversion between Catena-X SAMM models
and AAS (Asset Administration Shell) structures.
"""

from __future__ import annotations

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.config import get_settings
from app.dependencies import get_current_user, get_fetcher, get_parser
from app.errors import APIError, ErrorCode
from app.services.fetcher import TemplateFetcherService
from app.services.parser import ParserService
from app.services.samm.converter import SAMMConverter
from app.services.samm.models import ConversionResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/samm", tags=["samm"])


def get_samm_converter(
    fetcher: Annotated[TemplateFetcherService, Depends(get_fetcher)],
    parser: Annotated[ParserService, Depends(get_parser)],
) -> SAMMConverter:
    """Get SAMM converter instance with dependencies."""
    return SAMMConverter(fetcher=fetcher, parser=parser)


# ============================================================================
# SAMM → AAS Conversion (Import)
# ============================================================================


class SAMMImportRequest(BaseModel):
    """Request to import a SAMM model."""

    content: str = Field(description="SAMM model content (TTL or JSON-LD)")
    format: Literal["ttl", "json-ld"] = Field(
        default="ttl", description="Content format"
    )


@router.post("/import", response_model=ConversionResult)
async def import_samm(
    request: SAMMImportRequest,
    converter: Annotated[SAMMConverter, Depends(get_samm_converter)],
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> ConversionResult:
    """
    Import a SAMM model and convert to AAS structure.

    Converts Catena-X Semantic Aspect Meta Model (SAMM) to:
    - AAS template structure (SubmodelElements)
    - UI schema for form rendering

    This enables editing Catena-X aspect models using the IDTA editor.
    """
    settings = get_settings()
    if not settings.samm_enabled:
        raise APIError(
            code=ErrorCode.FEATURE_DISABLED,
            message="SAMM Converter is disabled",
        )

    try:
        result = await converter.convert_samm_to_aas(
            request.content, format=request.format
        )

        if not result.success:
            raise APIError(
                code=ErrorCode.BAD_REQUEST,
                message="SAMM conversion failed",
                detail={"warnings": [w.model_dump() for w in result.warnings]},
            )

        return result

    except APIError:
        raise
    except Exception as e:
        logger.exception("SAMM import failed")
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to import SAMM model",
            detail={"error": str(e)},
        )


@router.post("/import/file", response_model=ConversionResult)
async def import_samm_file(
    file: Annotated[UploadFile, File(description="SAMM model file (TTL or JSON-LD)")],
    converter: Annotated[SAMMConverter, Depends(get_samm_converter)],
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> ConversionResult:
    """
    Import a SAMM model from an uploaded file.

    Supports:
    - .ttl (Turtle format)
    - .json / .jsonld (JSON-LD format)
    """
    settings = get_settings()
    if not settings.samm_enabled:
        raise APIError(
            code=ErrorCode.FEATURE_DISABLED,
            message="SAMM Converter is disabled",
        )

    # Determine format from filename
    filename = file.filename or ""
    if filename.endswith(".ttl"):
        format = "ttl"
    elif filename.endswith(".json") or filename.endswith(".jsonld"):
        format = "json-ld"
    else:
        raise APIError(
            code=ErrorCode.BAD_REQUEST,
            message="Unsupported file format. Use .ttl or .json/.jsonld",
        )

    try:
        content = await file.read()
        result = await converter.convert_samm_to_aas(content, format=format)

        if not result.success:
            raise APIError(
                code=ErrorCode.BAD_REQUEST,
                message="SAMM conversion failed",
                detail={"warnings": [w.model_dump() for w in result.warnings]},
            )

        return result

    except APIError:
        raise
    except Exception as e:
        logger.exception("SAMM file import failed")
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to import SAMM file",
            detail={"error": str(e)},
        )


# ============================================================================
# AAS → SAMM Conversion (Export)
# ============================================================================


class SAMMExportRequest(BaseModel):
    """Request to export an AAS template as SAMM."""

    template_name: str = Field(description="AAS template name")
    template_status: Literal["published", "deprecated"] = Field(
        default="published"
    )
    template_version: str | None = Field(default=None)
    samm_version: str = Field(
        default="1.0.0", description="Version for the generated SAMM model"
    )


@router.post("/export", response_model=ConversionResult)
async def export_to_samm(
    request: SAMMExportRequest,
    converter: Annotated[SAMMConverter, Depends(get_samm_converter)],
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> ConversionResult:
    """
    Export an AAS template as SAMM model.

    Converts an IDTA submodel template to Catena-X SAMM format:
    - SAMMAspect model structure
    - TTL (Turtle) content

    This enables sharing AAS templates with the Catena-X ecosystem.
    """
    settings = get_settings()
    if not settings.samm_enabled:
        raise APIError(
            code=ErrorCode.FEATURE_DISABLED,
            message="SAMM Converter is disabled",
        )

    try:
        result = await converter.convert_aas_to_samm(
            request.template_name,
            template_status=request.template_status,
            template_version=request.template_version,
            version=request.samm_version,
        )

        if not result.success:
            raise APIError(
                code=ErrorCode.BAD_REQUEST,
                message="SAMM export failed",
                detail={"warnings": [w.model_dump() for w in result.warnings]},
            )

        return result

    except APIError:
        raise
    except Exception as e:
        logger.exception("SAMM export failed")
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to export to SAMM",
            detail={"error": str(e)},
        )


@router.post("/export/download")
async def download_samm(
    request: SAMMExportRequest,
    converter: Annotated[SAMMConverter, Depends(get_samm_converter)],
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> Response:
    """
    Export and download AAS template as SAMM TTL file.
    """
    settings = get_settings()
    if not settings.samm_enabled:
        raise APIError(
            code=ErrorCode.FEATURE_DISABLED,
            message="SAMM Converter is disabled",
        )

    try:
        result = await converter.convert_aas_to_samm(
            request.template_name,
            template_status=request.template_status,
            template_version=request.template_version,
            version=request.samm_version,
        )

        if not result.success or not result.samm_ttl:
            raise APIError(
                code=ErrorCode.BAD_REQUEST,
                message="SAMM export failed",
                detail={"warnings": [w.model_dump() for w in result.warnings]},
            )

        filename = f"{result.target_name or 'aspect'}.ttl"

        return Response(
            content=result.samm_ttl.encode("utf-8"),
            media_type="text/turtle",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except APIError:
        raise
    except Exception as e:
        logger.exception("SAMM download failed")
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to export SAMM file",
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
    Get the SAMM ↔ AAS type mappings.

    Returns the mapping between SAMM data types (XSD-based)
    and AAS DataTypeDefXsd values.
    """
    from app.services.samm.models import SAMM_TO_AAS_TYPE_MAP, AAS_TO_SAMM_TYPE_MAP

    return {
        "samm_to_aas": SAMM_TO_AAS_TYPE_MAP,
        "aas_to_samm": AAS_TO_SAMM_TYPE_MAP,
    }


@router.get("/supported-formats")
async def get_supported_formats(
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> dict:
    """
    Get supported SAMM model formats.
    """
    return {
        "import_formats": [
            {
                "format": "ttl",
                "name": "Turtle",
                "extension": ".ttl",
                "mime_type": "text/turtle",
            },
            {
                "format": "json-ld",
                "name": "JSON-LD",
                "extension": ".json",
                "mime_type": "application/ld+json",
            },
        ],
        "export_formats": [
            {
                "format": "ttl",
                "name": "Turtle",
                "extension": ".ttl",
                "mime_type": "text/turtle",
            },
        ],
    }
