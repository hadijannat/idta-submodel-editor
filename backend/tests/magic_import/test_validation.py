"""
Tests for ExtractionValidator.

Validates Magic Import extractions against template schemas.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.schemas.magic_import import (
    FieldExtraction,
    ValidationError,
    ValidationResult,
)
from app.services.magic_import.validator import ExtractionValidator


@pytest.fixture
def validator():
    """Create an ExtractionValidator instance."""
    return ExtractionValidator()


@pytest.fixture
def mock_schema():
    """Create a mock parsed schema for testing."""
    return {
        "name": "Test Template",
        "elements": [
            {
                "idShort": "ManufacturerName",
                "modelType": "Property",
                "valueType": "xs:string",
                "cardinality": "[1]",  # Required
            },
            {
                "idShort": "SerialNumber",
                "modelType": "Property",
                "valueType": "xs:string",
                "cardinality": "[1]",  # Required
            },
            {
                "idShort": "YearOfConstruction",
                "modelType": "Property",
                "valueType": "xs:integer",
                "cardinality": "[0..1]",  # Optional
            },
            {
                "idShort": "ContactInformation",
                "modelType": "SubmodelElementCollection",
                "cardinality": "[0..1]",
                "elements": [
                    {
                        "idShort": "Email",
                        "modelType": "Property",
                        "valueType": "xs:string",
                        "cardinality": "[1]",  # Required within collection
                    },
                    {
                        "idShort": "Phone",
                        "modelType": "Property",
                        "valueType": "xs:string",
                        "cardinality": "[0..1]",  # Optional
                    },
                ],
            },
            {
                "idShort": "Markings",
                "modelType": "SubmodelElementList",
                "cardinality": "[0..*]",
                "itemTemplate": {
                    "idShort": "Marking",
                    "modelType": "SubmodelElementCollection",
                    "elements": [
                        {
                            "idShort": "MarkingName",
                            "modelType": "Property",
                            "valueType": "xs:string",
                            "cardinality": "[1]",
                        },
                    ],
                },
            },
        ],
    }


def make_extraction(path: str, value: str, value_type: str | None = None) -> FieldExtraction:
    """Helper to create a FieldExtraction."""
    return FieldExtraction(
        path=path,
        value_type=value_type,
        value_raw=value,
        value_normalized=None,
        confidence=0.9,
        confidence_breakdown=None,
        confidence_reasons=[],
        evidence=None,
        needs_review=False,
        user_edited=False,
        user_approved=False,
    )


class TestTypeValidation:
    """Tests for type validation logic."""

    def test_validate_integer_valid(self, validator):
        """Test valid integer passes validation."""
        errors = validator._validate_type("42", "xs:integer", "TestField")
        assert len(errors) == 0

    def test_validate_integer_with_spaces(self, validator):
        """Test integer with spaces passes."""
        errors = validator._validate_type("  42  ", "xs:integer", "TestField")
        assert len(errors) == 0

    def test_validate_integer_invalid_float(self, validator):
        """Test float value fails integer validation."""
        errors = validator._validate_type("42.5", "xs:integer", "TestField")
        assert len(errors) == 1
        assert errors[0].code == "type_mismatch"
        assert "not a valid integer" in errors[0].message

    def test_validate_integer_invalid_string(self, validator):
        """Test string fails integer validation."""
        errors = validator._validate_type("hello", "xs:integer", "TestField")
        assert len(errors) == 1
        assert errors[0].code == "type_mismatch"

    def test_validate_decimal_valid(self, validator):
        """Test valid decimal passes validation."""
        errors = validator._validate_type("42.5", "xs:decimal", "TestField")
        assert len(errors) == 0

    def test_validate_decimal_with_comma(self, validator):
        """Test decimal with comma separator passes."""
        errors = validator._validate_type("42,5", "xs:decimal", "TestField")
        assert len(errors) == 0

    def test_validate_double_valid(self, validator):
        """Test valid double passes validation."""
        errors = validator._validate_type("3.14159", "xs:double", "TestField")
        assert len(errors) == 0

    def test_validate_float_valid(self, validator):
        """Test valid float passes validation."""
        errors = validator._validate_type("1.5", "xs:float", "TestField")
        assert len(errors) == 0

    def test_validate_boolean_true(self, validator):
        """Test 'true' passes boolean validation."""
        errors = validator._validate_type("true", "xs:boolean", "TestField")
        assert len(errors) == 0

    def test_validate_boolean_false(self, validator):
        """Test 'false' passes boolean validation."""
        errors = validator._validate_type("false", "xs:boolean", "TestField")
        assert len(errors) == 0

    def test_validate_boolean_yes(self, validator):
        """Test 'yes' passes boolean validation."""
        errors = validator._validate_type("yes", "xs:boolean", "TestField")
        assert len(errors) == 0

    def test_validate_boolean_numeric(self, validator):
        """Test '1' and '0' pass boolean validation."""
        assert len(validator._validate_type("1", "xs:boolean", "TestField")) == 0
        assert len(validator._validate_type("0", "xs:boolean", "TestField")) == 0

    def test_validate_boolean_invalid(self, validator):
        """Test invalid boolean fails validation."""
        errors = validator._validate_type("maybe", "xs:boolean", "TestField")
        assert len(errors) == 1
        assert errors[0].code == "type_mismatch"
        assert "not a valid boolean" in errors[0].message

    def test_validate_date_iso(self, validator):
        """Test ISO date format passes."""
        errors = validator._validate_type("2024-01-15", "xs:date", "TestField")
        assert len(errors) == 0

    def test_validate_date_european(self, validator):
        """Test European date format passes."""
        errors = validator._validate_type("15/01/2024", "xs:date", "TestField")
        assert len(errors) == 0

    def test_validate_date_american(self, validator):
        """Test American date format passes."""
        errors = validator._validate_type("01/15/2024", "xs:date", "TestField")
        assert len(errors) == 0

    def test_validate_datetime(self, validator):
        """Test datetime format passes."""
        errors = validator._validate_type("2024-01-15T10:30:00", "xs:dateTime", "TestField")
        assert len(errors) == 0

    def test_validate_date_invalid(self, validator):
        """Test invalid date fails validation."""
        errors = validator._validate_type("not-a-date", "xs:date", "TestField")
        assert len(errors) == 1
        assert errors[0].code == "type_mismatch"
        assert "not a valid date" in errors[0].message

    def test_validate_empty_value_passes(self, validator):
        """Test empty value doesn't fail type validation."""
        errors = validator._validate_type("", "xs:integer", "TestField")
        assert len(errors) == 0


class TestCardinalityParsing:
    """Tests for cardinality string parsing."""

    def test_parse_required_bracket(self, validator):
        """Test [1] parses as required."""
        assert validator._parse_min_cardinality("[1]") == 1

    def test_parse_optional_bracket(self, validator):
        """Test [0..1] parses as optional."""
        assert validator._parse_min_cardinality("[0..1]") == 0

    def test_parse_one_to_many(self, validator):
        """Test [1..*] parses as required."""
        assert validator._parse_min_cardinality("[1..*]") == 1

    def test_parse_zero_to_many(self, validator):
        """Test [0..*] parses as optional."""
        assert validator._parse_min_cardinality("[0..*]") == 0

    def test_parse_named_zero_to_one(self, validator):
        """Test ZeroToOne parses as optional."""
        assert validator._parse_min_cardinality("ZeroToOne") == 0

    def test_parse_named_zero_to_many(self, validator):
        """Test ZeroToMany parses as optional."""
        assert validator._parse_min_cardinality("ZeroToMany") == 0

    def test_parse_named_one_to_many(self, validator):
        """Test OneToMany parses as required."""
        assert validator._parse_min_cardinality("OneToMany") == 1

    def test_parse_named_one(self, validator):
        """Test One parses as required."""
        assert validator._parse_min_cardinality("One") == 1

    def test_parse_unknown_defaults_required(self, validator):
        """Test unknown cardinality defaults to required."""
        assert validator._parse_min_cardinality("unknown") == 1


class TestSchemaLookupBuilding:
    """Tests for building schema path lookup."""

    def test_build_simple_lookup(self, validator, mock_schema):
        """Test building lookup for simple elements."""
        lookup = validator._build_schema_lookup(mock_schema["elements"])

        assert "ManufacturerName" in lookup
        assert "SerialNumber" in lookup
        assert "YearOfConstruction" in lookup

    def test_build_nested_collection_lookup(self, validator, mock_schema):
        """Test building lookup includes nested collection paths."""
        lookup = validator._build_schema_lookup(mock_schema["elements"])

        assert "ContactInformation" in lookup
        assert "ContactInformation.Email" in lookup
        assert "ContactInformation.Phone" in lookup

    def test_build_list_item_lookup(self, validator, mock_schema):
        """Test building lookup includes list item paths."""
        lookup = validator._build_schema_lookup(mock_schema["elements"])

        assert "Markings" in lookup
        assert "Markings[]" in lookup
        assert "Markings[].MarkingName" in lookup


class TestRequiredPathsExtraction:
    """Tests for extracting required field paths."""

    def test_get_required_simple_fields(self, validator, mock_schema):
        """Test getting required simple fields."""
        required = validator._get_required_paths(mock_schema["elements"])

        assert "ManufacturerName" in required
        assert "SerialNumber" in required
        assert "YearOfConstruction" not in required  # Optional

    def test_get_required_nested_fields(self, validator, mock_schema):
        """Test getting required nested fields."""
        required = validator._get_required_paths(mock_schema["elements"])

        # Email is required within ContactInformation
        assert "ContactInformation.Email" in required
        assert "ContactInformation.Phone" not in required  # Optional


class TestValidateExtractions:
    """Integration tests for full validation flow."""

    def test_valid_extractions_pass(self, validator, mock_schema):
        """Test valid extractions pass validation."""
        with patch.object(validator, "_fetcher") as mock_fetcher, patch.object(
            validator, "_parser"
        ) as mock_parser:
            mock_fetcher.get_template.return_value = MagicMock()
            mock_parser.parse_template.return_value = mock_schema

            extractions = [
                make_extraction("ManufacturerName", "ACME Corp"),
                make_extraction("SerialNumber", "SN-123456"),
                make_extraction("ContactInformation.Email", "info@acme.com"),
            ]

            result = validator.validate_extractions(
                extractions, "test-template", mode="warn"
            )

            assert result.is_valid is True
            assert len(result.errors) == 0

    def test_unknown_field_creates_warning(self, validator, mock_schema):
        """Test unknown field path creates warning in warn mode."""
        with patch.object(validator, "_fetcher") as mock_fetcher, patch.object(
            validator, "_parser"
        ) as mock_parser:
            mock_fetcher.get_template.return_value = MagicMock()
            mock_parser.parse_template.return_value = mock_schema

            extractions = [
                make_extraction("ManufacturerName", "ACME Corp"),
                make_extraction("SerialNumber", "SN-123456"),
                make_extraction("ContactInformation.Email", "info@acme.com"),
                make_extraction("UnknownField", "some value"),  # Not in schema
            ]

            result = validator.validate_extractions(
                extractions, "test-template", mode="warn"
            )

            assert result.is_valid is True  # Still valid, just warnings
            assert len(result.warnings) >= 1
            unknown_warning = next(
                (w for w in result.warnings if w.code == "unknown_field"), None
            )
            assert unknown_warning is not None
            assert "UnknownField" in unknown_warning.message

    def test_unknown_field_creates_error_strict(self, validator, mock_schema):
        """Test unknown field path creates error in strict mode."""
        with patch.object(validator, "_fetcher") as mock_fetcher, patch.object(
            validator, "_parser"
        ) as mock_parser:
            mock_fetcher.get_template.return_value = MagicMock()
            mock_parser.parse_template.return_value = mock_schema

            extractions = [
                make_extraction("ManufacturerName", "ACME Corp"),
                make_extraction("SerialNumber", "SN-123456"),
                make_extraction("ContactInformation.Email", "info@acme.com"),
                make_extraction("UnknownField", "some value"),
            ]

            result = validator.validate_extractions(
                extractions, "test-template", mode="strict"
            )

            assert result.is_valid is False
            assert len(result.errors) >= 1
            unknown_error = next(
                (e for e in result.errors if e.code == "unknown_field"), None
            )
            assert unknown_error is not None

    def test_missing_required_field_warning(self, validator, mock_schema):
        """Test missing required field creates warning in warn mode."""
        with patch.object(validator, "_fetcher") as mock_fetcher, patch.object(
            validator, "_parser"
        ) as mock_parser:
            mock_fetcher.get_template.return_value = MagicMock()
            mock_parser.parse_template.return_value = mock_schema

            # Missing SerialNumber (required)
            extractions = [
                make_extraction("ManufacturerName", "ACME Corp"),
                make_extraction("ContactInformation.Email", "info@acme.com"),
            ]

            result = validator.validate_extractions(
                extractions, "test-template", mode="warn"
            )

            assert result.is_valid is True  # Still valid, just warnings
            missing_warning = next(
                (w for w in result.warnings if w.code == "missing_required"), None
            )
            assert missing_warning is not None
            assert "SerialNumber" in missing_warning.path

    def test_missing_required_field_error_strict(self, validator, mock_schema):
        """Test missing required field creates error in strict mode."""
        with patch.object(validator, "_fetcher") as mock_fetcher, patch.object(
            validator, "_parser"
        ) as mock_parser:
            mock_fetcher.get_template.return_value = MagicMock()
            mock_parser.parse_template.return_value = mock_schema

            # Missing SerialNumber (required)
            extractions = [
                make_extraction("ManufacturerName", "ACME Corp"),
                make_extraction("ContactInformation.Email", "info@acme.com"),
            ]

            result = validator.validate_extractions(
                extractions, "test-template", mode="strict"
            )

            assert result.is_valid is False
            missing_error = next(
                (e for e in result.errors if e.code == "missing_required"), None
            )
            assert missing_error is not None

    def test_type_mismatch_creates_warning(self, validator, mock_schema):
        """Test type mismatch creates warning."""
        with patch.object(validator, "_fetcher") as mock_fetcher, patch.object(
            validator, "_parser"
        ) as mock_parser:
            mock_fetcher.get_template.return_value = MagicMock()
            mock_parser.parse_template.return_value = mock_schema

            extractions = [
                make_extraction("ManufacturerName", "ACME Corp"),
                make_extraction("SerialNumber", "SN-123456"),
                make_extraction("YearOfConstruction", "not-a-number", "xs:integer"),
                make_extraction("ContactInformation.Email", "info@acme.com"),
            ]

            result = validator.validate_extractions(
                extractions, "test-template", mode="warn"
            )

            type_warning = next(
                (w for w in result.warnings if w.code == "type_mismatch"), None
            )
            assert type_warning is not None
            assert "YearOfConstruction" in type_warning.path

    def test_template_not_found_error(self, validator):
        """Test template not found returns error."""
        with patch.object(validator, "_fetcher") as mock_fetcher:
            mock_fetcher.get_template.return_value = None

            extractions = [make_extraction("ManufacturerName", "ACME Corp")]

            result = validator.validate_extractions(extractions, "nonexistent-template")

            assert result.is_valid is False
            assert len(result.errors) == 1
            assert result.errors[0].code == "template_not_found"

    def test_exception_handling(self, validator):
        """Test exception during validation is handled."""
        with patch.object(validator, "_fetcher") as mock_fetcher:
            mock_fetcher.get_template.side_effect = Exception("Fetch failed")

            extractions = [make_extraction("ManufacturerName", "ACME Corp")]

            result = validator.validate_extractions(extractions, "test-template")

            assert result.is_valid is False
            assert len(result.errors) == 1
            assert result.errors[0].code == "validation_error"
            assert "Fetch failed" in result.errors[0].message


class TestValidationResult:
    """Tests for ValidationResult model."""

    def test_validation_result_structure(self):
        """Test ValidationResult has expected structure."""
        result = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=[ValidationError(path="test", message="warning", code="test")],
        )

        assert result.is_valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 1
        assert result.warnings[0].path == "test"

    def test_validation_error_structure(self):
        """Test ValidationError has expected structure."""
        error = ValidationError(
            path="ManufacturerName",
            message="Field is required",
            code="missing_required",
        )

        assert error.path == "ManufacturerName"
        assert error.message == "Field is required"
        assert error.code == "missing_required"
