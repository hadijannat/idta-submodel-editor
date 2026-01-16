from app.schemas.mapper import MappingItem, MapperSourceColumn, MapperTargetField
from app.services.mapper.apply import apply_mapping


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
