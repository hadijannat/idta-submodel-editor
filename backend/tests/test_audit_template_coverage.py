from collections import defaultdict

from scripts.audit_template_coverage import (
    _empty_coverage_counter,
    analyze_schema,
    build_required_element,
    classify_renderer,
    compare_preservation,
    finalize_coverage,
    generate_default_form_data,
    generate_required_form_data,
    iter_schema_elements,
    json_safe_value,
    merge_metadata_coverage,
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
        ]
    }

    paths = [path for path, _ in iter_schema_elements(schema["elements"])]

    assert "Collection.elements.Nested" in paths
    assert "List.items.Item" in paths
    assert "List.itemTemplate.Template" in paths
    assert "Operation.inputVariables.Input" in paths
    assert "Operation.outputVariables.Output" in paths


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
