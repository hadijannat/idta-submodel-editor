from app.schemas.mapper import MappingItem, MapperSourceColumn, MapperTargetField
from app.services.mapper.apply import apply_mapping, apply_mapping_into


def test_apply_mapping_property():
    mapping = MappingItem(
        source=MapperSourceColumn(column_name="Weight", column_index=1),
        target=MapperTargetField(
            id_short_path="PhysicalDimensions.NetWeight",
            element_type="Property",
            value_type="xs:double",
        ),
    )

    row = ["Pump", "12.5"]
    header_map = {"Weight": 1}
    form_data, diagnostics = apply_mapping(row, [mapping], header_map, 1)

    assert not diagnostics
    assert form_data["elements"]["PhysicalDimensions"]["elements"]["NetWeight"][
        "value"
    ] == 12.5


def test_apply_mapping_list_items_grouped():
    mappings = [
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
    ]

    header_map = {"ProductId": 0, "Part": 1, "Quantity": 2}
    rows = [
        ["P-1", "Bolt", "4"],
        ["P-1", "Nut", "8"],
        ["P-2", "Washer", "16"],
    ]
    form_data = {"elements": {}}
    diagnostics = []
    for idx, row in enumerate(rows, start=1):
        diagnostics.extend(
            apply_mapping_into(
                form_data,
                row,
                mappings,
                header_map,
                idx,
                list_context={},
                preserve_existing=True,
            )
        )

    form_data.pop("_mapper_values", None)
    items = form_data["elements"]["BillOfMaterials"]["items"]

    assert len(items) == 3
    assert form_data["elements"]["ProductId"]["value"] == "P-1"
    assert items[0]["elements"]["Part"]["value"] == "Bolt"
    assert items[0]["elements"]["Quantity"]["value"] == 4
    assert items[1]["elements"]["Part"]["value"] == "Nut"
    assert items[1]["elements"]["Quantity"]["value"] == 8
    assert items[2]["elements"]["Part"]["value"] == "Washer"
    assert items[2]["elements"]["Quantity"]["value"] == 16
    assert any(d.code == "group_conflict" for d in diagnostics)
