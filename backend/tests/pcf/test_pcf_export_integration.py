"""
Tests for PCF validation integration in export router.
"""

import pytest
from app.services.pcf.validator import validate_pcf, is_pcf_template
from app.schemas.pcf import PCFValidateRequest


class TestIsPcfTemplate:
    """Tests for PCF template detection."""

    def test_non_pcf_template_returns_false(self):
        """Non-PCF template should return False."""
        schema = {
            "semanticId": "https://admin-shell.io/idta/SomeOtherTemplate/1/0",
            "elements": [],
        }
        assert is_pcf_template(schema) is False

    def test_pcf_template_by_full_iri_returns_true(self):
        """Template with CarbonFootprint IRI should return True."""
        schema = {
            "semanticId": "https://admin-shell.io/idta/CarbonFootprint/CarbonFootprint/1/0",
            "elements": [],
        }
        assert is_pcf_template(schema) is True

    def test_pcf_template_by_partial_match_returns_true(self):
        """Template with 'CarbonFootprint' in semanticId should return True."""
        schema = {
            "semanticId": "https://example.org/CarbonFootprint/v1",
            "elements": [],
        }
        assert is_pcf_template(schema) is True

    def test_pcf_template_by_irdi_returns_true(self):
        """Template with known PCF IRDI should return True."""
        schema = {
            "semanticId": "0173-1#01-AHE712#001",
            "elements": [],
        }
        assert is_pcf_template(schema) is True

    def test_case_insensitive_carbon_match(self):
        """Detection should be case-insensitive for 'carbon'."""
        schema = {
            "semanticId": "https://example.org/carbonfootprint/v1",
            "elements": [],
        }
        assert is_pcf_template(schema) is True

    def test_null_semantic_id_returns_false(self):
        """Schema with no semanticId should return False."""
        schema = {"elements": []}
        assert is_pcf_template(schema) is False


class TestPcfValidateErrors:
    """Tests for PCF validation error handling."""

    def test_validate_pcf_returns_errors_for_missing_required_fields(self):
        """Missing required fields should produce errors."""
        request = PCFValidateRequest(
            form_data={"elements": {}},
            template_schema={"elements": []},
        )
        result = validate_pcf(request)

        assert result.valid is False
        assert len(result.errors) == 5  # All 5 required fields missing
        error_fields = {e.field for e in result.errors}
        assert "PcfCO2eq" in error_fields
        assert "ReferenceImpactUnitForCalculation" in error_fields
        assert "QuantityOfMeasureForCalculation" in error_fields
        assert "PublicationDate" in error_fields
        assert "LifeCyclePhases" in error_fields

    def test_validate_pcf_returns_warnings_for_missing_recommended(self):
        """Missing recommended fields should produce warnings."""
        # Provide all required fields
        request = PCFValidateRequest(
            form_data={
                "elements": {
                    "PcfCO2eq": {"value": "10.5"},
                    "ReferenceImpactUnitForCalculation": {"value": "kg"},
                    "QuantityOfMeasureForCalculation": {"value": "1"},
                    "PublicationDate": {"value": "2024-01-15"},
                    "LifeCyclePhases": {"items": [{"value": "A1"}]},
                }
            },
            template_schema={"elements": []},
        )
        result = validate_pcf(request)

        assert result.valid is True
        assert len(result.warnings) == 2  # 2 recommended fields missing
        warning_fields = {w.field for w in result.warnings}
        assert "PcfCalculationMethod" in warning_fields
        assert "ExpirationDate" in warning_fields

    def test_validate_pcf_all_fields_complete(self):
        """Complete form should pass with no errors or warnings."""
        request = PCFValidateRequest(
            form_data={
                "elements": {
                    "PcfCO2eq": {"value": "10.5"},
                    "ReferenceImpactUnitForCalculation": {"value": "kg"},
                    "QuantityOfMeasureForCalculation": {"value": "1"},
                    "PublicationDate": {"value": "2024-01-15"},
                    "LifeCyclePhases": {"items": [{"value": "A1"}]},
                    "PcfCalculationMethod": {"value": "PEF"},
                    "ExpirationDate": {"value": "2025-01-15"},
                }
            },
            template_schema={"elements": []},
        )
        result = validate_pcf(request)

        assert result.valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 0
        assert result.completeness_score == 1.0

    def test_completeness_score_calculation(self):
        """Completeness score should reflect filled fields."""
        # 3 of 5 required + 1 of 2 recommended = 4 of 7 total
        request = PCFValidateRequest(
            form_data={
                "elements": {
                    "PcfCO2eq": {"value": "10.5"},
                    "ReferenceImpactUnitForCalculation": {"value": "kg"},
                    "QuantityOfMeasureForCalculation": {"value": "1"},
                    "ExpirationDate": {"value": "2025-01-15"},
                }
            },
            template_schema={"elements": []},
        )
        result = validate_pcf(request)

        assert result.valid is False
        assert result.completeness_score == pytest.approx(4 / 7, rel=0.01)
