"""Exported JSON carries no empty arrays."""

from __future__ import annotations

import json
from io import BytesIO
from zipfile import ZipFile

from aas_test_engines import file as aas_file
from basyx.aas import model
from basyx.aas.adapter import aasx
from basyx.aas.adapter import json as aas_json

from app.services.hydrator import HydratorService
from app.utils.aas_json_output import (
    NormalizingAASXWriter,
    drop_empty_arrays,
    normalize_aas_json,
)


def _store_with_entity() -> model.DictObjectStore:
    """An entity without specific asset IDs, which the SDK writes as an empty array."""
    submodel = model.Submodel(
        id_="urn:test:sm",
        id_short="Structure",
        submodel_element=[
            model.Entity(
                id_short="Node",
                entity_type=model.EntityType.CO_MANAGED_ENTITY,
                statement=[
                    model.Property(id_short="Name", value_type=model.datatypes.String, value="x")
                ],
            )
        ],
    )
    shell = model.AssetAdministrationShell(
        id_="urn:test:aas",
        asset_information=model.AssetInformation(
            asset_kind=model.AssetKind.INSTANCE, global_asset_id="urn:test:asset"
        ),
        submodel={model.ModelReference.from_referable(submodel)},
    )
    return model.DictObjectStore([shell, submodel])


def _aasx(store, writer_class) -> bytes:
    buffer = BytesIO()
    with writer_class(buffer) as writer:
        writer.write_all_aas_objects(
            "/aasx/data.json", store, aasx.DictSupplementaryFileContainer(), write_json=True
        )
    return buffer.getvalue()


def _json_part(package: bytes) -> dict:
    with ZipFile(BytesIO(package)) as archive:
        assert archive.testzip() is None
        return json.loads(archive.read("aasx/data.json"))


class TestDropEmptyArrays:
    def test_removes_empty_array_members_at_any_depth(self):
        document = {
            "keep": [1],
            "drop": [],
            "nested": {"drop": [], "keep": "x"},
            "items": [{"drop": [], "keep": 0}, []],
        }

        assert drop_empty_arrays(document) == {
            "keep": [1],
            "nested": {"keep": "x"},
            "items": [{"keep": 0}, []],
        }

    def test_leaves_other_empty_values_alone(self):
        document = {"text": "", "nothing": None, "object": {}, "zero": 0, "no": False}
        assert drop_empty_arrays(document) == document

    def test_text_that_is_not_json_is_returned_unchanged(self):
        assert normalize_aas_json("not json") == "not json"


class TestSerializedOutput:
    def test_sdk_output_fails_the_check_this_module_exists_for(self):
        # Documents the SDK behaviour; drop the workaround when this stops failing.
        buffer = BytesIO()
        aas_json.write_aas_json_file(buffer, _store_with_entity())
        document = json.loads(buffer.getvalue())

        assert document["submodels"][0]["submodelElements"][0]["specificAssetIds"] == []
        assert not aas_file.check_json_data(document, version="3.0").ok()

    def test_hydrator_json_passes(self):
        text = HydratorService().serialize_stores_to_json(_store_with_entity())
        document = json.loads(text)

        assert "specificAssetIds" not in document["submodels"][0]["submodelElements"][0]
        assert aas_file.check_json_data(document, version="3.0").ok()

    def test_hydrator_aasx_passes(self):
        package = HydratorService().serialize_stores_to_aasx(
            _store_with_entity(), aasx.DictSupplementaryFileContainer()
        )

        entity = _json_part(package)["submodels"][0]["submodelElements"][0]
        assert "specificAssetIds" not in entity
        assert entity["statements"][0]["value"] == "x"
        assert aas_file.check_aasx_file(BytesIO(package), version="3.0").ok()

    def test_normalizing_writer_only_changes_empty_arrays(self):
        plain = _json_part(_aasx(_store_with_entity(), aasx.AASXWriter))
        normalized = _json_part(_aasx(_store_with_entity(), NormalizingAASXWriter))

        assert normalized == drop_empty_arrays(plain)
        assert normalized != plain

    def test_package_can_be_read_back(self):
        package = _aasx(_store_with_entity(), NormalizingAASXWriter)

        store: model.DictObjectStore[model.Identifiable] = model.DictObjectStore()
        with aasx.AASXReader(BytesIO(package)) as reader:
            reader.read_into(store, aasx.DictSupplementaryFileContainer())

        entity = store.get_identifiable("urn:test:sm").get_referable("Node")
        assert [statement.value for statement in entity.statement] == ["x"]
