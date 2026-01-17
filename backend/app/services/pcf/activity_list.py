"""PCF activity list schema and hydration helpers."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from basyx.aas import model

PCF_ACTIVITY_LIST_SPEC_ENV_VAR = "PCF_ACTIVITY_LIST_SPEC_PATH"
PCF_ACTIVITY_LIST_INJECTION_ENABLED_ENV = "PCF_ACTIVITY_LIST_INJECTION_ENABLED"
DEFAULT_SPEC_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "pcf_activity_list_spec.json"
)

_REQUIRED_FIELDS = {"activityname", "activityquantity", "activityunit"}

_ACTIVITY_FIELD_ALIASES: dict[str, list[str]] = {
    "name": ["activityname", "name"],
    "category": ["activitycategory", "category", "scope"],
    "quantity": ["activityquantity", "quantity", "amount"],
    "unit": ["activityunit", "unit"],
    "factor_value": ["emissionfactorvalue", "factorvalue", "emissionfactor"],
    "factor_unit": ["emissionfactorunit", "factorunit"],
    "factor_source": ["emissionfactorsource", "factorsource", "source"],
    "factor_region": ["emissionfactorregion", "factorregion", "region"],
    "factor_year": ["emissionfactoryear", "factoryear", "year"],
    "co2e_kg": ["activityco2ekg", "co2ekg", "co2e", "co2eq"],
}

_SPEC_CACHE: dict[str, Any] | None = None


def _activity_list_injection_enabled() -> bool:
    value = os.getenv(PCF_ACTIVITY_LIST_INJECTION_ENABLED_ENV, "true").strip().lower()
    return value in {"1", "true", "yes", "on"}


def load_activity_list_spec() -> dict[str, Any]:
    global _SPEC_CACHE
    if _SPEC_CACHE is not None:
        return _SPEC_CACHE
    path = Path(os.getenv(PCF_ACTIVITY_LIST_SPEC_ENV_VAR) or DEFAULT_SPEC_PATH)
    if not path.exists():
        raise FileNotFoundError(f"PCF activity list spec not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("PCF activity list spec must be a JSON object.")
    _SPEC_CACHE = payload
    return payload


def ensure_activity_list_schema(schema: dict[str, Any]) -> dict[str, Any]:
    if not _activity_list_injection_enabled():
        schema["pcfActivityListInjected"] = False
        return schema

    spec = load_activity_list_spec()
    if schema_has_activity_list(schema, spec):
        schema["pcfActivityListInjected"] = False
        return schema

    list_schema = build_activity_list_schema(spec)
    elements = schema.get("elements")
    if isinstance(elements, list):
        elements.append(list_schema)
    else:
        schema["elements"] = [list_schema]
    schema["pcfActivityListInjected"] = True
    return schema


def schema_has_activity_list(schema: dict[str, Any], spec: dict[str, Any]) -> bool:
    list_spec = spec.get("list", {})
    list_id = (list_spec.get("idShort") or "").lower()
    list_semantic = list_spec.get("semanticId")

    def matches_required_fields(item_template: dict[str, Any] | None) -> bool:
        if not item_template:
            return False
        elements = item_template.get("elements") or []
        ids = {
            normalize_id_short(elem.get("idShort", ""))
            for elem in elements
            if isinstance(elem, dict)
        }
        return _REQUIRED_FIELDS.issubset(ids)

    def walk(elements: list[dict[str, Any]]) -> bool:
        for element in elements:
            if element.get("modelType") == "SubmodelElementList":
                semantic_id = element.get("semanticId")
                if list_semantic and semantic_id and list_semantic in semantic_id:
                    return True
                if list_id and element.get("idShort", "").lower() == list_id:
                    return True
                if matches_required_fields(element.get("itemTemplate")):
                    return True
            for child in element.get("elements") or []:
                if walk([child]):
                    return True
            for child in element.get("statements") or []:
                if walk([child]):
                    return True
            template = element.get("itemTemplate")
            if template and template.get("elements"):
                if walk(template.get("elements")):
                    return True
        return False

    return walk(schema.get("elements") or [])


def build_activity_list_schema(spec: dict[str, Any]) -> dict[str, Any]:
    list_spec = spec.get("list", {})
    item_spec = spec.get("item", {})
    item_elements = [
        build_property_schema(element)
        for element in item_spec.get("elements", [])
        if isinstance(element, dict)
    ]

    return {
        "idShort": list_spec.get("idShort", "PCFActivities"),
        "modelType": "SubmodelElementList",
        "semanticId": list_spec.get("semanticId"),
        "semanticLabel": list_spec.get("semanticLabel"),
        "description": list_spec.get("description"),
        "qualifiers": [],
        "cardinality": list_spec.get("cardinality", "[0..*]"),
        "category": list_spec.get("category"),
        "typeValueListElement": "SubmodelElementCollection",
        "valueTypeListElement": None,
        "semanticIdListElement": list_spec.get("semanticIdListElement"),
        "itemTemplate": {
            "idShort": item_spec.get("idShort", "PCFActivity"),
            "modelType": "SubmodelElementCollection",
            "semanticId": item_spec.get("semanticId"),
            "semanticLabel": item_spec.get("semanticLabel"),
            "description": item_spec.get("description"),
            "qualifiers": [],
            "cardinality": "[1]",
            "category": item_spec.get("category"),
            "elements": item_elements,
        },
    }


def build_property_schema(element_spec: dict[str, Any]) -> dict[str, Any]:
    value_type = element_spec.get("valueType", "xs:string")
    input_type = element_spec.get("inputType")
    if input_type is None and value_type in {"xs:int", "xs:integer", "xs:double", "xs:float"}:
        input_type = "number"

    return {
        "idShort": element_spec.get("idShort"),
        "modelType": "Property",
        "semanticId": element_spec.get("semanticId"),
        "semanticLabel": element_spec.get("semanticLabel"),
        "description": element_spec.get("description"),
        "qualifiers": [],
        "cardinality": element_spec.get("cardinality", "[0..1]"),
        "category": element_spec.get("category"),
        "valueType": value_type,
        "inputType": input_type,
    }


def build_activity_list_form_items(
    activities: list[dict[str, Any]],
    spec: dict[str, Any],
) -> list[dict[str, Any]]:
    item_spec = spec.get("item", {})
    item_elements = item_spec.get("elements", []) or []
    items: list[dict[str, Any]] = []

    for activity in activities:
        if not isinstance(activity, dict):
            continue
        elements: dict[str, Any] = {}
        for element in item_elements:
            if not isinstance(element, dict):
                continue
            id_short = element.get("idShort")
            if not id_short:
                continue
            normalized = normalize_id_short(id_short)
            value = resolve_activity_value(normalized, activity)
            elements[id_short] = {
                "value": value if value is not None else "",
                "semanticId": element.get("semanticId"),
                "valueId": element.get("valueId"),
                "semanticIdListElement": element.get("semanticIdListElement"),
            }
        items.append({"elements": elements, "semanticId": item_spec.get("semanticId")})

    return items


def resolve_activity_value(normalized_id_short: str, activity: dict[str, Any]) -> Any:
    for key, aliases in _ACTIVITY_FIELD_ALIASES.items():
        if normalized_id_short in aliases:
            return activity.get(key)
    return None


def normalize_id_short(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def ensure_activity_list_in_submodel(
    submodel: model.Submodel,
    form_data: dict[str, Any],
) -> None:
    if not _activity_list_injection_enabled():
        return

    spec = load_activity_list_spec()
    list_spec = spec.get("list", {})
    list_id = list_spec.get("idShort", "PCFActivities")

    form_elements = (form_data or {}).get("elements", {})
    metadata = (form_data or {}).get("metadata", {})
    pcf_meta = metadata.get("pcf") if isinstance(metadata, dict) else None

    if list_id not in form_elements and not pcf_meta:
        return

    if list_id not in form_elements and pcf_meta:
        activities = pcf_meta.get("activities", []) if isinstance(pcf_meta, dict) else []
        list_payload = {"items": build_activity_list_form_items(activities, spec)}
        list_semantic_id = list_spec.get("semanticIdListElement")
        if list_semantic_id:
            list_payload["semanticIdListElement"] = list_semantic_id
        form_elements[list_id] = list_payload
        form_data.setdefault("elements", {})[list_id] = form_elements[list_id]

    existing = None
    for element in submodel.submodel_element:
        if getattr(element, "id_short", None) == list_id:
            existing = element
            break

    if existing is None:
        submodel.submodel_element.add(build_activity_list_element(spec))
        return

    if isinstance(existing, model.SubmodelElementList) and len(list(existing.value)) == 0:
        template_item = build_activity_list_item(spec)
        if template_item is not None:
            existing.value.add(template_item)


def build_activity_list_element(spec: dict[str, Any]) -> model.SubmodelElementList:
    list_spec = spec.get("list", {})
    list_id = list_spec.get("idShort", "PCFActivities")

    list_element = model.SubmodelElementList(
        id_short=list_id,
        type_value_list_element=model.SubmodelElementCollection,
        value_type_list_element=None,
        value=(),
        order_relevant=True,
    )

    semantic_id = list_spec.get("semanticId")
    if semantic_id:
        list_element.semantic_id = model.ExternalReference(
            key=(model.Key(model.KeyTypes.GLOBAL_REFERENCE, semantic_id),)
        )

    template_item = build_activity_list_item(spec)
    if template_item is not None:
        list_element.value.add(template_item)

    return list_element


def build_activity_list_item(spec: dict[str, Any]) -> model.SubmodelElementCollection | None:
    item_spec = spec.get("item", {})
    item_elements = item_spec.get("elements", []) or []

    elements: list[model.SubmodelElement] = []
    for element_spec in item_elements:
        if not isinstance(element_spec, dict):
            continue
        id_short = element_spec.get("idShort")
        if not id_short:
            continue
        value_type = _value_type_from_string(element_spec.get("valueType"))
        prop = model.Property(id_short=id_short, value_type=value_type)
        semantic_id = element_spec.get("semanticId")
        if semantic_id:
            prop.semantic_id = model.ExternalReference(
                key=(model.Key(model.KeyTypes.GLOBAL_REFERENCE, semantic_id),)
            )
        elements.append(prop)

    if not elements:
        return None

    collection = model.SubmodelElementCollection(id_short=None, value=tuple(elements))
    semantic_id = item_spec.get("semanticId")
    if semantic_id:
        collection.semantic_id = model.ExternalReference(
            key=(model.Key(model.KeyTypes.GLOBAL_REFERENCE, semantic_id),)
        )
    return collection


def _value_type_from_string(value_type: str | None):
    if not value_type:
        return model.datatypes.String
    normalized = value_type.lower()
    if normalized in {"xs:int", "xs:integer"}:
        return model.datatypes.Int
    if normalized in {"xs:double", "xs:float"}:
        return model.datatypes.Double
    return model.datatypes.String
