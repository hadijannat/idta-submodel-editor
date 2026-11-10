"""Tests for the IDTA specification PDF extractor (app.services.spec_pdf).

The unit tests build small synthetic PDFs with WeasyPrint that reproduce the
IDTA table convention; they do not need the real specifications.  Optional
tests against real specification PDFs run when ``IDTA_SPEC_PDF_DIR`` points to
a directory containing them (e.g. ``nameplate.pdf``).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.services.spec_pdf import (
    SpecDocument,
    SpecElement,
    extract_spec_document,
    normalize_spec_key,
)

# ---------------------------------------------------------------------------
# Synthetic PDF builders
# ---------------------------------------------------------------------------

_CSS = """
@page { size: A4; margin: 2cm }
body { font-family: sans-serif; font-size: 9pt }
table { border-collapse: collapse; width: 100%; table-layout: fixed; margin-bottom: 14pt }
td { border: 0.5pt solid #444; padding: 3pt; vertical-align: top; text-align: left }
td.c0 { width: 15% }
td.c1 { width: 52%; overflow-wrap: anywhere }
td.c2 { width: 21%; overflow-wrap: anywhere; word-break: break-all }
td.c3 { width: 12% }
table.plain td { border: none }
tr { break-inside: avoid }
"""


def _render(body: str) -> bytes:
    weasyprint = pytest.importorskip("weasyprint")
    html = f"<html><head><style>{_CSS}</style></head><body>{body}</body></html>"
    return weasyprint.HTML(string=html).write_pdf()


def _header(
    id_short: str,
    *,
    cls: str = "Submodel",
    semantic_id: str = "https://example.org/idta/demo/1/0/Demo",
    parent: str = "-",
    explanation: str = "Demo table",
) -> str:
    return f"""
<tr><td class="c0">idShort:</td><td colspan="3">{id_short}</td></tr>
<tr><td class="c0">Class:</td><td colspan="3">{cls}</td></tr>
<tr><td class="c0">semanticId:</td><td colspan="3">{semantic_id}</td></tr>
<tr><td class="c0">Parent:</td><td colspan="3">{parent}</td></tr>
<tr><td class="c0">Explanation:</td><td colspan="3">{explanation}</td></tr>
<tr><td class="c0">[SME type]<br>idShort</td><td class="c1">semanticId<br>Description@en</td>
<td class="c2">[valueType]<br>example</td><td class="c3">card.</td></tr>"""


def _row(first: str, second: str, third: str, fourth: str) -> str:
    return (
        f'<tr><td class="c0">{first}</td><td class="c1">{second}</td>'
        f'<td class="c2">{third}</td><td class="c3">{fourth}</td></tr>'
    )


_NAMEPLATE_ROWS = [
    _row(
        "[Prop]<br>URIOfTheProd<br>uct",
        "0112/2///61987#ABN590#002<br>supplementalSemanticId: 0173-1#02-ABH173#003<br>"
        "unique global identification of the product instance using an universal resource "
        "identifier (URI)",
        "[AnyUri]<br>https://www.domain-abc.com/Model-Nr-1234/Serial-Nr-5678",
        "1",
    ),
    _row(
        "[MLP]<br>ManufacturerN<br>ame",
        "0112/2///61987#ABA565#009<br>legally valid designation of the natural or judicial person",
        '[]<br>"Muster AG"@de',
        "1",
    ),
    _row(
        "[SubmodelElem<br>entCollection]<br>ContactInformati<br>on{00}",
        "[IRI] https://example.org/zvei/nameplate/1/0/ContactInformations/ContactInformation<br>"
        "contains information on how to contact the manufacturer<br>See separate clause",
        "n/a",
        "[0..*]",
    ),
    _row(
        "[Prop]<br>DesignationOf<br>CertificateOrA<br>pproval",
        "0112/2///61987#ABH783#003<br>alphanumeric character sequence identifying a certificate "
        "or approval<br>Note: Approval identifier, reference to the certificate number, to be "
        "entered without spaces",
        "[String]<br>KEMA99IECEX1105/128-0123456789ABCDEFGHIJ",
        "0..1",
    ),
    _row(
        "[Prop]<br>IssueDate",
        "0112/2///61987#ABO097#001<br>date, at which the specified certificate is issued<br>"
        "Note: format by lexical representation: CCYY-MM-DD<br>Note: to be specified to the day",
        "[Date]<br>2022-01-01",
        "0..1",
    ),
    _row(
        "[SML]<br>Markings",
        "0112/2///61360_7#AAS006#001<br>Note: CE marking is declared as mandatory",
        "[]<br>1 elements",
        "0..1",
    ),
    _row(
        "[File]<br>CompanyLogo",
        "0112/2///61987#ABP463#001<br>a graphic mark used to represent a company",
        "-",
        "[0..1]",
    ),
    _row(
        "[Range]<br>OperatingRange",
        "https://example.org/idta/demo/1/0/OperatingRange<br>"
        "Constraint AASd-999: min shall be lower than max",
        "[Double]<br>1.5",
        "[1..*]",
    ),
]


@pytest.fixture(scope="module")
def nameplate_doc() -> SpecDocument:
    body = (
        "<h1>IDTA 09999-1-0 Demo Spec</h1><table>"
        + _header("Nameplate", explanation="Contains the nameplate information")
        + "".join(_NAMEPLATE_ROWS)
        + "</table>"
        # detail table of a nested collection, with an idShort that also occurs above
        + "<p>Detail table</p><table>"
        + _header(
            "Markings__00__",
            cls="SubmodelElementCollection",
            semantic_id="0112/2///61360_7#AAS009#001",
            parent="Markings",
            explanation="Note: one entry per marking",
        )
        + _row(
            "[Prop]<br>MarkingName",
            "0112/2///61987#ABA231#009<br>common name of the marking",
            "[String]<br>CE",
            "1",
        )
        + _row(
            "[Prop]<br>IssueDate",
            "0112/2///61987#ABO097#001<br>issue date of the marking",
            "[Date]",
            "1",
        )
        + "</table>"
        # the overview table repeats a row of the first table (duplicate)
        + "<p>Overview repeated</p><table>"
        + _header("Nameplate")
        + _row(
            "[Prop]<br>IssueDate",
            "0112/2///61987#ABO097#001<br>date, at which the specified certificate is issued "
            "and from which on it is valid<br>Note: overview note",
            "[Date]",
            "0..1",
        )
        + "</table>"
    )
    return extract_spec_document(_render(body))


# ---------------------------------------------------------------------------
# normalize_spec_key
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ManufacturerName", "manufacturername"),
        ("Markings__00__", "markings"),
        ("ContactInformation{00}", "contactinformation"),
        ("Time{00}", "time"),
        ("IPCommunication{ 01 }", "ipcommunication"),
        ("SoftwareNameplate_Instance", "softwarenameplateinstance"),
        ("  URIOfTheProduct ", "urioftheproduct"),
        ("PcfCO2eq", "pcfco2eq"),
        ("Document01", "document01"),
        ("{Variable}", "variable"),
        ("", ""),
    ],
)
def test_normalize_spec_key(raw: str, expected: str) -> None:
    assert normalize_spec_key(raw) == expected


def test_normalize_spec_key_tolerates_non_strings() -> None:
    assert normalize_spec_key(None) == ""  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Clean four-column layout
# ---------------------------------------------------------------------------


def test_clean_table_extracts_every_row(nameplate_doc: SpecDocument) -> None:
    assert nameplate_doc.page_count >= 1
    assert nameplate_doc.warnings == []
    rows = [el.id_short for el in nameplate_doc.elements if el.parent == "Nameplate"]
    assert rows == [
        "URIOfTheProduct",
        "ManufacturerName",
        "ContactInformation{00}",
        "DesignationOfCertificateOrApproval",
        "IssueDate",
        "Markings",
        "CompanyLogo",
        "OperatingRange",
    ]


def test_wrapped_id_shorts_are_joined(nameplate_doc: SpecDocument) -> None:
    element = nameplate_doc.lookup("DesignationOfCertificateOrApproval")
    assert element is not None
    assert element.id_short == "DesignationOfCertificateOrApproval"
    assert element.key == "designationofcertificateorapproval"
    assert element.sme_type == "Property"
    assert element.parent == "Nameplate"
    assert element.page == 1

    wrapped_tag = nameplate_doc.lookup("ContactInformation")
    assert wrapped_tag is not None
    assert wrapped_tag.id_short == "ContactInformation{00}"
    assert wrapped_tag.sme_type == "SubmodelElementCollection"
    assert wrapped_tag.cardinality == "[0..*]"


def test_notes_are_separated_from_description(nameplate_doc: SpecDocument) -> None:
    issue_date = nameplate_doc.lookup("IssueDate", parent="Nameplate")
    assert issue_date is not None
    assert issue_date.semantic_id == "0112/2///61987#ABO097#001"
    assert issue_date.value_type == "Date"
    assert issue_date.example == "2022-01-01"
    assert issue_date.cardinality == "[0..1]"
    assert "format by lexical representation: CCYY-MM-DD" in issue_date.notes
    assert "to be specified to the day" in issue_date.notes
    assert issue_date.description is not None
    assert "Note" not in issue_date.description
    assert "0112/2" not in issue_date.description

    designation = nameplate_doc.lookup("DesignationOfCertificateOrApproval")
    assert designation is not None
    assert designation.description == (
        "alphanumeric character sequence identifying a certificate or approval"
    )
    assert designation.notes == [
        "Approval identifier, reference to the certificate number, to be entered without spaces"
    ]


def test_constraint_sentences_become_notes(nameplate_doc: SpecDocument) -> None:
    element = nameplate_doc.lookup("OperatingRange")
    assert element is not None
    assert element.sme_type == "Range"
    assert element.description is None
    assert element.notes == ["Constraint AASd-999: min shall be lower than max"]
    assert element.semantic_id == "https://example.org/idta/demo/1/0/OperatingRange"


def test_supplemental_semantic_id_is_not_description(nameplate_doc: SpecDocument) -> None:
    element = nameplate_doc.lookup("URIOfTheProduct")
    assert element is not None
    assert element.semantic_id == "0112/2///61987#ABN590#002"
    assert element.description == (
        "unique global identification of the product instance using an universal resource "
        "identifier (URI)"
    )
    assert element.notes == []


def test_id_type_prefix_is_stripped(nameplate_doc: SpecDocument) -> None:
    element = nameplate_doc.lookup("ContactInformation{00}")
    assert element is not None
    assert element.semantic_id == (
        "https://example.org/zvei/nameplate/1/0/ContactInformations/ContactInformation"
    )
    assert element.description is not None
    assert element.description.startswith("contains information on how to contact")


@pytest.mark.parametrize(
    ("id_short", "cardinality"),
    [
        ("URIOfTheProduct", "[1]"),
        ("IssueDate", "[0..1]"),
        ("CompanyLogo", "[0..1]"),
        ("ContactInformation", "[0..*]"),
        ("OperatingRange", "[1..*]"),
    ],
)
def test_cardinalities_are_normalized(
    nameplate_doc: SpecDocument, id_short: str, cardinality: str
) -> None:
    element = nameplate_doc.lookup(id_short, parent="Nameplate")
    assert element is not None
    assert element.cardinality == cardinality


def test_examples_and_value_types(nameplate_doc: SpecDocument) -> None:
    uri = nameplate_doc.lookup("URIOfTheProduct")
    assert uri is not None
    assert uri.value_type == "AnyUri"
    # hard-wrapped inside the narrow cell: joined without blanks
    assert uri.example == "https://www.domain-abc.com/Model-Nr-1234/Serial-Nr-5678"

    designation = nameplate_doc.lookup("DesignationOfCertificateOrApproval")
    assert designation is not None
    assert designation.value_type == "String"
    assert designation.example == "KEMA99IECEX1105/128-0123456789ABCDEFGHIJ"

    name = nameplate_doc.lookup("ManufacturerName")
    assert name is not None
    assert name.sme_type == "MultiLanguageProperty"
    assert name.value_type is None  # "[]"
    assert name.example == '"Muster AG"@de'


@pytest.mark.parametrize("id_short", ["ContactInformation", "Markings", "CompanyLogo"])
def test_placeholder_examples_are_none(nameplate_doc: SpecDocument, id_short: str) -> None:
    element = nameplate_doc.lookup(id_short, parent="Nameplate")
    assert element is not None
    assert element.example is None  # "n/a", "1 elements", "-"
    assert element.value_type is None


def test_sme_type_names_are_normalized(nameplate_doc: SpecDocument) -> None:
    types = {el.id_short: el.sme_type for el in nameplate_doc.elements if el.parent == "Nameplate"}
    assert types["Markings"] == "SubmodelElementList"
    assert types["CompanyLogo"] == "File"
    assert types["ManufacturerName"] == "MultiLanguageProperty"
    assert types["ContactInformation{00}"] == "SubmodelElementCollection"


def test_table_header_yields_the_described_element(nameplate_doc: SpecDocument) -> None:
    submodel = nameplate_doc.lookup("Nameplate")
    assert submodel is not None
    assert submodel.sme_type == "Submodel"
    assert submodel.semantic_id == "https://example.org/idta/demo/1/0/Demo"
    assert submodel.description == "Contains the nameplate information"
    assert submodel.parent is None
    assert submodel.cardinality is None

    item = nameplate_doc.lookup("Markings__00__", parent="Markings")
    assert item is not None
    assert item.id_short == "Markings__00__"
    assert item.sme_type == "SubmodelElementCollection"
    assert item.semantic_id == "0112/2///61360_7#AAS009#001"
    assert item.notes == ["one entry per marking"]


def test_title_from_first_page(nameplate_doc: SpecDocument) -> None:
    assert nameplate_doc.title == "IDTA 09999-1-0 Demo Spec"


# ---------------------------------------------------------------------------
# Duplicates and lookup
# ---------------------------------------------------------------------------


def test_duplicate_rows_are_merged(nameplate_doc: SpecDocument) -> None:
    matches = [
        el for el in nameplate_doc.elements if el.key == "issuedate" and el.parent == "Nameplate"
    ]
    assert len(matches) == 1
    merged = matches[0]
    # richest description wins, notes are united, scalar fields of the first row survive
    assert merged.description == (
        "date, at which the specified certificate is issued and from which on it is valid"
    )
    assert merged.notes == [
        "format by lexical representation: CCYY-MM-DD",
        "to be specified to the day",
        "overview note",
    ]
    assert merged.example == "2022-01-01"
    assert merged.cardinality == "[0..1]"
    assert merged.page == 1


def test_lookup_prefers_matching_parent(nameplate_doc: SpecDocument) -> None:
    top = nameplate_doc.lookup("IssueDate", parent="Nameplate")
    nested = nameplate_doc.lookup("IssueDate", parent="Markings__00__")
    assert top is not None and nested is not None
    assert top is not nested
    assert top.cardinality == "[0..1]"
    assert nested.cardinality == "[1]"
    assert nested.parent == "Markings__00__"
    assert nested.description == "issue date of the marking"
    # parent is matched by normalized key as well
    assert nameplate_doc.lookup("issuedate", parent="markings{00}") is nested


def test_lookup_without_or_with_unknown_parent(nameplate_doc: SpecDocument) -> None:
    first = nameplate_doc.lookup("IssueDate")
    assert first is not None
    assert first.parent == "Nameplate"
    assert nameplate_doc.lookup("IssueDate", parent="DoesNotExist") is first
    assert nameplate_doc.lookup("NoSuchElement") is None
    assert nameplate_doc.lookup("") is None
    assert nameplate_doc.lookup("{00}") is None


def test_lookup_ignores_counters_and_case(nameplate_doc: SpecDocument) -> None:
    expected = nameplate_doc.lookup("ContactInformation{00}")
    assert expected is not None
    assert nameplate_doc.lookup("ContactInformation__00__") is expected
    assert nameplate_doc.lookup("contactinformation") is expected
    # a row beats the bare table header that shares its key
    markings = nameplate_doc.lookup("Markings")
    assert markings is not None
    assert markings.sme_type == "SubmodelElementList"
    assert markings.cardinality == "[0..1]"


def test_lookup_on_handmade_document() -> None:
    first = SpecElement(id_short="Name", key="name", cardinality="[1]", parent="Metadata", page=3)
    second = SpecElement(id_short="Name", key="name", cardinality="[0..1]", parent="Segment", page=5)
    doc = SpecDocument(elements=[first, second], page_count=9)
    assert doc.lookup("Name") is first
    assert doc.lookup("Name", parent="Segment") is second
    assert doc.lookup("Name", parent="segment{00}") is second
    assert doc.lookup("Name", parent="Other") is first


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def test_round_trip_through_dict(nameplate_doc: SpecDocument) -> None:
    payload = nameplate_doc.to_dict()
    encoded = json.dumps(payload)  # must be JSON serializable
    restored = SpecDocument.from_dict(json.loads(encoded))
    assert restored == nameplate_doc
    assert restored.to_dict() == payload
    looked_up = restored.lookup("IssueDate", parent="Markings__00__")
    assert looked_up is not None
    assert looked_up.cardinality == "[1]"


def test_from_dict_tolerates_sparse_and_odd_data() -> None:
    doc = SpecDocument.from_dict(
        {
            "elements": [
                {"id_short": "Markings__00__"},
                {"id_short": ""},
                "garbage",
                {"id_short": "X", "notes": "not a list", "page": "7", "cardinality": ""},
            ],
            "page_count": "many",
        }
    )
    assert [el.id_short for el in doc.elements] == ["Markings__00__", "X"]
    assert doc.elements[0].key == "markings"
    assert doc.elements[0].notes == []
    assert doc.elements[1].notes == []
    assert doc.elements[1].page == 0
    assert doc.elements[1].cardinality is None
    assert doc.page_count == 0
    assert doc.title is None
    assert doc.warnings == []
    assert SpecDocument.from_dict({}).elements == []


# ---------------------------------------------------------------------------
# Tables continuing over several pages
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def multipage_doc() -> SpecDocument:
    rows = []
    for index in range(36):
        cardinality = ["1", "0..1", "[0..*]", "[1..*]"][index % 4]
        rows.append(
            _row(
                f"[Prop]<br>LongTableProp<br>erty{index:02d}",
                f"0173-1#02-AAA{index:03d}#001<br>description of property number {index} which "
                "is long enough to need a second line inside the description cell<br>"
                f"Note: note for property {index}",
                f"[String]<br>value-{index}",
                cardinality,
            )
        )
    body = "<table>" + _header("LongTable") + "".join(rows) + "</table>"
    return extract_spec_document(_render(body))


def test_multi_page_table_keeps_parent_and_order(multipage_doc: SpecDocument) -> None:
    assert multipage_doc.page_count >= 2
    rows = [el for el in multipage_doc.elements if el.parent == "LongTable"]
    assert [el.id_short for el in rows] == [f"LongTableProperty{i:02d}" for i in range(36)]
    pages = [el.page for el in rows]
    assert pages == sorted(pages)
    assert pages[0] == 1
    assert pages[-1] == multipage_doc.page_count
    assert len(set(pages)) == multipage_doc.page_count


def test_multi_page_table_rows_are_complete(multipage_doc: SpecDocument) -> None:
    expected_cardinalities = ["[1]", "[0..1]", "[0..*]", "[1..*]"]
    for index in range(36):
        element = multipage_doc.lookup(f"LongTableProperty{index:02d}", parent="LongTable")
        assert element is not None
        assert element.cardinality == expected_cardinalities[index % 4]
        assert element.semantic_id == f"0173-1#02-AAA{index:03d}#001"
        assert element.value_type == "String"
        assert element.example == f"value-{index}"
        assert element.notes == [f"note for property {index}"]
        assert element.description == (
            f"description of property number {index} which is long enough to need a second "
            "line inside the description cell"
        )


@pytest.mark.parametrize(("line_count", "pages"), [(45, 2), (130, 5)])
def test_row_split_by_a_page_break_is_reassembled(line_count: int, pages: int) -> None:
    # the long row does not fit on the rest of the first page and is cut by the page
    # break(s); WeasyPrint leaves its cells open there, so no ruled table row exists
    lines = "<br>".join(f"line {i} of a very long description" for i in range(line_count))
    body = (
        "<style>tr { break-inside: auto }</style><table>"
        + _header("SplitTable")
        + _row("[Prop]<br>Before", "0173-1#02-AAA001#001<br>first row", "[String]<br>a", "1")
        + _row("[MLP]<br>SplitRow", f"0173-1#02-AAA002#001<br>{lines}", "[]", "0..1")
        + _row("[Prop]<br>After", "0173-1#02-AAA003#001<br>last row", "[String]<br>z", "[1]")
        + "</table>"
    )
    doc = extract_spec_document(_render(body))
    assert doc.page_count == pages
    rows = [el.id_short for el in doc.elements if el.parent == "SplitTable"]
    assert rows == ["Before", "SplitRow", "After"]
    split = doc.lookup("SplitRow")
    assert split is not None
    assert split.page == 1
    assert split.sme_type == "MultiLanguageProperty"
    assert split.cardinality == "[0..1]"
    assert split.semantic_id == "0173-1#02-AAA002#001"
    assert split.description == " ".join(
        f"line {i} of a very long description" for i in range(line_count)
    )
    after = doc.lookup("After")
    assert after is not None
    assert after.page == pages
    assert after.description == "last row"
    assert after.example == "z"


# ---------------------------------------------------------------------------
# Older / messier layouts
# ---------------------------------------------------------------------------


def test_rows_reported_line_by_line_are_reassembled() -> None:
    """Word exports in which every text line is a table row of its own."""
    body = (
        "<table>"
        + _header("GeneralInformation", cls="SubmodelElementCollection", parent="TechnicalData")
        + _row("[Prop]", "0173-1#02-AAO677#004", "[String]", "1")
        + _row("ManufacturerN", "supplementalSemanticId: https://api.example.org/0173-", "", "")
        + _row("ame", "1-02-AAO677-004", "", "")
        + _row("", "Legally valid designation of the natural or judicial person", "", "")
        + _row("", "which is directly responsible for the design", "", "")
        + _row("[SML]", "0173-1#02-ABM220#001", "[]", "0..1")
        + _row("ProductImages", "Pictorial representations of the product", "1 elements", "")
        + "</table>"
    )
    doc = extract_spec_document(_render(body))
    rows = [el for el in doc.elements if el.parent == "GeneralInformation"]
    assert [el.id_short for el in rows] == ["ManufacturerName", "ProductImages"]
    name, images = rows
    assert name.sme_type == "Property"
    assert name.cardinality == "[1]"
    assert name.value_type == "String"
    assert name.semantic_id == "0173-1#02-AAO677#004"
    assert name.description == (
        "Legally valid designation of the natural or judicial person which is directly "
        "responsible for the design"
    )
    assert images.sme_type == "SubmodelElementList"
    assert images.cardinality == "[0..1]"
    assert images.example is None
    assert images.description == "Pictorial representations of the product"
    header = doc.lookup("GeneralInformation")
    assert header is not None
    assert header.parent == "TechnicalData"


def test_footnote_markers_and_bracketed_cardinalities() -> None:
    body = (
        "<table>"
        + _header("ContactInformation", cls="SubmodelElementCollection")
        + _row(
            "[MLP]<sup style='font-size:5pt'>1</sup><br>NationalCode",
            "[IRDI] 0173-1#02-AAO134#002<br>code of a country<br>"
            "Note: country codes defined accord. to ISO 3166-1",
            "[langString]<sup style='font-size:5pt'>1</sup><br>DE@de",
            "[0..1]",
        )
        + _row(
            "[Property]<br>TimeZone",
            "[IRI] https://example.org/zvei/nameplate/1/0/ContactInformations/TimeZone<br>"
            "offsets from Coordinated Universal Time (UTC)",
            "[String]<br>Z<br>-12:00<br>+14:00",
            "[0..1]",
        )
        + _row(
            "[Ref]<br>RelatedThing",
            "[IRI] https://example.org/a/1/0/First or<br>[IRI] https://example.org/a/1/0/Second"
            "<br>one of two semantic ids may be used",
            "n/a",
            "0..n",
        )
        + "</table>"
    )
    doc = extract_spec_document(_render(body))
    code = doc.lookup("NationalCode")
    assert code is not None
    assert code.id_short == "NationalCode"
    assert code.sme_type == "MultiLanguageProperty"
    assert code.semantic_id == "0173-1#02-AAO134#002"
    assert code.value_type == "langString"
    assert code.example == "DE@de"
    assert code.cardinality == "[0..1]"
    assert code.notes == ["country codes defined accord. to ISO 3166-1"]

    zone = doc.lookup("TimeZone")
    assert zone is not None
    assert zone.sme_type == "Property"
    assert zone.semantic_id == "https://example.org/zvei/nameplate/1/0/ContactInformations/TimeZone"
    # deliberate line breaks separate alternative examples
    assert zone.example == "Z; -12:00; +14:00"

    related = doc.lookup("RelatedThing")
    assert related is not None
    assert related.sme_type == "ReferenceElement"
    assert related.cardinality == "[0..*]"
    # two alternative semantic ids are ambiguous: none is reported
    assert related.semantic_id is None
    assert related.description == "one of two semantic ids may be used"


def test_table_without_rulings_uses_text_positions() -> None:
    body = (
        '<table class="plain">'
        + _header("Plain", cls="SubmodelElementCollection")
        + _row(
            "[Prop]<br>FirstPlainProp<br>erty",
            "0173-1#02-AAA111#001<br>first description<br>Note: first note",
            "[String]<br>abc",
            "1",
        )
        + _row(
            "[MLP]<br>SecondPlain",
            "0173-1#02-AAA222#001<br>second description",
            "[]",
            "[0..*]",
        )
        + "</table>"
    )
    doc = extract_spec_document(_render(body))
    rows = {el.id_short: el for el in doc.elements}
    assert {"FirstPlainProperty", "SecondPlain"} <= set(rows)
    first = rows["FirstPlainProperty"]
    assert first.sme_type == "Property"
    assert first.cardinality == "[1]"
    assert first.parent == "Plain"
    assert first.semantic_id == "0173-1#02-AAA111#001"
    assert first.description == "first description"
    assert first.notes == ["first note"]
    assert first.example == "abc"
    second = rows["SecondPlain"]
    assert second.sme_type == "MultiLanguageProperty"
    assert second.cardinality == "[0..*]"
    assert second.description == "second description"


def test_unrelated_tables_are_ignored() -> None:
    body = (
        "<h1>Some report</h1><p>[1] a bibliography entry, [Prop] mentioned in prose.</p>"
        "<table><tr><td>Date</td><td>Version</td><td>Comment</td></tr>"
        "<tr><td>2024-01-01</td><td>1.0</td><td>Release [1]</td></tr></table>"
    )
    doc = extract_spec_document(_render(body))
    assert doc.elements == []
    assert doc.page_count == 1
    assert doc.warnings  # says that nothing was found


# ---------------------------------------------------------------------------
# Robustness
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"definitely not a pdf",
        b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<<>>\n%%EOF",
        b"%PDF-1.4\n" + bytes(range(256)) * 20,
        b"PK\x03\x04" + b"\x00" * 64,
        None,
        "a string",
        12345,
    ],
)
def test_garbage_input_returns_empty_document(payload: object) -> None:
    doc = extract_spec_document(payload)  # type: ignore[arg-type]
    assert isinstance(doc, SpecDocument)
    assert doc.elements == []
    assert doc.page_count == 0
    assert doc.title is None
    assert doc.warnings
    assert doc.lookup("Anything") is None
    json.dumps(doc.to_dict())


def test_truncated_pdf_does_not_raise() -> None:
    pdf = _render("<table>" + _header("Cut") + _NAMEPLATE_ROWS[0] + "</table>")
    for cut in (len(pdf) // 2, len(pdf) - 200, 64):
        doc = extract_spec_document(pdf[:cut])
        assert isinstance(doc, SpecDocument)
        json.dumps(doc.to_dict())


def test_encrypted_pdf_returns_empty_document_with_warning() -> None:
    fitz = pytest.importorskip("fitz")
    pdf = _render("<table>" + _header("Secret") + _NAMEPLATE_ROWS[0] + "</table>")
    source = fitz.open(stream=pdf, filetype="pdf")
    try:
        encrypted = source.tobytes(
            encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="user"
        )
    finally:
        source.close()
    doc = extract_spec_document(encrypted)
    assert doc.elements == []
    assert doc.warnings


def test_max_pages_is_respected(multipage_doc: SpecDocument) -> None:
    rows = "".join(
        _row(f"[Prop]<br>P{index:02d}", f"0173-1#02-AAA{index:03d}#001<br>text", "[String]", "1")
        for index in range(80)
    )
    pdf = _render("<table>" + _header("Limited") + rows + "</table>")
    full = extract_spec_document(pdf)
    assert full.page_count >= 2
    limited = extract_spec_document(pdf, max_pages=1)
    assert limited.page_count == full.page_count
    assert 0 < len(limited.elements) < len(full.elements)
    assert all(el.page == 1 for el in limited.elements)
    assert any("only the first 1" in warning for warning in limited.warnings)
    none = extract_spec_document(pdf, max_pages=0)
    assert none.elements == []
    assert none.warnings


def test_time_budget_stops_early_with_warning() -> None:
    pdf = _render("<table>" + _header("Budget") + "".join(_NAMEPLATE_ROWS) + "</table>")
    doc = extract_spec_document(pdf, time_budget_seconds=-1.0)
    assert doc.elements == []
    assert doc.page_count == 1
    assert any("time budget" in warning for warning in doc.warnings)


# ---------------------------------------------------------------------------
# Optional checks against real IDTA specifications
# ---------------------------------------------------------------------------

_REAL_DIR = os.environ.get("IDTA_SPEC_PDF_DIR")
_needs_real_pdfs = pytest.mark.skipif(
    not _REAL_DIR, reason="set IDTA_SPEC_PDF_DIR to a directory with IDTA specification PDFs"
)


def _real_document(name: str) -> SpecDocument:
    path = Path(_REAL_DIR or "") / name
    if not path.is_file():
        pytest.skip(f"{name} not found in IDTA_SPEC_PDF_DIR")
    return extract_spec_document(path.read_bytes())


@_needs_real_pdfs
def test_real_digital_nameplate_known_rows() -> None:
    doc = _real_document("nameplate.pdf")
    assert doc.page_count == 22
    assert doc.title is not None and "Digital Nameplate" in doc.title

    issue_date = doc.lookup("IssueDate")
    assert issue_date is not None
    assert issue_date.cardinality == "[0..1]"
    assert issue_date.example == "2022-01-01"
    assert issue_date.value_type == "Date"
    assert issue_date.sme_type == "Property"
    assert issue_date.semantic_id == "0112/2///61987#ABO097#001"
    assert issue_date.parent == "Markings__00__"
    assert any("CCYY-MM-DD" in note for note in issue_date.notes)
    assert issue_date.description == "date, at which the specified certificate is issued"

    designation = doc.lookup("DesignationOfCertificateOrApproval")
    assert designation is not None
    assert designation.id_short == "DesignationOfCertificateOrApproval"
    assert designation.example == "KEMA99IECEX1105/128"
    assert designation.cardinality == "[0..1]"

    uri = doc.lookup("URIOfTheProduct", parent="Nameplate")
    assert uri is not None
    assert uri.cardinality == "[1]"
    assert uri.value_type == "AnyUri"
    assert uri.example == "https://www.domain-abc.com/Model-Nr-1234/Serial-Nr-5678"

    name = doc.lookup("ManufacturerName")
    assert name is not None
    assert name.sme_type == "MultiLanguageProperty"
    assert name.example == '"Muster AG"@de'

    markings = doc.lookup("Markings", parent="Nameplate")
    assert markings is not None
    assert markings.sme_type == "SubmodelElementList"
    assert markings.cardinality == "[0..1]"
    item = doc.lookup("Markings__00__", parent="Markings")
    assert item is not None
    assert item.cardinality == "[1..*]"

    address = doc.lookup("AddressInformation")
    assert address is not None
    assert address.semantic_id == (
        "https://admin-shell.io/zvei/nameplate/1/0/ContactInformations/AddressInformation"
    )


@_needs_real_pdfs
def test_real_contact_information_older_layout() -> None:
    doc = _real_document("contact.pdf")
    role = doc.lookup("RoleOfContactPerson")
    assert role is not None
    assert role.sme_type == "Property"
    assert role.cardinality == "[0..1]"
    assert role.semantic_id == "0173-1#02-AAO204#003"
    code = doc.lookup("NationalCode")
    assert code is not None
    assert code.sme_type == "MultiLanguageProperty"
    assert code.value_type == "langString"
    assert code.example == "DE@de"
    channel = doc.lookup("IPCommunication", parent="ContactInformation")
    assert channel is not None
    assert channel.id_short == "IPCommunication{00}"
    assert channel.cardinality == "[0..*]"
    link = doc.lookup("AddressOfAdditionalLink", parent="IPCommunication")
    assert link is not None
    assert link.cardinality == "[1]"


@_needs_real_pdfs
@pytest.mark.parametrize(
    "name",
    [
        "nameplate.pdf",
        "dbp_nameplate.pdf",
        "contact.pdf",
        "contact_101.pdf",
        "carbon_footprint.pdf",
        "technical_data.pdf",
        "handover.pdf",
        "timeseries.pdf",
        "software_nameplate.pdf",
    ],
)
def test_real_specifications_yield_consistent_elements(name: str) -> None:
    doc = _real_document(name)
    assert len(doc.elements) >= 15
    for element in doc.elements:
        assert element.id_short and " " not in element.id_short
        assert element.key == normalize_spec_key(element.id_short)
        assert 1 <= element.page <= doc.page_count
        if element.cardinality is not None:
            assert element.cardinality.startswith("[") and element.cardinality.endswith("]")
        if element.semantic_id is not None:
            assert " " not in element.semantic_id
            assert not element.semantic_id.endswith("-")
        assert all(note and not note.lower().startswith("note:") for note in element.notes)
    assert SpecDocument.from_dict(json.loads(json.dumps(doc.to_dict()))) == doc
