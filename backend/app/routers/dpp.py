"""
DPP (Digital Product Passport) Builder API endpoints.

Provides endpoints for assembling and validating DPP packages
for EU ESPR (Ecodesign for Sustainable Products Regulation) compliance.
"""

from __future__ import annotations

import logging
import re
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from app.config import get_settings
from app.dependencies import get_current_user, get_fetcher, get_hydrator, get_parser
from app.errors import APIError, ErrorCode
from app.services.dpp.builder import DPPBuilder
from app.services.dpp.models import (
    DPPExportRequest,
    DPPPackage,
    DPPPackageCreate,
    DPPPackageStatus,
    DPPSubmodelAdd,
    DPPValidationResult,
)
from app.services.fetcher import TemplateFetcherService
from app.services.hydrator import HydratorService
from app.services.parser import ParserService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dpp", tags=["dpp"])

# Package ID validation pattern - must match format generated in DPPBuilder.create_package
DPP_PACKAGE_ID_PATTERN = re.compile(r"^dpp-[a-f0-9]{12}$")


def validate_package_id(package_id: str) -> str:
    """
    Validate package_id format to prevent path traversal attacks.

    Package IDs are generated as 'dpp-{uuid.hex[:12]}' in DPPBuilder.
    This validation ensures only valid IDs are accepted.
    """
    if not DPP_PACKAGE_ID_PATTERN.match(package_id):
        raise APIError(
            code=ErrorCode.BAD_REQUEST,
            message="Invalid package ID format",
            detail={"package_id": package_id},
        )
    return package_id


def get_dpp_builder(
    fetcher: Annotated[TemplateFetcherService, Depends(get_fetcher)],
    parser: Annotated[ParserService, Depends(get_parser)],
    hydrator: Annotated[HydratorService, Depends(get_hydrator)],
) -> DPPBuilder:
    """Get DPP builder instance with dependencies."""
    return DPPBuilder(fetcher=fetcher, parser=parser, hydrator=hydrator)


# ============================================================================
# Package Management
# ============================================================================


@router.post("/packages", response_model=DPPPackage)
async def create_package(
    request: DPPPackageCreate,
    builder: Annotated[DPPBuilder, Depends(get_dpp_builder)],
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> DPPPackage:
    """
    Create a new DPP package.

    Starts the DPP assembly process. Submodels can be added subsequently.
    """
    settings = get_settings()
    if not settings.dpp_enabled:
        raise APIError(
            code=ErrorCode.FEATURE_DISABLED,
            message="DPP Builder is disabled",
        )

    try:
        return builder.create_package(request)
    except Exception as e:
        logger.exception("Failed to create DPP package")
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to create DPP package",
            detail={"error": str(e)},
        )


@router.get("/packages", response_model=list[DPPPackage])
async def list_packages(
    status: Annotated[DPPPackageStatus | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    builder: Annotated[DPPBuilder, Depends(get_dpp_builder)] = None,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> list[DPPPackage]:
    """List DPP packages, optionally filtered by status."""
    settings = get_settings()
    if not settings.dpp_enabled:
        raise APIError(
            code=ErrorCode.FEATURE_DISABLED,
            message="DPP Builder is disabled",
        )

    return builder.list_packages(status=status, limit=limit)


@router.get("/packages/{package_id}", response_model=DPPPackage)
async def get_package(
    package_id: str,
    builder: Annotated[DPPBuilder, Depends(get_dpp_builder)],
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> DPPPackage:
    """Get a DPP package by ID."""
    settings = get_settings()
    if not settings.dpp_enabled:
        raise APIError(
            code=ErrorCode.FEATURE_DISABLED,
            message="DPP Builder is disabled",
        )

    validate_package_id(package_id)
    package = builder.get_package(package_id)
    if package is None:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="DPP package not found",
            detail={"package_id": package_id},
        )

    return package


@router.put("/packages/{package_id}", response_model=DPPPackage)
async def update_package(
    package_id: str,
    product_id: str | None = None,
    product_name: str | None = None,
    manufacturer_name: str | None = None,
    manufacturer_id: str | None = None,
    notes: str | None = None,
    builder: Annotated[DPPBuilder, Depends(get_dpp_builder)] = None,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> DPPPackage:
    """Update DPP package metadata."""
    settings = get_settings()
    if not settings.dpp_enabled:
        raise APIError(
            code=ErrorCode.FEATURE_DISABLED,
            message="DPP Builder is disabled",
        )

    validate_package_id(package_id)
    package = builder.update_package(
        package_id,
        product_id=product_id,
        product_name=product_name,
        manufacturer_name=manufacturer_name,
        manufacturer_id=manufacturer_id,
        notes=notes,
    )

    if package is None:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="DPP package not found",
            detail={"package_id": package_id},
        )

    return package


@router.delete("/packages/{package_id}")
async def delete_package(
    package_id: str,
    builder: Annotated[DPPBuilder, Depends(get_dpp_builder)],
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> dict:
    """Delete a DPP package."""
    settings = get_settings()
    if not settings.dpp_enabled:
        raise APIError(
            code=ErrorCode.FEATURE_DISABLED,
            message="DPP Builder is disabled",
        )

    validate_package_id(package_id)
    if not builder.delete_package(package_id):
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="DPP package not found",
            detail={"package_id": package_id},
        )

    return {"deleted": package_id}


# ============================================================================
# Submodel Management
# ============================================================================


@router.post("/packages/{package_id}/submodels", response_model=DPPPackage)
async def add_submodel(
    package_id: str,
    request: DPPSubmodelAdd,
    builder: Annotated[DPPBuilder, Depends(get_dpp_builder)],
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> DPPPackage:
    """
    Add a submodel to a DPP package.

    The submodel's role determines its function in the DPP:
    - identification: Product identification (Nameplate, etc.)
    - sustainability: Environmental data (Carbon Footprint, etc.)
    - technical: Technical specifications
    - documentation: Supporting documents
    """
    settings = get_settings()
    if not settings.dpp_enabled:
        raise APIError(
            code=ErrorCode.FEATURE_DISABLED,
            message="DPP Builder is disabled",
        )

    validate_package_id(package_id)
    try:
        package = await builder.add_submodel(package_id, request)
        if package is None:
            raise APIError(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message="DPP package not found",
                detail={"package_id": package_id},
            )
        return package
    except APIError:
        raise
    except Exception as e:
        logger.exception("Failed to add submodel to package %s", package_id)
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to add submodel",
            detail={"error": str(e)},
        )


@router.delete("/packages/{package_id}/submodels/{template_name}", response_model=DPPPackage)
async def remove_submodel(
    package_id: str,
    template_name: str,
    builder: Annotated[DPPBuilder, Depends(get_dpp_builder)],
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> DPPPackage:
    """Remove a submodel from a DPP package."""
    settings = get_settings()
    if not settings.dpp_enabled:
        raise APIError(
            code=ErrorCode.FEATURE_DISABLED,
            message="DPP Builder is disabled",
        )

    validate_package_id(package_id)
    package = builder.remove_submodel(package_id, template_name)
    if package is None:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="DPP package not found",
            detail={"package_id": package_id},
        )

    return package


# ============================================================================
# Validation
# ============================================================================


@router.post("/packages/{package_id}/validate", response_model=DPPValidationResult)
async def validate_package(
    package_id: str,
    builder: Annotated[DPPBuilder, Depends(get_dpp_builder)],
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> DPPValidationResult:
    """
    Validate a DPP package for EU ESPR compliance.

    Checks:
    - Required submodels are present
    - Mandatory fields are filled
    - Cross-submodel consistency
    - ESPR regulatory requirements
    """
    settings = get_settings()
    if not settings.dpp_enabled:
        raise APIError(
            code=ErrorCode.FEATURE_DISABLED,
            message="DPP Builder is disabled",
        )

    validate_package_id(package_id)
    try:
        result = await builder.validate_package(package_id)
        if result is None:
            raise APIError(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message="DPP package not found",
                detail={"package_id": package_id},
            )
        return result
    except APIError:
        raise
    except Exception as e:
        logger.exception("Failed to validate package %s", package_id)
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to validate DPP package",
            detail={"error": str(e)},
        )


# ============================================================================
# Export
# ============================================================================


@router.post("/packages/{package_id}/export")
async def export_package(
    package_id: str,
    request: DPPExportRequest | None = None,
    builder: Annotated[DPPBuilder, Depends(get_dpp_builder)] = None,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> Response:
    """
    Export a DPP package to AASX or JSON format.

    The AASX export creates a ZIP containing:
    - Individual AASX files for each submodel
    - DPP manifest (dpp-manifest.json)
    - Validation report (if requested)
    """
    settings = get_settings()
    if not settings.dpp_enabled:
        raise APIError(
            code=ErrorCode.FEATURE_DISABLED,
            message="DPP Builder is disabled",
        )

    validate_package_id(package_id)
    if request is None:
        request = DPPExportRequest()

    try:
        content = await builder.export_package(
            package_id,
            format=request.format,
            include_validation_report=request.include_validation_report,
        )

        if content is None:
            raise APIError(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message="DPP package not found",
                detail={"package_id": package_id},
            )

        if request.format == "json":
            return Response(
                content=content,
                media_type="application/json",
                headers={
                    "Content-Disposition": f'attachment; filename="dpp-{package_id}.json"'
                },
            )
        else:  # aasx
            return Response(
                content=content,
                media_type="application/zip",
                headers={
                    "Content-Disposition": f'attachment; filename="dpp-{package_id}.zip"'
                },
            )

    except APIError:
        raise
    except Exception as e:
        logger.exception("Failed to export package %s", package_id)
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to export DPP package",
            detail={"error": str(e)},
        )


# ============================================================================
# Suggested Submodels
# ============================================================================


@router.get("/suggested-submodels")
async def get_suggested_submodels(
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> dict:
    """
    Get suggested submodel templates for DPP assembly.

    Returns templates organized by DPP role with ESPR requirements.
    """
    return {
        "identification": {
            "description": "Product identification information",
            "espr_requirement": "Article 8 - Product Identification",
            "required": True,
            "templates": [
                {
                    "name": "IDTA-02006-2-0-Nameplate",
                    "display_name": "Digital Nameplate",
                    "mandatory_fields": [
                        "ManufacturerName",
                        "SerialNumber",
                        "ProductType",
                    ],
                },
            ],
        },
        "sustainability": {
            "description": "Environmental and sustainability data",
            "espr_requirement": "Article 7 - Sustainability Information",
            "required": False,
            "templates": [
                {
                    "name": "IDTA-02023-0-9-CarbonFootprint",
                    "display_name": "Carbon Footprint",
                    "mandatory_fields": [
                        "PCFCalculationMethod",
                        "CO2eq",
                    ],
                },
            ],
        },
        "technical": {
            "description": "Technical specifications and data",
            "espr_requirement": "Article 9 - Technical Documentation",
            "required": False,
            "templates": [
                {
                    "name": "IDTA-02004-1-2-TechnicalData",
                    "display_name": "Technical Data",
                    "mandatory_fields": [],
                },
            ],
        },
        "documentation": {
            "description": "Supporting documentation",
            "espr_requirement": "Article 10 - Digital Documentation",
            "required": False,
            "templates": [
                {
                    "name": "IDTA-02005-1-0-HiearchicalStructures",
                    "display_name": "Hierarchical Structures",
                    "mandatory_fields": [],
                },
            ],
        },
    }


# ============================================================================
# Compliance Information
# ============================================================================


@router.get("/compliance-levels")
async def get_compliance_levels(
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> dict:
    """
    Get information about EU ESPR compliance levels.
    """
    return {
        "levels": [
            {
                "level": "full",
                "name": "Full Compliance",
                "description": "All mandatory fields present and validated",
                "requirements": [
                    "Identification submodel with complete data",
                    "Sustainability information present",
                    "No validation errors",
                ],
            },
            {
                "level": "partial",
                "name": "Partial Compliance",
                "description": "Core requirements met with some gaps",
                "requirements": [
                    "Identification submodel present",
                    "Minor issues or missing optional data",
                ],
            },
            {
                "level": "minimal",
                "name": "Minimal Compliance",
                "description": "Basic identification only",
                "requirements": [
                    "Identification submodel present",
                    "Significant data gaps",
                ],
            },
            {
                "level": "non_compliant",
                "name": "Non-Compliant",
                "description": "Critical information missing",
                "requirements": [
                    "Missing identification submodel",
                    "Or critical validation errors",
                ],
            },
        ],
        "espr_reference": "EU Regulation 2024/XXXX - Ecodesign for Sustainable Products",
    }
