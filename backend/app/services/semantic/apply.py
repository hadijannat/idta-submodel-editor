"""Semantic apply-preview helpers."""

from __future__ import annotations

from app.schemas.semantic import SemanticEntry


ECLASS_DATATYPE_MAP: dict[str, tuple[str, str | None]] = {
    "STRING_TRANSLATABLE": ("MultiLanguageProperty", "xs:string"),
    "STRING": ("Property", "xs:string"),
    "REAL_MEASURE": ("Property", "xs:double"),
    "REAL": ("Property", "xs:double"),
    "INTEGER_MEASURE": ("Property", "xs:int"),
    "INTEGER": ("Property", "xs:int"),
    "BOOLEAN": ("Property", "xs:boolean"),
    "DATE": ("Property", "xs:date"),
    "DATE_TIME": ("Property", "xs:dateTime"),
}


def preview_application(
    entry: SemanticEntry,
    current_element_type: str | None,
    current_value_type: str | None,
    prefer_iri: bool,
) -> tuple[str, str | None, str | None, list[str], list[str]]:
    warnings: list[str] = []
    notes: list[str] = []

    semantic_id = entry.canonicalIri if prefer_iri and entry.canonicalIri else entry.canonicalId

    suggested_element_type: str | None = None
    suggested_value_type: str | None = None

    if entry.datatypeHint:
        mapping = ECLASS_DATATYPE_MAP.get(entry.datatypeHint.upper())
        if mapping:
            suggested_element_type, suggested_value_type = mapping
            if current_element_type and current_element_type != suggested_element_type:
                warnings.append(
                    f"Dictionary datatype suggests {suggested_element_type}"
                )
            if current_value_type and suggested_value_type and current_value_type != suggested_value_type:
                warnings.append(
                    f"Dictionary datatype suggests valueType {suggested_value_type}"
                )
        else:
            notes.append(
                f"No datatype mapping available for {entry.datatypeHint}"
            )

    return semantic_id, suggested_element_type, suggested_value_type, warnings, notes
