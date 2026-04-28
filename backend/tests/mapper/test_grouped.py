import io
from pathlib import Path

import pytest
from fastapi import UploadFile

from app.config import get_settings
from app.schemas.mapper import (
    MapperMode,
    MapperRecipe,
    MapperRunRequest,
    MapperSourceColumn,
    MapperSourceProfileRef,
    MapperTargetField,
    MapperTemplateRef,
    MappingItem,
)
from app.services.fetcher import TemplateFetcherService
from app.services.hydrator import HydratorService
from app.services.mapper import MapperService
from app.services.parser import ParserService


@pytest.mark.asyncio
async def test_grouped_mode_builds_list_items(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "0123456789abcdef0123456789abcdef")
    get_settings.cache_clear()

    csv_path = Path(__file__).resolve().parents[1] / "fixtures/mapper/grouped.csv"
    data = csv_path.read_bytes()
    file = UploadFile(filename="grouped.csv", file=io.BytesIO(data))

    mapper = MapperService(
        fetcher=TemplateFetcherService(),
        parser=ParserService(),
        hydrator=HydratorService(),
    )

    profile = await mapper.profile(file, sheet=None, header_row=1, sample_rows=10)

    recipe = MapperRecipe(
        name="Grouped BOM",
        template=MapperTemplateRef(name="Demo", status="published"),
        source_profile=MapperSourceProfileRef(
            format="csv",
            header_row=profile.header_row,
            sheet=None,
            header_fingerprint=None,
        ),
        mode=MapperMode(type="grouped", group_by=["ProductId"]),
        mappings=[
            MappingItem(
                source=MapperSourceColumn(column_name="ProductId", column_index=0),
                target=MapperTargetField(
                    id_short_path="ProductId",
                    element_type="Property",
                    value_type="xs:string",
                ),
            ),
            MappingItem(
                source=MapperSourceColumn(column_name="Part", column_index=1),
                target=MapperTargetField(
                    id_short_path="BillOfMaterials[].Part",
                    element_type="Property",
                    value_type="xs:string",
                ),
            ),
            MappingItem(
                source=MapperSourceColumn(column_name="Quantity", column_index=2),
                target=MapperTargetField(
                    id_short_path="BillOfMaterials[].Quantity",
                    element_type="Property",
                    value_type="xs:int",
                ),
            ),
        ],
    )

    request = MapperRunRequest(
        template_name="Demo",
        status="published",
        version=None,
        profile_id=profile.profile_id,
        recipe=recipe,
        output_format="form",
    )

    response = await mapper.run(request)

    assert response.form_data_batch is not None
    assert len(response.form_data_batch) == 2

    first = response.form_data_batch[0]
    items = first["elements"]["BillOfMaterials"]["items"]

    assert first["elements"]["ProductId"]["value"] == "P-100"
    assert len(items) == 2
    assert items[0]["elements"]["Part"]["value"] == "Bolt"
    assert items[0]["elements"]["Quantity"]["value"] == 4
    assert items[1]["elements"]["Part"]["value"] == "Nut"
    assert items[1]["elements"]["Quantity"]["value"] == 8
