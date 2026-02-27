"""
Tests for form validation helpers.
"""

from app.services.validation import _is_valid_reference, validate_form_data


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


def test_collection_with_none_elements_does_not_raise():
    schema = _schema(
        [
            {
                "idShort": "Coll",
                "modelType": "SubmodelElementCollection",
                "cardinality": "[0..1]",
                "elements": [
                    {
                        "idShort": "Inner",
                        "modelType": "Property",
                        "cardinality": "[1]",
                        "valueType": "xs:string",
                    }
                ],
            }
        ]
    )
    form_data = {"elements": {"Coll": {"elements": None}}}
    errors, warnings = validate_form_data(schema, form_data)

    assert any(e.code == "required" and e.field == "Coll.Inner" for e in errors)
    assert warnings == []


def test_list_with_none_items_does_not_raise():
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
    form_data = {"elements": {"Items": {"items": None}}}
    errors, warnings = validate_form_data(schema, form_data)

    assert any(e.code == "min_items" and e.field == "Items" for e in errors)
    assert warnings == []


def test_entity_with_none_statements_does_not_raise():
    schema = _schema(
        [
            {
                "idShort": "EntityX",
                "modelType": "Entity",
                "cardinality": "[0..1]",
                "statements": [
                    {
                        "idShort": "Inner",
                        "modelType": "Property",
                        "cardinality": "[1]",
                        "valueType": "xs:string",
                    }
                ],
            }
        ]
    )
    form_data = {"elements": {"EntityX": {"statements": None}}}
    errors, warnings = validate_form_data(schema, form_data)

    assert any(e.code == "required" and e.field == "EntityX.Inner" for e in errors)
    assert warnings == []


def test_reference_validation_accepts_valid_irdi():
    assert _is_valid_reference("0173-1#02-AAA123#001")


def test_reference_validation_rejects_invalid_irdi():
    assert not _is_valid_reference("0173-1#2-AAA123#001")


def test_reference_validation_accepts_https_uri():
    assert _is_valid_reference("https://example.com/semantic/123")


def test_reference_validation_accepts_urn_uri():
    assert _is_valid_reference("urn:example:semantic:123")


def test_reference_validation_rejects_non_uri_value():
    assert not _is_valid_reference("not a valid reference")


def test_cardinality_symbolic_one_to_many_requires_items():
    schema = _schema(
        [
            {
                "idShort": "Documents",
                "modelType": "SubmodelElementList",
                "cardinality": "OneToMany",
                "itemTemplate": {
                    "idShort": "",
                    "modelType": "Property",
                    "cardinality": "[1]",
                    "valueType": "xs:string",
                },
            }
        ]
    )
    form_data = {"elements": {"Documents": {"items": []}}}
    errors, _ = validate_form_data(schema, form_data)
    assert any(e.code == "min_items" for e in errors)


def test_reference_element_rejects_invalid_reference():
    schema = _schema(
        [
            {
                "idShort": "RelatedAsset",
                "modelType": "ReferenceElement",
                "cardinality": "[1]",
            }
        ]
    )
    form_data = {"elements": {"RelatedAsset": {"value": "not-an-iri"}}}
    errors, warnings = validate_form_data(schema, form_data)
    assert any(e.code == "invalid_reference" for e in errors)
    assert warnings == []


def test_property_date_type_mismatch_is_reported():
    schema = _schema(
        [
            {
                "idShort": "ManufacturedOn",
                "modelType": "Property",
                "cardinality": "[1]",
                "valueType": "xs:date",
            }
        ]
    )
    form_data = {"elements": {"ManufacturedOn": {"value": "31-12-2025"}}}
    errors, _ = validate_form_data(schema, form_data)
    assert any(e.code == "type_mismatch" for e in errors)
