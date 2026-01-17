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
    if not schema_elements:
        return _has_value_in_form_elements(form_elements, field_name, semantic_id)

    for schema_element in schema_elements:
        element_id = schema_element.get("idShort")
        form_element = (
            form_elements.get(element_id) if element_id and form_elements else None
        )
        if _has_value_in_element(
            schema_element,
            form_element,
            field_name,
            semantic_id,
        ):
            return True
    return _has_value_in_form_elements(form_elements, field_name, semantic_id)


def _has_value_in_element(
    schema_element: dict[str, Any],
    form_element: dict[str, Any] | None,
    field_name: str,
    semantic_id: str,
) -> bool:
    if _matches_field(schema_element, form_element, field_name, semantic_id):
        if _element_has_value(form_element):
            return True

    # Recurse into collections
    for child in schema_element.get("elements", []) or []:
        child_id = child.get("idShort")
        child_form = (
            (form_element or {}).get("elements", {}).get(child_id)
            if child_id
            else None
        )
        if _has_value_in_element(child, child_form, field_name, semantic_id):
            return True

    # Recurse into entity statements
    for stmt in schema_element.get("statements", []) or []:
        stmt_id = stmt.get("idShort")
        stmt_form = (
            (form_element or {}).get("statements", {}).get(stmt_id)
            if stmt_id
            else None
        )
        if _has_value_in_element(stmt, stmt_form, field_name, semantic_id):
            return True

    # Recurse into list items
    item_template = schema_element.get("itemTemplate")
    item_schemas = schema_element.get("items") or []
    form_items = (form_element or {}).get("items") or []
    if item_template or item_schemas:
        for index, item_form in enumerate(form_items):
            item_schema = None
            if item_schemas and index < len(item_schemas):
                item_schema = item_schemas[index]
            else:
                item_schema = item_template
            if item_schema and _has_value_in_element(
                item_schema, item_form, field_name, semantic_id
            ):
                return True

    return False


def _matches_field(
    schema_element: dict[str, Any],
    form_element: dict[str, Any] | None,
    field_name: str,
    semantic_id: str,
) -> bool:
    schema_semantic_id = schema_element.get("semanticId") or ""
    form_semantic_id = (form_element or {}).get("semanticId") or ""
    if semantic_id and (
        semantic_id in schema_semantic_id or semantic_id in form_semantic_id
    ):
        return True

    id_short = schema_element.get("idShort") or ""
    if id_short.lower() == field_name.lower():
        return True

    return False


def _element_has_value(element: dict[str, Any] | None) -> bool:
    if not element:
        return False

    if "value" in element and _is_non_empty_value(element.get("value")):
        return True

    if _is_non_empty_value(element.get("min")) or _is_non_empty_value(
        element.get("max")
    ):
        return True

    items = element.get("items")
    if items and len(items) > 0:
        return True

    elements = element.get("elements") or {}
    for child in elements.values():
        if _element_has_value(child):
            return True

    statements = element.get("statements") or {}
    for child in statements.values():
        if _element_has_value(child):
            return True

    return False


def _has_value_in_form_elements(
    form_elements: dict[str, Any],
    field_name: str,
    semantic_id: str,
) -> bool:
    for key, element in (form_elements or {}).items():
        if key.lower() == field_name.lower() and _element_has_value(element):
            return True
        if semantic_id and semantic_id in ((element or {}).get("semanticId") or ""):
            if _element_has_value(element):
                return True
        if isinstance(element, dict):
            if _has_value_in_form_elements(
                element.get("elements") or {}, field_name, semantic_id
            ):
                return True
            if _has_value_in_form_elements(
                element.get("statements") or {}, field_name, semantic_id
            ):
                return True
            for item in element.get("items") or []:
                if semantic_id and semantic_id in ((item or {}).get("semanticId") or ""):
                    if _element_has_value(item):
                        return True
                if isinstance(item, dict):
                    if _has_value_in_form_elements(
                        item.get("elements") or {}, field_name, semantic_id
                    ):
                        return True
                    if _has_value_in_form_elements(
                        item.get("statements") or {}, field_name, semantic_id
                    ):
                        return True
    return False


def _is_non_empty_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, dict):
        return any(_is_non_empty_value(v) for v in value.values())
    if isinstance(value, list):
        return len(value) > 0
    return True
