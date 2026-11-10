"""Hydration turns a filled template into a submodel instance."""

from __future__ import annotations

import json
import sys
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from aas_test_engines import file as aas_file
from basyx.aas import model
from basyx.aas.adapter import aasx as aasx_adapter

from app.services.hydrator import HydratorService, is_template_only_qualifier
from app.utils.aasx_reader import SafeAASXReader

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from audit_template_coverage import instance_export_problems  # noqa: E402

TEMPLATE_ID = "https://admin-shell.io/idta/SubmodelTemplate/Example/1/0"
STRING = model.datatypes.String


def _qualifier(type_: str, value: str, kind: model.QualifierKind | None = None) -> model.Qualifier:
    kwargs = {} if kind is None else {"kind": kind}
    return model.Qualifier(type_=type_, value_type=STRING, value=value, **kwargs)


def _cardinality(value: str) -> model.Qualifier:
    return _qualifier("SMT/Cardinality", value, model.QualifierKind.TEMPLATE_QUALIFIER)


def _template() -> model.Submodel:
    """A template that carries each kind of qualifier at each nesting level."""
    return model.Submodel(
        id_=TEMPLATE_ID,
        id_short="Example",
        kind=model.ModellingKind.TEMPLATE,
        qualifier=[_qualifier("FormTitle", "Example", model.QualifierKind.TEMPLATE_QUALIFIER)],
        submodel_element=[
            model.Property(
                id_short="Name",
                value_type=STRING,
                qualifier=[
                    _cardinality("One"),
                    # Template instructions that published templates carry
                    # without the TemplateQualifier kind.
                    _qualifier("SMT/ExampleValue", "ACME", model.QualifierKind.VALUE_QUALIFIER),
                    _qualifier("FormInfo", "Name of the thing"),
                    # A statement about the value, valid in an instance.
                    _qualifier("unit", "m", model.QualifierKind.CONCEPT_QUALIFIER),
                ],
            ),
            model.SubmodelElementCollection(
                id_short="Address",
                qualifier=[_cardinality("ZeroToOne")],
                value=[
                    model.Property(
                        id_short="Street",
                        value_type=STRING,
                        qualifier=[_cardinality("ZeroToOne")],
                    )
                ],
            ),
            model.SubmodelElementList(
                id_short="Phones",
                type_value_list_element=model.Property,
                value_type_list_element=STRING,
                qualifier=[_cardinality("ZeroToMany")],
                value=[
                    model.Property(
                        id_short=None,
                        value_type=STRING,
                        qualifier=[_cardinality("One")],
                    )
                ],
            ),
            model.Entity(
                id_short="Part",
                entity_type=model.EntityType.CO_MANAGED_ENTITY,
                qualifier=[_cardinality("ZeroToOne")],
                statement=[
                    model.Property(
                        id_short="Weight",
                        value_type=STRING,
                        qualifier=[_cardinality("ZeroToOne")],
                    )
                ],
            ),
        ],
    )


def _aasx(submodel: model.Submodel) -> bytes:
    shell = model.AssetAdministrationShell(
        id_="urn:test-aas",
        id_short="TestAAS",
        asset_information=model.AssetInformation(
            asset_kind=model.AssetKind.INSTANCE,
            global_asset_id="urn:test-asset",
        ),
        submodel={model.ModelReference.from_referable(submodel)},
    )
    store: model.DictObjectStore[model.Identifiable] = model.DictObjectStore([shell, submodel])
    buffer = BytesIO()
    with aasx_adapter.AASXWriter(buffer) as writer:
        writer.write_all_aas_objects(
            part_name="/aasx/aas/aas.json",
            objects=store,
            file_store=aasx_adapter.DictSupplementaryFileContainer(),
            write_json=True,
        )
    return buffer.getvalue()


def _form(**metadata) -> dict:
    return {
        "elements": {"Name": {"value": "Widget"}},
        "metadata": metadata or None,
    }


def _submodel(store) -> model.Submodel:
    return next(obj for obj in store if isinstance(obj, model.Submodel))


def _shell(store) -> model.AssetAdministrationShell:
    return next(obj for obj in store if isinstance(obj, model.AssetAdministrationShell))


def _all_qualifiers(submodel: model.Submodel) -> list[model.Qualifier]:
    def walk(elements):
        for element in elements:
            yield element
            if isinstance(element, (model.SubmodelElementCollection, model.SubmodelElementList)):
                yield from walk(element.value)
            elif isinstance(element, model.Entity):
                yield from walk(element.statement)

    qualifiers = list(submodel.qualifier)
    for element in walk(submodel.submodel_element):
        qualifiers.extend(element.qualifier)
    return qualifiers


@pytest.fixture
def hydrator() -> HydratorService:
    return HydratorService()


@pytest.fixture(scope="module")
def template_aasx() -> bytes:
    return _aasx(_template())


class TestInstanceIsTheDefault:
    def test_kind_becomes_instance(self, hydrator, template_aasx):
        store, _ = hydrator.hydrate_to_stores(template_aasx, _form())
        assert _submodel(store).kind == model.ModellingKind.INSTANCE

    def test_template_only_qualifiers_are_removed_at_every_level(self, hydrator, template_aasx):
        store, _ = hydrator.hydrate_to_stores(template_aasx, _form())

        remaining = _all_qualifiers(_submodel(store))

        assert [(q.type, q.value) for q in remaining] == [("unit", "m")]

    def test_values_are_kept(self, hydrator, template_aasx):
        store, _ = hydrator.hydrate_to_stores(template_aasx, _form())
        name = _submodel(store).get_referable("Name")
        assert name.value == "Widget"

    def test_serialized_json_is_an_instance(self, hydrator, template_aasx):
        payload = json.loads(hydrator.hydrate_to_json(template_aasx, _form()))

        submodel = payload["submodels"][0]
        assert submodel.get("kind", "Instance") == "Instance"
        assert "TemplateQualifier" not in json.dumps(payload)
        assert "SMT/Cardinality" not in json.dumps(payload)

    def test_serialized_aasx_is_an_instance(self, hydrator, template_aasx):
        hydrated = hydrator.hydrate_submodel(template_aasx, _form())

        store: model.DictObjectStore[model.Identifiable] = model.DictObjectStore()
        with SafeAASXReader(BytesIO(hydrated)) as reader:
            reader.read_into(store, aasx_adapter.DictSupplementaryFileContainer())

        submodel = _submodel(store)
        assert submodel.kind == model.ModellingKind.INSTANCE
        assert [q.type for q in _all_qualifiers(submodel)] == ["unit"]

    def test_output_passes_metamodel_checks(self, hydrator, template_aasx):
        payload = json.loads(hydrator.hydrate_to_json(template_aasx, _form()))

        result = aas_file.check_json_data(payload, version="3.0")
        assert result.ok(), "\n".join(result.to_lines())


class TestIdentifier:
    def test_instance_does_not_reuse_the_template_id(self, hydrator, template_aasx):
        store, _ = hydrator.hydrate_to_stores(template_aasx, _form())

        submodel = _submodel(store)
        assert submodel.id != TEMPLATE_ID
        assert submodel.id.startswith("urn:uuid:")

    def test_form_that_echoes_the_template_id_still_gets_a_new_one(self, hydrator, template_aasx):
        # The editor pre-fills the ID field with the template's ID.
        store, _ = hydrator.hydrate_to_stores(template_aasx, _form(submodelId=TEMPLATE_ID))
        assert _submodel(store).id != TEMPLATE_ID

    def test_shell_reference_and_store_follow_the_new_id(self, hydrator, template_aasx):
        store, _ = hydrator.hydrate_to_stores(template_aasx, _form())

        submodel = _submodel(store)
        references = [ref.key[-1].value for ref in _shell(store).submodel]
        assert references == [submodel.id]
        assert store.get_identifiable(submodel.id) is submodel
        assert TEMPLATE_ID not in store

    def test_explicit_id_is_used_as_given(self, hydrator, template_aasx):
        store, _ = hydrator.hydrate_to_stores(
            template_aasx, _form(submodelId="https://example.com/ids/sm/1")
        )
        assert _submodel(store).id == "https://example.com/ids/sm/1"

    def test_each_export_without_an_id_gets_a_different_one(self, hydrator, template_aasx):
        first, _ = hydrator.hydrate_to_stores(template_aasx, _form())
        second, _ = hydrator.hydrate_to_stores(template_aasx, _form())
        assert _submodel(first).id != _submodel(second).id


class TestTemplateLink:
    def test_template_id_is_recorded(self, hydrator, template_aasx):
        store, _ = hydrator.hydrate_to_stores(template_aasx, _form())
        assert _submodel(store).administration.template_id == TEMPLATE_ID

    def test_template_id_from_the_form_wins(self, hydrator, template_aasx):
        store, _ = hydrator.hydrate_to_stores(
            template_aasx,
            _form(administration={"templateId": "urn:company:profile:7"}),
        )
        assert _submodel(store).administration.template_id == "urn:company:profile:7"

    def test_existing_administration_is_extended_not_replaced(self, hydrator):
        template = _template()
        template.administration = model.AdministrativeInformation(version="1", revision="0")

        store, _ = hydrator.hydrate_to_stores(_aasx(template), _form())

        administration = _submodel(store).administration
        assert (administration.version, administration.revision) == ("1", "0")
        assert administration.template_id == TEMPLATE_ID


class TestTemplateOutput:
    def test_template_output_keeps_the_template_as_is(self, hydrator, template_aasx):
        store, _ = hydrator.hydrate_to_stores(template_aasx, _form(), "template")

        submodel = _submodel(store)
        assert submodel.kind == model.ModellingKind.TEMPLATE
        assert submodel.id == TEMPLATE_ID
        assert submodel.administration is None
        assert len(_all_qualifiers(submodel)) == len(_all_qualifiers(_template()))
        assert submodel.get_referable("Name").value == "Widget"

    @pytest.mark.parametrize("configured,expected", [
        ("template", model.ModellingKind.TEMPLATE),
        ("instance", model.ModellingKind.INSTANCE),
    ])
    def test_setting_chooses_the_default(self, hydrator, template_aasx, configured, expected):
        settings = MagicMock(
            semantic_embed_concept_descriptions=False,
            export_submodel_kind=configured,
        )
        with patch("app.services.hydrator.get_settings", return_value=settings):
            store, _ = hydrator.hydrate_to_stores(template_aasx, _form())
        assert _submodel(store).kind == expected

    def test_explicit_kind_overrides_the_setting(self, hydrator, template_aasx):
        settings = MagicMock(
            semantic_embed_concept_descriptions=False,
            export_submodel_kind="template",
        )
        with patch("app.services.hydrator.get_settings", return_value=settings):
            store, _ = hydrator.hydrate_to_stores(template_aasx, _form(), "instance")
        assert _submodel(store).kind == model.ModellingKind.INSTANCE


class TestTemplateOnlyQualifiers:
    @pytest.mark.parametrize("type_", [
        "SMT/Cardinality",
        "SMT/AllowedValue",
        "smt/examplevalue",
        "Cardinality",
        "Multiplicity",
        "FormTitle",
        "FormChoices",
        "EditIdShort",
        "PresetIdShort",
        "AllowedIdShort",
        "ExampleValue",
        "DefaultValue",
    ])
    def test_template_instructions_are_recognised_whatever_their_kind(self, type_):
        assert is_template_only_qualifier(_qualifier(type_, "x"))

    @pytest.mark.parametrize("type_", ["unit", "enumeration", "RequiredAtDQL", "Note", "LifeCycleQual"])
    def test_statements_about_the_asset_are_kept(self, type_):
        assert not is_template_only_qualifier(_qualifier(type_, "x"))

    def test_template_qualifier_kind_always_counts(self):
        qualifier = _qualifier("CompanySpecific", "x", model.QualifierKind.TEMPLATE_QUALIFIER)
        assert is_template_only_qualifier(qualifier)


def _template_with_annotation() -> model.Submodel:
    """A relationship whose annotation carries a template qualifier."""
    template = _template()
    name = model.ModelReference.from_referable(template.get_referable("Name"))
    template.submodel_element.add(
        model.AnnotatedRelationshipElement(
            id_short="Link",
            first=name,
            second=name,
            qualifier=[_cardinality("ZeroToOne")],
            annotation=[
                model.Property(
                    id_short="Note", value_type=STRING, qualifier=[_cardinality("ZeroToOne")]
                )
            ],
        )
    )
    return template


class TestNestedInRelationships:
    def test_qualifiers_on_annotations_are_removed(self, hydrator):
        store, _ = hydrator.hydrate_to_stores(_aasx(_template_with_annotation()), _form())

        link = _submodel(store).get_referable("Link")
        assert list(link.qualifier) == []
        assert [list(annotation.qualifier) for annotation in link.annotation] == [[]]

    def test_audit_sees_a_qualifier_left_on_an_annotation(self, hydrator):
        store, _ = hydrator.hydrate_to_stores(_aasx(_template_with_annotation()), _form())
        assert instance_export_problems(store, TEMPLATE_ID) == []

        # What a hydrator that missed annotations would leave behind.
        link = _submodel(store).get_referable("Link")
        next(iter(link.annotation)).qualifier.add(_cardinality("ZeroToOne"))

        assert instance_export_problems(store, TEMPLATE_ID) == [
            "1 template-only qualifier(s) remain"
        ]


class TestAuditCheck:
    def test_instance_output_has_no_problems(self, hydrator, template_aasx):
        store, _ = hydrator.hydrate_to_stores(template_aasx, _form())
        assert instance_export_problems(store, TEMPLATE_ID) == []

    def test_template_output_is_reported(self, hydrator, template_aasx):
        store, _ = hydrator.hydrate_to_stores(template_aasx, _form(), "template")

        problems = instance_export_problems(store, TEMPLATE_ID)

        assert len(problems) == 3
        assert "kind=Template" in problems[0]
        assert "template-only qualifier" in problems[1]
        assert "template's identifier" in problems[2]
