"""
End-to-end tests for template requirements: what the parser reads from a
template package and how validation enforces it.
"""

import datetime
import zipfile
from io import BytesIO

from basyx.aas import model
from basyx.aas.adapter import aasx

from app.services.hydrator import HydratorService
from app.services.parser import ParserService, humanize_id_short
from app.services.spec_notes import match_spec_to_schema
from app.services.spec_pdf import SpecDocument, SpecElement, normalize_spec_key
from app.services.validation import validate_form_data
from app.utils.aasx_reader import SafeAASXReader


def _ref(value: str) -> model.ExternalReference:
    return model.ExternalReference(key=(model.Key(model.KeyTypes.GLOBAL_REFERENCE, value),))


def _qualifier(type_: str, value: str) -> model.Qualifier:
    return model.Qualifier(type_=type_, value_type=model.datatypes.String, value=value)


def _concept_description(identifier: str, **iec) -> model.ConceptDescription:
    content = model.DataSpecificationIEC61360(
        preferred_name=model.PreferredNameTypeIEC61360({"en": iec.pop("name", "Name")}),
        **iec,
    )
    return model.ConceptDescription(
        id_=identifier,
        embedded_data_specifications=[
            model.EmbeddedDataSpecification(
                data_specification=_ref(
                    "https://admin-shell.io/DataSpecificationTemplates/DataSpecificationIEC61360/3"
                ),
                data_specification_content=content,
            )
        ],
    )


def _build_aasx(elements, concept_descriptions=(), kind=model.ModellingKind.TEMPLATE) -> bytes:
    submodel = model.Submodel(
        id_="https://example.org/SubmodelTemplate/Test/1/0",
        id_short="TestTemplate",
        kind=kind,
        submodel_element=list(elements),
    )
    aas_obj = model.AssetAdministrationShell(
        id_="urn:test:aas",
        id_short="TestAAS",
        asset_information=model.AssetInformation(
            asset_kind=model.AssetKind.TYPE, global_asset_id="urn:test:asset"
        ),
        submodel={model.ModelReference.from_referable(submodel)},
    )
    store: model.DictObjectStore = model.DictObjectStore(
        [aas_obj, submodel, *concept_descriptions]
    )
    output = BytesIO()
    with aasx.AASXWriter(output) as writer:
        writer.write_all_aas_objects(
            "/aasx/data.xml", store, aasx.DictSupplementaryFileContainer(), write_json=False
        )
    return output.getvalue()


def _template_elements():
    country = model.Property(
        id_short="CountryOfOrigin",
        value_type=model.datatypes.String,
        value="DE",
        semantic_id=_ref("urn:cd:country"),
        description=model.MultiLanguageTextType(
            {"en": "Note: Country codes defined accord. to DIN EN ISO 3166-1 alpha-2 codes"}
        ),
        qualifier=[_qualifier("SMT/Cardinality", "ZeroToOne")],
    )
    issue_date = model.Property(
        id_short="IssueDate",
        value_type=model.datatypes.Date,
        value=model.datatypes.Date(2022, 1, 1),
        qualifier=[_qualifier("SMT/SMT/Cardinality", "ZeroToOne")],
    )
    conformity = model.Property(
        id_short="Conformity",
        value_type=model.datatypes.String,
        qualifier=[
            _qualifier("SMT/Cardinality", "One"),
            _qualifier("SMT/AllowedValue", "pass;fail"),
            _qualifier("SMT/ExampleValue", "pass"),
        ],
    )
    offset = model.Property(
        id_short="canv_offset",
        value_type=model.datatypes.UnsignedByte,
        qualifier=[
            _qualifier("Cardinality", "ZeroToOne"),
            _qualifier("SMT/AllowedRange", "[0,63]"),
        ],
    )
    phone_type = model.Property(
        id_short="TypeOfTelephone",
        value_type=model.datatypes.String,
        semantic_id=_ref("urn:cd:phone-type"),
        qualifier=[_qualifier("Multiplicity", "ZeroToOne")],
    )
    name = model.MultiLanguageProperty(
        id_short="ManufacturerName",
        value=model.MultiLanguageTextType({"de": "Muster AG"}),
        qualifier=[
            _qualifier("SMT/Cardinality", "One"),
            _qualifier("SMT/RequiredLang", "en"),
        ],
    )
    component_name = model.Property(
        id_short="ComponentName",
        value_type=model.datatypes.String,
        qualifier=[
            _qualifier("SMT/Cardinality", "ZeroToOne"),
            _qualifier("SMT/EitherOr", "Location"),
        ],
    )
    component_id = model.Property(
        id_short="ComponentId",
        value_type=model.datatypes.String,
        qualifier=[
            _qualifier("SMT/Cardinality", "ZeroToOne"),
            _qualifier("SMT/EitherOr", "Location"),
        ],
    )
    marking = model.SubmodelElementCollection(
        id_short=None,
        value=[
            model.Property(
                id_short="MarkingName",
                value_type=model.datatypes.String,
                value="CE",
                qualifier=[_qualifier("SMT/Cardinality", "One")],
            )
        ],
        qualifier=[_qualifier("SMT/Cardinality", "OneToMany")],
    )
    markings = model.SubmodelElementList(
        id_short="Markings",
        type_value_list_element=model.SubmodelElementCollection,
        value=[marking],
        qualifier=[_qualifier("SMT/Cardinality", "ZeroToOne")],
    )
    return [
        country,
        issue_date,
        conformity,
        offset,
        phone_type,
        name,
        component_name,
        component_id,
        markings,
    ]


def _concept_descriptions():
    return [
        _concept_description(
            "urn:cd:country",
            name="CountryOfOrigin",
            definition=model.DefinitionTypeIEC61360(
                {"en": "country where the product was manufactured"}
            ),
            value_format="X..2",
        ),
        _concept_description(
            "urn:cd:phone-type",
            name="type of telephone",
            value_list={
                model.ValueReferencePair("office", _ref("0173-1#07-AAS754#001")),
                model.ValueReferencePair("home", _ref("0173-1#07-AAS756#001")),
            },
        ),
    ]


def _parse_template() -> dict:
    return ParserService().parse_aasx_to_ui_schema(
        _build_aasx(_template_elements(), _concept_descriptions())
    )


def _by_id(schema: dict) -> dict:
    return {element["idShort"]: element for element in schema["elements"]}


class TestParserRequirements:
    def test_value_types_are_xsd_names_with_matching_inputs(self):
        elements = _by_id(_parse_template())

        assert elements["CountryOfOrigin"]["valueType"] == "xs:string"
        assert elements["IssueDate"]["valueType"] == "xs:date"
        assert elements["IssueDate"]["inputType"] == "date"
        assert elements["IssueDate"]["value"] == "2022-01-01"
        assert elements["canv_offset"]["valueType"] == "xs:unsignedByte"
        assert elements["canv_offset"]["inputType"] == "number"
        assert elements["canv_offset"]["constraints"] == {"min": 0, "max": 255}

    def test_cardinality_spellings(self):
        elements = _by_id(_parse_template())

        assert elements["IssueDate"]["cardinality"] == "[0..1]"  # SMT/SMT/Cardinality
        assert elements["canv_offset"]["cardinality"] == "[0..1]"  # Cardinality
        assert elements["TypeOfTelephone"]["cardinality"] == "[0..1]"  # Multiplicity
        assert elements["Conformity"]["cardinality"] == "[1]"

    def test_description_notes_and_definition_are_both_exposed(self):
        country = _by_id(_parse_template())["CountryOfOrigin"]

        assert "ISO 3166-1" in country["description"]["en"]
        assert country["definition"] == {"en": "country where the product was manufactured"}
        assert country["label"] == "Country Of Origin"
        assert country["standards"] == ["DIN EN ISO 3166-1"]
        assert country["formatHint"]["id"] == "iso3166-1-alpha2"
        assert country["valueFormat"] == "X..2"
        assert country["maxLength"] == 2

    def test_qualifier_and_concept_description_constraints(self):
        elements = _by_id(_parse_template())

        conformity = elements["Conformity"]
        assert [o["value"] for o in conformity["allowedValues"]] == ["pass", "fail"]
        assert conformity["allowedValuesStrict"] is True
        assert conformity["exampleValues"] == ["pass"]

        assert elements["canv_offset"]["allowedRange"] == {"min": 0, "max": 63}

        phone_type = elements["TypeOfTelephone"]
        assert phone_type["allowedValues"] == [
            {"value": "home", "label": None, "valueId": "0173-1#07-AAS756#001"},
            {"value": "office", "label": None, "valueId": "0173-1#07-AAS754#001"},
        ]
        assert phone_type["allowedValuesStrict"] is False
        assert phone_type["label"] == "Type Of Telephone"

        assert elements["ManufacturerName"]["requiredLanguages"] == ["en"]
        assert elements["ComponentName"]["eitherOr"] == "Location"

    def test_template_values_are_marked_as_examples(self):
        elements = _by_id(_parse_template())

        assert elements["CountryOfOrigin"]["exampleValues"] == ["DE"]
        assert elements["ManufacturerName"]["exampleValues"] == ["Muster AG"]
        assert elements["IssueDate"]["exampleValues"] == ["2022-01-01"]

    def test_instance_values_are_not_examples(self):
        schema = ParserService().parse_aasx_to_ui_schema(
            _build_aasx(
                _template_elements(),
                _concept_descriptions(),
                kind=model.ModellingKind.INSTANCE,
            )
        )

        assert schema["kind"] == "Instance"
        assert "exampleValues" not in _by_id(schema)["CountryOfOrigin"]

    def test_list_items_get_stable_names_instead_of_sdk_placeholders(self):
        first = _parse_template()
        second = _parse_template()
        markings = _by_id(first)["Markings"]

        assert markings["typeValueListElement"] == "SubmodelElementCollection"
        assert markings["itemTemplate"]["idShort"] == "MarkingsItem"
        assert markings["items"][0]["idShort"] == "MarkingsItem"
        assert markings["itemTemplate"]["cardinality"] == "[1..*]"
        assert "generated_submodel_list_hack" not in str(first)
        assert first == second

    def test_humanize_id_short(self):
        assert humanize_id_short("ManufacturerProductDesignation") == (
            "Manufacturer Product Designation"
        )
        assert humanize_id_short("URIOfTheProduct") == "URI Of The Product"
        assert humanize_id_short("Markings__00__") == "Markings"
        assert humanize_id_short("ContactInformation{00}") == "Contact Information"
        assert humanize_id_short("min_max") == "Min max"
        assert humanize_id_short("PCFCO2eq") == "PCFCO2eq"


def _valid_form() -> dict:
    return {
        "elements": {
            "CountryOfOrigin": {"value": "FR"},
            "Conformity": {"value": "pass"},
            "canv_offset": {"value": 10},
            "TypeOfTelephone": {"value": "office"},
            "ManufacturerName": {"value": {"en": "ACME Corp"}},
            "ComponentName": {"value": "Cell"},
            "Markings": {"items": [{"elements": {"MarkingName": {"value": "UKCA"}}}]},
        }
    }


class TestValidationRequirements:
    def test_valid_form_has_no_findings(self):
        errors, warnings = validate_form_data(_parse_template(), _valid_form())

        assert errors == []
        assert warnings == []

    def test_strict_enumeration_and_range_are_errors(self):
        form = _valid_form()
        form["elements"]["Conformity"]["value"] = "maybe"
        form["elements"]["canv_offset"]["value"] = 64

        errors, _ = validate_form_data(_parse_template(), form)

        assert {(e.field, e.code) for e in errors} == {
            ("Conformity", "not_allowed"),
            ("canv_offset", "out_of_range"),
        }

    def test_xsd_type_bounds_are_enforced(self):
        form = _valid_form()
        form["elements"]["canv_offset"]["value"] = -1

        errors, _ = validate_form_data(_parse_template(), form)

        assert [(e.field, e.code) for e in errors] == [("canv_offset", "out_of_range")]

    def test_value_list_format_hint_and_value_format_are_warnings(self):
        form = _valid_form()
        form["elements"]["TypeOfTelephone"]["value"] = "satellite"
        form["elements"]["CountryOfOrigin"]["value"] = "France"

        errors, warnings = validate_form_data(_parse_template(), form)

        assert errors == []
        assert {(w.field, w.code) for w in warnings} == {
            ("TypeOfTelephone", "not_in_value_list"),
            ("CountryOfOrigin", "format_hint"),
            ("CountryOfOrigin", "value_format"),
        }

    def test_unchanged_example_values_are_reported(self):
        form = _valid_form()
        form["elements"]["CountryOfOrigin"]["value"] = "DE"
        form["elements"]["ManufacturerName"]["value"] = {"en": "Muster AG"}

        errors, warnings = validate_form_data(_parse_template(), form)

        assert errors == []
        assert {(w.field, w.code) for w in warnings} == {
            ("CountryOfOrigin", "example_value"),
            ("ManufacturerName", "example_value"),
        }

    def test_required_language_is_enforced(self):
        form = _valid_form()
        form["elements"]["ManufacturerName"]["value"] = {"de": "ACME GmbH"}

        errors, _ = validate_form_data(_parse_template(), form)

        assert [(e.field, e.code) for e in errors] == [("ManufacturerName", "required_language")]

    def test_either_or_group_requires_one_alternative(self):
        form = _valid_form()
        form["elements"]["ComponentName"]["value"] = ""

        errors, _ = validate_form_data(_parse_template(), form)
        assert [(e.field, e.code) for e in errors] == [("ComponentName", "either_or")]

        form["elements"]["ComponentId"] = {"value": "C-1"}
        errors, _ = validate_form_data(_parse_template(), form)
        assert errors == []

    def test_list_occurring_once_accepts_several_items(self):
        form = _valid_form()
        form["elements"]["Markings"]["items"] = [
            {"elements": {"MarkingName": {"value": "UKCA"}}},
            {"elements": {"MarkingName": {"value": "WEEE"}}},
        ]

        errors, _ = validate_form_data(_parse_template(), form)

        assert errors == []

    def test_bounded_list_cardinality_still_limits_items(self):
        schema = {
            "elements": [
                {
                    "idShort": "Tags",
                    "modelType": "SubmodelElementList",
                    "cardinality": "[0..2]",
                    "itemTemplate": {
                        "idShort": "TagsItem",
                        "modelType": "Property",
                        "cardinality": "[1]",
                        "valueType": "xs:string",
                    },
                }
            ]
        }
        form = {"elements": {"Tags": {"items": [{"value": "a"}, {"value": "b"}, {"value": "c"}]}}}

        errors, _ = validate_form_data(schema, form)

        assert [e.code for e in errors] == ["max_items"]

    def test_duration_and_year_month_types(self):
        schema = {
            "elements": [
                {"idShort": "Duration", "modelType": "Property", "cardinality": "[1]", "valueType": "xs:duration"},
                {"idShort": "Month", "modelType": "Property", "cardinality": "[1]", "valueType": "xs:gYearMonth"},
            ]
        }

        ok, _ = validate_form_data(
            schema, {"elements": {"Duration": {"value": "PT30M"}, "Month": {"value": "2024-05"}}}
        )
        bad, _ = validate_form_data(
            schema, {"elements": {"Duration": {"value": "30 min"}, "Month": {"value": "2024"}}}
        )

        assert ok == []
        assert [e.code for e in bad] == ["type_mismatch", "type_mismatch"]


def test_hydration_round_trip_keeps_requirements_and_new_values():
    template = _build_aasx(_template_elements(), _concept_descriptions())
    form = _valid_form()
    form["elements"]["IssueDate"] = {"value": "2024-05-06"}
    form["elements"]["Markings"]["items"].append({"elements": {"MarkingName": {"value": "WEEE"}}})

    hydrated = HydratorService().hydrate_submodel(template, form)
    elements = _by_id(ParserService().parse_aasx_to_ui_schema(hydrated))

    assert elements["CountryOfOrigin"]["value"] == "FR"
    assert elements["IssueDate"]["value"] == "2024-05-06"
    assert elements["Conformity"]["allowedValuesStrict"] is True
    assert [
        item["elements"][0]["value"] for item in elements["Markings"]["items"]
    ] == ["UKCA", "WEEE"]


def test_hydrator_parses_remaining_xsd_types():
    hydrator = HydratorService()

    duration = hydrator._coerce_value("PT30M", model.datatypes.Duration)
    assert duration.minutes == 30
    assert hydrator._coerce_value("2024-05-06", model.datatypes.Date) == datetime.date(2024, 5, 6)
    assert hydrator._coerce_value("text", model.datatypes.String) == "text"


def test_reader_repairs_internal_parts_declared_as_external():
    """Some exporters mark package-internal relationship targets as external."""
    original = _build_aasx(_template_elements(), _concept_descriptions())
    broken = BytesIO()
    with zipfile.ZipFile(BytesIO(original)) as source, zipfile.ZipFile(broken, "w") as target:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename.endswith(".rels"):
                data = data.replace(b"<Relationship ", b'<Relationship TargetMode="External" ')
            target.writestr(info, data)
    assert b'TargetMode="External"' in zipfile.ZipFile(BytesIO(broken.getvalue())).read("_rels/.rels")

    schema = ParserService().parse_aasx_to_ui_schema(broken.getvalue())

    assert schema["idShort"] == "TestTemplate"
    assert len(schema["elements"]) == 9
    # Reading through a file object also works for the hydrator.
    store: model.DictObjectStore = model.DictObjectStore()
    with SafeAASXReader(BytesIO(broken.getvalue())) as reader:
        reader.read_into(store, aasx.DictSupplementaryFileContainer())
    assert any(isinstance(obj, model.Submodel) for obj in store)


def _spec_element(id_short: str, parent: str | None, **kwargs) -> SpecElement:
    defaults = dict(
        sme_type=None,
        semantic_id=None,
        value_type=None,
        cardinality=None,
        description=None,
        notes=[],
        example=None,
        page=1,
    )
    defaults.update(kwargs)
    return SpecElement(
        id_short=id_short, key=normalize_spec_key(id_short), parent=parent, **defaults
    )


def test_specification_rows_are_matched_to_schema_paths():
    document = SpecDocument(
        elements=[
            _spec_element(
                "CountryOfOrigin",
                "TestTemplate",
                sme_type="Property",
                cardinality="[1]",
                notes=["Country codes accord. to ISO 3166-1"],
                example="DE",
                page=10,
            ),
            _spec_element("Markings", "TestTemplate", sme_type="SubmodelElementList", page=11),
            _spec_element(
                "MarkingName",
                "Markings__00__",
                sme_type="Property",
                cardinality="[1]",
                notes=["common name of the marking"],
                page=12,
            ),
            # A row of another element type must not be attached to a Property.
            _spec_element("Conformity", "TestTemplate", sme_type="File", page=13),
        ],
        page_count=20,
    )

    notes, matched, total = match_spec_to_schema(document, _parse_template())

    assert notes["CountryOfOrigin"]["page"] == 10
    assert notes["CountryOfOrigin"]["cardinality"] == "[1]"
    assert notes["CountryOfOrigin"]["templateCardinality"] == "[0..1]"
    assert notes["CountryOfOrigin"]["example"] == "DE"
    assert notes["Markings.MarkingName"]["notes"] == ["common name of the marking"]
    assert "Conformity" not in notes
    assert matched == 3
    assert total == 10
