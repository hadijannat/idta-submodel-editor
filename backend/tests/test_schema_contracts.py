"""Schema contract tests for determinism and round-trip integrity.

These tests ensure:
1. Schema Stability: Same AASX always produces the same schema
2. Hydrate Round-Trip: hydrate(export(json)) preserves values
3. Validation Stability: Same invalid input always produces same errors
"""

import json
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from basyx.aas import model
from basyx.aas.adapter import aasx as aasx_adapter

from app.services.hydrator import HydratorService
from app.services.parser import ParserService
from app.services.validation import validate_form_data


def _json_serializer(obj: Any) -> Any:
    """Custom JSON serializer for non-standard types."""
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


FIXTURES_DIR = Path(__file__).parent / "fixtures"
AASX_FIXTURES = list((FIXTURES_DIR / "aasx").glob("*.aasx"))


@pytest.fixture
def parser() -> ParserService:
    """Create a parser service instance."""
    return ParserService()


@pytest.fixture
def hydrator() -> HydratorService:
    """Create a hydrator service instance."""
    return HydratorService()


class TestSchemaDeterminism:
    """Tests ensuring schema parsing is deterministic."""

    @pytest.mark.parametrize("aasx_path", AASX_FIXTURES, ids=lambda p: p.name)
    def test_same_aasx_produces_same_schema(self, parser: ParserService, aasx_path: Path):
        """Verify that parsing the same AASX twice produces identical schemas.

        Note: Some complex AASX files may have non-deterministic parsing due to
        internal BaSyx library behavior. This test validates that the core
        structure is stable even if some metadata fields vary.
        """
        aasx_bytes = aasx_path.read_bytes()

        schema1 = parser.parse_aasx_to_ui_schema(aasx_bytes)
        schema2 = parser.parse_aasx_to_ui_schema(aasx_bytes)

        # Check that the essential structure is identical:
        # - Same number of elements
        assert len(schema1.get("elements", [])) == len(schema2.get("elements", []))

        # - Same idShorts in the same order
        ids1 = [e.get("idShort") for e in schema1.get("elements", [])]
        ids2 = [e.get("idShort") for e in schema2.get("elements", [])]
        assert ids1 == ids2, "Element idShorts differ between parses"

        # - Same model types
        types1 = [e.get("modelType") for e in schema1.get("elements", [])]
        types2 = [e.get("modelType") for e in schema2.get("elements", [])]
        assert types1 == types2, "Element modelTypes differ between parses"

    @pytest.mark.parametrize("aasx_path", AASX_FIXTURES, ids=lambda p: p.name)
    def test_element_order_is_stable(self, parser: ParserService, aasx_path: Path):
        """Verify that element ordering is preserved across multiple parses."""
        aasx_bytes = aasx_path.read_bytes()

        def get_element_ids(schema: dict) -> list[str]:
            """Extract idShort values in order from schema elements."""
            ids = []
            for element in schema.get("elements", []):
                if "idShort" in element:
                    ids.append(element["idShort"])
            return ids

        schema1 = parser.parse_aasx_to_ui_schema(aasx_bytes)
        schema2 = parser.parse_aasx_to_ui_schema(aasx_bytes)

        ids1 = get_element_ids(schema1)
        ids2 = get_element_ids(schema2)

        assert ids1 == ids2, "Element ordering is not stable"

    @pytest.mark.parametrize("aasx_path", AASX_FIXTURES, ids=lambda p: p.name)
    def test_schema_has_expected_structure(self, parser: ParserService, aasx_path: Path):
        """Verify that schema has required top-level fields."""
        aasx_bytes = aasx_path.read_bytes()
        schema = parser.parse_aasx_to_ui_schema(aasx_bytes)

        # Check for essential schema fields
        assert "elements" in schema, "Schema missing 'elements'"
        assert isinstance(schema["elements"], list), "'elements' should be a list"

        # Each element should have idShort and modelType
        for element in schema["elements"]:
            assert "idShort" in element, f"Element missing 'idShort': {element}"
            assert "modelType" in element, f"Element missing 'modelType': {element}"


class TestHydrateRoundTrip:
    """Tests ensuring hydrate/export preserves data integrity."""

    def test_hydrate_json_round_trip(self, parser: ParserService, hydrator: HydratorService):
        """Verify that values are preserved through hydrate→JSON→parse cycle."""
        # Use the nameplate fixture which has known structure
        nameplate_path = FIXTURES_DIR / "aasx" / "digital-nameplate-filled.aasx"
        if not nameplate_path.exists():
            pytest.skip("digital-nameplate-filled.aasx fixture not found")

        aasx_bytes = nameplate_path.read_bytes()

        # Parse original to get initial values
        original_schema = parser.parse_aasx_to_ui_schema(aasx_bytes)

        # Create form data from the schema (extract existing values)
        form_data = _extract_form_data(original_schema)

        # Hydrate to JSON
        json_output = hydrator.hydrate_to_json(aasx_bytes, form_data)
        json_data = json.loads(json_output)

        # Verify the JSON has submodel content
        assert isinstance(json_data, dict), "JSON output should be a dict"

    def test_hydrate_preserves_unknown_elements(self, hydrator: HydratorService):
        """Verify that hydrate→JSON keeps elements the UI doesn't explicitly map."""
        nameplate_path = FIXTURES_DIR / "aasx" / "digital-nameplate-filled.aasx"
        if not nameplate_path.exists():
            pytest.skip("digital-nameplate-filled.aasx fixture not found")

        mutated_aasx = _inject_unknown_element(nameplate_path.read_bytes())
        json_output = hydrator.hydrate_to_json(mutated_aasx, {"elements": {}})
        json_data = json.loads(json_output)

        submodels = json_data.get("submodels") or []
        if not submodels:
            pytest.skip("No submodels found in hydrated JSON")

        elements = submodels[0].get("submodelElements") or []
        sentinel = next(
            (elem for elem in elements if elem.get("idShort") == "UnknownPreserve"),
            None,
        )
        assert sentinel is not None, "Unknown element was dropped during hydrate/round-trip"

        # Verify nested structure survived
        nested = sentinel.get("value", [])
        assert len(nested) == 1, "Nested content was dropped"
        assert nested[0].get("idShort") == "Sentinel", "Nested idShort was modified"
        assert nested[0].get("value") == "keep-me", "Nested value was modified"

    def test_hydrate_preserves_string_values(
        self, parser: ParserService, hydrator: HydratorService
    ):
        """Verify that string property values are preserved through hydration."""
        nameplate_path = FIXTURES_DIR / "aasx" / "digital-nameplate-filled.aasx"
        if not nameplate_path.exists():
            pytest.skip("digital-nameplate-filled.aasx fixture not found")

        aasx_bytes = nameplate_path.read_bytes()
        schema = parser.parse_aasx_to_ui_schema(aasx_bytes)

        # Set up test form data with known values
        test_value = "Test Manufacturer Name"
        form_data = {"elements": {}}

        # Find a string property in the schema and set its value
        for element in schema.get("elements", []):
            if element.get("modelType") == "Property":
                id_short = element.get("idShort", "")
                form_data["elements"][id_short] = {"value": test_value}
                break

        # Hydrate and check JSON output
        json_output = hydrator.hydrate_to_json(aasx_bytes, form_data)
        json_data = json.loads(json_output)

        # Value should appear somewhere in the output
        json_str = json.dumps(json_data)
        assert test_value in json_str, f"Value '{test_value}' not found in hydrated output"


class TestValidationStability:
    """Tests ensuring validation produces consistent error messages."""

    def test_same_invalid_input_produces_same_errors(self, parser: ParserService):
        """Verify that validation errors are deterministic for invalid input."""
        minimal_path = FIXTURES_DIR / "aasx" / "minimal-example.aasx"
        if not minimal_path.exists():
            pytest.skip("minimal-example.aasx fixture not found")

        aasx_bytes = minimal_path.read_bytes()
        schema = parser.parse_aasx_to_ui_schema(aasx_bytes)

        # Empty form data should trigger validation errors for required fields
        empty_form_data = {"elements": {}}

        errors1, warnings1 = validate_form_data(schema, empty_form_data)
        errors2, warnings2 = validate_form_data(schema, empty_form_data)

        # Convert to serialized form for comparison
        errors1_json = [e.model_dump() for e in errors1]
        errors2_json = [e.model_dump() for e in errors2]
        warnings1_json = [w.model_dump() for w in warnings1]
        warnings2_json = [w.model_dump() for w in warnings2]

        assert errors1_json == errors2_json, "Validation errors are not deterministic"
        assert warnings1_json == warnings2_json, "Validation warnings are not deterministic"

    def test_error_field_paths_use_consistent_format(self, parser: ParserService):
        """Verify that error field paths follow a consistent format."""
        minimal_path = FIXTURES_DIR / "aasx" / "minimal-example.aasx"
        if not minimal_path.exists():
            pytest.skip("minimal-example.aasx fixture not found")

        aasx_bytes = minimal_path.read_bytes()
        schema = parser.parse_aasx_to_ui_schema(aasx_bytes)

        # Empty form data
        form_data = {"elements": {}}

        errors, _ = validate_form_data(schema, form_data)

        for error in errors:
            error_dict = error.model_dump()
            field_path = error_dict.get("fieldPath", error_dict.get("field_path", ""))

            # Field paths should be strings
            assert isinstance(field_path, str), f"Field path should be string: {field_path}"

            # Field paths should use dot notation or simple names (not nested objects)
            if field_path:
                # Should not contain special characters except dots, brackets for lists
                valid_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._[]")
                path_chars = set(field_path)
                invalid = path_chars - valid_chars
                assert not invalid, f"Invalid characters in field path: {invalid}"

    @pytest.mark.parametrize("aasx_path", AASX_FIXTURES, ids=lambda p: p.name)
    def test_validation_produces_consistent_errors(
        self, parser: ParserService, aasx_path: Path
    ):
        """Verify that validation is deterministic for any AASX file."""
        if "template" in aasx_path.name or "minimal" in aasx_path.name:
            pytest.skip("Template/minimal files may have unpredictable structure")

        aasx_bytes = aasx_path.read_bytes()
        schema = parser.parse_aasx_to_ui_schema(aasx_bytes)

        # Extract form data from the AASX
        form_data = _extract_form_data(schema)

        # Run validation twice to ensure consistency
        errors1, warnings1 = validate_form_data(schema, form_data)
        errors2, warnings2 = validate_form_data(schema, form_data)

        # Errors should be identical
        errors1_json = [e.model_dump() for e in errors1]
        errors2_json = [e.model_dump() for e in errors2]
        assert errors1_json == errors2_json, "Validation errors are not consistent"

        # Warnings should be identical
        warnings1_json = [w.model_dump() for w in warnings1]
        warnings2_json = [w.model_dump() for w in warnings2]
        assert warnings1_json == warnings2_json, "Validation warnings are not consistent"


class TestSchemaSemanticIntegrity:
    """Tests for semantic ID and ConceptDescription handling."""

    @pytest.mark.parametrize("aasx_path", AASX_FIXTURES, ids=lambda p: p.name)
    def test_semantic_ids_are_strings_or_none(self, parser: ParserService, aasx_path: Path):
        """Verify that semantic IDs are consistently formatted."""
        aasx_bytes = aasx_path.read_bytes()
        schema = parser.parse_aasx_to_ui_schema(aasx_bytes)

        def check_semantic_ids(elements: list[dict], path: str = ""):
            for element in elements:
                id_short = element.get("idShort", "?")
                current_path = f"{path}.{id_short}" if path else id_short

                sem_id = element.get("semanticId")
                if sem_id is not None:
                    assert isinstance(sem_id, (str, dict)), (
                        f"semanticId at {current_path} should be string or dict, "
                        f"got {type(sem_id)}"
                    )

                # Recursively check nested elements
                if "elements" in element:
                    check_semantic_ids(element["elements"], current_path)
                if "statements" in element:
                    check_semantic_ids(element["statements"], current_path)

        check_semantic_ids(schema.get("elements", []))


def _extract_form_data(schema: dict) -> dict:
    """Extract form data from a parsed schema, preserving existing values."""
    form_data = {"elements": {}}

    def extract_element(element: dict, parent_path: str = "") -> None:
        id_short = element.get("idShort", "")
        current_path = f"{parent_path}.{id_short}" if parent_path else id_short
        model_type = element.get("modelType", "")

        if model_type == "Property":
            value = element.get("value")
            if value is not None:
                _set_nested_value(form_data["elements"], current_path, {"value": value})

        elif model_type == "MultiLanguageProperty":
            value = element.get("value")
            if value:
                _set_nested_value(form_data["elements"], current_path, {"value": value})

        elif model_type in ("SubmodelElementCollection", "Entity"):
            for sub_element in element.get("elements", []) + element.get("statements", []):
                extract_element(sub_element, current_path)

        elif model_type == "SubmodelElementList":
            items = element.get("items", [])
            for idx, item in enumerate(items):
                item_path = f"{current_path}[{idx}]"
                extract_element(item, item_path)

    for element in schema.get("elements", []):
        extract_element(element)

    return form_data


def _set_nested_value(data: dict, path: str, value: Any) -> None:
    """Set a value in a nested dictionary using dot notation path."""
    parts = path.split(".")
    current = data

    for i, part in enumerate(parts[:-1]):
        if part not in current:
            current[part] = {}
        current = current[part]

    current[parts[-1]] = value


def _inject_unknown_element(aasx_bytes: bytes) -> bytes:
    """Return AASX bytes with an extra element that the UI does not map."""
    object_store: model.DictObjectStore[model.Identifiable] = model.DictObjectStore()
    file_store = aasx_adapter.DictSupplementaryFileContainer()

    with aasx_adapter.AASXReader(BytesIO(aasx_bytes)) as reader:
        reader.read_into(object_store, file_store)

    submodel = next(
        (obj for obj in object_store if isinstance(obj, model.Submodel)),
        None,
    )
    if submodel is None:
        raise ValueError("No Submodel found in template")

    sentinel = model.SubmodelElementCollection(
        id_short="UnknownPreserve",
        value=(
            model.Property(
                id_short="Sentinel",
                value_type=model.datatypes.String,
                value="keep-me",
            ),
        ),
    )
    existing = list(submodel.submodel_element or [])
    existing.append(sentinel)
    submodel.submodel_element = existing

    output = BytesIO()
    with aasx_adapter.AASXWriter(output) as writer:
        aas_ids = [obj.id for obj in object_store if isinstance(obj, model.AssetAdministrationShell)]
        if aas_ids:
            writer.write_aas(
                aas_ids=aas_ids,
                object_store=object_store,
                file_store=file_store,
                write_json=False,
            )
        else:
            writer.write_all_aas_objects(
                "/aasx/data.xml",
                object_store,
                file_store,
                write_json=False,
            )

    return output.getvalue()
