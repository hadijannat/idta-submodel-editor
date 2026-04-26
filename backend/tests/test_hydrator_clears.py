import base64
from datetime import date

import pytest
from basyx.aas import model

from app.services.hydrator import HydratorService


@pytest.mark.asyncio
async def test_hydrator_clears_multilang_and_blob():
    hydrator = HydratorService()
    multilang = model.MultiLanguageProperty(id_short="ml")
    multilang.value = model.MultiLanguageTextType({"en": "Hello"})

    blob = model.Blob(id_short="blob", content_type="text/plain")
    blob.value = b"data"

    hydrator._hydrate_multilang(multilang, {"value": {"en": ""}})
    hydrator._hydrate_blob(blob, {"value": ""})

    assert multilang.value is None
    assert blob.value is None


@pytest.mark.asyncio
async def test_hydrator_clears_reference_and_relationship():
    hydrator = HydratorService()
    ref = model.ReferenceElement(id_short="ref")
    ref.value = model.ExternalReference(key=(model.Key(model.KeyTypes.GLOBAL_REFERENCE, "urn:old"),))

    rel = model.RelationshipElement(
        id_short="rel",
        first=model.ExternalReference(
            key=(model.Key(model.KeyTypes.GLOBAL_REFERENCE, "urn:first"),)
        ),
        second=model.ExternalReference(
            key=(model.Key(model.KeyTypes.GLOBAL_REFERENCE, "urn:second"),)
        ),
    )

    hydrator._hydrate_reference(ref, {"value": ""})
    hydrator._hydrate_relationship(rel, {"first": "", "second": ""})

    assert ref.value is None
    assert rel.first is None
    assert rel.second is None


def test_hydrator_decodes_base64_blob_values():
    hydrator = HydratorService()
    blob = model.Blob(id_short="blob", content_type="application/octet-stream")
    original = b"\xff\xfe\x00\x01"
    encoded = base64.b64encode(original).decode("ascii")

    hydrator._hydrate_blob(
        blob,
        {"value": f"base64:{encoded}", "valueEncoding": "base64"},
    )

    assert blob.value == original


def test_hydrator_keeps_utf8_blob_behavior():
    hydrator = HydratorService()
    blob = model.Blob(id_short="blob", content_type="text/plain")

    hydrator._hydrate_blob(blob, {"value": "hello"})

    assert blob.value == b"hello"


def test_hydrator_clears_blank_file_value_without_invalid_path():
    hydrator = HydratorService()
    file_element = model.File(
        id_short="file",
        content_type="application/pdf",
        value="existing.pdf",
    )

    hydrator._hydrate_file(file_element, {"value": "", "contentType": ""})

    assert file_element.value is None
    assert file_element.content_type == "application/pdf"


def test_hydrator_ignores_blank_entity_global_asset_id():
    hydrator = HydratorService()
    entity = model.Entity(
        id_short="entity",
        entity_type=model.EntityType.CO_MANAGED_ENTITY,
        global_asset_id=None,
        statement=(),
    )

    hydrator._hydrate_entity(entity, {"globalAssetId": "", "statements": {}})

    assert entity.global_asset_id is None


def test_hydrator_find_submodel_ignores_unreferenced_template_identifier():
    hydrator = HydratorService()
    referenced = model.Submodel(
        id_="urn:referenced-submodel",
        id_short="ReferencedSubmodel",
    )
    decoy = model.Submodel(
        id_="https://admin-shell.io/idta/SubmodelTemplate/Decoy/1/0",
        id_short="DecoyTemplate",
    )
    aas_obj = model.AssetAdministrationShell(
        id_="urn:test:aas",
        id_short="TestAAS",
        asset_information=model.AssetInformation(
            asset_kind=model.AssetKind.INSTANCE,
            global_asset_id="urn:test:asset",
        ),
        submodel={model.ModelReference.from_referable(referenced)},
    )
    object_store = model.DictObjectStore([aas_obj, decoy, referenced])

    selected = hydrator._find_submodel(object_store, aas_obj)

    assert selected is referenced


def test_hydrator_coerces_gyear_property_values():
    hydrator = HydratorService()
    prop = model.Property(
        id_short="year",
        value_type=model.datatypes.GYear,
        value=model.datatypes.GYear(1988),
    )

    hydrator._hydrate_property(prop, {"value": "2024"})

    assert isinstance(prop.value, model.datatypes.GYear)
    assert prop.value.year == 2024


def test_hydrator_rejects_invalid_property_assignment():
    hydrator = HydratorService()
    prop = model.Property(
        id_short="date",
        value_type=model.datatypes.Date,
        value=date(2023, 1, 1),
    )

    with pytest.raises(ValueError, match="Invalid value for property date"):
        hydrator._hydrate_property(prop, {"value": "not-a-date"})

    assert prop.value == date(2023, 1, 1)


def test_hydrator_updates_annotated_relationship_annotations():
    hydrator = HydratorService()
    annotation = model.Property(
        id_short="annotation",
        value_type=model.datatypes.String,
        value="before",
    )
    relationship = model.AnnotatedRelationshipElement(
        id_short="rel",
        first=model.ExternalReference(
            key=(model.Key(model.KeyTypes.GLOBAL_REFERENCE, "urn:first"),)
        ),
        second=model.ExternalReference(
            key=(model.Key(model.KeyTypes.GLOBAL_REFERENCE, "urn:second"),)
        ),
        annotation=(annotation,),
    )

    hydrator._hydrate_single_element(
        relationship,
        {
            "first": "urn:first-updated",
            "second": "urn:second-updated",
            "annotations": [{"value": "after"}],
        },
    )

    assert relationship.first.key[-1].value == "urn:first-updated"
    assert relationship.second.key[-1].value == "urn:second-updated"
    assert list(relationship.annotation)[0].value == "after"


def test_hydrator_updates_readonly_list_semantic_id_field():
    hydrator = HydratorService()
    list_element = model.SubmodelElementList(
        id_short="list",
        type_value_list_element=model.Property,
        value_type_list_element=model.datatypes.String,
        value=(),
    )

    hydrator._apply_semantic_fields(
        list_element,
        {"semanticIdListElement": "urn:list-semantic"},
    )

    assert list_element.semantic_id_list_element.key[-1].value == "urn:list-semantic"

    hydrator._apply_semantic_fields(
        list_element,
        {"semanticIdListElement": None},
    )

    assert list_element.semantic_id_list_element is None
