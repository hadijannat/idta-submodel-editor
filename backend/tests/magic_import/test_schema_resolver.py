"""Tests for SchemaResolver hint extraction."""

from app.services.magic_import.schema_resolver import SchemaResolver


def test_hint_extraction_required_and_value_type():
    resolver = SchemaResolver()

    elements = [
        {
            "idShort": "Foo",
            "modelType": "Property",
            "cardinality": "[1]",
            "valueType": "xsd:int",
            "semanticId": "urn:foo",
        },
        {
            "idShort": "Bar",
            "modelType": "Property",
            "cardinality": "[0..1]",
            "valueType": "xs:date",
            "semanticId": {"keys": [{"value": "urn:bar"}]},
        },
        {
            "idShort": "Baz",
            "modelType": "Property",
            "cardinality": "ZeroToMany",
            "valueType": "xsd:decimal",
        },
        {
            "idShort": "Qux",
            "modelType": "Property",
            "cardinality": "OneToMany",
            "valueType": "xs:string",
        },
    ]

    hints = resolver._extract_hints(elements)
    hints_by_path = {hint.path: hint for hint in hints}

    foo = hints_by_path["Foo"]
    assert foo.required is True
    assert foo.value_type == "xs:int"
    assert foo.semantic_id == "urn:foo"

    bar = hints_by_path["Bar"]
    assert bar.required is False
    assert bar.value_type == "xs:date"
    assert bar.semantic_id == "urn:bar"

    baz = hints_by_path["Baz"]
    assert baz.required is False
    assert baz.value_type == "xs:decimal"

    qux = hints_by_path["Qux"]
    assert qux.required is True
    assert qux.value_type == "xs:string"


def test_list_item_hint_path_and_type():
    resolver = SchemaResolver()

    elements = [
        {
            "idShort": "Measurements",
            "modelType": "SubmodelElementList",
            "itemTemplate": {
                "idShort": "Temperature",
                "modelType": "Property",
                "valueType": "xsd:double",
            },
        }
    ]

    hints = resolver._extract_hints(elements)
    assert len(hints) == 1

    hint = hints[0]
    assert hint.path == "Measurements[].Temperature"
    assert hint.value_type == "xs:double"
