"""Exported packages must reference supplementary files by their stored names."""

from __future__ import annotations

import zipfile
from io import BytesIO
from xml.etree import ElementTree

from aas_test_engines import file as aas_file
from basyx.aas import model
from basyx.aas.adapter import aasx

from app.services.hydrator import HydratorService
from app.utils.aasx_reader import SafeAASXReader

MIXED_CASE_PART = "/aasx/files/IDTA-02023-1-0-_Submodel_CarbonFootprint-Titel.png"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"mixed-case supplementary file"
THUMBNAIL_PART = "/aasx/files/Product_Thumbnail.PNG"
THUMBNAIL_BYTES = b"\x89PNG\r\n\x1a\n" + b"thumbnail"

_RELATIONSHIP = "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"
_AAS_SUPPL = "http://admin-shell.io/aasx/relationships/aas-suppl"


def _build_aasx(with_shell: bool = True) -> bytes:
    """Build a package whose supplementary files have upper-case letters in their names."""
    file_store = aasx.DictSupplementaryFileContainer()
    file_store.add_file(MIXED_CASE_PART, BytesIO(PNG_BYTES), "image/png")

    submodel = model.Submodel(
        id_="https://example.org/Submodel/MixedCaseFiles/1/0",
        id_short="MixedCaseFiles",
        submodel_element=[
            model.File(id_short="TitleImage", content_type="image/png", value=MIXED_CASE_PART),
            model.Property(
                id_short="Name", value_type=model.datatypes.String, value="original"
            ),
        ],
    )
    objects: list[model.Identifiable] = [submodel]
    if with_shell:
        file_store.add_file(THUMBNAIL_PART, BytesIO(THUMBNAIL_BYTES), "image/png")
        objects.append(
            model.AssetAdministrationShell(
                id_="urn:test:aas:mixed-case-files",
                id_short="MixedCaseFilesAAS",
                asset_information=model.AssetInformation(
                    asset_kind=model.AssetKind.TYPE,
                    global_asset_id="urn:test:asset:mixed-case-files",
                    default_thumbnail=model.Resource(
                        path=THUMBNAIL_PART, content_type="image/png"
                    ),
                ),
                submodel={model.ModelReference.from_referable(submodel)},
            )
        )

    output = BytesIO()
    with aasx.AASXWriter(output) as writer:
        writer.write_all_aas_objects(
            "/aasx/data.xml", model.DictObjectStore(objects), file_store, write_json=False
        )
    return output.getvalue()


def _assert_conformant(package: bytes) -> None:
    result = aas_file.check_aasx_file(BytesIO(package))
    assert result.ok(), "\n".join(result.to_lines())


def _supplementary_targets(package: bytes) -> list[str]:
    """Return the aas-suppl relationship targets of every AAS data part."""
    targets: list[str] = []
    with zipfile.ZipFile(BytesIO(package)) as archive:
        for name in archive.namelist():
            if not name.startswith("aasx/_rels/data."):
                continue
            for relationship in ElementTree.fromstring(archive.read(name)).iter(_RELATIONSHIP):
                if relationship.attrib["Type"] == _AAS_SUPPL:
                    targets.append(relationship.attrib["Target"])
    return targets


def _read_file_element(package: bytes) -> tuple[model.File, aasx.DictSupplementaryFileContainer]:
    object_store: model.DictObjectStore[model.Identifiable] = model.DictObjectStore()
    file_store = aasx.DictSupplementaryFileContainer()
    with SafeAASXReader(BytesIO(package)) as reader:
        reader.read_into(object_store, file_store)
    submodel = next(obj for obj in object_store if isinstance(obj, model.Submodel))
    file_element = submodel.get_referable("TitleImage")
    assert isinstance(file_element, model.File)
    return file_element, file_store


def _stored_content(file_store: aasx.DictSupplementaryFileContainer, name: str) -> bytes:
    buffer = BytesIO()
    file_store.write_file(name, buffer)
    return buffer.getvalue()


def test_export_without_edits_keeps_mixed_case_file_conformant() -> None:
    exported = HydratorService().hydrate_submodel(_build_aasx(), {"elements": {}})

    _assert_conformant(exported)

    with zipfile.ZipFile(BytesIO(exported)) as archive:
        names = archive.namelist()
        # The files keep their original names and content ...
        assert archive.read(MIXED_CASE_PART[1:]) == PNG_BYTES
        assert archive.read(THUMBNAIL_PART[1:]) == THUMBNAIL_BYTES
    # ... and the relationships name exactly those parts.
    targets = _supplementary_targets(exported)
    assert sorted(targets) == sorted([MIXED_CASE_PART, THUMBNAIL_PART])
    assert all(target[1:] in names for target in targets)


def test_exported_file_element_resolves_to_stored_file() -> None:
    exported = HydratorService().hydrate_submodel(
        _build_aasx(), {"elements": {"Name": "edited"}}
    )

    _assert_conformant(exported)

    file_element, file_store = _read_file_element(exported)
    assert file_element.value == MIXED_CASE_PART
    assert file_element.value in file_store
    assert _stored_content(file_store, file_element.value) == PNG_BYTES
    with zipfile.ZipFile(BytesIO(exported)) as archive:
        assert archive.read(file_element.value[1:]) == PNG_BYTES


def test_export_without_shell_keeps_mixed_case_file_conformant() -> None:
    exported = HydratorService().hydrate_submodel(
        _build_aasx(with_shell=False), {"elements": {}}
    )

    _assert_conformant(exported)
    assert _supplementary_targets(exported) == [MIXED_CASE_PART]

    file_element, file_store = _read_file_element(exported)
    assert file_element.value == MIXED_CASE_PART
    assert _stored_content(file_store, file_element.value) == PNG_BYTES
