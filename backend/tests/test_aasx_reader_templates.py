"""Templates are read as published: nothing is dropped silently."""

from __future__ import annotations

import json
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from basyx.aas import model
from basyx.aas.adapter import aasx

from app.services.hydrator import HydratorService
from app.services.parser import ParserService
from app.services.validation import validate_form_data
from app.utils.aasx_reader import (
    SafeAASXReader,
    construct_template_entity,
    construct_template_list,
    count_submodel_elements,
    count_submodel_elements_in_json,
    count_submodel_elements_in_xml,
)

NS = "https://admin-shell.io/aas/3/1"
ORIGIN_TYPE = "http://admin-shell.io/aasx/relationships/aasx-origin"
SPEC_TYPE = "http://admin-shell.io/aasx/relationships/aas-spec"
RELS_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

CARDINALITY_ONE = """
<qualifiers><qualifier>
  <kind>TemplateQualifier</kind><type>SMT/Cardinality</type>
  <valueType>xs:string</valueType><value>One</value>
</qualifier></qualifiers>"""

CARDINALITY_OPTIONAL = CARDINALITY_ONE.replace(">One<", ">ZeroToOne<")

SELF_MANAGED_ENTITY = f"""
<entity>
  <idShort>EntryNode</idShort>{CARDINALITY_ONE}
  <statements>
    <property>
      <idShort>Level</idShort>{CARDINALITY_OPTIONAL}
      <valueType>xs:string</valueType>
    </property>
  </statements>
  <entityType>SelfManagedEntity</entityType>
</entity>"""

MIXED_LIST = """
<submodelElementList>
  <idShort>Anything</idShort>
  <typeValueListElement>SubmodelElement</typeValueListElement>
  <value>
    <range><valueType>xs:int</valueType></range>
    <property><valueType>xs:string</valueType></property>
  </value>
</submodelElementList>"""

REPEATED_QUALIFIER = """
<submodelElementCollection>
  <idShort>Container</idShort>
  <qualifiers>
    <qualifier><type>SMT/Cardinality</type><valueType>xs:string</valueType><value>ZeroToMany</value></qualifier>
    <qualifier><type>SMT/Cardinality</type><valueType>xs:string</valueType><value>Recursive</value></qualifier>
    <qualifier><type>unit</type><valueType>xs:string</valueType><value>m</value></qualifier>
  </qualifiers>
  <value>
    <property><idShort>Inside</idShort><valueType>xs:string</valueType></property>
  </value>
</submodelElementCollection>"""

UNREADABLE_PROPERTY = """
<property><idShort>Broken</idShort><valueType>xs:noSuchType</valueType></property>"""

PLAIN_PROPERTY = """
<property><idShort>Fine</idShort><valueType>xs:string</valueType></property>"""


def _environment_xml(*elements: str, submodel_id: str = "urn:test:sm") -> bytes:
    return (
        f'<environment xmlns="{NS}"><submodels><submodel>'
        f"<idShort>Template</idShort><id>{submodel_id}</id><kind>Template</kind>"
        f"<submodelElements>{''.join(elements)}</submodelElements>"
        "</submodel></submodels></environment>"
    ).encode()


def _relationships(type_: str, target: str) -> str:
    return (
        f'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="{RELS_NS}">'
        f'<Relationship Id="r1" Target="{target}" Type="{type_}"/>'
        "</Relationships>"
    )


def _package(spec: bytes, *, part: str = "aasx/data.xml") -> bytes:
    """A minimal AASX package around one AAS document."""
    content_type = "application/json" if part.endswith(".json") else "application/xml"
    extension = part.rsplit(".", 1)[-1]
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as package:
        package.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" '
            'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            f'<Default Extension="{extension}" ContentType="{content_type}"/>'
            '<Override PartName="/aasx/aasx-origin" ContentType="text/plain"/>'
            "</Types>",
        )
        package.writestr("_rels/.rels", _relationships(ORIGIN_TYPE, "/aasx/aasx-origin"))
        package.writestr("aasx/aasx-origin", "")
        package.writestr("aasx/_rels/aasx-origin.rels", _relationships(SPEC_TYPE, f"/{part}"))
        package.writestr(part, spec)
    return buffer.getvalue()


def _read(package: bytes, reader_class=SafeAASXReader):
    store: model.DictObjectStore[model.Identifiable] = model.DictObjectStore()
    with reader_class(BytesIO(package)) as reader:
        reader.read_into(store, aasx.DictSupplementaryFileContainer())
        issues = list(getattr(reader, "read_issues", []))
    submodels = [obj for obj in store if isinstance(obj, model.Submodel)]
    return (submodels[0] if submodels else None), issues


class TestSelfManagedEntityWithoutAssetId:
    def test_entity_and_its_statements_are_kept(self):
        submodel, issues = _read(_package(_environment_xml(SELF_MANAGED_ENTITY)))

        entity = submodel.get_referable("EntryNode")
        assert isinstance(entity, model.Entity)
        assert type(entity) is model.Entity
        assert entity.entity_type == model.EntityType.SELF_MANAGED_ENTITY
        assert entity.global_asset_id is None
        assert [statement.id_short for statement in entity.statement] == ["Level"]
        assert [qualifier.value for qualifier in entity.qualifier] == ["One"]
        assert issues == []

    def test_the_sdk_reader_drops_it(self):
        submodel, _ = _read(_package(_environment_xml(SELF_MANAGED_ENTITY)), aasx.AASXReader)
        assert len(submodel.submodel_element) == 0

    def test_asset_id_can_be_filled_in_afterwards(self):
        submodel, _ = _read(_package(_environment_xml(SELF_MANAGED_ENTITY)))
        entity = submodel.get_referable("EntryNode")

        entity.global_asset_id = "urn:asset:1"

        assert entity.global_asset_id == "urn:asset:1"

    def test_json_part_is_read_the_same_way(self):
        document = {
            "submodels": [
                {
                    "modelType": "Submodel",
                    "id": "urn:test:sm",
                    "idShort": "Template",
                    "kind": "Template",
                    "submodelElements": [
                        {
                            "modelType": "Entity",
                            "idShort": "EntryNode",
                            "entityType": "SelfManagedEntity",
                            "statements": [
                                {"modelType": "Property", "idShort": "Level", "valueType": "xs:string"}
                            ],
                        }
                    ],
                }
            ]
        }
        package = _package(json.dumps(document).encode(), part="aasx/data.json")

        submodel, issues = _read(package)

        entity = submodel.get_referable("EntryNode")
        assert entity.entity_type == model.EntityType.SELF_MANAGED_ENTITY
        assert len(entity.statement) == 1
        assert issues == []

    def test_other_entity_rules_still_apply(self):
        with pytest.raises(model.AASConstraintViolation):
            construct_template_entity(
                "Node", model.EntityType.CO_MANAGED_ENTITY, global_asset_id="urn:asset:1"
            )

    def test_complete_entities_are_built_normally(self):
        entity = construct_template_entity(
            "Node", model.EntityType.SELF_MANAGED_ENTITY, global_asset_id="urn:asset:1"
        )
        assert entity.global_asset_id == "urn:asset:1"


class TestListOfAbstractType:
    def test_mixed_items_are_kept(self):
        submodel, issues = _read(_package(_environment_xml(MIXED_LIST)))

        list_ = submodel.get_referable("Anything")
        assert type(list_) is model.SubmodelElementList
        assert [type(item).__name__ for item in list_.value] == ["Range", "Property"]
        assert issues == []

    def test_the_sdk_reader_drops_the_list(self):
        submodel, _ = _read(_package(_environment_xml(MIXED_LIST)), aasx.AASXReader)
        assert len(submodel.submodel_element) == 0

    def test_items_can_be_replaced_after_reading(self):
        # Hydration clears a list and adds its items again.
        submodel, _ = _read(_package(_environment_xml(MIXED_LIST)))
        list_ = submodel.get_referable("Anything")
        items = list(list_.value)

        list_.value.clear()
        for item in items:
            list_.value.add(item)

        assert len(list_.value) == 2

    def test_concrete_list_types_stay_strict(self):
        list_ = construct_template_list(
            "Numbers", model.Property, value_type_list_element=model.datatypes.Int
        )
        with pytest.raises(model.AASConstraintViolation):
            list_.value.add(model.Range(None, value_type=model.datatypes.Int))


class TestRepeatedQualifierType:
    def test_element_is_kept_with_the_first_qualifier(self):
        submodel, issues = _read(_package(_environment_xml(REPEATED_QUALIFIER)))

        container = submodel.get_referable("Container")
        assert sorted((q.type, q.value) for q in container.qualifier) == [
            ("SMT/Cardinality", "ZeroToMany"),
            ("unit", "m"),
        ]
        assert [child.id_short for child in container.value] == ["Inside"]
        assert issues == []

    def test_the_sdk_reader_drops_the_element_and_its_children(self):
        submodel, _ = _read(_package(_environment_xml(REPEATED_QUALIFIER)), aasx.AASXReader)
        assert len(submodel.submodel_element) == 0

    def test_json_part_is_read_the_same_way(self):
        qualifier = {"type": "SMT/Cardinality", "valueType": "xs:string"}
        document = {
            "submodels": [
                {
                    "modelType": "Submodel",
                    "id": "urn:test:sm",
                    "submodelElements": [
                        {
                            "modelType": "Property",
                            "idShort": "Twice",
                            "valueType": "xs:string",
                            "qualifiers": [
                                {**qualifier, "value": "One"},
                                {**qualifier, "value": "ZeroToOne"},
                            ],
                        }
                    ],
                }
            ]
        }
        submodel, issues = _read(
            _package(json.dumps(document).encode(), part="aasx/data.json")
        )

        assert [q.value for q in submodel.get_referable("Twice").qualifier] == ["One"]
        assert issues == []


class TestLossIsReported:
    def test_unreadable_element_is_counted_and_explained(self):
        package = _package(_environment_xml(PLAIN_PROPERTY, UNREADABLE_PROPERTY))

        submodel, issues = _read(package)

        assert [element.id_short for element in submodel.submodel_element] == ["Fine"]
        assert issues[0].startswith("1 of 2 elements in this template could not be read")
        assert any("xs:noSuchType" in issue for issue in issues[1:])

    def test_children_of_an_unreadable_element_count_as_lost(self):
        broken_collection = (
            "<submodelElementCollection><idShort>Outer</idShort><value>"
            f"{PLAIN_PROPERTY}{UNREADABLE_PROPERTY}"
            "</value></submodelElementCollection>"
        )
        _, issues = _read(_package(_environment_xml(broken_collection)))
        assert issues[0].startswith("1 of 3 elements")

    def test_complete_read_reports_nothing(self):
        _, issues = _read(_package(_environment_xml(PLAIN_PROPERTY)))
        assert issues == []

    def test_parser_passes_the_report_on(self):
        package = _package(_environment_xml(PLAIN_PROPERTY, UNREADABLE_PROPERTY))

        schema = ParserService().parse_aasx_to_ui_schema(package)

        assert schema["readWarnings"][0].startswith("1 of 2 elements")
        assert [element["idShort"] for element in schema["elements"]] == ["Fine"]

    def test_parser_reports_nothing_for_a_complete_read(self):
        schema = ParserService().parse_aasx_to_ui_schema(
            _package(_environment_xml(PLAIN_PROPERTY))
        )
        assert schema["readWarnings"] == []

    def test_parser_says_when_a_package_holds_more_submodels(self):
        document = (
            f'<environment xmlns="{NS}"><submodels>'
            "<submodel><idShort>First</idShort><id>urn:test:a</id></submodel>"
            "<submodel><idShort>Second</idShort><id>urn:test:b</id></submodel>"
            "</submodels></environment>"
        ).encode()

        schema = ParserService().parse_aasx_to_ui_schema(_package(document))

        assert schema["idShort"] == "First"
        assert schema["readWarnings"] == [
            "This package contains 2 submodels. The form shows 'First' only; "
            "the others are exported unchanged."
        ]


class TestElementCounts:
    def test_xml_count_covers_every_nesting_level(self):
        raw = _environment_xml(SELF_MANAGED_ENTITY, MIXED_LIST, REPEATED_QUALIFIER)
        assert count_submodel_elements_in_xml(raw) == 2 + 3 + 2

    def test_xml_count_ignores_other_sections(self):
        raw = (
            f'<environment xmlns="{NS}">'
            "<conceptDescriptions><conceptDescription><id>urn:cd</id>"
            "</conceptDescription></conceptDescriptions>"
            "</environment>"
        ).encode()
        assert count_submodel_elements_in_xml(raw) == 0
        assert count_submodel_elements_in_xml(b"not xml") is None

    def test_json_count(self):
        document = {
            "submodels": [
                {
                    "modelType": "Submodel",
                    "submodelElements": [
                        {
                            "modelType": "SubmodelElementCollection",
                            "value": [{"modelType": "Property"}, {"modelType": "Range"}],
                        },
                        {
                            "modelType": "Operation",
                            "inputVariables": [{"value": {"modelType": "Property"}}],
                        },
                    ],
                }
            ],
            "conceptDescriptions": [{"modelType": "ConceptDescription"}],
        }
        assert count_submodel_elements_in_json(document) == 5
        assert count_submodel_elements_in_json([]) is None

    def test_object_count_matches_document_count(self):
        raw = _environment_xml(SELF_MANAGED_ENTITY, MIXED_LIST, REPEATED_QUALIFIER)
        submodel, _ = _read(_package(raw))
        assert count_submodel_elements([submodel]) == count_submodel_elements_in_xml(raw)


class TestSelfManagedEntityInTheEditor:
    @pytest.fixture(scope="class")
    def package(self) -> bytes:
        return _package(_environment_xml(SELF_MANAGED_ENTITY))

    @pytest.fixture(scope="class")
    def schema(self, package) -> dict:
        return ParserService().parse_aasx_to_ui_schema(package)

    def test_schema_shows_the_entity(self, schema):
        entity = schema["elements"][0]
        assert entity["modelType"] == "Entity"
        assert "SELF_MANAGED" in entity["entityType"]
        assert [statement["idShort"] for statement in entity["statements"]] == ["Level"]

    def test_missing_asset_id_is_a_validation_error(self, schema):
        form = {"elements": {"EntryNode": {"globalAssetId": "", "statements": {}}}}

        errors, _ = validate_form_data(schema, form)

        assert [(e.field, e.code) for e in errors] == [
            ("EntryNode.globalAssetId", "required_value")
        ]

    def test_asset_id_satisfies_validation(self, schema):
        form = {"elements": {"EntryNode": {"globalAssetId": "urn:asset:1", "statements": {}}}}
        errors, warnings = validate_form_data(schema, form)
        assert errors == [] and warnings == []

    def test_optional_entity_only_warns(self, schema):
        optional = {**schema, "elements": [{**schema["elements"][0], "cardinality": "[0..1]"}]}
        form = {"elements": {"EntryNode": {"globalAssetId": "", "statements": {}}}}

        errors, warnings = validate_form_data(optional, form)

        assert errors == []
        assert [w.field for w in warnings] == ["EntryNode.globalAssetId"]

    def test_co_managed_entity_needs_no_asset_id(self, schema):
        co_managed = {
            **schema,
            "elements": [{**schema["elements"][0], "entityType": "EntityType.CO_MANAGED_ENTITY"}],
        }
        form = {"elements": {"EntryNode": {"statements": {}}}}
        errors, warnings = validate_form_data(co_managed, form)
        assert errors == [] and warnings == []

    def test_filled_entity_is_exported(self, package):
        form = {
            "elements": {
                "EntryNode": {
                    "globalAssetId": "urn:asset:1",
                    "statements": {"Level": {"value": "top"}},
                }
            }
        }

        payload = json.loads(HydratorService().hydrate_to_json(package, form))

        entity = payload["submodels"][0]["submodelElements"][0]
        assert entity["entityType"] == "SelfManagedEntity"
        assert entity["globalAssetId"] == "urn:asset:1"
        assert entity["statements"][0]["value"] == "top"
