"""
PDF Conformance Summary Generator.

Generates compliance summary blocks for PDF export showing:
- Template name/version
- Validation status
- AAS compliance checks
- Template-specific validation
"""

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class ConformanceCheck:
    """A single conformance check result."""

    name: str
    status: Literal["pass", "fail", "warning", "info"]
    message: str


@dataclass
class ConformanceSummary:
    """Complete conformance summary for PDF rendering."""

    template_name: str
    template_version: str | None
    metamodel_version: str = "IDTA Metamodel V3.0"
    validation_status: Literal["valid", "invalid", "warnings"] = "valid"
    error_count: int = 0
    warning_count: int = 0
    checks: list[ConformanceCheck] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for template rendering."""
        return {
            "templateName": self.template_name,
            "templateVersion": self.template_version,
            "metamodelVersion": self.metamodel_version,
            "validationStatus": self.validation_status,
            "errorCount": self.error_count,
            "warningCount": self.warning_count,
            "checks": [
                {"name": c.name, "status": c.status, "message": c.message}
                for c in self.checks
            ],
        }


def generate_conformance_summary(
    schema: dict[str, Any],
    form_data: dict[str, Any],
    errors: list | None = None,
    warnings: list | None = None,
    template_name: str | None = None,
) -> ConformanceSummary:
    """
    Generate a conformance summary for PDF export.

    Args:
        schema: Parsed UI schema from parser
        form_data: User-submitted form data
        errors: Validation errors (if already computed)
        warnings: Validation warnings (if already computed)
        template_name: Template name for display

    Returns:
        ConformanceSummary with all checks
    """
    errors = errors or []
    warnings = warnings or []

    # Extract template info
    admin = schema.get("administration") or {}
    version = admin.get("version")
    if version and admin.get("revision"):
        version = f"{version}.{admin['revision']}"

    summary = ConformanceSummary(
        template_name=template_name or schema.get("idShort", "Unknown"),
        template_version=version,
        error_count=len(errors),
        warning_count=len(warnings),
    )

    # Determine overall validation status
    if errors:
        summary.validation_status = "invalid"
    elif warnings:
        summary.validation_status = "warnings"
    else:
        summary.validation_status = "valid"

    # AAS compliance checks
    _check_aas_compliance(schema, summary)

    # Template-specific checks
    _check_template_specific(schema, form_data, summary)

    return summary


def _check_aas_compliance(schema: dict[str, Any], summary: ConformanceSummary) -> None:
    """Check AAS metamodel compliance requirements."""
    aas = schema.get("aas")

    if not aas:
        summary.checks.append(
            ConformanceCheck(
                name="AAS Wrapper",
                status="info",
                message="Template contains Submodel only (no AAS wrapper)",
            )
        )
        return

    # Check assetInformation (MANDATORY per IDTA Metamodel V3.0)
    asset_info = aas.get("assetInformation") or {}

    # assetKind is MANDATORY within assetInformation
    asset_kind = asset_info.get("assetKind")
    if asset_kind:
        summary.checks.append(
            ConformanceCheck(
                name="Asset Kind",
                status="pass",
                message=f"Asset kind specified: {asset_kind}",
            )
        )
    else:
        summary.checks.append(
            ConformanceCheck(
                name="Asset Kind",
                status="fail",
                message="assetKind is MANDATORY but not specified",
            )
        )

    # At least globalAssetId OR specificAssetId required
    global_asset_id = asset_info.get("globalAssetId")
    specific_asset_ids = asset_info.get("specificAssetIds") or []

    if global_asset_id or specific_asset_ids:
        if global_asset_id:
            summary.checks.append(
                ConformanceCheck(
                    name="Asset Identification",
                    status="pass",
                    message=f"Global Asset ID: {_truncate(global_asset_id, 50)}",
                )
            )
        if specific_asset_ids:
            summary.checks.append(
                ConformanceCheck(
                    name="Specific Asset IDs",
                    status="pass",
                    message=f"{len(specific_asset_ids)} specific identifier(s) present",
                )
            )
    else:
        summary.checks.append(
            ConformanceCheck(
                name="Asset Identification",
                status="warning",
                message="Neither globalAssetId nor specificAssetId present",
            )
        )

    # Check submodel references
    submodel_refs = aas.get("submodelRefs") or []
    if submodel_refs:
        summary.checks.append(
            ConformanceCheck(
                name="Submodel References",
                status="pass",
                message=f"{len(submodel_refs)} submodel(s) referenced",
            )
        )

    # Check derivedFrom (optional, but note if present)
    derived_from = aas.get("derivedFrom")
    if derived_from:
        summary.checks.append(
            ConformanceCheck(
                name="Derived From",
                status="info",
                message=f"Inherits from: {_truncate(derived_from, 50)}",
            )
        )


def _check_template_specific(
    schema: dict[str, Any],
    form_data: dict[str, Any],
    summary: ConformanceSummary,
) -> None:
    """Run template-specific conformance checks."""
    semantic_id = schema.get("semanticId") or ""
    id_short = (schema.get("idShort") or "").lower()

    # Digital Nameplate (IDTA 02006)
    if "nameplate" in id_short or "02006" in semantic_id:
        _check_nameplate_requirements(schema, form_data, summary)

    # Product Carbon Footprint (IDTA 02023)
    elif "carbonfootprint" in id_short or "02023" in semantic_id:
        _check_pcf_requirements(schema, form_data, summary)


def _check_nameplate_requirements(
    schema: dict[str, Any],
    form_data: dict[str, Any],
    summary: ConformanceSummary,
) -> None:
    """
    Check IDTA 02006 Digital Nameplate required fields.

    Per the spec, these fields are MANDATORY:
    - URIOfTheProduct
    - ManufacturerName
    - ManufacturerProductDesignation
    """
    elements = form_data.get("elements", {})

    required_fields = [
        ("URIOfTheProduct", "Product URI"),
        ("ManufacturerName", "Manufacturer Name"),
        ("ManufacturerProductDesignation", "Product Designation"),
    ]

    for field_id, display_name in required_fields:
        field_data = elements.get(field_id, {})
        value = field_data.get("value") if isinstance(field_data, dict) else None

        # For MultiLanguageProperty, check if any translation exists
        if isinstance(value, dict):
            has_value = any(v for v in value.values() if v)
        else:
            has_value = value not in (None, "")

        if has_value:
            summary.checks.append(
                ConformanceCheck(
                    name=f"IDTA 02006: {display_name}",
                    status="pass",
                    message=f"{display_name} is provided",
                )
            )
        else:
            summary.checks.append(
                ConformanceCheck(
                    name=f"IDTA 02006: {display_name}",
                    status="fail",
                    message=f"{display_name} is MANDATORY but not provided",
                )
            )


def _check_pcf_requirements(
    schema: dict[str, Any],
    form_data: dict[str, Any],
    summary: ConformanceSummary,
) -> None:
    """
    Check IDTA 02023 Product Carbon Footprint requirements.

    Delegates to existing PCF validator for detailed checks,
    but adds summary-level status here.
    """
    # Import PCF validator to avoid circular imports
    try:
        from app.schemas.pcf import PCFValidateRequest
        from app.services.pcf import validate_pcf

        result = validate_pcf(
            PCFValidateRequest(
                form_data=form_data,
                template_schema=schema,
            )
        )

        if result.valid:
            summary.checks.append(
                ConformanceCheck(
                    name="IDTA 02023: PCF Validation",
                    status="pass",
                    message=f"PCF validation passed (completeness: {result.completeness_score:.0%})",
                )
            )
        else:
            summary.checks.append(
                ConformanceCheck(
                    name="IDTA 02023: PCF Validation",
                    status="fail",
                    message=f"PCF validation failed with {len(result.errors)} error(s)",
                )
            )

    except ImportError:
        summary.checks.append(
            ConformanceCheck(
                name="IDTA 02023: PCF Validation",
                status="info",
                message="PCF validator not available",
            )
        )


def _truncate(text: str, max_length: int) -> str:
    """Truncate text with ellipsis if too long."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."
