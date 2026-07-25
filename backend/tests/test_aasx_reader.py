from pathlib import Path

from basyx.aas import model
from basyx.aas.adapter import aasx

from app.services.parser import ParserService
from app.utils.aasx_reader import SafeAASXReader


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "aasx"


class _MissingPartReader:
    def __init__(self) -> None:
        self.opened_parts: list[str] = []

    def open_part(self, part_name: str):
        self.opened_parts.append(part_name)
        raise KeyError(part_name)


def _reader_with_missing_parts() -> tuple[SafeAASXReader, _MissingPartReader]:
    reader = SafeAASXReader.__new__(SafeAASXReader)
    missing_part_reader = _MissingPartReader()
    reader.reader = missing_part_reader
    return reader, missing_part_reader


def test_reads_legacy_aas_30_fixture_with_basyx_21():
    schema = ParserService().parse_aasx_to_ui_schema(
        (FIXTURES_DIR / "minimal-example.aasx").read_bytes()
    )

    assert schema["submodelId"]
    assert schema["idShort"]


def test_namespace_mapping_does_not_rewrite_element_values():
    legacy_namespace = b"https://admin-shell.io/aas/3/0"
    raw = (
        b'<environment xmlns="' + legacy_namespace + b'">'
        b"<value>" + legacy_namespace + b"</value>"
        b"</environment>"
    )

    mapped = SafeAASXReader._map_xml_namespace_to_sdk(raw)

    assert mapped is not None
    assert b'xmlns="https://admin-shell.io/aas/3/1"' in mapped
    assert b"<value>" + legacy_namespace + b"</value>" in mapped


def test_missing_default_thumbnail_is_tolerated():
    reader, missing_part_reader = _reader_with_missing_parts()
    shell = model.AssetAdministrationShell(
        id_="urn:test:aas",
        asset_information=model.AssetInformation(
            global_asset_id="urn:test:asset",
            default_thumbnail=model.Resource("missing-thumbnail.png"),
        ),
    )

    reader._collect_supplementary_files(
        "/aasx/data.xml",
        shell,
        aasx.DictSupplementaryFileContainer(),
    )

    assert missing_part_reader.opened_parts == ["/aasx/missing-thumbnail.png"]
    assert shell.asset_information.default_thumbnail.path == "missing-thumbnail.png"


def test_missing_nested_entity_and_operation_files_are_tolerated():
    reader, missing_part_reader = _reader_with_missing_parts()
    entity_file = model.File(
        id_short="EntityDocument",
        content_type="application/pdf",
        value="entity.pdf",
    )
    operation_file = model.File(
        id_short="OperationDocument",
        content_type="application/pdf",
        value="operation.pdf",
    )
    submodel = model.Submodel(
        id_="urn:test:submodel",
        submodel_element=[
            model.Entity(
                id_short="Entity",
                entity_type=model.EntityType.CO_MANAGED_ENTITY,
                statement=[entity_file],
            ),
            model.Operation(
                id_short="Operation",
                input_variable=[operation_file],
            ),
        ],
    )

    reader._collect_supplementary_files(
        "/aasx/data.xml",
        submodel,
        aasx.DictSupplementaryFileContainer(),
    )

    assert missing_part_reader.opened_parts == [
        "/aasx/entity.pdf",
        "/aasx/operation.pdf",
    ]
    assert entity_file.value == "entity.pdf"
    assert operation_file.value == "operation.pdf"
