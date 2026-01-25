"""
Tests for form validation helpers.
"""

from app.services.validation import validate_form_data


def _schema(elements):
    return {"elements": elements}


def test_required_property_string_empty_is_error():
    schema = _schema(
        [
            {
                "idShort": "Name",
                "modelType": "Property",
                "cardinality": "[1]",
                "valueType": "xs:string",
            }
        ]
    )
    form_data = {"elements": {"Name": {"value": ""}}}
    errors, warnings = validate_form_data(schema, form_data)

    assert any(e.code == "required_value" for e in errors)
    assert warnings == []


def test_optional_property_missing_is_ok():
    schema = _schema(
        [
            {
                "idShort": "Note",
                "modelType": "Property",
                "cardinality": "[0..1]",
                "valueType": "xs:string",
            }
        ]
    )
    form_data = {"elements": {}}
    errors, warnings = validate_form_data(schema, form_data)

    assert errors == []
    assert warnings == []


def test_list_item_property_type_mismatch_is_reported():
    schema = _schema(
        [
            {
                "idShort": "Items",
                "modelType": "SubmodelElementList",
                "cardinality": "[1..*]",
                "itemTemplate": {
                    "idShort": "",
                    "modelType": "Property",
                    "cardinality": "[1]",
                    "valueType": "xs:int",
                },
            }
        ]
    )
    form_data = {"elements": {"Items": {"items": [{"value": "abc"}]}}}
    errors, warnings = validate_form_data(schema, form_data)

    assert any(e.code == "type_mismatch" and e.field == "Items[0]" for e in errors)
    assert warnings == []


def test_list_min_items_enforced():
    schema = _schema(
        [
            {
                "idShort": "Items",
                "modelType": "SubmodelElementList",
                "cardinality": "[1..*]",
                "itemTemplate": {
                    "idShort": "",
                    "modelType": "Property",
                    "cardinality": "[1]",
                    "valueType": "xs:string",
                },
            }
        ]
    )
    form_data = {"elements": {"Items": {"items": []}}}
    errors, warnings = validate_form_data(schema, form_data)

    assert any(e.code == "min_items" for e in errors)
    assert warnings == []


def test_multilang_whitespace_is_invalid():
    schema = _schema(
        [
            {
                "idShort": "Label",
                "modelType": "MultiLanguageProperty",
                "cardinality": "[1]",
            }
        ]
    )
    form_data = {"elements": {"Label": {"value": {"en": "   "}}}}
    errors, warnings = validate_form_data(schema, form_data)

    assert any(e.code == "required_translation" for e in errors)
    assert warnings == []
