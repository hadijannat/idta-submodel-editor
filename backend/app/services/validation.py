"""
Shared validation helpers for submodel form data.

Keeps API validation logic consistent across validate/export/hydrate endpoints.
"""

import re
from typing import Any

from app.schemas.form_data import ValidationError
from app.services.format_rules import check_format
from app.services.template_constraints import normalize_cardinality

# Longest value a template-supplied regular expression is applied to. Keeps
# pathological patterns from stalling a request.
_MAX_PATTERN_INPUT = 2000

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

    _validate_either_or_groups(schema_elements, form_elements, errors, path)


def _validate_either_or_groups(
    schema_elements: list[dict[str, Any]],
    form_elements: dict[str, Any],
    errors: list[ValidationError],
    path: str,
) -> None:
    """
    Enforce SMT/EitherOr: of the sibling elements sharing a group, at least
    one has to be provided.
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    for schema_elem in schema_elements:
        group = schema_elem.get("eitherOr")
        if group:
            groups.setdefault(str(group), []).append(schema_elem)

    for group, members in groups.items():
        if len(members) < 2:
            continue
        if any(
            _has_content(member, form_elements.get(member["idShort"]))
            for member in members
        ):
            continue
        names = ", ".join(member["idShort"] for member in members)
        first_path = (
            f"{path}.{members[0]['idShort']}" if path else members[0]["idShort"]
        )
        errors.append(
            ValidationError(
                field=first_path,
                message=f"At least one of these alternatives is required: {names}",
                code="either_or",
            )
        )


def _has_content(schema_elem: dict[str, Any], form_elem: Any) -> bool:
    """Whether the user provided any value for an element (recursively)."""
    if not isinstance(form_elem, dict):
        return False
    model_type = schema_elem.get("modelType")

    if model_type == "SubmodelElementCollection":
        nested = form_elem.get("elements") or {}
        return any(
            _has_content(child, nested.get(child["idShort"]))
            for child in schema_elem.get("elements") or []
        )
    if model_type == "Entity":
        nested = form_elem.get("statements") or {}
        return any(
            _has_content(child, nested.get(child["idShort"]))
            for child in schema_elem.get("statements") or []
        )
    if model_type == "SubmodelElementList":
        items = form_elem.get("items")
        return isinstance(items, list) and len(items) > 0
    if model_type == "MultiLanguageProperty":
        value = form_elem.get("value")
        return isinstance(value, dict) and any(
            str(text).strip() for text in value.values() if text is not None
        )
    if model_type == "Range":
        return not (
            _is_blank_value(form_elem.get("min")) and _is_blank_value(form_elem.get("max"))
        )
    if model_type in ("RelationshipElement", "AnnotatedRelationshipElement"):
        return bool(form_elem.get("first") or form_elem.get("second"))
    value = form_elem.get("value")
    if isinstance(value, bool):
        return True
    return not _is_blank_value(value)


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

        # The cardinality of a list states how often the list occurs, not how
        # many items it holds: a list that occurs once may hold any number of
        # items unless its item declares a bound.
        if max_items is not None and max_items <= 1:
            item_schema = schema_elem.get("itemTemplate") or {}
            _, item_max = _parse_cardinality(item_schema.get("cardinality", "[1]"))
            max_items = (
                item_max if item_schema and item_max is not None and item_max > 1 else None
            )

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
        if min_items >= 1 and _is_blank_value(value):
            errors.append(
                ValidationError(
                    field=elem_path,
                    message="Value is required",
                    code="required_value",
                )
            )
        elif not _is_blank_value(value):
            value_type = schema_elem.get("valueType")
            if not _value_matches_type(value, value_type):
                errors.append(
                    ValidationError(
                        field=elem_path,
                        message=f"Value does not match expected type {value_type}",
                        code="type_mismatch",
                    )
                )
            else:
                _validate_property_requirements(
                    schema_elem, value, errors, warnings, elem_path
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
        else:
            provided = {
                _base_language(lang)
                for lang, text in value.items()
                if text is not None and str(text).strip()
            }
            missing = [
                lang
                for lang in schema_elem.get("requiredLanguages") or []
                if _base_language(lang) not in provided
            ]
            if missing:
                errors.append(
                    ValidationError(
                        field=elem_path,
                        message=(
                            "The template requires a translation for: "
                            + ", ".join(missing)
                        ),
                        code="required_language",
                    )
                )
            examples = {str(e).strip() for e in schema_elem.get("exampleValues") or []}
            if examples and any(
                str(text).strip() in examples
                for text in value.values()
                if text is not None and str(text).strip()
            ):
                warnings.append(
                    ValidationError(
                        field=elem_path,
                        message="Still contains the example text from the template",
                        code="example_value",
                    )
                )

    elif model_type == "Range":
        min_val = form_elem.get("min") if form_elem else None
        max_val = form_elem.get("max") if form_elem else None
        value_type = schema_elem.get("valueType")
        if min_items >= 1 and (_is_blank_value(min_val) or _is_blank_value(max_val)):
            errors.append(
                ValidationError(
                    field=elem_path,
                    message="Both min and max are required",
                    code="required_value",
                )
            )
        else:
            if not _is_blank_value(min_val) and not _value_matches_type(
                min_val, value_type
            ):
                errors.append(
                    ValidationError(
                        field=f"{elem_path}.min",
                        message=f"Min does not match expected type {value_type}",
                        code="type_mismatch",
                    )
                )
            if not _is_blank_value(max_val) and not _value_matches_type(
                max_val, value_type
            ):
                errors.append(
                    ValidationError(
                        field=f"{elem_path}.max",
                        message=f"Max does not match expected type {value_type}",
                        code="type_mismatch",
                    )
                )
            low, high = _as_number(min_val), _as_number(max_val)
            if low is not None and high is not None and low > high:
                errors.append(
                    ValidationError(
                        field=elem_path,
                        message="Min must not be greater than max",
                        code="range_order",
                    )
                )
            for bound_name, bound in (("min", low), ("max", high)):
                message = _range_violation(schema_elem, bound)
                if message:
                    errors.append(
                        ValidationError(
                            field=f"{elem_path}.{bound_name}",
                            message=message,
                            code="out_of_range",
                        )
                    )

    elif model_type == "File":
        value = form_elem.get("value") if form_elem else None
        if min_items >= 1 and _is_blank_value(value):
            errors.append(
                ValidationError(
                    field=elem_path,
                    message="File path or URL is required",
                    code="required_value",
                )
            )

    elif model_type == "ReferenceElement":
        value = form_elem.get("value") if form_elem else None
        if min_items >= 1 and _is_blank_value(value):
            errors.append(
                ValidationError(
                    field=elem_path,
                    message="Reference is required",
                    code="required_value",
                )
            )
        elif _is_blank_value(value):
            return
        elif not _is_valid_reference(value):
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
    return normalize_cardinality(value)


def _base_language(lang: str) -> str:
    return str(lang).strip().lower().split("-", 1)[0]


def _as_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _range_violation(schema_elem: dict[str, Any], number: float | None) -> str | None:
    """Check a number against SMT/AllowedRange and the XSD type bounds."""
    if number is None:
        return None
    for key, label in (("allowedRange", "allowed range"), ("constraints", "range of the value type")):
        bounds = schema_elem.get(key)
        if not isinstance(bounds, dict):
            continue
        low, high = bounds.get("min"), bounds.get("max")
        if low is not None and number < low:
            return f"Value must be at least {low} ({label})"
        if high is not None and number > high:
            return f"Value must be at most {high} ({label})"
    return None


def _validate_property_requirements(
    schema_elem: dict[str, Any],
    value: Any,
    errors: list[ValidationError],
    warnings: list[ValidationError],
    elem_path: str,
) -> None:
    """Check a Property value against the requirements of the template."""
    text = str(value).strip() if not isinstance(value, bool) else str(value).lower()

    allowed = [
        str(option.get("value"))
        for option in schema_elem.get("allowedValues") or []
        if isinstance(option, dict) and option.get("value") is not None
    ]
    if allowed:
        is_boolean = isinstance(value, bool) or "bool" in str(
            schema_elem.get("valueType") or ""
        ).lower()
        matches = text in allowed or (
            is_boolean and text.lower() in {option.lower() for option in allowed}
        )
        if not matches:
            preview = ", ".join(allowed[:8]) + (" ..." if len(allowed) > 8 else "")
            if schema_elem.get("allowedValuesStrict"):
                errors.append(
                    ValidationError(
                        field=elem_path,
                        message=f"Value must be one of: {preview}",
                        code="not_allowed",
                    )
                )
            else:
                warnings.append(
                    ValidationError(
                        field=elem_path,
                        message=f"Value is not in the value list of the template ({preview})",
                        code="not_in_value_list",
                    )
                )

    pattern = schema_elem.get("pattern")
    if pattern and len(text) <= _MAX_PATTERN_INPUT:
        try:
            if re.fullmatch(pattern, text) is None:
                errors.append(
                    ValidationError(
                        field=elem_path,
                        message=f"Value does not match the pattern required by the template: {pattern}",
                        code="pattern_mismatch",
                    )
                )
        except re.error:
            pass

    range_message = _range_violation(schema_elem, _as_number(value))
    if range_message:
        errors.append(
            ValidationError(field=elem_path, message=range_message, code="out_of_range")
        )

    max_length = schema_elem.get("maxLength")
    if isinstance(max_length, int) and isinstance(value, str) and len(text) > max_length:
        warnings.append(
            ValidationError(
                field=elem_path,
                message=(
                    f"Value is longer than the value format "
                    f"{schema_elem.get('valueFormat') or ''} allows ({max_length} characters)"
                ).replace("  ", " "),
                code="value_format",
            )
        )

    hint = schema_elem.get("formatHint")
    if isinstance(hint, dict) and hint.get("id") and not allowed:
        problem = check_format(hint["id"], value)
        if problem:
            warnings.append(
                ValidationError(
                    field=elem_path,
                    message=f"Value {problem}",
                    code="format_hint",
                )
            )

    if not allowed and not isinstance(value, bool) and text not in ("0", "1"):
        examples = {str(e).strip() for e in schema_elem.get("exampleValues") or []}
        if text in examples:
            warnings.append(
                ValidationError(
                    field=elem_path,
                    message="Still contains the example value from the template",
                    code="example_value",
                )
            )


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
    normalized_value = value.strip() if isinstance(value, str) else value
    try:
        if "int" in type_str or "integer" in type_str:
            num = float(normalized_value)
            return num.is_integer()
        if any(t in type_str for t in ("float", "double", "decimal")):
            float(normalized_value)
            return True
        if "bool" in type_str:
            if isinstance(normalized_value, bool):
                return True
            return str(normalized_value).lower() in ("true", "false", "1", "0", "yes", "no")
        if "gyearmonth" in type_str:
            return bool(
                re.match(r"^-?\d{4,}-(0[1-9]|1[0-2])(Z|[+-]\d{2}:\d{2})?$", str(normalized_value))
            )
        if "gyear" in type_str:
            return bool(re.match(r"^-?\d{4,}(Z|[+-]\d{2}:\d{2})?$", str(normalized_value)))
        if "duration" in type_str:
            return bool(
                re.match(
                    r"^-?P(?=\d|T\d)(\d+Y)?(\d+M)?(\d+D)?(T(?=\d)(\d+H)?(\d+M)?(\d+(\.\d+)?S)?)?$",
                    str(normalized_value),
                )
            )
        if "datetime" in type_str or "date" in type_str:
            from datetime import date, datetime

            if "datetime" in type_str:
                datetime.fromisoformat(str(normalized_value))
            else:
                # xs:date allows an optional time zone suffix
                date.fromisoformat(
                    re.sub(r"(Z|[+-]\d{2}:\d{2})$", "", str(normalized_value))
                )
            return True
        if "time" in type_str:
            from datetime import time

            time.fromisoformat(str(normalized_value))
            return True
    except Exception:
        return False

    return True


def _is_valid_reference(value: str) -> bool:
    if not value:
        return False
    normalized = value.strip()
    if not normalized:
        return False
    return bool(_URI_SCHEME_PATTERN.match(normalized) or _IRDI_PATTERN.match(normalized))


def _is_blank_value(value: Any) -> bool:
    if value is None:
        return True
    return isinstance(value, str) and value.strip() == ""
