"""
DPP Validator - Validates DPP packages for EU ESPR compliance.

Checks:
- Required submodels are present
- Mandatory fields are filled
- Cross-submodel consistency
- ESPR regulatory requirements
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.services.dpp.models import (
    DPPPackage,
    DPPSubmodelRef,
    DPPValidationError,
    DPPValidationResult,
    ESPRComplianceLevel,
)

if TYPE_CHECKING:
    from app.services.parser import ParserService
    from app.services.fetcher import TemplateFetcherService

logger = logging.getLogger(__name__)


# ESPR DPP requirements by submodel role
REQUIRED_SUBMODELS = {
    "identification": {
        "templates": [
            "IDTA-02006-2-0-Nameplate",
            "IDTA-02007-1-0-SoftwareNameplate",
        ],
        "mandatory_fields": [
            "ManufacturerName",
            "SerialNumber",
            "ProductType",
        ],
        "espr_article": "Article 8 - Product Identification",
    },
    "sustainability": {
        "templates": [
            "IDTA-02023-0-9-CarbonFootprint",
            "IDTA-02056-1-0-MaterialComposition",
        ],
        "mandatory_fields": [],  # Depends on product category
        "espr_article": "Article 7 - Sustainability Information",
    },
    "technical": {
        "templates": [
            "IDTA-02004-1-2-TechnicalData",
            "IDTA-02010-1-0-ServiceRequestNotification",
        ],
        "mandatory_fields": [],
        "espr_article": "Article 9 - Technical Documentation",
    },
    "documentation": {
        "templates": [
            "IDTA-02005-1-0-HiearchicalStructures",
            "IDTA-02008-1-1-TimeSeriesData",
        ],
        "mandatory_fields": [],
        "espr_article": "Article 10 - Digital Documentation",
    },
}

# ESPR mandatory fields for DPP
ESPR_MANDATORY_FIELDS = [
    # From identification submodel
    ("identification", "ManufacturerName"),
    ("identification", "ProductType"),
    # Unique identifiers
    ("identification", "SerialNumber"),
]


class DPPValidator:
    """Validates DPP packages for EU ESPR compliance."""

    def __init__(
        self,
        fetcher: "TemplateFetcherService | None" = None,
        parser: "ParserService | None" = None,
    ):
        self._fetcher = fetcher
        self._parser = parser

    async def validate(self, package: DPPPackage) -> DPPValidationResult:
        """
        Validate a DPP package for EU ESPR compliance.

        Args:
            package: The DPP package to validate

        Returns:
            Validation result with compliance level and errors
        """
        errors: list[DPPValidationError] = []
        warnings: list[DPPValidationError] = []
        submodel_statuses: dict[str, str] = {}
        missing_required: list[str] = []
        missing_fields: list[str] = []

        # Track which roles are covered
        roles_covered = set()
        for sm in package.submodels:
            roles_covered.add(sm.role)
            submodel_statuses[sm.template_name] = "included"

        # Check for required identification submodel
        if "identification" not in roles_covered:
            missing_required.append("identification")
            errors.append(
                DPPValidationError(
                    code="MISSING_IDENTIFICATION",
                    message="DPP requires an identification submodel (e.g., Nameplate)",
                    severity="error",
                    espr_requirement="Article 8 - Product Identification",
                )
            )

        # Check mandatory product fields
        if not package.product_id and not self._has_field(
            package.submodels, "SerialNumber"
        ):
            missing_fields.append("SerialNumber")
            errors.append(
                DPPValidationError(
                    code="MISSING_PRODUCT_ID",
                    message="Product identifier (SerialNumber) is required",
                    severity="error",
                    espr_requirement="Article 8.1",
                )
            )

        if not package.manufacturer_name and not self._has_field(
            package.submodels, "ManufacturerName"
        ):
            missing_fields.append("ManufacturerName")
            errors.append(
                DPPValidationError(
                    code="MISSING_MANUFACTURER",
                    message="Manufacturer name is required",
                    severity="error",
                    espr_requirement="Article 8.2",
                )
            )

        # Check for sustainability information (warning if missing)
        if "sustainability" not in roles_covered:
            warnings.append(
                DPPValidationError(
                    code="MISSING_SUSTAINABILITY",
                    message="Sustainability information recommended for ESPR compliance",
                    severity="warning",
                    espr_requirement="Article 7 - Sustainability Information",
                )
            )

        # Validate each submodel
        for submodel in package.submodels:
            sm_errors = await self._validate_submodel(submodel)
            for err in sm_errors:
                if err.severity == "error":
                    errors.append(err)
                else:
                    warnings.append(err)
            submodel_statuses[submodel.template_name] = (
                "valid" if not sm_errors else "invalid"
            )

        # Cross-submodel consistency checks
        cross_errors = self._check_cross_consistency(package)
        for err in cross_errors:
            if err.severity == "error":
                errors.append(err)
            else:
                warnings.append(err)

        # Calculate completeness score
        total_checks = 10  # Base checks
        passed_checks = total_checks - len([e for e in errors if e.severity == "error"])
        completeness_score = max(0.0, min(1.0, passed_checks / total_checks))

        # Determine compliance level
        compliance_level = self._determine_compliance_level(
            errors=errors,
            roles_covered=roles_covered,
            completeness_score=completeness_score,
        )

        # Package is valid if no errors (warnings OK)
        is_valid = len([e for e in errors if e.severity == "error"]) == 0

        return DPPValidationResult(
            is_valid=is_valid,
            compliance_level=compliance_level,
            completeness_score=completeness_score,
            errors=errors,
            warnings=warnings,
            submodel_statuses=submodel_statuses,
            missing_required_submodels=missing_required,
            missing_mandatory_fields=missing_fields,
        )

    async def _validate_submodel(
        self, submodel: DPPSubmodelRef
    ) -> list[DPPValidationError]:
        """Validate a single submodel."""
        errors: list[DPPValidationError] = []

        # Check if form data is empty
        if not submodel.form_data:
            errors.append(
                DPPValidationError(
                    submodel=submodel.template_name,
                    code="EMPTY_SUBMODEL",
                    message=f"Submodel {submodel.template_name} has no data",
                    severity="warning",
                )
            )
            return errors

        # Check for required role-specific fields
        role_config = REQUIRED_SUBMODELS.get(submodel.role, {})
        mandatory_fields = role_config.get("mandatory_fields", [])

        for field in mandatory_fields:
            if not self._has_field_in_data(submodel.form_data, field):
                errors.append(
                    DPPValidationError(
                        submodel=submodel.template_name,
                        field_path=field,
                        code="MISSING_MANDATORY_FIELD",
                        message=f"Mandatory field {field} is missing",
                        severity="error",
                        espr_requirement=role_config.get("espr_article"),
                    )
                )

        return errors

    def _check_cross_consistency(
        self, package: DPPPackage
    ) -> list[DPPValidationError]:
        """Check cross-submodel consistency."""
        errors: list[DPPValidationError] = []

        # Check manufacturer consistency
        manufacturers = set()
        for sm in package.submodels:
            mfr = self._get_field_value(sm.form_data, "ManufacturerName")
            if mfr:
                manufacturers.add(mfr)

        if package.manufacturer_name:
            manufacturers.add(package.manufacturer_name)

        if len(manufacturers) > 1:
            errors.append(
                DPPValidationError(
                    code="INCONSISTENT_MANUFACTURER",
                    message="Manufacturer name differs across submodels",
                    severity="warning",
                )
            )

        # Check serial number consistency
        serials = set()
        for sm in package.submodels:
            serial = self._get_field_value(sm.form_data, "SerialNumber")
            if serial:
                serials.add(serial)

        if package.product_id:
            serials.add(package.product_id)

        if len(serials) > 1:
            errors.append(
                DPPValidationError(
                    code="INCONSISTENT_SERIAL",
                    message="Serial number differs across submodels",
                    severity="warning",
                )
            )

        return errors

    def _determine_compliance_level(
        self,
        errors: list[DPPValidationError],
        roles_covered: set[str],
        completeness_score: float,
    ) -> ESPRComplianceLevel:
        """Determine the ESPR compliance level."""
        error_count = len([e for e in errors if e.severity == "error"])

        # Full compliance: no errors, all core roles covered
        core_roles = {"identification", "sustainability"}
        if error_count == 0 and core_roles.issubset(roles_covered):
            return ESPRComplianceLevel.FULL

        # Partial compliance: identification present, some issues
        if "identification" in roles_covered and error_count <= 2:
            return ESPRComplianceLevel.PARTIAL

        # Minimal: identification present but significant issues
        if "identification" in roles_covered:
            return ESPRComplianceLevel.MINIMAL

        # Non-compliant: missing critical information
        return ESPRComplianceLevel.NON_COMPLIANT

    def _has_field(self, submodels: list[DPPSubmodelRef], field_name: str) -> bool:
        """Check if any submodel has a field value."""
        for sm in submodels:
            if self._has_field_in_data(sm.form_data, field_name):
                return True
        return False

    def _has_field_in_data(self, form_data: dict, field_name: str) -> bool:
        """Check if form data has a field with a non-empty value."""
        elements = form_data.get("elements", {})
        if field_name in elements:
            value = elements[field_name]
            if isinstance(value, dict):
                return bool(value.get("value"))
            return bool(value)

        # Check nested structures
        for key, value in elements.items():
            if isinstance(value, dict):
                nested_elements = value.get("elements", {})
                if field_name in nested_elements:
                    nested_value = nested_elements[field_name]
                    if isinstance(nested_value, dict):
                        return bool(nested_value.get("value"))
                    return bool(nested_value)

        return False

    def _get_field_value(self, form_data: dict, field_name: str) -> str | None:
        """Get a field value from form data."""
        elements = form_data.get("elements", {})
        if field_name in elements:
            value = elements[field_name]
            if isinstance(value, dict):
                return value.get("value")
            return value

        # Check nested structures
        for key, value in elements.items():
            if isinstance(value, dict):
                nested_elements = value.get("elements", {})
                if field_name in nested_elements:
                    nested_value = nested_elements[field_name]
                    if isinstance(nested_value, dict):
                        return nested_value.get("value")
                    return nested_value

        return None
