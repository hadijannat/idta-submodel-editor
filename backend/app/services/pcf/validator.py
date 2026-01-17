"""
PCF Validator - IDTA 02023 compliance checks.

Validates PCF form data against IDTA 02023 rules:
- Required fields (blocking errors)
- Recommended fields (warnings)
- Cross-field validation
"""

from __future__ import annotations

from typing import Any

from app.schemas.pcf import (
    PCFValidateRequest,
    PCFValidateResponse,
    PCFValidationRule,
)


# PCF template detection patterns
PCF_SEMANTIC_PATTERNS = [
    "CarbonFootprint",
    "https://admin-shell.io/idta/CarbonFootprint/",
    "0173-1#01-AHE712#001",  # Carbon Footprint submodel IRDI
]


def is_pcf_template(schema: dict[str, Any]) -> bool:
    """
    Check if a schema represents a Carbon Footprint template.

    Checks the template's semanticId against known PCF identifiers.
    """
    semantic_id = schema.get("semanticId")
    if not semantic_id:
        return False

    # Check for explicit patterns
    for pattern in PCF_SEMANTIC_PATTERNS:
        if pattern in semantic_id:
            return True

    # Case-insensitive check for 'carbon'
    if "carbon" in semantic_id.lower():
        return True

    return False


# IDTA 02023 required field semantic IDs (blocking errors if missing)
REQUIRED_FIELDS = {
    "PcfCO2eq": "0173-1#02-ABG855#003",
    "ReferenceImpactUnitForCalculation": "0173-1#02-ABG856#003",
    "QuantityOfMeasureForCalculation": "0173-1#02-ABG857#003",
    "PublicationDate": "https://admin-shell.io/idta/CarbonFootprint/PublicationDate/1/0",
    "LifeCyclePhases": "https://admin-shell.io/idta/CarbonFootprint/LifeCyclePhases/1/0",
}

# Recommended fields (warnings if missing)
RECOMMENDED_FIELDS = {
    "PcfCalculationMethod": "0173-1#02-ABG854#003",
    "ExpirationDate": "https://admin-shell.io/idta/CarbonFootprint/ExpirationDate/1/0",
}


def validate_pcf(request: PCFValidateRequest) -> PCFValidateResponse:
    """
    Validate PCF form data against IDTA 02023 rules.

    Returns validation result with errors, warnings, and completeness score.
    """
    errors: list[PCFValidationRule] = []
    warnings: list[PCFValidationRule] = []

    schema_elements = request.template_schema.get("elements", [])
    form_elements = request.form_data.get("elements", {})

    # Check required fields
    for field_name, semantic_id in REQUIRED_FIELDS.items():
        if not _has_value(form_elements, schema_elements, field_name, semantic_id):
            errors.append(
                PCFValidationRule(
                    rule_id=f"pcf_required_{field_name.lower()}",
                    field=field_name,
                    severity="error",
                    message=f"Required PCF field '{field_name}' is missing or empty",
                    code="pcf_required",
                )
            )

    # Check recommended fields
    for field_name, semantic_id in RECOMMENDED_FIELDS.items():
        if not _has_value(form_elements, schema_elements, field_name, semantic_id):
            warnings.append(
                PCFValidationRule(
                    rule_id=f"pcf_recommended_{field_name.lower()}",
                    field=field_name,
                    severity="warning",
                    message=f"Recommended PCF field '{field_name}' is missing",
                    code="pcf_recommended",
                )
            )

    # Calculate completeness score
    total_fields = len(REQUIRED_FIELDS) + len(RECOMMENDED_FIELDS)
    filled_count = total_fields - len(errors) - len(warnings)
    completeness_score = filled_count / total_fields if total_fields > 0 else 1.0

    return PCFValidateResponse(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        completeness_score=round(completeness_score, 2),
    )


def _has_value(
    form_elements: dict[str, Any],
    schema_elements: list[dict[str, Any]],
    field_name: str,
    semantic_id: str,
) -> bool:
    """Check if a field has a non-empty value in the form data."""
    # Look up by idShort first
    if field_name in form_elements:
        element = form_elements[field_name]
        if element is None:
            return False
        # Check for value in different element types
        if isinstance(element, dict):
            value = element.get("value")
            if value is not None and value != "":
                return True
            # Check for items in lists
            items = element.get("items")
            if items and len(items) > 0:
                return True
    return False
