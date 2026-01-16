"""Mapping application logic for Smart Mapper."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from app.schemas.mapper import MappingItem, MapperDiagnostic


@dataclass
class MappingContext:
    row_index: int | None


def _normalize_value(value: Any, trim: bool) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip() if trim else value
        return text if text != "" else None
    return value


def _parse_boolean(value: str, true_values: set[str], false_values: set[str]) -> bool | None:
    lowered = value.lower()
    if lowered in true_values:
        return True
    if lowered in false_values:
        return False
    return None


def _parse_number(value: str, decimal: str | None, thousands: str | None) -> float | None:
    text = value
    if thousands:
        text = text.replace(thousands, "")
    if decimal and decimal != ".":
        text = text.replace(decimal, ".")
    return float(text)


def _parse_date(value: str, date_format: str | None) -> str:
    if date_format:
        parsed = datetime.strptime(value, date_format)
        return parsed.isoformat()
    return datetime.fromisoformat(value).isoformat()


def convert_value(value: Any, mapping: MappingItem) -> tuple[Any, str | None]:
    transform = mapping.transform
    trim = transform.trim if transform else True
    default_value = transform.default_value if transform else None
    decimal = transform.decimal if transform else "."
    thousands = transform.thousands if transform else None
    date_format = transform.date_format if transform else None
    true_values = set(
        v.lower()
        for v in (
            transform.true_values
            if transform and transform.true_values
            else ["true", "yes", "1"]
        )
    )
    false_values = set(
        v.lower()
        for v in (
            transform.false_values
            if transform and transform.false_values
            else ["false", "no", "0"]
        )
    )

    value = _normalize_value(value, trim)
    if value is None:
        return default_value, None

    if mapping.target.value_type is None:
        return value, None

    value_type = mapping.target.value_type.lower()
    try:
        if "boolean" in value_type:
            if isinstance(value, bool):
                return value, None
            parsed = _parse_boolean(str(value), true_values, false_values)
            if parsed is None:
                return value, "boolean_parse"
            return parsed, None

        if any(token in value_type for token in ["int", "integer"]):
            if isinstance(value, int):
                return value, None
            parsed = _parse_number(str(value), decimal, thousands)
            return int(parsed), None

        if any(token in value_type for token in ["float", "double", "decimal"]):
            if isinstance(value, (int, float)):
                return float(value), None
            parsed = _parse_number(str(value), decimal, thousands)
            return parsed, None

        if "datetime" in value_type:
            if isinstance(value, datetime):
                return value.isoformat(), None
            if isinstance(value, date):
                return datetime.combine(value, datetime.min.time()).isoformat(), None
            return _parse_date(str(value), date_format), None

        if value_type.endswith("date"):
            if isinstance(value, date):
                return value.isoformat(), None
            parsed = _parse_date(str(value), date_format)
            return parsed.split("T")[0], None

        return str(value), None

    except Exception:
        return value, "parse_error"


def set_form_value(
    form_elements: dict,
    path: list[str],
    mapping: MappingItem,
    value: Any,
) -> None:
    current = form_elements
    for segment in path[:-1]:
        node = current.setdefault(segment, {})
        if "elements" not in node:
            node["elements"] = {}
        current = node["elements"]

    leaf = current.setdefault(path[-1], {})
    target = mapping.target

    if target.element_type == "MultiLanguageProperty":
        language = target.language or "en"
        container = leaf.setdefault("value", {})
        if isinstance(container, dict):
            container[language] = value
        else:
            leaf["value"] = {language: value}
        return

    field = target.field
    if target.element_type == "Range":
        field = field or "min"
        leaf[field] = value
        return

    if target.element_type == "File":
        field = field or "value"
        leaf[field] = value
        return

    if target.element_type in {"ReferenceElement", "RelationshipElement"}:
        field = field or "value"
        leaf[field] = value
        return

    leaf[field or "value"] = value


def apply_mapping(
    row: list[Any],
    mappings: list[MappingItem],
    header_map: dict[str, int],
    row_index: int | None,
) -> tuple[dict, list[MapperDiagnostic]]:
    form_data = {"elements": {}}
    diagnostics: list[MapperDiagnostic] = []

    for mapping in mappings:
        source = mapping.source
        col_index = source.column_index
        if col_index is None:
            col_index = header_map.get(source.column_name)
        if col_index is None:
            diagnostics.append(
                MapperDiagnostic(
                    severity="error",
                    row_index=row_index,
                    source_column=source.column_name,
                    target_path=mapping.target.id_short_path,
                    code="missing_column",
                    message=f"Column '{source.column_name}' not found",
                )
            )
            continue
        if col_index >= len(row):
            diagnostics.append(
                MapperDiagnostic(
                    severity="error",
                    row_index=row_index,
                    source_column=source.column_name,
                    target_path=mapping.target.id_short_path,
                    code="column_out_of_range",
                    message=f"Column index {col_index} out of range",
                )
            )
            continue
        raw_value = row[col_index]
        value, error_code = convert_value(raw_value, mapping)
        if mapping.required and (value is None or value == ""):
            diagnostics.append(
                MapperDiagnostic(
                    severity="error",
                    row_index=row_index,
                    source_column=source.column_name,
                    target_path=mapping.target.id_short_path,
                    code="required_missing",
                    message="Required value missing",
                )
            )
            continue
        if error_code:
            diagnostics.append(
                MapperDiagnostic(
                    severity="warning",
                    row_index=row_index,
                    source_column=source.column_name,
                    target_path=mapping.target.id_short_path,
                    code=error_code,
                    message="Value could not be parsed cleanly",
                    sample=str(raw_value) if raw_value is not None else None,
                )
            )
        path = [segment for segment in mapping.target.id_short_path.split(".") if segment]
        if not path:
            diagnostics.append(
                MapperDiagnostic(
                    severity="error",
                    row_index=row_index,
                    source_column=source.column_name,
                    code="invalid_target",
                    message="Invalid target path",
                )
            )
            continue
        set_form_value(form_data["elements"], path, mapping, value)

    return form_data, diagnostics
