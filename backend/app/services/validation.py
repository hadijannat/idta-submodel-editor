"""
Shared validation helpers for submodel form data.

Keeps API validation logic consistent across validate/export/hydrate endpoints.
"""

import re
from typing import Any

from app.schemas.form_data import ValidationError

_URI_SCHEME_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:[^\s]+$")
_IRDI_PATTERN = re.compile(r"^\d{4}-\d#\d{2}-[A-Z]{3}\d{3}#\d{3}$")


def validate_form_data(
    schema: dict[str, Any],
    form_data: dict[str, Any],
) -> tuple[list[ValidationError], list[ValidationError]]:
    """
    Validate form data against a parsed UI schema.

    Returns:
        (errors, warnings)
    """
    errors: list[ValidationError] = []
    warnings: list[ValidationError] = []

    _validate_elements(
        schema.get("elements", []),
        form_data.get("elements", {}),
        errors,
        warnings,
        "",
    )

    return errors, warnings


def _validate_elements(
    schema_elements: list[dict[str, Any]],
    form_elements: dict[str, Any] | None,
    errors: list[ValidationError],
    warnings: list[ValidationError],
    path: str,
) -> None:
    """Recursively validate form elements against schema."""
    if not isinstance(form_elements, dict):
        form_elements = {}

    for schema_elem in schema_elements:
        id_short = schema_elem["idShort"]
        elem_path = f"{path}.{id_short}" if path else id_short
        form_elem = form_elements.get(id_short)
        _validate_element(schema_elem, form_elem, errors, warnings, elem_path)


def _validate_element(
    schema_elem: dict[str, Any],
    form_elem: dict[str, Any] | None,
    errors: list[ValidationError],
    warnings: list[ValidationError],
    elem_path: str,
) -> None:
    """Validate a single element and recurse into nested structures."""
    cardinality = schema_elem.get("cardinality", "[1]")
    min_items, max_items = _parse_cardinality(cardinality)

    if min_items >= 1 and form_elem is None:
        errors.append(
            ValidationError(
                field=elem_path,
                message=f"Required field '{schema_elem['idShort']}' is missing",
                code="required",
            )
        )
        return

    if form_elem is None:
        return

    model_type = schema_elem.get("modelType")

    if model_type == "SubmodelElementCollection":
        nested_schema = schema_elem.get("elements", [])
        nested_form = form_elem.get("elements") or {}
        _validate_elements(nested_schema, nested_form, errors, warnings, elem_path)

    elif model_type == "SubmodelElementList":
        items_raw = form_elem.get("items")
        items = items_raw if isinstance(items_raw, list) else []

        if min_items >= 1 and len(items) == 0:
            errors.append(
                ValidationError(
                    field=elem_path,
                    message="At least one item is required",
                    code="min_items",
                )
            )
        if max_items is not None and len(items) > max_items:
            errors.append(
                ValidationError(
                    field=elem_path,
                    message=f"At most {max_items} item(s) are allowed",
                    code="max_items",
                )
            )

        item_template = schema_elem.get("itemTemplate")
        if item_template:
            for idx, item in enumerate(items):
                item_path = f"{elem_path}[{idx}]"
                _validate_element(item_template, item, errors, warnings, item_path)

    elif model_type == "Property":
        value = form_elem.get("value") if form_elem else None
        if min_items >= 1 and (value is None or value == ""):
            errors.append(
                ValidationError(
                    field=elem_path,
                    message="Value is required",
                    code="required_value",
                )
            )
        elif value not in (None, ""):
            value_type = schema_elem.get("valueType")
            if not _value_matches_type(value, value_type):
                errors.append(
                    ValidationError(
                        field=elem_path,
                        message=f"Value does not match expected type {value_type}",
                        code="type_mismatch",
                    )
                )

    elif model_type == "MultiLanguageProperty":
        value_raw = form_elem.get("value")
        value = value_raw if isinstance(value_raw, dict) else {}
        has_translation = any(
            str(v).strip() for v in value.values() if v is not None
        )
        if min_items >= 1 and not has_translation:
            errors.append(
                ValidationError(
                    field=elem_path,
                    message="At least one language translation is required",
                    code="required_translation",
                )
            )
        elif not has_translation:
            warnings.append(
                ValidationError(
                    field=elem_path,
                    message="At least one language translation is recommended",
                    code="recommended_value",
                )
            )

    elif model_type == "Range":
        min_val = form_elem.get("min") if form_elem else None
        max_val = form_elem.get("max") if form_elem else None
        value_type = schema_elem.get("valueType")
        if min_items >= 1 and (min_val in (None, "") or max_val in (None, "")):
            errors.append(
                ValidationError(
                    field=elem_path,
                    message="Both min and max are required",
                    code="required_value",
                )
            )
        else:
            if min_val not in (None, "") and not _value_matches_type(
                min_val, value_type
            ):
                errors.append(
                    ValidationError(
                        field=f"{elem_path}.min",
                        message=f"Min does not match expected type {value_type}",
                        code="type_mismatch",
                    )
                )
            if max_val not in (None, "") and not _value_matches_type(
                max_val, value_type
            ):
                errors.append(
                    ValidationError(
                        field=f"{elem_path}.max",
                        message=f"Max does not match expected type {value_type}",
                        code="type_mismatch",
                    )
                )

    elif model_type == "File":
        value = form_elem.get("value") if form_elem else None
        if min_items >= 1 and (value is None or value == ""):
            errors.append(
                ValidationError(
                    field=elem_path,
                    message="File path or URL is required",
                    code="required_value",
                )
            )

    elif model_type == "ReferenceElement":
        value = form_elem.get("value") if form_elem else None
        if min_items >= 1 and (value is None or value == ""):
            errors.append(
                ValidationError(
                    field=elem_path,
                    message="Reference is required",
                    code="required_value",
                )
            )
        elif value and not _is_valid_reference(value):
            errors.append(
                ValidationError(
                    field=elem_path,
                    message="Reference must be a valid IRI or IRDI",
                    code="invalid_reference",
                )
            )

    elif model_type in ("RelationshipElement", "AnnotatedRelationshipElement"):
        first = form_elem.get("first") if form_elem else None
        second = form_elem.get("second") if form_elem else None
        if min_items >= 1 and (not first or not second):
            errors.append(
                ValidationError(
                    field=elem_path,
                    message="Both relationship references are required",
                    code="required_value",
                )
            )

        if model_type == "AnnotatedRelationshipElement":
            annotations_schema = schema_elem.get("annotations", []) or []
            annotations_form_raw = form_elem.get("annotations")
            annotations_form = (
                annotations_form_raw if isinstance(annotations_form_raw, list) else []
            )
            for idx, annotation_schema in enumerate(annotations_schema):
                if idx >= len(annotations_form):
                    continue
                annotation_path = f"{elem_path}.annotations[{idx}]"
                _validate_element(
                    annotation_schema,
                    annotations_form[idx],
                    errors,
                    warnings,
                    annotation_path,
                )

    elif model_type == "Entity":
        nested_schema = schema_elem.get("statements", []) or []
        nested_form = form_elem.get("statements") or {}
        _validate_elements(nested_schema, nested_form, errors, warnings, elem_path)


def _normalize_cardinality_value(value: str | None) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None
    mapping = {
        "ZeroToOne": "[0..1]",
        "ZeroToMany": "[0..*]",
        "OneToMany": "[1..*]",
        "One": "[1]",
        "Zero": "[0]",
    }
    if value in mapping:
        return mapping[value]
    if value.startswith("[") and value.endswith("]"):
        return value
    if ".." in value:
        return f"[{value}]"
    if value.isdigit():
        return f"[{value}]"
    return value


def _parse_cardinality(cardinality: str) -> tuple[int, int | None]:
    normalized = _normalize_cardinality_value(cardinality) or "[1]"
    match = re.match(r"^\[(\d+)(?:\.\.(\d+|\*))?\]$", normalized)
    if not match:
        return (1, 1)

    min_items = int(match.group(1))
    max_group = match.group(2)
    if max_group is None:
        return (min_items, min_items)
    if max_group == "*":
        return (min_items, None)
    return (min_items, int(max_group))


def _value_matches_type(value: Any, value_type: str | None) -> bool:
    if value_type is None:
        return True

    type_str = str(value_type).lower()
    try:
        if "int" in type_str or "integer" in type_str:
            num = float(value)
            return num.is_integer()
        if any(t in type_str for t in ("float", "double", "decimal")):
            float(value)
            return True
        if "bool" in type_str:
            if isinstance(value, bool):
                return True
            return str(value).lower() in ("true", "false", "1", "0", "yes", "no")
        if "datetime" in type_str or "date" in type_str:
            from datetime import date, datetime

            if "datetime" in type_str:
                datetime.fromisoformat(str(value))
            else:
                date.fromisoformat(str(value))
            return True
    except Exception:
        return False

    return True


def _is_valid_reference(value: str) -> bool:
    if not value:
        return True
    normalized = value.strip()
    if not normalized:
        return True
    return bool(_URI_SCHEME_PATTERN.match(normalized) or _IRDI_PATTERN.match(normalized))
