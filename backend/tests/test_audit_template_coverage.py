from collections import defaultdict
from pathlib import Path

import pytest

from scripts.audit_template_coverage import (
    _empty_coverage_counter,
    analyze_schema,
    audit_template,
    build_required_element,
    classify_renderer,
    compare_preservation,
    finalize_coverage,
    generate_default_form_data,
    generate_required_form_data,
    iter_schema_elements,
    json_safe_value,
    merge_results,
    merge_metadata_coverage,
    resolve_report_path,
    run_audit,
)


def property_schema(id_short: str, **overrides):
    schema = {
        "idShort": id_short,
        "modelType": "Property",
        "semanticId": "urn:semantic",
        "semanticLabel": None,
        "description": None,
        "qualifiers": [],
        "cardinality": "[1]",
        "category": None,
        "valueType": "xs:string",
        "value": None,
        "inputType": "text",
        "step": None,
        "constraints": None,
        "unit": None,
        "valueId": None,
    }
    schema.update(overrides)
    return schema


def test_iter_schema_elements_walks_nested_and_template_nodes():
    schema = {
        "elements": [
            {
                "idShort": "Collection",
                "modelType": "SubmodelElementCollection",
                "elements": [property_schema("Nested")],
            },
            {
                "idShort": "List",
                "modelType": "SubmodelElementList",
                "items": [property_schema("Item")],
                "itemTemplate": property_schema("Template"),
            },
            {
                "idShort": "Operation",
                "modelType": "Operation",
                "inputVariables": [property_schema("Input")],
                "outputVariables": [property_schema("Output")],
                "inoutputVariables": [],
            },
            {
                "idShort": "Entity",
                "modelType": "Entity",
                "statements": [property_schema("Statement")],
            },
            {
                "idShort": "Annotated",
                "modelType": "AnnotatedRelationshipElement",
                "annotations": [property_schema("Annotation")],
            },
        ]
    }

    paths = [path for path, _ in iter_schema_elements(schema["elements"])]

    assert "Collection.elements.Nested" in paths
    assert "List.items.Item" in paths
    assert "List.itemTemplate.Template" in paths
    assert "Operation.inputVariables.Input" in paths
    assert "Operation.outputVariables.Output" in paths
    assert "Entity.statements.Statement" in paths
    assert "Annotated.annotations.Annotation" in paths


def test_analyze_schema_classifies_renderers_and_missing_metadata():
    schema = {
        "elements": [
            property_schema("Editable"),
            {
                "idShort": "Operation",
                "modelType": "Operation",
                "semanticId": None,
                "semanticLabel": None,
                "description": None,
                "qualifiers": [],
                "cardinality": "[1]",
                "category": None,
                "inputVariables": [],
                "outputVariables": [],
                "inoutputVariables": [],
            },
            {
                "idShort": "Mystery",
                "modelType": "FutureElement",
                "semanticId": None,
                "semanticLabel": None,
                "description": None,
                "qualifiers": [],
                "cardinality": "[1]",
                "category": None,
            },
            {
                "idShort": "BrokenProperty",
                "modelType": "Property",
                "semanticId": None,
                "semanticLabel": None,
                "description": None,
                "qualifiers": [],
                "cardinality": "[1]",
                "category": None,
                "value": None,
            },
        ]
    }

    analysis = analyze_schema(schema)

    assert analysis["rendererCoverage"] == {
        "editable": 2,
        "readOnly": 1,
        "unknown": 1,
    }
    assert analysis["unknownModelTypes"] == {"FutureElement": 1}
    assert any(
        sample["path"] == "BrokenProperty" and sample["missingKey"] == "valueType"
        for sample in analysis["missingRequiredMetadata"]
    )


def test_default_and_required_form_data_match_supported_shapes():
    schema = {
        "idShort": "Submodel",
        "submodelId": "urn:submodel",
        "administration": {"version": "1", "revision": "0", "templateId": "tpl"},
        "elements": [
            property_schema("Name", value="Existing"),
            {
                "idShort": "Range",
                "modelType": "Range",
                "semanticId": None,
                "semanticLabel": None,
                "description": None,
                "qualifiers": [],
                "cardinality": "[1]",
                "category": None,
                "valueType": "xs:int",
                "min": None,
                "max": None,
                "inputType": "number",
                "step": "1",
                "unit": None,
            },
            {
                "idShort": "Texts",
                "modelType": "MultiLanguageProperty",
                "semanticId": None,
                "semanticLabel": None,
                "description": None,
                "qualifiers": [],
                "cardinality": "[1]",
                "category": None,
                "value": {},
                "supportedLanguages": ["en"],
                "valueId": None,
            },
            {
                "idShort": "List",
                "modelType": "SubmodelElementList",
                "semanticId": None,
                "semanticLabel": None,
                "description": None,
                "qualifiers": [],
                "cardinality": "[1..*]",
                "category": None,
                "typeValueListElement": "Property",
                "orderRelevant": True,
                "valueTypeListElement": "xs:string",
                "semanticIdListElement": None,
                "items": [],
                "itemTemplate": property_schema(""),
            },
        ],
    }

    defaults = generate_default_form_data(schema)
    required = generate_required_form_data(schema)

    assert defaults["metadata"]["submodelId"] == "urn:submodel"
    assert defaults["elements"]["Name"]["value"] == "Existing"
    assert defaults["elements"]["Range"] == {
        "min": "",
        "max": "",
        "semanticId": None,
        "valueId": None,
        "semanticIdListElement": None,
    }
    assert required["elements"]["Range"] == {"min": 1, "max": 2}
    assert required["elements"]["Texts"] == {"value": {"en": "Example"}}
    assert required["elements"]["List"] == {"items": [{"value": "Example"}]}


def test_build_required_element_returns_none_for_optional_elements():
    optional = property_schema("Optional", cardinality="[0..1]")

    assert build_required_element(optional) is None


def test_json_safe_value_serializes_frontend_wire_values():
    class CustomString(str):
        pass

    class CustomValue:
        def __str__(self):
            return "custom"

    assert json_safe_value({"value": CustomValue()}) == {"value": "custom"}
    assert type(json_safe_value(CustomString("2024"))) is str


def test_resolve_report_path_constrains_outputs_to_audit_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    resolved = resolve_report_path(
        Path("tmp/template-audit/report.json"),
        "--output",
    )

    assert resolved == (tmp_path / "tmp/template-audit/report.json").resolve()
    with pytest.raises(ValueError, match="must be under tmp/template-audit"):
        resolve_report_path(Path("tmp/report.json"), "--output")
    with pytest.raises(ValueError, match="must be under tmp/template-audit"):
        resolve_report_path(tmp_path / "outside.json", "--summary")


def test_metadata_coverage_merge_and_finalize():
    aggregate = defaultdict(_empty_coverage_counter)
    merge_metadata_coverage(
        aggregate,
        {
            "idShort": {
                "applicable": 2,
                "emitted": 1,
                "nonEmpty": 1,
                "missingSamples": [{"path": "Missing"}],
            }
        },
    )
    merge_metadata_coverage(
        aggregate,
        {
            "idShort": {
                "applicable": 1,
                "emitted": 1,
                "nonEmpty": 0,
                "missingSamples": [],
            }
        },
    )

    finalized = finalize_coverage(aggregate)

    assert finalized["idShort"]["applicable"] == 3
    assert finalized["idShort"]["emitted"] == 2
    assert finalized["idShort"]["emittedPct"] == 66.67
    assert finalized["idShort"]["missingSamples"] == [{"path": "Missing"}]


def test_merge_results_aggregates_pipeline_failures_and_preservation():
    report = {
        "totals": {"selected": 2},
        "failures": [],
        "templates": [
            {
                "name": "Template A",
                "path": "published/A",
                "stages": {
                    "fetched": True,
                    "parsed": True,
                    "defaultFormGenerated": True,
                    "defaultValidationPassed": False,
                    "requiredFormGenerated": True,
                    "requiredValidationPassed": True,
                    "hydratedAasx": True,
                    "hydratedJson": True,
                    "reparsed": True,
                },
                "elementMetrics": {
                    "modelTypes": {"Property": 2},
                    "rendererCoverage": {"editable": 2},
                    "unknownModelTypes": {},
                    "metadataCoverageRaw": {},
                },
                "preservation": {
                    "modelTypeCountsPreserved": True,
                    "nestedStructurePreserved": True,
                    "semanticIdsPreserved": True,
                    "qualifiersPreserved": True,
                    "supplementaryFilesPreserved": True,
                },
                "failures": [
                    {
                        "category": "default_validation_errors",
                        "stage": "validate",
                        "severity": "warning",
                        "message": "default invalid",
                    }
                ],
            },
            {
                "name": "Template B",
                "path": "published/B",
                "stages": {
                    "fetched": True,
                    "parsed": True,
                    "defaultFormGenerated": True,
                    "defaultValidationPassed": True,
                    "requiredFormGenerated": True,
                    "requiredValidationPassed": False,
                    "hydratedAasx": False,
                    "hydratedJson": False,
                    "reparsed": False,
                },
                "elementMetrics": {
                    "modelTypes": {"FutureElement": 1},
                    "rendererCoverage": {"unknown": 1},
                    "unknownModelTypes": {"FutureElement": 1},
                    "metadataCoverageRaw": {},
                },
                "preservation": {
                    "modelTypeCountsPreserved": False,
                    "nestedStructurePreserved": True,
                    "semanticIdsPreserved": False,
                    "qualifiersPreserved": True,
                    "supplementaryFilesPreserved": True,
                },
                "failures": [
                    {
                        "category": "hydration_failure",
                        "stage": "hydrate-aasx",
                        "severity": "error",
                        "message": "hydrate failed",
                    }
                ],
            },
        ],
    }

    merge_results(report)

    assert report["pipelineRates"]["fetched"] == {"count": 2, "total": 2, "pct": 100.0}
    assert report["pipelineRates"]["hydratedAasx"] == {
        "count": 1,
        "total": 2,
        "pct": 50.0,
    }
    assert report["contractCoverage"]["requiredValidationPassed"]["count"] == 1
    assert report["elements"]["rendererCoverage"] == {"editable": 2, "unknown": 1}
    assert report["elements"]["unknownModelTypes"] == {"FutureElement": 1}
    assert report["preservation"]["semanticIdsPreserved"]["count"] == 1
    assert report["failures"][1]["template"] == "Template B"
    assert report["failures"][1]["path"] == "published/B"
    assert report["shouldFail"] is True


def test_renderer_classification():
    assert classify_renderer("Property") == "editable"
    assert classify_renderer("SubmodelElement") == "readOnly"
    assert classify_renderer("BasicEventElement") == "readOnly"
    assert classify_renderer("FutureElement") == "unknown"


def test_compare_preservation_detects_round_trip_changes():
    original = {
        "supplementaryFiles": ["file.pdf"],
        "elements": [property_schema("Name", semanticId="urn:original")],
    }
    changed = {
        "supplementaryFiles": [],
        "elements": [property_schema("Name", semanticId="urn:changed")],
    }

    preservation = compare_preservation(original, changed)

    assert preservation == {
        "modelTypeCountsPreserved": True,
        "nestedStructurePreserved": True,
        "semanticIdsPreserved": False,
        "qualifiersPreserved": True,
        "supplementaryFilesPreserved": False,
    }


def test_compare_preservation_ignores_list_item_id_short_normalization():
    original = {
        "supplementaryFiles": [],
        "elements": [
            {
                "idShort": "List",
                "modelType": "SubmodelElementList",
                "semanticId": None,
                "semanticLabel": None,
                "description": None,
                "qualifiers": [],
                "cardinality": "[1..*]",
                "category": None,
                "items": [property_schema("PropertyRange")],
            }
        ],
    }
    reparsed = {
        "supplementaryFiles": [],
        "elements": [
            {
                "idShort": "List",
                "modelType": "SubmodelElementList",
                "semanticId": None,
                "semanticLabel": None,
                "description": None,
                "qualifiers": [],
                "cardinality": "[1..*]",
                "category": None,
                "items": [property_schema(None)],
            }
        ],
    }

    assert compare_preservation(original, reparsed)["nestedStructurePreserved"] is True


class FakeFetcher:
    def __init__(self, payload=b"aasx", error: Exception | None = None):
        self.payload = payload
        self.error = error

    async def fetch_template_aasx(self, _template_path):
        if self.error:
            raise self.error
        return self.payload


class FakeParser:
    def __init__(self, schemas=None, error: Exception | None = None):
        self.schemas = list(schemas or [])
        self.error = error

    def parse_aasx_to_ui_schema(self, _aasx_bytes):
        if self.error:
            raise self.error
        return self.schemas.pop(0)


class FakeHydrator:
    def __init__(self, error: Exception | None = None):
        self.error = error

    def hydrate_to_stores(self, _aasx_bytes, _form_data):
        if self.error:
            raise self.error
        return {"store": True}, {"files": True}

    def serialize_stores_to_aasx(self, _store, _files):
        return b"hydrated"

    def serialize_stores_to_json(self, _store):
        return "{}"


class FakeValidationError:
    def __init__(self, *, field="Field", message="invalid", code="invalid"):
        self.field = field
        self.message = message
        self.code = code

    def model_dump(self):
        return {
            "field": self.field,
            "message": self.message,
            "code": self.code,
        }


@pytest.mark.asyncio
async def test_audit_template_classifies_fetch_failure():
    result = await audit_template(
        {"path": "published/Template", "name": "Template"},
        FakeFetcher(error=RuntimeError("offline")),
        FakeParser(),
        FakeHydrator(),
        timeout_seconds=1,
        max_aasx_bytes=100,
        max_schema_nodes=100,
    )

    assert result["failures"][0]["category"] == "fetch_failure"
    assert result["failures"][0]["stage"] == "fetch"


@pytest.mark.asyncio
async def test_audit_template_classifies_parser_failure():
    result = await audit_template(
        {"path": "published/Template", "name": "Template"},
        FakeFetcher(),
        FakeParser(error=ValueError("bad aasx")),
        FakeHydrator(),
        timeout_seconds=1,
        max_aasx_bytes=100,
        max_schema_nodes=100,
    )

    assert result["stages"]["fetched"] is True
    assert result["failures"][0]["category"] == "parser_failure"
    assert result["failures"][0]["stage"] == "parse"


@pytest.mark.asyncio
async def test_audit_template_classifies_size_and_schema_limits():
    too_large = await audit_template(
        {"path": "published/Template", "name": "Template"},
        FakeFetcher(payload=b"x" * 5),
        FakeParser(),
        FakeHydrator(),
        timeout_seconds=1,
        max_aasx_bytes=4,
        max_schema_nodes=100,
    )

    too_many_nodes = await audit_template(
        {"path": "published/Template", "name": "Template"},
        FakeFetcher(),
        FakeParser(schemas=[{"elements": [property_schema("Name")]}]),
        FakeHydrator(),
        timeout_seconds=1,
        max_aasx_bytes=100,
        max_schema_nodes=0,
    )

    assert too_large["failures"][0]["category"] == "aasx_too_large"
    assert too_many_nodes["failures"][0]["category"] == "schema_too_large"


@pytest.mark.asyncio
async def test_audit_template_classifies_required_validation_mismatch(monkeypatch):
    calls = 0

    def fake_validate_form_data(_schema, _form_data):
        nonlocal calls
        calls += 1
        if calls == 2:
            return [FakeValidationError()], []
        return [], []

    monkeypatch.setattr(
        "scripts.audit_template_coverage.validate_form_data",
        fake_validate_form_data,
    )

    result = await audit_template(
        {"path": "published/Template", "name": "Template"},
        FakeFetcher(),
        FakeParser(
            schemas=[
                {"elements": [property_schema("Name")]},
                {"elements": [property_schema("Name")]},
            ]
        ),
        FakeHydrator(),
        timeout_seconds=1,
        max_aasx_bytes=100,
        max_schema_nodes=100,
    )

    assert "validation_mismatch" in {
        failure["category"] for failure in result["failures"]
    }
    assert result["stages"]["requiredValidationPassed"] is False


@pytest.mark.asyncio
async def test_audit_template_classifies_metadata_and_preservation_failures():
    original = {
        "elements": [
            {
                "idShort": "Mystery",
                "modelType": "FutureElement",
                "semanticId": None,
                "semanticLabel": None,
                "description": None,
                "qualifiers": [],
                "cardinality": "[0..1]",
                "category": None,
            },
            property_schema("Broken", value=None),
        ],
        "supplementaryFiles": ["file.pdf"],
    }
    del original["elements"][1]["valueType"]
    reparsed = {
        "elements": [property_schema("Changed", semanticId="urn:changed")],
        "supplementaryFiles": [],
    }

    result = await audit_template(
        {"path": "published/Template", "name": "Template"},
        FakeFetcher(),
        FakeParser(schemas=[original, reparsed]),
        FakeHydrator(),
        timeout_seconds=1,
        max_aasx_bytes=100,
        max_schema_nodes=100,
    )
    categories = {failure["category"] for failure in result["failures"]}

    assert "unsupported_model_type" in categories
    assert "missing_metadata" in categories
    assert "round_trip_mismatch" in categories


@pytest.mark.asyncio
async def test_audit_template_classifies_hydration_failure():
    result = await audit_template(
        {"path": "published/Template", "name": "Template"},
        FakeFetcher(),
        FakeParser(schemas=[{"elements": [property_schema("Name")]}]),
        FakeHydrator(error=RuntimeError("cannot hydrate")),
        timeout_seconds=1,
        max_aasx_bytes=100,
        max_schema_nodes=100,
    )

    assert result["failures"][-1]["category"] == "hydration_failure"
    assert result["failures"][-1]["stage"] == "hydrate-aasx"


@pytest.mark.asyncio
async def test_run_audit_uses_scoped_cache_and_disables_local_templates(
    tmp_path,
    monkeypatch,
):
    captured = {}

    class FakeAuditFetcher:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        async def list_available_templates(self, statuses, include_local=False):
            captured["statuses"] = statuses
            captured["include_local"] = include_local
            return [], False

    monkeypatch.setattr(
        "scripts.audit_template_coverage.TemplateFetcherService",
        FakeAuditFetcher,
    )

    report = await run_audit(
        statuses=["published", "deprecated"],
        template_filters=[],
        max_templates=None,
        concurrency=99,
        cache_dir=tmp_path / "tmp/template-audit/cache/templates",
        timeout_seconds=1,
        max_aasx_bytes=100,
        max_schema_nodes=100,
    )

    assert captured["cache_dir"] == tmp_path / "tmp/template-audit/cache/templates"
    assert captured["local_templates_enabled"] is False
    assert captured["statuses"] == ["published", "deprecated"]
    assert captured["include_local"] is False
    assert report["requestedConcurrency"] == 99
    assert report["concurrency"] == 8
