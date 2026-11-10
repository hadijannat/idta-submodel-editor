"""Repeatable elements: validation, export and naming of further occurrences."""

from __future__ import annotations

import json
from io import BytesIO

import pytest
from aas_test_engines import file as aas_file
from basyx.aas import model
from basyx.aas.adapter import aasx as aasx_adapter

from app.schemas.form_data import SubmodelFormData
from app.schemas.ui_schema import SubmodelUISchema
from app.services.hydrator import HydratorService
from app.services.occurrences import (
    additional_occurrences,
    is_repeatable,
    max_occurrences,
    occurrence_id_shorts,
)
from app.services.parser import ParserService
from app.services.validation import validate_form_data

STRING = model.datatypes.String


def _cardinality(value: str) -> model.Qualifier:
    return model.Qualifier(
        type_="SMT/Cardinality",
        value_type=STRING,
        value=value,
        kind=model.QualifierKind.TEMPLATE_QUALIFIER,
    )


def _property(id_short: str | None, cardinality: str) -> model.Property:
    return model.Property(id_short, value_type=STRING, qualifier=[_cardinality(cardinality)])


def _template() -> model.Submodel:
    return model.Submodel(
        id_="https://example.com/templates/contact/1/0",
        id_short="Contact",
        kind=model.ModellingKind.TEMPLATE,
        submodel_element=[
            _property("Name", "One"),
            model.SubmodelElementCollection(
                "Phone",
                qualifier=[_cardinality("ZeroToMany")],
                value=[
                    _property("Number", "One"),
                    _property("Tag__00__", "ZeroToMany"),
                ],
            ),
            _property("Mail", "OneToMany"),
            model.SubmodelElementList(
                "Notes",
                type_value_list_element=model.Property,
                value_type_list_element=STRING,
                qualifier=[_cardinality("ZeroToOne")],
                value=[_property(None, "ZeroToMany")],
            ),
            model.Entity(
                "Site",
                entity_type=model.EntityType.CO_MANAGED_ENTITY,
                qualifier=[_cardinality("ZeroToOne")],
                statement=[_property("Door", "ZeroToMany")],
            ),
            _property("Last", "ZeroToOne"),
        ],
    )


def _aasx(submodel: model.Submodel) -> bytes:
    shell = model.AssetAdministrationShell(
        id_="urn:test:aas",
        asset_information=model.AssetInformation(
            asset_kind=model.AssetKind.INSTANCE, global_asset_id="urn:test:asset"
        ),
        submodel={model.ModelReference.from_referable(submodel)},
    )
    buffer = BytesIO()
    with aasx_adapter.AASXWriter(buffer) as writer:
        writer.write_all_aas_objects(
            "/aasx/data.json",
            model.DictObjectStore([shell, submodel]),
            aasx_adapter.DictSupplementaryFileContainer(),
            write_json=True,
        )
    return buffer.getvalue()


@pytest.fixture(scope="module")
def package() -> bytes:
    return _aasx(_template())


@pytest.fixture(scope="module")
def schema(package) -> dict:
    return ParserService().parse_aasx_to_ui_schema(package)


def _form(**elements) -> dict:
    return {"elements": {"Name": {"value": "ACME"}, "Mail": {"value": "a@example.com"}, **elements}}


def _export(package: bytes, form: dict) -> list[dict]:
    payload = json.loads(HydratorService().hydrate_to_json(package, form))
    return payload["submodels"][0]["submodelElements"]


def _by_id_short(elements: list[dict]) -> dict[str, dict]:
    return {element["idShort"]: element for element in elements}


class TestSchemaFlag:
    def test_to_many_elements_in_containers_are_repeatable(self, schema):
        flags = {e["idShort"]: e.get("repeatable", False) for e in schema["elements"]}
        assert flags == {
            "Name": False,
            "Phone": True,
            "Mail": True,
            "Notes": False,
            "Site": False,
            "Last": False,
        }

    def test_children_of_collections_and_entities_are_flagged(self, schema):
        elements = _by_id_short(schema["elements"])
        phone = _by_id_short(elements["Phone"]["elements"])
        assert phone["Tag__00__"]["repeatable"] is True
        assert "repeatable" not in phone["Number"]
        assert elements["Site"]["statements"][0]["repeatable"] is True

    def test_list_items_repeat_through_their_list(self, schema):
        notes = _by_id_short(schema["elements"])["Notes"]
        assert "repeatable" not in notes["items"][0]
        assert "repeatable" not in notes["itemTemplate"]

    def test_flag_survives_the_response_model(self, schema):
        response = SubmodelUISchema(**schema).model_dump()
        flags = {e["idShort"]: e["repeatable"] for e in response["elements"]}
        assert flags["Phone"] is True and flags["Name"] is False


class TestRules:
    @pytest.mark.parametrize("cardinality,expected", [
        ("[1]", 1),
        ("[0..1]", 1),
        ("[0..*]", None),
        ("[1..*]", None),
        ("[0..3]", 3),
        ("[2]", 2),
        ("Recursive", 1),
        (None, 1),
    ])
    def test_max_occurrences(self, cardinality, expected):
        assert max_occurrences(cardinality) == expected

    def test_lists_and_read_only_elements_are_not_repeatable(self):
        assert is_repeatable("Property", "[0..*]")
        assert is_repeatable("SubmodelElementCollection", "[1..*]")
        assert not is_repeatable("Property", "[0..1]")
        assert not is_repeatable("SubmodelElementList", "[0..*]")
        assert not is_repeatable("Operation", "[0..*]")

    def test_counter_in_the_template_name_is_continued(self):
        assert occurrence_id_shorts("Mode__00__", 2, {"Mode__00__"}) == [
            "Mode__01__",
            "Mode__02__",
        ]
        assert occurrence_id_shorts("Axis__007__", 1, set()) == ["Axis__008__"]

    def test_plain_name_gets_a_counter_appended(self):
        assert occurrence_id_shorts("Phone", 2, {"Phone"}) == ["Phone__01__", "Phone__02__"]

    def test_trailing_digits_are_part_of_the_name(self):
        # "B10" is a reliability figure, not occurrence number ten.
        assert occurrence_id_shorts("B10", 1, {"B10"}) == ["B10__01__"]

    def test_taken_names_are_skipped(self):
        assert occurrence_id_shorts("Phone", 2, {"Phone", "Phone__01__"}) == [
            "Phone__02__",
            "Phone__03__",
        ]

    def test_additional_occurrences_tolerates_any_shape(self):
        assert additional_occurrences(None) == []
        assert additional_occurrences({"occurrences": None}) == []
        assert additional_occurrences({"occurrences": "x"}) == []
        assert additional_occurrences({"occurrences": [{"value": 1}]}) == [{"value": 1}]


class TestValidation:
    def test_occurrences_are_validated_like_the_element(self, schema):
        form = _form(
            Phone={
                "elements": {"Number": {"value": "1"}},
                "occurrences": [{"elements": {"Number": {"value": ""}}}],
            }
        )

        errors, _ = validate_form_data(schema, form)

        assert [(e.field, e.code) for e in errors] == [
            ("Phone.occurrences[0].Number", "required_value")
        ]

    def test_valid_occurrences_pass(self, schema):
        form = _form(
            Phone={
                "elements": {
                    "Number": {"value": "1"},
                    "Tag__00__": {"value": "a", "occurrences": [{"value": "b"}]},
                },
                "occurrences": [{"elements": {"Number": {"value": "2"}}}],
            },
            Mail={"value": "a@example.com", "occurrences": [{"value": "b@example.com"}]},
        )
        assert validate_form_data(schema, form) == ([], [])

    def test_element_that_may_occur_once_rejects_occurrences(self, schema):
        form = _form(Last={"value": "x", "occurrences": [{"value": "y"}]})

        errors, _ = validate_form_data(schema, form)

        assert [(e.field, e.code) for e in errors] == [("Last.occurrences", "not_repeatable")]

    def test_upper_bound_is_enforced(self, schema):
        bounded = {
            **schema,
            "elements": [
                {**e, "cardinality": "[0..2]"} if e["idShort"] == "Phone" else e
                for e in schema["elements"]
            ],
        }
        occurrence = {"elements": {"Number": {"value": "2"}}}
        form = _form(
            Phone={"elements": {"Number": {"value": "1"}}, "occurrences": [occurrence] * 2}
        )

        errors, _ = validate_form_data(bounded, form)

        assert [(e.field, e.code) for e in errors] == [("Phone.occurrences", "max_items")]

    def test_occurrences_cannot_be_nested_in_occurrences(self, schema):
        form = _form(
            Mail={
                "value": "a@example.com",
                "occurrences": [{"value": "b@example.com", "occurrences": [{"value": "c"}]}],
            }
        )

        errors, _ = validate_form_data(schema, form)

        assert [(e.field, e.code) for e in errors] == [
            ("Mail.occurrences[0].occurrences", "invalid_occurrence")
        ]

    def test_form_model_keeps_occurrences(self):
        form = SubmodelFormData(
            elements={"Mail": {"value": "a", "occurrences": [{"value": "b"}]}}
        ).model_dump()
        assert form["elements"]["Mail"]["occurrences"][0]["value"] == "b"


class TestExport:
    def test_each_occurrence_becomes_a_sibling_next_to_the_first(self, package):
        elements = _export(
            package,
            _form(
                Phone={
                    "elements": {"Number": {"value": "1"}},
                    "occurrences": [
                        {"elements": {"Number": {"value": "2"}}},
                        {"elements": {"Number": {"value": "3"}}},
                    ],
                }
            ),
        )

        assert [e["idShort"] for e in elements] == [
            "Name",
            "Phone",
            "Phone__01__",
            "Phone__02__",
            "Mail",
            "Notes",
            "Site",
            "Last",
        ]
        numbers = [
            _by_id_short(e["value"])["Number"]["value"]
            for e in elements
            if e["idShort"].startswith("Phone")
        ]
        assert numbers == ["1", "2", "3"]

    def test_occurrences_inside_occurrences_of_a_parent(self, package):
        elements = _export(
            package,
            _form(
                Phone={
                    "elements": {
                        "Number": {"value": "1"},
                        "Tag__00__": {"value": "a", "occurrences": [{"value": "b"}]},
                    },
                    "occurrences": [
                        {
                            "elements": {
                                "Number": {"value": "2"},
                                "Tag__00__": {
                                    "value": "x",
                                    "occurrences": [{"value": "y"}, {"value": "z"}],
                                },
                            }
                        }
                    ],
                }
            ),
        )

        by_id = _by_id_short(elements)
        first = [(e["idShort"], e.get("value")) for e in by_id["Phone"]["value"]]
        second = [(e["idShort"], e.get("value")) for e in by_id["Phone__01__"]["value"]]
        assert first == [("Number", "1"), ("Tag__00__", "a"), ("Tag__01__", "b")]
        assert second == [
            ("Number", "2"),
            ("Tag__00__", "x"),
            ("Tag__01__", "y"),
            ("Tag__02__", "z"),
        ]

    def test_entity_statements_can_repeat(self, package):
        elements = _export(
            package,
            _form(
                Site={
                    "statements": {
                        "Door": {"value": "north", "occurrences": [{"value": "south"}]}
                    }
                }
            ),
        )

        statements = _by_id_short(elements)["Site"]["statements"]
        assert [(s["idShort"], s["value"]) for s in statements] == [
            ("Door", "north"),
            ("Door__01__", "south"),
        ]

    def test_an_occurrence_starts_from_the_template_not_from_the_first_one(self, package):
        elements = _export(
            package,
            _form(
                Phone={
                    "elements": {"Number": {"value": "1"}, "Tag__00__": {"value": "first"}},
                    "occurrences": [{"elements": {"Number": {"value": "2"}}}],
                }
            ),
        )

        second = _by_id_short(_by_id_short(elements)["Phone__01__"]["value"])
        assert "value" not in second["Tag__00__"]

    def test_occurrences_keep_semantics_and_lose_template_qualifiers(self, package):
        elements = _export(
            package,
            _form(Mail={"value": "a@example.com", "occurrences": [{"value": "b@example.com"}]}),
        )

        occurrence = _by_id_short(elements)["Mail__01__"]
        assert occurrence["modelType"] == "Property"
        assert occurrence["valueType"] == "xs:string"
        assert "qualifiers" not in occurrence

    def test_template_output_keeps_the_cardinality_on_each_occurrence(self, package):
        payload = json.loads(
            HydratorService().hydrate_to_json(
                package,
                _form(Mail={"value": "a", "occurrences": [{"value": "b"}]}),
                "template",
            )
        )
        elements = _by_id_short(payload["submodels"][0]["submodelElements"])
        assert elements["Mail__01__"]["qualifiers"][0]["value"] == "OneToMany"

    def test_form_without_occurrences_exports_as_before(self, package):
        elements = _export(package, _form())
        assert [e["idShort"] for e in elements] == [
            "Name", "Phone", "Mail", "Notes", "Site", "Last",
        ]

    def test_export_is_conformant(self, package):
        payload = json.loads(
            HydratorService().hydrate_to_json(
                package,
                _form(
                    Phone={
                        "elements": {"Number": {"value": "1"}},
                        "occurrences": [{"elements": {"Number": {"value": "2"}}}],
                    },
                    Mail={"value": "a", "occurrences": [{"value": "b"}]},
                ),
            )
        )
        result = aas_file.check_json_data(payload, version="3.0")
        assert result.ok(), "\n".join(result.to_lines())

    def test_aasx_export_carries_the_occurrences(self, package):
        hydrated = HydratorService().hydrate_submodel(
            package, _form(Mail={"value": "a", "occurrences": [{"value": "b"}]})
        )
        reparsed = ParserService().parse_aasx_to_ui_schema(hydrated)
        assert [e["idShort"] for e in reparsed["elements"]][2:4] == ["Mail", "Mail__01__"]

    def test_more_occurrences_than_allowed_fail_the_export(self, package):
        with pytest.raises(ValueError, match="may occur only once"):
            _export(package, _form(Last={"value": "x", "occurrences": [{"value": "y"}]}))

    def test_generated_names_avoid_existing_siblings(self):
        template = _template()
        template.submodel_element.add(_property("Mail__01__", "ZeroToOne"))

        elements = _export(
            _aasx(template),
            _form(Mail={"value": "a", "occurrences": [{"value": "b"}]}),
        )

        assert sorted(e["idShort"] for e in elements if e["idShort"].startswith("Mail")) == [
            "Mail",
            "Mail__01__",
            "Mail__02__",
        ]
        assert _by_id_short(elements)["Mail__02__"]["value"] == "b"
