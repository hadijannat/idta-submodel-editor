#!/usr/bin/env python
"""Brute-force coverage audit for IDTA submodel template editing.

The audit intentionally runs outside normal CI because it talks to the live
IDTA template repository and can be slow or rate-limited. It fetches every
selected template, parses it into the UI schema, checks renderer/schema
coverage, generates frontend-shaped default form data, validates synthetic
required form data, hydrates the defaults back to AASX/JSON, reparses, and
reports preservation metrics.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.fetcher import TemplateFetcherService
from app.services.hydrator import HydratorService
from app.services.parser import ParserService
from app.services.validation import validate_form_data


EDITABLE_MODEL_TYPES = {
    "Property",
    "MultiLanguageProperty",
    "SubmodelElementCollection",
    "SubmodelElementList",
    "File",
    "Blob",
    "Range",
    "ReferenceElement",
    "Entity",
    "RelationshipElement",
    "AnnotatedRelationshipElement",
}

READ_ONLY_MODEL_TYPES = {
    "SubmodelElement",
    "Operation",
    "Capability",
    "BasicEventElement",
}

KNOWN_MODEL_TYPES = EDITABLE_MODEL_TYPES | READ_ONLY_MODEL_TYPES

COMMON_REQUIRED_KEYS = (
    "idShort",
    "modelType",
    "semanticId",
    "semanticLabel",
    "description",
    "qualifiers",
    "cardinality",
    "category",
)

TYPE_REQUIRED_KEYS: dict[str, tuple[str, ...]] = {
    "Property": (
        "valueType",
        "value",
        "inputType",
        "step",
        "constraints",
        "unit",
        "valueId",
    ),
    "MultiLanguageProperty": ("value", "supportedLanguages", "valueId"),
    "SubmodelElementCollection": ("elements",),
    "SubmodelElementList": (
        "typeValueListElement",
        "orderRelevant",
        "valueTypeListElement",
        "semanticIdListElement",
        "items",
    ),
    "File": ("contentType", "value"),
    "Blob": ("contentType", "value", "valueEncoding"),
    "Range": ("valueType", "min", "max", "inputType", "step", "unit"),
    "ReferenceElement": ("value",),
    "Entity": ("entityType", "globalAssetId", "specificAssetIds", "statements"),
    "RelationshipElement": ("first", "second"),
    "AnnotatedRelationshipElement": ("first", "second", "annotations"),
    "Operation": ("inputVariables", "outputVariables", "inoutputVariables"),
    "Capability": (),
    "BasicEventElement": (
        "observed",
        "direction",
        "state",
        "messageTopic",
        "messageBroker",
        "lastUpdate",
        "minInterval",
        "maxInterval",
    ),
}

STAGES = (
    "fetched",
    "parsed",
    "defaultFormGenerated",
    "defaultValidationPassed",
    "requiredFormGenerated",
    "requiredValidationPassed",
    "hydratedAasx",
    "hydratedJson",
    "reparsed",
)

REPORT_DIR = Path("tmp/template-audit")
AUDIT_CACHE_DIR = REPORT_DIR / "cache/templates"
MAX_CONCURRENCY = 8
DEFAULT_TEMPLATE_TIMEOUT_SECONDS = 120.0
DEFAULT_MAX_AASX_BYTES = 256 * 1024 * 1024
DEFAULT_MAX_SCHEMA_NODES = 100_000
MAX_VALIDATION_DETAILS = 25


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit UI schema and hydration coverage across IDTA templates."
    )
    parser.add_argument(
        "--statuses",
        nargs="+",
        default=["published", "deprecated"],
        help="Template repository roots to include.",
    )
    parser.add_argument(
        "--template",
        action="append",
        default=[],
        help="Case-insensitive substring filter over name, title, or path. Can repeat.",
    )
    parser.add_argument(
        "--max-templates",
        type=int,
        default=None,
        help="Limit the number of selected templates for smoke runs.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=4,
        help=f"Maximum templates processed concurrently. Capped at {MAX_CONCURRENCY}.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=DEFAULT_TEMPLATE_TIMEOUT_SECONDS,
        help="Maximum wall-clock seconds per template.",
    )
    parser.add_argument(
        "--max-aasx-bytes",
        type=int,
        default=DEFAULT_MAX_AASX_BYTES,
        help="Reject fetched AASX files larger than this byte count.",
    )
    parser.add_argument(
        "--max-schema-nodes",
        type=int,
        default=DEFAULT_MAX_SCHEMA_NODES,
        help="Reject parsed UI schemas larger than this recursive node count.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("tmp/template-audit/idta-template-coverage.json"),
        help="Machine-readable JSON report path.",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path("tmp/template-audit/idta-template-coverage.md"),
        help="Markdown summary report path.",
    )
    parser.add_argument(
        "--no-fail",
        action="store_true",
        help="Always exit 0 after writing reports.",
    )
    return parser.parse_args()


def resolve_report_path(path: Path, option_name: str) -> Path:
    """Resolve and constrain generated reports to the gitignored audit directory."""
    cwd = Path.cwd()
    base_dir = (cwd / REPORT_DIR).resolve(strict=False)
    candidate = path if path.is_absolute() else cwd / path
    resolved = candidate.resolve(strict=False)

    try:
        resolved.relative_to(base_dir)
    except ValueError as exc:
        raise ValueError(
            f"{option_name} must be under {REPORT_DIR}/, got {path}"
        ) from exc

    if resolved == base_dir:
        raise ValueError(f"{option_name} must be a file path under {REPORT_DIR}/")

    return resolved


def iter_schema_elements(
    elements: list[dict[str, Any]] | None,
    *,
    path: str = "",
    include_item_templates: bool = True,
):
    """Yield ``(path, element)`` for every recursive UI schema node."""
    if not isinstance(elements, list):
        return

    for index, element in enumerate(elements):
        if not isinstance(element, dict):
            continue

        model_type = element.get("modelType") or "Unknown"
        id_short = element.get("idShort")
        segment = str(id_short) if id_short not in (None, "") else f"<{model_type}:{index}>"
        element_path = f"{path}.{segment}" if path else segment
        yield element_path, element

        for child_key in (
            "elements",
            "items",
            "statements",
            "annotations",
            "inputVariables",
            "outputVariables",
            "inoutputVariables",
        ):
            child_items = element.get(child_key)
            if isinstance(child_items, list):
                yield from iter_schema_elements(
                    child_items,
                    path=f"{element_path}.{child_key}",
                    include_item_templates=include_item_templates,
                )

        item_template = element.get("itemTemplate")
        if include_item_templates and isinstance(item_template, dict):
            yield from iter_schema_elements(
                [item_template],
                path=f"{element_path}.itemTemplate",
                include_item_templates=include_item_templates,
            )


def required_schema_keys(element: dict[str, Any]) -> tuple[str, ...]:
    model_type = str(element.get("modelType") or "")
    return COMMON_REQUIRED_KEYS + TYPE_REQUIRED_KEYS.get(model_type, ())


def classify_renderer(model_type: str | None) -> str:
    if model_type in EDITABLE_MODEL_TYPES:
        return "editable"
    if model_type in READ_ONLY_MODEL_TYPES:
        return "readOnly"
    return "unknown"


def _is_non_empty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return True


def _empty_coverage_counter() -> dict[str, Any]:
    return {"applicable": 0, "emitted": 0, "nonEmpty": 0, "missingSamples": []}


def _record_coverage(
    coverage: dict[str, dict[str, Any]],
    key: str,
    element: dict[str, Any],
    path: str,
) -> None:
    stats = coverage[key]
    stats["applicable"] += 1
    if key in element:
        stats["emitted"] += 1
        if _is_non_empty(element.get(key)):
            stats["nonEmpty"] += 1
    elif len(stats["missingSamples"]) < 10:
        stats["missingSamples"].append(
            {
                "path": path,
                "modelType": element.get("modelType"),
                "missingKey": key,
            }
        )


def finalize_coverage(
    coverage: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    finalized: dict[str, dict[str, Any]] = {}
    for key in sorted(coverage):
        stats = coverage[key]
        applicable = stats["applicable"]
        finalized[key] = {
            "applicable": applicable,
            "emitted": stats["emitted"],
            "nonEmpty": stats["nonEmpty"],
            "emittedPct": _pct(stats["emitted"], applicable),
            "nonEmptyPct": _pct(stats["nonEmpty"], applicable),
            "missingSamples": list(stats["missingSamples"]),
        }
    return finalized


def analyze_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Collect renderer, model type, and metadata coverage for one schema."""
    elements = list(
        iter_schema_elements(schema.get("elements", []), include_item_templates=True)
    )
    model_counts: Counter[str] = Counter()
    renderer_counts: Counter[str] = Counter()
    unknown_model_counts: Counter[str] = Counter()
    coverage: dict[str, dict[str, Any]] = defaultdict(_empty_coverage_counter)

    for path, element in elements:
        model_type = str(element.get("modelType") or "Unknown")
        model_counts[model_type] += 1
        renderer_class = classify_renderer(model_type)
        renderer_counts[renderer_class] += 1
        if model_type not in KNOWN_MODEL_TYPES:
            unknown_model_counts[model_type] += 1

        for key in required_schema_keys(element):
            _record_coverage(coverage, key, element, path)

    finalized_coverage = finalize_coverage(coverage)
    missing_required_metadata = [
        sample
        for key_stats in finalized_coverage.values()
        for sample in key_stats["missingSamples"]
    ]

    return {
        "totalNodes": len(elements),
        "modelTypes": dict(sorted(model_counts.items())),
        "rendererCoverage": dict(sorted(renderer_counts.items())),
        "unknownModelTypes": dict(sorted(unknown_model_counts.items())),
        "metadataCoverage": finalized_coverage,
        "metadataCoverageRaw": {
            key: {
                "applicable": value["applicable"],
                "emitted": value["emitted"],
                "nonEmpty": value["nonEmpty"],
                "missingSamples": list(value["missingSamples"]),
            }
            for key, value in coverage.items()
        },
        "missingRequiredMetadata": missing_required_metadata,
    }


def generate_default_form_data(schema: dict[str, Any]) -> dict[str, Any]:
    """Mirror frontend generateDefaultValues/generateElementDefaults."""
    elements: dict[str, Any] = {}
    for element in schema.get("elements", []) or []:
        elements[str(element.get("idShort"))] = generate_element_defaults(element)

    administration = schema.get("administration") or {}
    return {
        "elements": elements,
        "metadata": {
            "idShort": schema.get("idShort") or "",
            "submodelId": schema.get("submodelId") or "",
            "administration": {
                "version": administration.get("version") or "",
                "revision": administration.get("revision") or "",
                "templateId": administration.get("templateId") or "",
            },
        },
    }


def generate_element_defaults(element: dict[str, Any]) -> dict[str, Any]:
    def with_semantic_defaults(defaults: dict[str, Any]) -> dict[str, Any]:
        return {
            **defaults,
            "semanticId": element.get("semanticId"),
            "valueId": element.get("valueId"),
            "semanticIdListElement": element.get("semanticIdListElement"),
        }

    model_type = element.get("modelType")

    if model_type == "Property":
        return with_semantic_defaults(
            {"value": json_safe_value(element.get("value")) if element.get("value") is not None else ""}
        )

    if model_type == "MultiLanguageProperty":
        value = element.get("value")
        return with_semantic_defaults({"value": value if isinstance(value, dict) else {}})

    if model_type == "SubmodelElementCollection":
        return with_semantic_defaults(
            {
                "elements": {
                    str(child.get("idShort")): generate_element_defaults(child)
                    for child in element.get("elements", []) or []
                    if isinstance(child, dict)
                }
            }
        )

    if model_type == "SubmodelElementList":
        return with_semantic_defaults(
            {
                "items": [
                    generate_element_defaults(item)
                    for item in element.get("items", []) or []
                    if isinstance(item, dict)
                ],
                "semanticIdListElement": element.get("semanticIdListElement"),
            }
        )

    if model_type == "File":
        return with_semantic_defaults(
            {
                "value": json_safe_value(element.get("value")) if element.get("value") is not None else "",
                "contentType": element.get("contentType") or "",
            }
        )

    if model_type == "Blob":
        return with_semantic_defaults(
            {
                "value": json_safe_value(element.get("value")) if element.get("value") is not None else "",
                "contentType": element.get("contentType") or "application/octet-stream",
                "valueEncoding": element.get("valueEncoding") or "utf-8",
            }
        )

    if model_type == "Range":
        return with_semantic_defaults(
            {
                "min": json_safe_value(element.get("min")) if element.get("min") is not None else "",
                "max": json_safe_value(element.get("max")) if element.get("max") is not None else "",
            }
        )

    if model_type == "ReferenceElement":
        return with_semantic_defaults(
            {"value": element.get("value") if element.get("value") is not None else ""}
        )

    if model_type == "Entity":
        return with_semantic_defaults(
            {
                "globalAssetId": element.get("globalAssetId") or "",
                "statements": {
                    str(statement.get("idShort")): generate_element_defaults(statement)
                    for statement in element.get("statements", []) or []
                    if isinstance(statement, dict)
                },
            }
        )

    if model_type == "RelationshipElement":
        return with_semantic_defaults(
            {
                "first": element.get("first") if element.get("first") is not None else "",
                "second": element.get("second")
                if element.get("second") is not None
                else "",
            }
        )

    if model_type == "AnnotatedRelationshipElement":
        return with_semantic_defaults(
            {
                "first": element.get("first") if element.get("first") is not None else "",
                "second": element.get("second")
                if element.get("second") is not None
                else "",
                "annotations": [
                    generate_element_defaults(annotation)
                    for annotation in element.get("annotations", []) or []
                    if isinstance(annotation, dict)
                ],
            }
        )

    return with_semantic_defaults(
        {"value": json_safe_value(element.get("value")) if element.get("value") is not None else ""}
    )


def json_safe_value(value: Any) -> Any:
    """Approximate the value shape that the React frontend receives over JSON."""
    if value is None or type(value) in (str, int, float, bool):
        return value
    if isinstance(value, dict):
        return {str(key): json_safe_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe_value(item) for item in value]
    if hasattr(value, "year"):
        return str(value.year)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def dump_validation_results(results: list[Any]) -> list[dict[str, Any]]:
    """Bound validation details so large audits do not duplicate huge payloads."""
    dumped = [result.model_dump() for result in results[:MAX_VALIDATION_DETAILS]]
    truncated = len(results) - MAX_VALIDATION_DETAILS
    if truncated > 0:
        dumped.append(
            {
                "field": "<truncated>",
                "message": f"{truncated} additional validation result(s) omitted.",
                "code": "truncated",
            }
        )
    return dumped


def parse_cardinality(cardinality: str | None) -> tuple[int, int | None]:
    value = str(cardinality or "").strip()
    if not value:
        return 1, 1
    mapping = {
        "ZeroToOne": "[0..1]",
        "ZeroToMany": "[0..*]",
        "OneToMany": "[1..*]",
        "One": "[1]",
        "Zero": "[0]",
    }
    value = mapping.get(value, value)
    if ".." in value and not value.startswith("["):
        value = f"[{value}]"
    if value.isdigit():
        value = f"[{value}]"

    import re

    match = re.match(r"^\[(\d+)(?:\.\.(\d+|\*))?\]$", value)
    if not match:
        return 1, 1
    min_items = int(match.group(1))
    max_group = match.group(2)
    if max_group is None:
        return min_items, min_items
    if max_group == "*":
        return min_items, None
    return min_items, int(max_group)


def sample_value(value_type: str | None, *, high: bool = False) -> Any:
    value_type_lower = (value_type or "xs:string").lower()
    if "bool" in value_type_lower:
        return True
    if "int" in value_type_lower or "integer" in value_type_lower:
        return 2 if high else 1
    if any(token in value_type_lower for token in ("float", "double", "decimal")):
        return 2.0 if high else 1.0
    if "datetime" in value_type_lower:
        return "2024-01-02T00:00:00" if high else "2024-01-01T00:00:00"
    if "date" in value_type_lower:
        return "2024-01-02" if high else "2024-01-01"
    if "time" in value_type_lower:
        return "00:00:01" if high else "00:00:00"
    if "anyuri" in value_type_lower or "uri" in value_type_lower:
        return "urn:example:high" if high else "urn:example"
    return "Example B" if high else "Example"


def generate_required_form_data(schema: dict[str, Any]) -> dict[str, Any]:
    elements: dict[str, Any] = {}
    for element in schema.get("elements", []) or []:
        data = build_required_element(element)
        if data is not None:
            elements[str(element.get("idShort"))] = data
    return {"elements": elements}


def build_required_element(element: dict[str, Any]) -> dict[str, Any] | None:
    model_type = element.get("modelType")
    min_items, _ = parse_cardinality(element.get("cardinality"))
    required = min_items >= 1

    if model_type == "SubmodelElementCollection":
        elements: dict[str, Any] = {}
        for child in element.get("elements", []) or []:
            child_data = build_required_element(child)
            if child_data is not None:
                elements[str(child.get("idShort"))] = child_data
        return {"elements": elements} if required or elements else None

    if model_type == "SubmodelElementList":
        item_template = element.get("itemTemplate")
        items = []
        if min_items >= 1 and isinstance(item_template, dict):
            items.append(build_required_element(item_template) or {})
        return {"items": items} if required or items else None

    if model_type == "Property":
        return {"value": sample_value(element.get("valueType"))} if required else None

    if model_type == "MultiLanguageProperty":
        return {"value": {"en": "Example"}} if required else None

    if model_type == "Range":
        if not required:
            return None
        value_type = element.get("valueType")
        return {
            "min": sample_value(value_type),
            "max": sample_value(value_type, high=True),
        }

    if model_type == "File":
        return (
            {"value": "file://example.txt", "contentType": "text/plain"}
            if required
            else None
        )

    if model_type == "Blob":
        return (
            {
                "value": "Example",
                "contentType": "text/plain",
                "valueEncoding": "utf-8",
            }
            if required
            else None
        )

    if model_type == "ReferenceElement":
        return {"value": "urn:example"} if required else None

    if model_type in ("RelationshipElement", "AnnotatedRelationshipElement"):
        if not required:
            return None
        data: dict[str, Any] = {"first": "urn:example:first", "second": "urn:example:second"}
        if model_type == "AnnotatedRelationshipElement":
            annotations = []
            for annotation in element.get("annotations", []) or []:
                annotation_data = build_required_element(annotation)
                if annotation_data is not None:
                    annotations.append(annotation_data)
            data["annotations"] = annotations
        return data

    if model_type == "Entity":
        statements: dict[str, Any] = {}
        for child in element.get("statements", []) or []:
            child_data = build_required_element(child)
            if child_data is not None:
                statements[str(child.get("idShort"))] = child_data
        return {"statements": statements} if required or statements else None

    if required:
        return {}
    return None


def schema_preservation_signature(schema: dict[str, Any]) -> dict[str, Any]:
    elements = list(
        iter_schema_elements(schema.get("elements", []), include_item_templates=False)
    )
    return {
        "modelTypes": Counter(str(element.get("modelType") or "Unknown") for _, element in elements),
        "structure": Counter(schema_structure_entries(schema.get("elements", []))),
        "semanticIds": Counter(
            str(element.get("semanticId"))
            for _, element in elements
            if element.get("semanticId")
        ),
        "qualifiers": Counter(
            json.dumps(element.get("qualifiers"), sort_keys=True, default=str)
            for _, element in elements
            if element.get("qualifiers")
        ),
        "supplementaryFiles": Counter(schema.get("supplementaryFiles") or []),
    }


def schema_structure_entries(
    elements: list[dict[str, Any]] | None,
    *,
    path: str = "",
):
    """Yield position-based structure entries for actual AAS element nodes."""
    if not isinstance(elements, list):
        return

    for index, element in enumerate(elements):
        if not isinstance(element, dict):
            continue
        model_type = str(element.get("modelType") or "Unknown")
        element_path = f"{path}/{index}:{model_type}" if path else f"{index}:{model_type}"
        yield element_path

        for child_key in (
            "elements",
            "items",
            "statements",
            "annotations",
            "inputVariables",
            "outputVariables",
            "inoutputVariables",
        ):
            child_items = element.get(child_key)
            if isinstance(child_items, list):
                yield from schema_structure_entries(
                    child_items,
                    path=f"{element_path}/{child_key}",
                )


def compare_preservation(
    original_schema: dict[str, Any],
    reparsed_schema: dict[str, Any],
) -> dict[str, bool]:
    original = schema_preservation_signature(original_schema)
    reparsed = schema_preservation_signature(reparsed_schema)
    return {
        "modelTypeCountsPreserved": original["modelTypes"] == reparsed["modelTypes"],
        "nestedStructurePreserved": original["structure"] == reparsed["structure"],
        "semanticIdsPreserved": original["semanticIds"] == reparsed["semanticIds"],
        "qualifiersPreserved": original["qualifiers"] == reparsed["qualifiers"],
        "supplementaryFilesPreserved": (
            original["supplementaryFiles"] == reparsed["supplementaryFiles"]
        ),
    }


def make_template_result(template: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": template.get("name"),
        "title": template.get("title"),
        "path": template.get("path"),
        "status": template.get("status"),
        "idtaNumber": template.get("idta_number"),
        "stages": {stage: False for stage in STAGES},
        "elementMetrics": None,
        "validation": {},
        "preservation": {},
        "failures": [],
    }


def add_failure(
    result: dict[str, Any],
    *,
    category: str,
    stage: str,
    message: str,
    severity: str = "error",
    path: str | None = None,
) -> None:
    failure = {
        "category": category,
        "stage": stage,
        "severity": severity,
        "message": message[:1000],
    }
    if path:
        failure["path"] = path
    result["failures"].append(failure)


async def audit_template(
    template: dict[str, Any],
    fetcher: TemplateFetcherService,
    parser: ParserService,
    hydrator: HydratorService,
    *,
    timeout_seconds: float,
    max_aasx_bytes: int,
    max_schema_nodes: int,
) -> dict[str, Any]:
    result = make_template_result(template)
    template_path = template.get("path")
    if not template_path:
        add_failure(
            result,
            category="missing_template_path",
            stage="list",
            message="Template entry did not include a path.",
        )
        return result

    try:
        return await asyncio.wait_for(
            _audit_template_inner(
                result,
                str(template_path),
                fetcher,
                parser,
                hydrator,
                max_aasx_bytes=max_aasx_bytes,
                max_schema_nodes=max_schema_nodes,
            ),
            timeout=timeout_seconds,
        )
    except TimeoutError:
        add_failure(
            result,
            category="template_timeout",
            stage="timeout",
            message=f"Template audit exceeded {timeout_seconds} seconds.",
        )
        return result


async def _audit_template_inner(
    result: dict[str, Any],
    template_path: str,
    fetcher: TemplateFetcherService,
    parser: ParserService,
    hydrator: HydratorService,
    *,
    max_aasx_bytes: int,
    max_schema_nodes: int,
) -> dict[str, Any]:
    try:
        aasx_bytes = await fetcher.fetch_template_aasx(template_path)
        if not aasx_bytes:
            add_failure(
                result,
                category="missing_aasx",
                stage="fetch",
                message="Fetched AASX was empty.",
            )
            return result
        if len(aasx_bytes) > max_aasx_bytes:
            add_failure(
                result,
                category="aasx_too_large",
                stage="fetch",
                message=(
                    f"Fetched AASX is {len(aasx_bytes)} bytes, "
                    f"above max {max_aasx_bytes}."
                ),
            )
            return result
        result["stages"]["fetched"] = True
    except Exception as exc:
        add_failure(
            result,
            category="fetch_failure",
            stage="fetch",
            message=f"{type(exc).__name__}: {exc}",
        )
        return result

    try:
        schema = await asyncio.to_thread(parser.parse_aasx_to_ui_schema, aasx_bytes)
        result["stages"]["parsed"] = True
    except Exception as exc:
        add_failure(
            result,
            category="parser_failure",
            stage="parse",
            message=f"{type(exc).__name__}: {exc}",
        )
        return result

    analysis = analyze_schema(schema)
    result["elementMetrics"] = analysis
    if analysis["totalNodes"] > max_schema_nodes:
        add_failure(
            result,
            category="schema_too_large",
            stage="metadata",
            message=(
                f"Parsed schema has {analysis['totalNodes']} nodes, "
                f"above max {max_schema_nodes}."
            ),
        )
        return result
    for model_type, count in analysis["unknownModelTypes"].items():
        add_failure(
            result,
            category="unsupported_model_type",
            stage="metadata",
            message=f"{count} node(s) use unsupported modelType {model_type}.",
        )
    for sample in analysis["missingRequiredMetadata"]:
        add_failure(
            result,
            category="missing_metadata",
            stage="metadata",
            path=sample.get("path"),
            message=(
                f"{sample.get('modelType')} is missing required UI schema key "
                f"{sample.get('missingKey')}."
            ),
        )

    try:
        default_form_data = generate_default_form_data(schema)
        result["stages"]["defaultFormGenerated"] = True
    except Exception as exc:
        add_failure(
            result,
            category="default_form_failure",
            stage="defaults",
            message=f"{type(exc).__name__}: {exc}",
        )
        return result

    default_errors, default_warnings = validate_form_data(schema, default_form_data)
    result["validation"]["defaultErrors"] = dump_validation_results(default_errors)
    result["validation"]["defaultWarnings"] = dump_validation_results(default_warnings)
    result["stages"]["defaultValidationPassed"] = len(default_errors) == 0
    if default_errors:
        add_failure(
            result,
            category="default_validation_errors",
            stage="validate",
            severity="warning",
            message=f"Default frontend-shaped data produced {len(default_errors)} validation error(s).",
        )

    try:
        required_form_data = generate_required_form_data(schema)
        result["stages"]["requiredFormGenerated"] = True
    except Exception as exc:
        add_failure(
            result,
            category="required_form_failure",
            stage="required-defaults",
            message=f"{type(exc).__name__}: {exc}",
        )
        required_form_data = None

    if required_form_data is not None:
        required_errors, required_warnings = validate_form_data(
            schema, required_form_data
        )
        result["validation"]["requiredErrors"] = dump_validation_results(
            required_errors
        )
        result["validation"]["requiredWarnings"] = dump_validation_results(
            required_warnings
        )
        result["stages"]["requiredValidationPassed"] = len(required_errors) == 0
        if required_errors:
            add_failure(
                result,
                category="validation_mismatch",
                stage="validate",
                message=(
                    "Synthetic required form data did not satisfy backend "
                    f"validation: {len(required_errors)} error(s)."
                ),
            )

    try:
        hydrated_store, hydrated_files = await asyncio.to_thread(
            hydrator.hydrate_to_stores,
            aasx_bytes,
            default_form_data,
        )
        hydrated_aasx = await asyncio.to_thread(
            hydrator.serialize_stores_to_aasx,
            hydrated_store,
            hydrated_files,
        )
        if not hydrated_aasx:
            raise ValueError("Hydrated AASX was empty.")
        result["stages"]["hydratedAasx"] = True
    except Exception as exc:
        add_failure(
            result,
            category="hydration_failure",
            stage="hydrate-aasx",
            message=f"{type(exc).__name__}: {exc}",
        )
        return result

    try:
        hydrated_json = await asyncio.to_thread(
            hydrator.serialize_stores_to_json,
            hydrated_store,
        )
        json.loads(hydrated_json)
        result["stages"]["hydratedJson"] = True
    except Exception as exc:
        add_failure(
            result,
            category="hydration_failure",
            stage="hydrate-json",
            message=f"{type(exc).__name__}: {exc}",
        )

    try:
        reparsed_schema = await asyncio.to_thread(
            parser.parse_aasx_to_ui_schema,
            hydrated_aasx,
        )
        result["stages"]["reparsed"] = True
    except Exception as exc:
        add_failure(
            result,
            category="round_trip_mismatch",
            stage="reparse",
            message=f"{type(exc).__name__}: {exc}",
        )
        return result

    preservation = compare_preservation(schema, reparsed_schema)
    result["preservation"] = preservation
    for key, preserved in preservation.items():
        if not preserved:
            add_failure(
                result,
                category="round_trip_mismatch",
                stage="preservation",
                message=f"Round-trip preservation check failed: {key}.",
            )

    return result


async def run_audit(
    *,
    statuses: list[str],
    template_filters: list[str],
    max_templates: int | None,
    concurrency: int,
    cache_dir: Path,
    timeout_seconds: float,
    max_aasx_bytes: int,
    max_schema_nodes: int,
) -> dict[str, Any]:
    fetcher = TemplateFetcherService(
        cache_dir=cache_dir,
        local_templates_enabled=False,
    )
    effective_concurrency = min(max(1, concurrency), MAX_CONCURRENCY)

    report: dict[str, Any] = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "statuses": statuses,
        "templateFilters": template_filters,
        "maxTemplates": max_templates,
        "concurrency": effective_concurrency,
        "requestedConcurrency": concurrency,
        "timeoutSeconds": timeout_seconds,
        "maxAasxBytes": max_aasx_bytes,
        "maxSchemaNodes": max_schema_nodes,
        "cacheDir": str(cache_dir),
        "totals": {},
        "pipelineRates": {},
        "elements": {},
        "metadataCoverage": {},
        "contractCoverage": {},
        "preservation": {},
        "failures": [],
        "templates": [],
        "shouldFail": False,
    }

    try:
        templates, index_cached = await fetcher.list_available_templates(
            statuses=statuses,
            include_local=False,
        )
    except Exception as exc:
        failure = {
            "template": None,
            "path": None,
            "category": "list_failure",
            "stage": "list",
            "severity": "error",
            "message": f"{type(exc).__name__}: {exc}",
        }
        report["failures"].append(failure)
        report["shouldFail"] = True
        report["totals"] = {
            "listed": 0,
            "selected": 0,
            "indexCached": False,
        }
        return report

    selected_templates = filter_templates(templates, template_filters)
    if max_templates is not None:
        selected_templates = selected_templates[:max_templates]

    results: list[dict[str, Any] | None] = [None] * len(selected_templates)
    queue: asyncio.Queue[tuple[int, dict[str, Any]] | None] = asyncio.Queue()
    for index, template in enumerate(selected_templates):
        queue.put_nowait((index, template))

    async def worker() -> None:
        while True:
            item = await queue.get()
            if item is None:
                queue.task_done()
                return
            index, template = item
            try:
                results[index] = await audit_template(
                    template,
                    fetcher,
                    ParserService(),
                    HydratorService(),
                    timeout_seconds=timeout_seconds,
                    max_aasx_bytes=max_aasx_bytes,
                    max_schema_nodes=max_schema_nodes,
                )
            finally:
                queue.task_done()

    workers = [asyncio.create_task(worker()) for _ in range(effective_concurrency)]
    await queue.join()
    for _ in workers:
        queue.put_nowait(None)
    await asyncio.gather(*workers)

    report["templates"] = [result for result in results if result is not None]
    report["totals"] = {
        "listed": len(templates),
        "selected": len(selected_templates),
        "indexCached": index_cached,
    }
    merge_results(report)
    return report


def filter_templates(
    templates: list[dict[str, Any]],
    template_filters: list[str],
) -> list[dict[str, Any]]:
    if not template_filters:
        return list(templates)

    filters = [value.lower() for value in template_filters]
    selected = []
    for template in templates:
        haystack = " ".join(
            str(template.get(key) or "")
            for key in ("name", "title", "path", "idta_number")
        ).lower()
        if any(filter_value in haystack for filter_value in filters):
            selected.append(template)
    return selected


def merge_results(report: dict[str, Any]) -> None:
    results = report["templates"]
    stage_counts: Counter[str] = Counter()
    model_counts: Counter[str] = Counter()
    renderer_counts: Counter[str] = Counter()
    unknown_counts: Counter[str] = Counter()
    metadata_raw: dict[str, dict[str, Any]] = defaultdict(_empty_coverage_counter)
    preservation_counts: Counter[str] = Counter()
    all_failures = list(report.get("failures", []))

    for result in results:
        for stage, passed in result.get("stages", {}).items():
            if passed:
                stage_counts[stage] += 1

        analysis = result.get("elementMetrics")
        if analysis:
            model_counts.update(analysis.get("modelTypes", {}))
            renderer_counts.update(analysis.get("rendererCoverage", {}))
            unknown_counts.update(analysis.get("unknownModelTypes", {}))
            merge_metadata_coverage(metadata_raw, analysis.get("metadataCoverageRaw", {}))

        for key, preserved in result.get("preservation", {}).items():
            if preserved:
                preservation_counts[key] += 1

        for failure in result.get("failures", []):
            all_failures.append(
                {
                    "template": result.get("name"),
                    "path": result.get("path"),
                    **failure,
                }
            )

    selected = report["totals"].get("selected", 0)
    report["pipelineRates"] = {
        stage: {
            "count": stage_counts[stage],
            "total": selected,
            "pct": _pct(stage_counts[stage], selected),
        }
        for stage in STAGES
    }
    report["elements"] = {
        "totalNodes": sum(model_counts.values()),
        "byModelType": dict(sorted(model_counts.items())),
        "rendererCoverage": dict(sorted(renderer_counts.items())),
        "unknownModelTypes": dict(sorted(unknown_counts.items())),
    }
    report["metadataCoverage"] = finalize_coverage(metadata_raw)
    report["contractCoverage"] = {
        "defaultFormGenerated": report["pipelineRates"]["defaultFormGenerated"],
        "defaultValidationPassed": report["pipelineRates"]["defaultValidationPassed"],
        "requiredFormGenerated": report["pipelineRates"]["requiredFormGenerated"],
        "requiredValidationPassed": report["pipelineRates"]["requiredValidationPassed"],
    }
    report["preservation"] = {
        key: {
            "count": preservation_counts[key],
            "total": selected,
            "pct": _pct(preservation_counts[key], selected),
        }
        for key in (
            "modelTypeCountsPreserved",
            "nestedStructurePreserved",
            "semanticIdsPreserved",
            "qualifiersPreserved",
            "supplementaryFilesPreserved",
        )
    }
    report["failures"] = all_failures
    report["shouldFail"] = any(
        failure.get("severity") == "error" for failure in all_failures
    )


def merge_metadata_coverage(
    aggregate: dict[str, dict[str, Any]],
    item: dict[str, dict[str, Any]],
) -> None:
    for key, stats in item.items():
        target = aggregate[key]
        target["applicable"] += stats.get("applicable", 0)
        target["emitted"] += stats.get("emitted", 0)
        target["nonEmpty"] += stats.get("nonEmpty", 0)
        remaining = max(0, 10 - len(target["missingSamples"]))
        target["missingSamples"].extend(stats.get("missingSamples", [])[:remaining])


def _pct(count: int, total: int) -> float:
    if total == 0:
        return 100.0
    return round((count / total) * 100, 2)


def write_reports(report: dict[str, Any], output_path: Path, summary_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(report, output_file, indent=2, sort_keys=True)
    summary_path.write_text(render_markdown_summary(report), encoding="utf-8")


def render_markdown_summary(report: dict[str, Any]) -> str:
    lines = [
        "# IDTA Template Coverage Audit",
        "",
        f"- Generated: `{report.get('generatedAt')}`",
        f"- Statuses: `{', '.join(report.get('statuses', []))}`",
        f"- Listed templates: `{report.get('totals', {}).get('listed', 0)}`",
        f"- Selected templates: `{report.get('totals', {}).get('selected', 0)}`",
        f"- Cache directory: `{report.get('cacheDir')}`",
        f"- Should fail: `{report.get('shouldFail')}`",
        "",
        "## Pipeline",
        "",
        "| Stage | Count | Total | Rate |",
        "| --- | ---: | ---: | ---: |",
    ]
    for stage, stats in report.get("pipelineRates", {}).items():
        lines.append(
            f"| {stage} | {stats['count']} | {stats['total']} | {stats['pct']}% |"
        )

    renderer = report.get("elements", {}).get("rendererCoverage", {})
    lines.extend(
        [
            "",
            "## Renderer Coverage",
            "",
            "| Class | Nodes |",
            "| --- | ---: |",
        ]
    )
    for key, count in renderer.items():
        lines.append(f"| {key} | {count} |")

    lines.extend(
        [
            "",
            "## Model Types",
            "",
            "| modelType | Nodes |",
            "| --- | ---: |",
        ]
    )
    for model_type, count in report.get("elements", {}).get("byModelType", {}).items():
        lines.append(f"| {model_type} | {count} |")

    lines.extend(
        [
            "",
            "## Metadata Coverage",
            "",
            "| Key | Applicable | Emitted | Emitted % | Non-empty % |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for key, stats in report.get("metadataCoverage", {}).items():
        lines.append(
            f"| {key} | {stats['applicable']} | {stats['emitted']} | "
            f"{stats['emittedPct']}% | {stats['nonEmptyPct']}% |"
        )

    lines.extend(
        [
            "",
            "## Preservation",
            "",
            "| Check | Count | Total | Rate |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for key, stats in report.get("preservation", {}).items():
        lines.append(
            f"| {key} | {stats['count']} | {stats['total']} | {stats['pct']}% |"
        )

    failures = report.get("failures", [])
    lines.extend(
        [
            "",
            "## Failures",
            "",
            "| Severity | Category | Template | Stage | Message |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for failure in failures[:100]:
        message = str(failure.get("message", "")).replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {failure.get('severity')} | {failure.get('category')} | "
            f"{failure.get('path') or failure.get('template') or ''} | "
            f"{failure.get('stage')} | {message} |"
        )
    if len(failures) > 100:
        lines.append(f"| info | truncated |  |  | {len(failures) - 100} more failure(s) in JSON report. |")

    lines.append("")
    return "\n".join(lines)


def print_console_summary(report: dict[str, Any], output: Path, summary: Path) -> None:
    selected = report.get("totals", {}).get("selected", 0)
    failures = report.get("failures", [])
    error_count = sum(1 for failure in failures if failure.get("severity") == "error")
    warning_count = sum(
        1 for failure in failures if failure.get("severity") == "warning"
    )
    parsed = report.get("pipelineRates", {}).get("parsed", {}).get("count", 0)
    hydrated = report.get("pipelineRates", {}).get("hydratedAasx", {}).get("count", 0)
    reparsed = report.get("pipelineRates", {}).get("reparsed", {}).get("count", 0)
    print(
        "Audit complete: "
        f"{selected} selected, {parsed} parsed, {hydrated} hydrated, "
        f"{reparsed} reparsed, {error_count} errors, {warning_count} warnings."
    )
    print(f"JSON report: {output}")
    print(f"Summary report: {summary}")


def main() -> int:
    args = parse_args()
    try:
        output_path = resolve_report_path(args.output, "--output")
        summary_path = resolve_report_path(args.summary, "--summary")
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    report = asyncio.run(
        run_audit(
            statuses=args.statuses,
            template_filters=args.template,
            max_templates=args.max_templates,
            concurrency=args.concurrency,
            cache_dir=(Path.cwd() / AUDIT_CACHE_DIR).resolve(strict=False),
            timeout_seconds=args.timeout_seconds,
            max_aasx_bytes=args.max_aasx_bytes,
            max_schema_nodes=args.max_schema_nodes,
        )
    )
    write_reports(report, output_path, summary_path)
    print_console_summary(report, output_path, summary_path)
    if report.get("shouldFail") and not args.no_fail:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
