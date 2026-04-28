import json
from io import BytesIO

from basyx.aas import model
from basyx.aas.adapter import aasx as aasx_adapter

from app.services.hydrator import HydratorService
from app.utils.aasx_reader import SafeAASXReader


def test_apply_metadata_updates_submodel_fields():
    submodel = model.Submodel(
        id_="urn:old-submodel",
        id_short="OldId",
        submodel_element=[],
    )
    hydrator = HydratorService()

    metadata = {
        "idShort": "NewId",
        "submodelId": "urn:new-submodel",
        "administration": {
            "version": "2",
            "revision": "5",
            "templateId": "template-42",
        },
    }

    hydrator._apply_metadata(submodel, metadata)

    assert submodel.id_short == "NewId"
    submodel_id = getattr(submodel, "id_", None) or getattr(submodel, "id", None)
    assert submodel_id == "urn:new-submodel"
    assert submodel.administration is not None
    assert submodel.administration.version == "2"
    assert submodel.administration.revision == "5"
    assert submodel.administration.template_id == "template-42"


def test_metadata_id_change_rewrites_aas_submodel_reference_and_store_index():
    hydrator = HydratorService()
    submodel = model.Submodel(
        id_="urn:old-submodel",
        id_short="OldId",
        submodel_element=[],
    )
    aas = _aas_for_submodel(submodel)
    object_store: model.DictObjectStore[model.Identifiable] = model.DictObjectStore(
        [aas, submodel]
    )

    hydrator._apply_metadata_with_reference_updates(
        object_store,
        submodel,
        {"submodelId": "urn:new-submodel"},
    )

    assert submodel.id == "urn:new-submodel"
    assert object_store.get_identifiable("urn:new-submodel") is submodel
    assert "urn:old-submodel" not in object_store
    assert _aas_submodel_reference_ids(aas) == ["urn:new-submodel"]


def test_metadata_id_change_serializes_to_json_with_updated_aas_reference():
    hydrator = HydratorService()
    aasx_bytes = _create_aasx_from_submodel(
        model.Submodel(
            id_="urn:old-submodel",
            id_short="OldId",
            submodel_element=[],
        )
    )

    payload = json.loads(
        hydrator.hydrate_to_json(
            aasx_bytes,
            {"elements": {}, "metadata": {"submodelId": "urn:new-submodel"}},
        )
    )

    assert payload["submodels"][0]["id"] == "urn:new-submodel"
    assert (
        payload["assetAdministrationShells"][0]["submodels"][0]["keys"][-1]["value"]
        == "urn:new-submodel"
    )


def test_metadata_id_change_serializes_to_aasx_with_updated_aas_reference():
    hydrator = HydratorService()
    aasx_bytes = _create_aasx_from_submodel(
        model.Submodel(
            id_="urn:old-submodel",
            id_short="OldId",
            submodel_element=[],
        )
    )

    hydrated_bytes = hydrator.hydrate_submodel(
        aasx_bytes,
        {"elements": {}, "metadata": {"submodelId": "urn:new-submodel"}},
    )

    object_store: model.DictObjectStore[model.Identifiable] = model.DictObjectStore()
    file_store = aasx_adapter.DictSupplementaryFileContainer()
    with SafeAASXReader(BytesIO(hydrated_bytes)) as reader:
        reader.read_into(object_store, file_store)

    submodels = [obj for obj in object_store if isinstance(obj, model.Submodel)]
    aases = [
        obj for obj in object_store if isinstance(obj, model.AssetAdministrationShell)
    ]
    assert [submodel.id for submodel in submodels] == ["urn:new-submodel"]
    assert _aas_submodel_reference_ids(aases[0]) == ["urn:new-submodel"]


def _aas_for_submodel(submodel: model.Submodel) -> model.AssetAdministrationShell:
    return model.AssetAdministrationShell(
        id_="urn:test-aas",
        id_short="TestAAS",
        asset_information=model.AssetInformation(
            asset_kind=model.AssetKind.INSTANCE,
            global_asset_id="urn:test-asset",
        ),
        submodel={model.ModelReference.from_referable(submodel)},
    )


def _create_aasx_from_submodel(submodel: model.Submodel) -> bytes:
    object_store: model.DictObjectStore[model.Identifiable] = model.DictObjectStore(
        [_aas_for_submodel(submodel), submodel]
    )
    file_store = aasx_adapter.DictSupplementaryFileContainer()

    buffer = BytesIO()
    with aasx_adapter.AASXWriter(buffer) as writer:
        writer.write_all_aas_objects(
            part_name="/aasx/aas/aas.json",
            objects=object_store,
            file_store=file_store,
            write_json=True,
        )
    return buffer.getvalue()


def _aas_submodel_reference_ids(aas: model.AssetAdministrationShell) -> list[str]:
    return sorted(
        ref.key[-1].value
        for ref in aas.submodel or ()
        if getattr(ref, "key", None)
    )
