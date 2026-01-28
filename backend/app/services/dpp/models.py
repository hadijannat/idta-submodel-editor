"""
Data models for Digital Product Passport (DPP) Builder.

Defines the structure of DPP packages, validation results,
and EU ESPR compliance levels.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class ESPRComplianceLevel(str, Enum):
    """EU ESPR (Ecodesign for Sustainable Products Regulation) compliance levels."""

    FULL = "full"  # All mandatory fields present and validated
    PARTIAL = "partial"  # Some mandatory fields missing
    MINIMAL = "minimal"  # Only basic identification present
    NON_COMPLIANT = "non_compliant"  # Critical fields missing


class DPPPackageStatus(str, Enum):
    """Status of a DPP package."""

    DRAFT = "draft"  # Being assembled
    VALIDATING = "validating"  # Validation in progress
    VALID = "valid"  # Validated and ready for export/publish
    INVALID = "invalid"  # Validation failed
    PUBLISHED = "published"  # Published to dataspace


class DPPSubmodelRef(BaseModel):
    """Reference to a submodel included in the DPP package."""

    template_name: str = Field(description="IDTA template name")
    template_status: Literal["published", "deprecated"] = Field(default="published")
    template_version: str | None = Field(default=None)
    semantic_id: str | None = Field(
        default=None, description="Submodel semantic ID (extracted from template)"
    )
    role: str = Field(
        description="Role in DPP (e.g., 'identification', 'sustainability', 'technical')"
    )
    form_data: dict = Field(default_factory=dict, description="Filled form data")
    is_required: bool = Field(
        default=False, description="Whether this submodel is required for ESPR compliance"
    )
    validation_errors: list[str] = Field(
        default_factory=list, description="Validation errors for this submodel"
    )


class DPPValidationError(BaseModel):
    """A validation error in the DPP package."""

    submodel: str | None = Field(
        default=None, description="Submodel name (None for package-level errors)"
    )
    field_path: str | None = Field(
        default=None, description="Field path (None for submodel-level errors)"
    )
    code: str = Field(description="Error code")
    message: str = Field(description="Human-readable error message")
    severity: Literal["error", "warning", "info"] = Field(default="error")
    espr_requirement: str | None = Field(
        default=None, description="Related ESPR article/requirement"
    )


class DPPValidationResult(BaseModel):
    """Result of validating a DPP package."""

    is_valid: bool = Field(description="Whether the package is valid for export")
    compliance_level: ESPRComplianceLevel = Field(
        description="EU ESPR compliance level"
    )
    completeness_score: float = Field(
        ge=0.0, le=1.0, description="Overall completeness (0-1)"
    )
    errors: list[DPPValidationError] = Field(
        default_factory=list, description="Validation errors"
    )
    warnings: list[DPPValidationError] = Field(
        default_factory=list, description="Validation warnings"
    )
    submodel_statuses: dict[str, str] = Field(
        default_factory=dict, description="Status per submodel"
    )
    missing_required_submodels: list[str] = Field(
        default_factory=list, description="Required submodels not included"
    )
    missing_mandatory_fields: list[str] = Field(
        default_factory=list, description="Mandatory fields not filled"
    )


class DPPPackage(BaseModel):
    """A Digital Product Passport package being assembled."""

    package_id: str = Field(description="Unique package identifier")
    status: DPPPackageStatus = Field(default=DPPPackageStatus.DRAFT)
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")

    # Product identification (from Nameplate or similar)
    product_id: str | None = Field(
        default=None, description="Unique product identifier"
    )
    product_name: str | None = Field(default=None, description="Product name")
    manufacturer_name: str | None = Field(default=None, description="Manufacturer name")
    manufacturer_id: str | None = Field(
        default=None, description="Manufacturer ID (e.g., DUNS, VAT)"
    )

    # Submodels
    submodels: list[DPPSubmodelRef] = Field(
        default_factory=list, description="Submodels included in package"
    )

    # Validation
    validation_result: DPPValidationResult | None = Field(
        default=None, description="Last validation result"
    )

    # Publication (if published)
    publication_id: str | None = Field(
        default=None, description="Dataspace publication ID"
    )
    publication_url: str | None = Field(
        default=None, description="Public access URL"
    )

    # Metadata
    notes: str | None = Field(default=None, description="User notes")


class DPPPackageCreate(BaseModel):
    """Request to create a new DPP package."""

    product_id: str | None = Field(
        default=None, description="Optional product identifier"
    )
    product_name: str | None = Field(
        default=None, description="Optional product name"
    )
    manufacturer_name: str | None = Field(
        default=None, description="Optional manufacturer name"
    )
    manufacturer_id: str | None = Field(
        default=None, description="Optional manufacturer ID"
    )
    notes: str | None = Field(default=None, description="Optional notes")


class DPPSubmodelAdd(BaseModel):
    """Request to add a submodel to a DPP package."""

    template_name: str = Field(description="IDTA template name")
    template_status: Literal["published", "deprecated"] = Field(default="published")
    template_version: str | None = Field(default=None)
    role: str = Field(
        description="Role in DPP (identification, sustainability, technical, documentation)"
    )
    form_data: dict = Field(description="Filled form data for the submodel")


class DPPExportRequest(BaseModel):
    """Request to export a DPP package."""

    format: Literal["aasx", "json"] = Field(
        default="aasx", description="Export format"
    )
    include_validation_report: bool = Field(
        default=True, description="Include validation report in export"
    )


class DPPPublishRequest(BaseModel):
    """Request to publish a DPP package to dataspace."""

    connection_id: str = Field(description="Dataspace connection ID")
    policy_template: str | None = Field(
        default=None, description="Policy template to use"
    )
    aas_id: str | None = Field(
        default=None, description="Optional AAS ID (auto-generated if not provided)"
    )
