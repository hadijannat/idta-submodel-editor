"""
Export a sample package with the current code for the CI conformance check.

The fixtures under ``backend/tests/fixtures`` were exported once and are
checked as committed, so a defect in the export code stays invisible until
they are regenerated. This script exports a small template on every run, as
AASX and as JSON, for ``aas_test_engines`` to check.

The template is built in memory, so the check needs no network. It contains
what has broken exports before:

- supplementary files with upper-case letters in their names (a ``File``
  element and a thumbnail), which the SDK references by a lower-cased name
- an entity without specific asset IDs, which the SDK serializes with an
  empty array

Usage::

    PYTHONPATH=backend python backend/scripts/export_conformance_sample.py <output directory>
"""

from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

from basyx.aas import model
from basyx.aas.adapter import aasx

from app.services.hydrator import HydratorService

AASX_NAME = "fresh-export.aasx"
JSON_NAME = "fresh-export.json"

_TITLE_IMAGE = "/aasx/files/Sample_Template-Title.png"
_THUMBNAIL = "/aasx/files/Thumbnail.PNG"
_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"sample"


def build_template() -> bytes:
    """Build the template package the sample is exported from."""
    file_store = aasx.DictSupplementaryFileContainer()
    file_store.add_file(_TITLE_IMAGE, BytesIO(_PNG_BYTES), "image/png")
    file_store.add_file(_THUMBNAIL, BytesIO(_PNG_BYTES), "image/png")

    submodel = model.Submodel(
        id_="https://example.org/SubmodelTemplate/ConformanceSample/1/0",
        id_short="ConformanceSample",
        kind=model.ModellingKind.TEMPLATE,
        submodel_element=[
            model.Property(id_short="Name", value_type=model.datatypes.String),
            model.File(id_short="TitleImage", content_type="image/png", value=_TITLE_IMAGE),
            model.Entity(
                id_short="Component",
                entity_type=model.EntityType.CO_MANAGED_ENTITY,
                statement=[
                    model.Property(
                        id_short="Label", value_type=model.datatypes.String, value="part"
                    )
                ],
            ),
        ],
    )
    shell = model.AssetAdministrationShell(
        id_="https://example.org/AAS/ConformanceSample",
        id_short="ConformanceSampleAAS",
        asset_information=model.AssetInformation(
            asset_kind=model.AssetKind.TYPE,
            global_asset_id="https://example.org/Asset/ConformanceSample",
            default_thumbnail=model.Resource(path=_THUMBNAIL, content_type="image/png"),
        ),
        submodel={model.ModelReference.from_referable(submodel)},
    )

    output = BytesIO()
    with aasx.AASXWriter(output) as writer:
        writer.write_all_aas_objects(
            "/aasx/data.xml",
            model.DictObjectStore([shell, submodel]),
            file_store,
            write_json=False,
        )
    return output.getvalue()


def export_sample(output_dir: Path) -> tuple[Path, Path]:
    """Export the sample template and return the paths of the AASX and JSON files."""
    template = build_template()
    form_data = {"elements": {"Name": {"value": "Sample"}}}
    hydrator = HydratorService()

    output_dir.mkdir(parents=True, exist_ok=True)
    aasx_path = output_dir / AASX_NAME
    aasx_path.write_bytes(hydrator.hydrate_submodel(template, form_data))
    json_path = output_dir / JSON_NAME
    json_path.write_text(hydrator.hydrate_to_json(template, form_data), encoding="utf-8")
    return aasx_path, json_path


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {Path(argv[0]).name} <output directory>", file=sys.stderr)
        return 2
    for path in export_sample(Path(argv[1])):
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
