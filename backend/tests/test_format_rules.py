"""Tests for recognising format standards in template specification text."""

import pytest

from app.services.format_rules import (
    check_format,
    detect_format_hint,
    find_irdi_enumeration,
    find_referenced_standards,
)


def hint_id(id_short: str, text: str = "", value_type: str = "xs:string") -> str | None:
    hint = detect_format_hint(
        id_short=id_short, model_type="Property", value_type=value_type, texts=[text]
    )
    return hint.id if hint else None


@pytest.mark.parametrize(
    ("id_short", "text", "expected"),
    [
        (
            "CountryOfOrigin",
            "Note: Country codes defined accord. to DIN EN ISO 3166-1 alpha-2 codes",
            "iso3166-1-alpha2",
        ),
        ("NationalCode", "Two-digit country code according to ISO 3166 ALPHA-2", "iso3166-1-alpha2"),
        ("Language", "Note: language codes defined accord. to ISO 639-1.", "iso639"),
        ("Currency", "The currency used. Must be a three-letter ISO currency code.", "iso4217"),
        ("StatusSetDate", "Date when the document status was set. Format is YYYY-MM-DD.", "iso8601-date"),
        (
            "Duration",
            "represented according to ISO 8601 by the format P[n]Y[n]M[n]DT[n]H[n]M[n]S",
            "iso8601-duration",
        ),
        ("TimeZone", "Note: notation accord. to ISO 8601", "iso8601-timezone"),
        (
            "lastUpdate",
            "String formatted as Timestamp UTC-based according to ISO 8601-1:2019",
            "iso8601-datetime",
        ),
        ("URIOfTheProduct", "identification link according to IEC 61406", "iec61406"),
        ("EmailAddress", "electronic mail address of a business partner", "email"),
        ("TelephoneNumber", "complete telephone number", "phone"),
        ("FaxNumber", "", "phone"),
        ("YearOfConstruction", "year in which the manufacturing process is completed", "year"),
        ("AddressOfAdditionalLink", "web site address", "url"),
        ("GTIN", "GTIN", "gtin"),
        ("MimeType", "The MIME-Type of the file", "mime"),
    ],
)
def test_detects_format_from_specification_text_or_name(id_short, text, expected):
    assert hint_id(id_short, text) == expected


@pytest.mark.parametrize(
    "id_short",
    ["TypeOfEmailAddress", "TypeOfTelephone", "ManufacturerName", "SerialNumber"],
)
def test_does_not_guess_for_unrelated_fields(id_short):
    assert hint_id(id_short, "characterization of an address according to its usage") is None


def test_any_uri_value_type_yields_uri_hint():
    hint = detect_format_hint(
        id_short="proxy", model_type="Property", value_type="xs:anyURI", texts=[]
    )

    assert hint is not None
    assert hint.id == "uri"
    assert hint.source == "valueType"


def test_typed_and_non_property_elements_get_no_hint():
    assert hint_id("IssueDate", "format CCYY-MM-DD", value_type="xs:date") is None
    assert (
        detect_format_hint(
            id_short="CountryOfOrigin",
            model_type="MultiLanguageProperty",
            value_type=None,
            texts=["ISO 3166-1"],
        )
        is None
    )


@pytest.mark.parametrize(
    ("hint", "value", "ok"),
    [
        ("iso3166-1-alpha2", "DE", True),
        ("iso3166-1-alpha2", "de", False),
        ("iso3166-1-alpha2", "XX", False),
        ("iso4217", "EUR", True),
        ("iso4217", "EURO", False),
        ("iso639", "en-US", True),
        ("iso639", "English", False),
        ("iso8601-date", "2025-01-31", True),
        ("iso8601-date", "31.01.2025", False),
        ("iso8601-datetime", "2025-01-31T14:30:00Z", True),
        ("iso8601-duration", "PT30M", True),
        ("iso8601-duration", "30 minutes", False),
        ("iso8601-timezone", "+01:00", True),
        ("iso8601-timezone", "CET", False),
        ("email", "info@example.com", True),
        ("email", "info at example", False),
        ("phone", "+49 241 123456", True),
        ("uri", "www.example.com", False),
        ("uri", "urn:example:1", True),
        ("gtin", "4006381333931", True),
        ("gtin", "4006381333932", False),
        ("year", "2025", True),
        ("year", "25", False),
        ("uuid", "123e4567-e89b-12d3-a456-426614174000", True),
        ("mime", "application/pdf", True),
        ("mime", "pdf", False),
    ],
)
def test_check_format(hint, value, ok):
    assert (check_format(hint, value) is None) is ok


def test_check_format_ignores_blank_and_unknown():
    assert check_format("iso3166-1-alpha2", "") is None
    assert check_format("iso3166-1-alpha2", None) is None
    assert check_format("unknown-hint", "anything") is None


def test_find_referenced_standards():
    standards = find_referenced_standards(
        [
            "Country codes accord. to DIN EN ISO 3166-1 alpha-2, see also IEC 61406 "
            "and ISO8601. Media types per RFC2046 (VDI 2770).",
            "ISO 3166-1 again",
        ]
    )

    assert standards == ["DIN EN ISO 3166-1", "IEC 61406", "ISO 8601", "RFC 2046", "VDI 2770"]
    assert find_referenced_standards(["page 12 of 20, version 3"]) == []


def test_find_irdi_enumeration():
    options = find_irdi_enumeration(
        [
            "enumeration: 0173-1#07-AAS927#001 (administrativ contact), "
            "0173-1#07-AAS928#001 (commercial contact), 0173-1#07-AAS929#001 (other contact)"
        ]
    )

    assert options[0] == {
        "value": "0173-1#07-AAS927#001",
        "label": "administrativ contact",
        "valueId": "0173-1#07-AAS927#001",
    }
    assert len(options) == 3
    # A single IRDI in prose is a reference, not an enumeration.
    assert find_irdi_enumeration(["see 0173-1#07-AAS927#001 (administrativ contact)"]) == []
