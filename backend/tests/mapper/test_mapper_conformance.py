"""
Mapper conformance tests.

Tests the complete mapper flow (profile → map → export) and validates
the output AASX against expected structure.
"""

from __future__ import annotations

import io
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from fastapi import UploadFile

from app.config import get_settings
from app.schemas.mapper import (
    MappingItem,
    MapperMode,
    MapperRecipe,
    MapperRunRequest,
    MapperSourceColumn,
    MapperSourceProfileRef,
    MapperTargetField,
    MapperTemplateRef,
)
from app.services.fetcher import TemplateFetcherService
from app.services.hydrator import HydratorService
from app.services.mapper import MapperService
from app.services.parser import ParserService

if TYPE_CHECKING:
    pass


FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "mapper"


def _has_aas_test_engines() -> bool:
    """Check if aas_test_engines is available on PATH."""
    return shutil.which("aas_test_engines") is not None


@pytest.fixture
def mapper_service(monkeypatch) -> MapperService:
    """Create a MapperService for testing."""
    monkeypatch.setenv("SECRET_KEY", "0123456789abcdef0123456789abcdef")
    get_settings.cache_clear()

    return MapperService(
        fetcher=TemplateFetcherService(),
        parser=ParserService(),
        hydrator=HydratorService(),
    )


@pytest.fixture
def nameplate_csv() -> bytes:
    """CSV data that can be mapped to Digital Nameplate template."""
    return b"""ManufacturerName,ManufacturerProductDesignation,YearOfConstruction,SerialNumber
ACME Corp,Industrial Pump Model X,2024,SN-12345
"""


@pytest.mark.asyncio
async def test_mapper_single_row_produces_valid_form_data(mapper_service, nameplate_csv):
    """Test that mapper produces valid form data structure."""
    # Profile the CSV
    file = UploadFile(filename="nameplate.csv", file=io.BytesIO(nameplate_csv))
    profile = await mapper_service.profile(file, sheet=None, header_row=1, sample_rows=10)

    assert len(profile.columns) == 4
    assert profile.columns[0].name_original == "ManufacturerName"

    # Create a simple mapping
    # Note: id_short_path should be just the element name (no .value suffix)
    # The field/language is specified separately in the target
    recipe = MapperRecipe(
        name="test-recipe",
        schema_version="1.0.0",
        template=MapperTemplateRef(name="Digital nameplate", status="published"),
        source_profile=MapperSourceProfileRef(format="csv", header_row=1),
        mode=MapperMode(type="single"),
        mappings=[
            MappingItem(
                source=MapperSourceColumn(column_name="ManufacturerName", column_index=0),
                target=MapperTargetField(
                    id_short_path="ManufacturerName",
                    element_type="MultiLanguageProperty",
                    language="en",
                ),
                required=True,
            ),
            MappingItem(
                source=MapperSourceColumn(
                    column_name="ManufacturerProductDesignation", column_index=1
                ),
                target=MapperTargetField(
                    id_short_path="ManufacturerProductDesignation",
                    element_type="MultiLanguageProperty",
                    language="en",
                ),
                required=True,
            ),
            MappingItem(
                source=MapperSourceColumn(column_name="YearOfConstruction", column_index=2),
                target=MapperTargetField(
                    id_short_path="YearOfConstruction",
                    element_type="Property",
                    value_type="xs:integer",
                ),
                required=True,
            ),
            MappingItem(
                source=MapperSourceColumn(column_name="SerialNumber", column_index=3),
                target=MapperTargetField(
                    id_short_path="SerialNumber",
                    element_type="Property",
                    value_type="xs:string",
                ),
                required=True,
            ),
        ],
    )

    # Run the mapper
    request = MapperRunRequest(
        template_name="Digital nameplate",
        status="published",
        profile_id=profile.profile_id,
        recipe=recipe,
        output_format="form",
        row_index=1,
    )

    result = await mapper_service.run(request)

    # Verify the output structure
    assert result.form_data is not None
    elements = result.form_data.get("elements", {})

    # Check that mapped values are present
    assert "ManufacturerName" in elements
    assert elements["ManufacturerName"]["value"]["en"] == "ACME Corp"

    assert "ManufacturerProductDesignation" in elements
    assert elements["ManufacturerProductDesignation"]["value"]["en"] == "Industrial Pump Model X"

    assert "YearOfConstruction" in elements
    assert elements["YearOfConstruction"]["value"] == 2024  # Converted to int

    assert "SerialNumber" in elements
    assert elements["SerialNumber"]["value"] == "SN-12345"


@pytest.mark.asyncio
async def test_mapper_produces_hydratable_form_data(mapper_service, nameplate_csv):
    """Test that mapper produces form data that can be used with the hydrator.

    This test verifies the mapper output structure is compatible with
    the hydrator's expectations, without requiring full template validation.
    """
    # Profile the CSV
    file = UploadFile(filename="nameplate.csv", file=io.BytesIO(nameplate_csv))
    profile = await mapper_service.profile(file, sheet=None, header_row=1, sample_rows=10)

    # Create mapping with multiple field types
    recipe = MapperRecipe(
        name="test-recipe",
        schema_version="1.0.0",
        template=MapperTemplateRef(name="Digital nameplate", status="published"),
        source_profile=MapperSourceProfileRef(format="csv", header_row=1),
        mode=MapperMode(type="single"),
        mappings=[
            MappingItem(
                source=MapperSourceColumn(column_name="ManufacturerName", column_index=0),
                target=MapperTargetField(
                    id_short_path="ManufacturerName",
                    element_type="MultiLanguageProperty",
                    language="en",
                ),
                required=True,
            ),
            MappingItem(
                source=MapperSourceColumn(column_name="SerialNumber", column_index=3),
                target=MapperTargetField(
                    id_short_path="SerialNumber",
                    element_type="Property",
                    value_type="xs:string",
                ),
                required=True,
            ),
        ],
    )

    # Run the mapper to get form data
    request = MapperRunRequest(
        template_name="Digital nameplate",
        status="published",
        profile_id=profile.profile_id,
        recipe=recipe,
        output_format="form",
        row_index=1,
    )

    result = await mapper_service.run(request)

    # Verify form data structure is correct for hydrator
    assert result.form_data is not None
    assert "elements" in result.form_data
    elements = result.form_data["elements"]

    # MultiLanguageProperty structure
    assert "ManufacturerName" in elements
    assert "value" in elements["ManufacturerName"]
    assert isinstance(elements["ManufacturerName"]["value"], dict)
    assert "en" in elements["ManufacturerName"]["value"]

    # Property structure
    assert "SerialNumber" in elements
    assert "value" in elements["SerialNumber"]

    # The form_data should be JSON-serializable
    import json
    json_str = json.dumps(result.form_data)
    assert len(json_str) > 0


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires complete CSV data mapping all required fields for Digital Nameplate")
async def test_mapper_export_passes_conformance(mapper_service, tmp_path):
    """Test that mapper-exported AASX passes aas_test_engines conformance check.

    NOTE: This test is skipped by default because it requires:
    1. aas_test_engines installed on PATH
    2. A complete CSV with all required Digital Nameplate fields mapped

    To run this test:
    1. Create a comprehensive CSV with all required fields
    2. Remove the skip marker
    3. Run with: PYTHONPATH=backend pytest backend/tests/mapper/test_mapper_conformance.py::test_mapper_export_passes_conformance -v
    """
    if not _has_aas_test_engines():
        pytest.skip("aas_test_engines not installed")

    # This test would need a complete CSV dataset with all required fields:
    # - URIOfTheProduct
    # - ManufacturerName
    # - ManufacturerProductDesignation
    # - AddressInformation (nested SMC with sub-fields)
    # - OrderCodeOfManufacturer
    # Plus their corresponding mappings

    # For now, this is a placeholder showing the test structure
    complete_csv = b"""URIOfTheProduct,ManufacturerName,ManufacturerProductDesignation,OrderCodeOfManufacturer,Street,City,ZipCode,Country
https://example.com/pump-123,ACME Corp,Industrial Pump Model X,ORD-2024-001,123 Main St,Berlin,10115,DE
"""
    file = UploadFile(filename="complete.csv", file=io.BytesIO(complete_csv))
    profile = await mapper_service.profile(file, sheet=None, header_row=1, sample_rows=10)

    # Create mapping for all required fields
    recipe = MapperRecipe(
        name="conformance-test",
        schema_version="1.0.0",
        template=MapperTemplateRef(name="Digital nameplate", status="published"),
        source_profile=MapperSourceProfileRef(format="csv", header_row=1),
        mode=MapperMode(type="single"),
        mappings=[
            MappingItem(
                source=MapperSourceColumn(column_name="URIOfTheProduct", column_index=0),
                target=MapperTargetField(
                    id_short_path="URIOfTheProduct",
                    element_type="Property",
                    value_type="xs:anyURI",
                ),
                required=True,
            ),
            MappingItem(
                source=MapperSourceColumn(column_name="ManufacturerName", column_index=1),
                target=MapperTargetField(
                    id_short_path="ManufacturerName",
                    element_type="MultiLanguageProperty",
                    language="en",
                ),
                required=True,
            ),
            MappingItem(
                source=MapperSourceColumn(
                    column_name="ManufacturerProductDesignation", column_index=2
                ),
                target=MapperTargetField(
                    id_short_path="ManufacturerProductDesignation",
                    element_type="MultiLanguageProperty",
                    language="en",
                ),
                required=True,
            ),
            MappingItem(
                source=MapperSourceColumn(column_name="OrderCodeOfManufacturer", column_index=3),
                target=MapperTargetField(
                    id_short_path="OrderCodeOfManufacturer",
                    element_type="Property",
                    value_type="xs:string",
                ),
                required=True,
            ),
            # AddressInformation is a nested SMC - would need nested path mapping
        ],
    )

    # Export to AASX
    request = MapperRunRequest(
        template_name="Digital nameplate",
        status="published",
        profile_id=profile.profile_id,
        recipe=recipe,
        output_format="aasx",
        row_index=1,
    )

    content, _, _ = await mapper_service.export(request)

    # Write to temp file for conformance check
    aasx_path = tmp_path / "mapper-output.aasx"
    aasx_path.write_bytes(content)

    # Run aas_test_engines conformance check
    result = subprocess.run(
        ["aas_test_engines", "check_file", "--format", "aasx", str(aasx_path)],
        capture_output=True,
        text=True,
    )

    # aas_test_engines may emit warnings but should not fail
    # Exit code 0 means conformant
    assert result.returncode == 0, f"Conformance check failed:\n{result.stdout}\n{result.stderr}"


@pytest.mark.asyncio
async def test_mapper_batch_mode_produces_form_data_batch(mapper_service):
    """Test that row-per-submodel mode produces form_data_batch with one item per row."""
    # Create CSV with multiple rows
    csv_data = b"""ManufacturerName,SerialNumber
Company A,SN-001
Company B,SN-002
Company C,SN-003
"""
    file = UploadFile(filename="batch.csv", file=io.BytesIO(csv_data))
    profile = await mapper_service.profile(file, sheet=None, header_row=1, sample_rows=10)

    # Create mapping
    recipe = MapperRecipe(
        name="batch-test",
        schema_version="1.0.0",
        template=MapperTemplateRef(name="Digital nameplate", status="published"),
        source_profile=MapperSourceProfileRef(format="csv", header_row=1),
        mode=MapperMode(type="row-per-submodel"),
        mappings=[
            MappingItem(
                source=MapperSourceColumn(column_name="ManufacturerName", column_index=0),
                target=MapperTargetField(
                    id_short_path="ManufacturerName",
                    element_type="MultiLanguageProperty",
                    language="en",
                ),
                required=True,
            ),
            MappingItem(
                source=MapperSourceColumn(column_name="SerialNumber", column_index=1),
                target=MapperTargetField(
                    id_short_path="SerialNumber",
                    element_type="Property",
                    value_type="xs:string",
                ),
                required=True,
            ),
        ],
    )

    # Run mapper in batch mode to get form_data_batch
    request = MapperRunRequest(
        template_name="Digital nameplate",
        status="published",
        profile_id=profile.profile_id,
        recipe=recipe,
        output_format="form",  # Request form data, not export
    )

    result = await mapper_service.run(request)

    # Should have 3 form_data items (one per CSV row)
    assert result.form_data_batch is not None
    assert len(result.form_data_batch) == 3
    assert result.row_count == 3

    # Verify each form_data has correct structure
    expected_names = ["Company A", "Company B", "Company C"]
    expected_serials = ["SN-001", "SN-002", "SN-003"]

    for i, form_data in enumerate(result.form_data_batch):
        assert "elements" in form_data
        elements = form_data["elements"]

        # Check ManufacturerName (MLP)
        assert "ManufacturerName" in elements
        assert elements["ManufacturerName"]["value"]["en"] == expected_names[i]

        # Check SerialNumber (Property)
        assert "SerialNumber" in elements
        assert elements["SerialNumber"]["value"] == expected_serials[i]
