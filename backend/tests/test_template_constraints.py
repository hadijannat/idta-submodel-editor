"""Tests for the interpretation of template qualifiers and IEC 61360 content."""

import pytest

from app.services.template_constraints import (
    describe_value_format,
    extract_constraints,
    normalize_cardinality,
    parse_allowed_range,
    parse_allowed_value,
    qualifier_family,
)


def q(qualifier_type: str, value: str) -> dict:
    return {"type": qualifier_type, "value": value, "valueType": "xs:string", "kind": None}


@pytest.mark.parametrize(
    ("qualifier_type", "family"),
    [
        ("SMT/Cardinality", "cardinality"),
        ("Cardinality", "cardinality"),
        ("SMT/SMT/Cardinality", "cardinality"),
        ("Multiplicity", "multiplicity"),
        ("SMT/AllowedValue2", "allowedvalue"),
        ("SMT/ExampleValue/ECLASS", "examplevalue"),
        ("life cycle qual", "lifecyclequal"),
        ("FormChoices", "formchoices"),
        (None, ""),
    ],
)
def test_qualifier_family_normalizes_published_spellings(qualifier_type, family):
    assert qualifier_family(qualifier_type) == family


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("One", "[1]"),
        ("ZeroToOne", "[0..1]"),
        ("zeroToMany", "[0..*]"),
        ("OneToMany", "[1..*]"),
        ("0..1", "[0..1]"),
        ("[1..*]", "[1..*]"),
        ("1", "[1]"),
        ("", None),
        (None, None),
    ],
)
def test_normalize_cardinality(value, expected):
    assert normalize_cardinality(value) == expected


def test_allowed_value_enumeration_is_strict():
    result = extract_constraints([q("SMT/AllowedValue", "pass;fail")])

    assert [option["value"] for option in result["allowedValues"]] == ["pass", "fail"]
    assert result["allowedValuesStrict"] is True
    assert "pattern" not in result


def test_numbered_allowed_values_are_merged():
    result = extract_constraints(
        [
            q("SMT/AllowedValue1", "Purchaser"),
            q("SMT/AllowedValue2", "Consignee"),
            q("SMT/AllowedValue3", "ConsigneeOfCertificate"),
        ]
    )

    assert [option["value"] for option in result["allowedValues"]] == [
        "Purchaser",
        "Consignee",
        "ConsigneeOfCertificate",
    ]
    assert result["allowedValuesStrict"] is True


def test_allowed_value_regular_expression_becomes_pattern():
    choices, pattern = parse_allowed_value(r"[A-Z]{2}\d{4}")

    assert choices == []
    assert pattern == r"[A-Z]{2}\d{4}"
    assert parse_allowed_value("[unclosed") == ([], None)


def test_form_choices_and_enumeration_are_suggestions():
    result = extract_constraints(
        [q("FormChoices", "low;medium;high"), q("enumeration", "SIL 1, SIL 2")]
    )

    assert [option["value"] for option in result["allowedValues"]] == [
        "low",
        "medium",
        "high",
        "SIL 1",
        "SIL 2",
    ]
    assert result["allowedValuesStrict"] is False


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("[0,63]", {"min": 0, "max": 63}),
        ("[0x00000000 , 0x1fffffff]", {"min": 0, "max": 536870911}),
        ("0..100", {"min": 0, "max": 100}),
        ("[0.5;2.5]", {"min": 0.5, "max": 2.5}),
        (">= 1", {"min": 1, "max": None}),
        ("< 10", {"min": None, "max": 10}),
        ("positive numbers", None),
    ],
)
def test_parse_allowed_range(value, expected):
    assert parse_allowed_range(value) == expected


def test_examples_defaults_languages_and_groups():
    result = extract_constraints(
        [
            q("SMT/ExampleValue", "2.35"),
            q("ExampleValue", "ECLASS|IEC CDD|UNSPSC"),
            q("SMT/DefaultValue", "Medium"),
            q("SMT/InitialValue", "0"),
            q("SMT/RequiredLang", "en"),
            q("SMT/RequiredLang", "de, en"),
            q("SMT/EitherOr", "Location"),
            q("SMT/AllowedRange", "[1,64]"),
            q("AllowedIdShort", r"Policy[\d]{2,3}"),
            q("EditIdShort", "True"),
            q("SMT/AccessMode", "ReadOnly"),
            q("FormInfo", "Explain the field"),
            q("FormUrl", "https://example.org/spec"),
            q("Note", "see chapter 4"),
            q("LifeCycleQual", "SPEC"),
            q("unit", "per hour"),
            q("SMT/Cardinality", "ZeroToOne"),
        ]
    )

    assert result["exampleValues"] == ["2.35", "ECLASS", "IEC CDD", "UNSPSC"]
    assert result["defaultValue"] == "Medium"
    assert result["initialValue"] == "0"
    assert result["requiredLanguages"] == ["en", "de"]
    assert result["eitherOr"] == "Location"
    assert result["allowedRange"] == {"min": 1, "max": 64}
    assert result["allowedIdShort"] == r"Policy[\d]{2,3}"
    assert result["editIdShort"] is True
    assert result["readOnly"] is True
    assert result["formInfo"] == "Explain the field"
    assert result["formUrl"] == "https://example.org/spec"
    assert result["notes"] == ["see chapter 4", "Life cycle: SPEC"]
    assert result["qualifierUnit"] == "per hour"
    assert "cardinality" not in result


def test_iec61360_value_list_becomes_non_strict_enumeration():
    result = extract_constraints(
        [],
        value_list=[
            {"value": "office", "valueId": "0173-1#07-AAS754#001"},
            {"value": "home", "valueId": "0173-1#07-AAS756#001"},
        ],
    )

    assert result["allowedValues"] == [
        {"value": "office", "label": None, "valueId": "0173-1#07-AAS754#001"},
        {"value": "home", "label": None, "valueId": "0173-1#07-AAS756#001"},
    ]
    assert result["allowedValuesStrict"] is False


def test_single_entry_value_list_is_an_example_not_an_enumeration():
    result = extract_constraints([], value_list=[{"value": "en", "valueId": None}])

    assert "allowedValues" not in result
    assert result["exampleValues"] == ["en"]


@pytest.mark.parametrize(
    ("value_format", "description", "max_length", "min_length"),
    [
        ("X..10", "up to 10 characters", 10, None),
        ("X10", "exactly 10 characters", 10, 10),
        ("NR1..7", "integer with up to 7 digits", None, None),
        ("NR2..2.1", "decimal number with up to 2 integer and 1 fractional digits", None, None),
        ("NR3..1.2E1", "number in exponent notation", None, None),
    ],
)
def test_describe_value_format(value_format, description, max_length, min_length):
    info = describe_value_format(value_format)

    assert info is not None
    assert info["description"] == description
    assert info["maxLength"] == max_length
    assert info["minLength"] == min_length


def test_value_format_is_exposed_with_length_bound():
    result = extract_constraints([], value_format="X..35")

    assert result["valueFormat"] == "X..35"
    assert result["valueFormatDescription"] == "up to 35 characters"
    assert result["maxLength"] == 35
    assert describe_value_format(None) is None
