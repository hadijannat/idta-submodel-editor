"""
Generate AASX/JSON fixtures for CI conformance checks.

Requires:
- SECRET_KEY env var (min 32 chars)
- Network access to GitHub templates repo
- aas_test_engines installed on PATH
"""

from __future__ import annotations

import asyncio
import re
import subprocess
from io import BytesIO
from pathlib import Path

from basyx.aas import model
from basyx.aas.adapter import aasx as aasx_adapter, json as aas_json

from app.services.fetcher import TemplateFetcherService
from app.services.hydrator import HydratorService
from app.services.parser import ParserService

OUTPUT_DIR = Path(__file__).resolve().parent
OUTPUT_AASX = OUTPUT_DIR / "aasx"
OUTPUT_JSON = OUTPUT_DIR / "json"


# ---------------------------
# Helpers for hydration data
# ---------------------------

def parse_cardinality(cardinality: str | None) -> tuple[int, int | None]:
    if not cardinality:
        return 1, 1
    value = str(cardinality).strip()
    if not value:
        return 1, 1
    mapping = {
        "ZeroToOne": "[0..1]",
        "ZeroToMany": "[0..*]",
        "OneToMany": "[1..*]",
        "One": "[1]",
        "Zero": "[0]",
    }
    if value in mapping:
        value = mapping[value]
    if ".." in value and not value.startswith("["):
        value = f"[{value}]"
    if value.isdigit():
        value = f"[{value}]"
    match = re.match(r"^\[(\d+)(?:\.\.(\d+|\*))?\]$", value)
    if not match:
        return 1, 1
    min_items = int(match.group(1))
    max_group = match.group(2)
    if max_group is None:
        return min_items, min_items
    if max_group == "*":
        return min_items, None
    return min_items, int(max_group)


def sample_value(value_type: str | None):
    vt = (value_type or "xs:string").lower()
    if "bool" in vt:
        return True
    if "int" in vt or "integer" in vt:
        return 1
    if any(t in vt for t in ("float", "double", "decimal")):
        return 1.0
    if "datetime" in vt:
        return "2024-01-01T00:00:00"
    if "date" in vt:
        return "2024-01-01"
    if "time" in vt:
        return "00:00:00"
    if "anyuri" in vt or "uri" in vt:
        return "urn:example"
    return "Example"


def build_element(schema: dict):
    model_type = schema.get("modelType")
    min_items, _ = parse_cardinality(schema.get("cardinality"))
    required = min_items >= 1

    if model_type == "SubmodelElementCollection":
        elements = {}
        for child in schema.get("elements", []) or []:
            child_data = build_element(child)
            if child_data is not None:
                elements[child["idShort"]] = child_data
        if required or elements:
            return {"elements": elements}
        return None

    if model_type == "SubmodelElementList":
        item_template = schema.get("itemTemplate")
        items = []
        if min_items >= 1 and item_template:
            item_data = build_element(item_template)
            if item_data is None:
                item_data = {}
            items.append(item_data)
        if required or items:
            return {"items": items}
        return None

    if model_type == "Property":
        if not required:
            return None
        return {"value": sample_value(schema.get("valueType"))}

    if model_type == "MultiLanguageProperty":
        if not required:
            return None
        return {"value": {"en": "Example"}}

    if model_type == "Range":
        if not required:
            return None
        return {"min": 0, "max": 1}

    if model_type == "File":
        if not required:
            return None
        return {"value": "file://example.txt", "contentType": "text/plain"}

    if model_type == "ReferenceElement":
        if not required:
            return None
        return {"value": "https://example.com"}

    if model_type in ("RelationshipElement", "AnnotatedRelationshipElement"):
        if not required:
            return None
        return {"first": "https://example.com/first", "second": "https://example.com/second"}

    if model_type == "Entity":
        statements = {}
        for child in schema.get("statements", []) or []:
            child_data = build_element(child)
            if child_data is not None:
                statements[child["idShort"]] = child_data
        if required or statements:
            return {"statements": statements}
        return None

    if required:
        return {}
    return None


# ---------------------------
# Fixture generators
# ---------------------------


def write_json_from_aasx(aasx_bytes: bytes, output_path: Path) -> None:
    object_store: model.DictObjectStore[model.Identifiable] = model.DictObjectStore()
    file_store = aasx_adapter.DictSupplementaryFileContainer()
    with aasx_adapter.AASXReader(BytesIO(aasx_bytes)) as reader:
        reader.read_into(object_store, file_store)

    json_buffer = BytesIO()
    aas_json.write_aas_json_file(json_buffer, object_store)
    output_path.write_bytes(json_buffer.getvalue())


async def generate_digital_nameplate_filled(
    fetcher: TemplateFetcherService,
    parser: ParserService,
    hydrator: HydratorService,
) -> None:
    template_path = "published/Digital nameplate"
    aasx_bytes = await fetcher.fetch_template_aasx(template_path)
    schema = parser.parse_aasx_to_ui_schema(aasx_bytes)

    elements = {}
    for element in schema.get("elements", []):
        data = build_element(element)
        if data is not None:
            elements[element["idShort"]] = data

    form_data = {"elements": elements}

    hydrated_aasx = hydrator.hydrate_submodel(aasx_bytes, form_data)
    aasx_path = OUTPUT_AASX / "digital-nameplate-filled.aasx"
    aasx_path.write_bytes(hydrated_aasx)

    json_path = OUTPUT_JSON / "digital-nameplate-filled.json"
    json_path.write_text(
        hydrator.hydrate_to_json(aasx_bytes, form_data),
        encoding="utf-8",
    )


async def generate_ai_dataset_template(fetcher: TemplateFetcherService) -> None:
    template_path = "published/Artificial Intelligence Dataset"
    aasx_bytes = await fetcher.fetch_template_aasx(template_path)

    aasx_path = OUTPUT_AASX / "artificial-intelligence-dataset-template.aasx"
    aasx_path.write_bytes(aasx_bytes)

    json_path = OUTPUT_JSON / "artificial-intelligence-dataset-template.json"
    write_json_from_aasx(aasx_bytes, json_path)


async def generate_carbon_footprint_filled(
    fetcher: TemplateFetcherService,
    parser: ParserService,
    hydrator: HydratorService,
) -> None:
    template_path = "published/Carbon Footprint"
    aasx_bytes = await fetcher.fetch_template_aasx(template_path)
    schema = parser.parse_aasx_to_ui_schema(aasx_bytes)

    elements = {}
    for element in schema.get("elements", []):
        data = build_element(element)
        if data is not None:
            elements[element["idShort"]] = data

    form_data = {"elements": elements}

    hydrated_aasx = hydrator.hydrate_submodel(aasx_bytes, form_data)
    aasx_path = OUTPUT_AASX / "carbon-footprint-filled.aasx"
    aasx_path.write_bytes(hydrated_aasx)

    json_path = OUTPUT_JSON / "carbon-footprint-filled.json"
    json_path.write_text(
        hydrator.hydrate_to_json(aasx_bytes, form_data),
        encoding="utf-8",
    )


async def generate_minimal_example() -> None:
    aasx_path = OUTPUT_AASX / "minimal-example.aasx"
    if aasx_path.exists():
        return

    asset_info = model.AssetInformation(global_asset_id="urn:example:asset:1")
    submodel = model.Submodel(
        id_="urn:example:submodel:1",
        id_short="ExampleSubmodel",
        submodel_element=[
            model.Property(
                id_short="ManufacturerName",
                value_type=model.datatypes.String,
                value="ACME",
            )
        ],
    )

    submodel_ref = model.ModelReference.from_referable(submodel)

    aas = model.AssetAdministrationShell(
        asset_information=asset_info,
        id_="urn:example:aas:1",
        id_short="ExampleAAS",
        submodel={submodel_ref},
    )

    store = model.DictObjectStore([aas, submodel])
    file_store = aasx_adapter.DictSupplementaryFileContainer()

    with aasx_adapter.AASXWriter(aasx_path) as writer:
        writer.write_aas(
            aas_ids=[aas.id],
            object_store=store,
            file_store=file_store,
            write_json=False,
        )


def run_conformance_checks() -> None:
    for path in OUTPUT_AASX.glob("*.aasx"):
        subprocess.run(
            ["aas_test_engines", "check_file", "--format", "aasx", str(path)],
            check=True,
        )

    for path in OUTPUT_JSON.glob("*.json"):
        subprocess.run(
            ["aas_test_engines", "check_file", "--format", "json", str(path)],
            check=True,
        )


async def main() -> None:
    OUTPUT_AASX.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.mkdir(parents=True, exist_ok=True)

    fetcher = TemplateFetcherService()
    parser = ParserService()
    hydrator = HydratorService()

    await generate_minimal_example()
    await generate_digital_nameplate_filled(fetcher, parser, hydrator)
    await generate_carbon_footprint_filled(fetcher, parser, hydrator)
    await generate_ai_dataset_template(fetcher)

    run_conformance_checks()


if __name__ == "__main__":
    asyncio.run(main())
