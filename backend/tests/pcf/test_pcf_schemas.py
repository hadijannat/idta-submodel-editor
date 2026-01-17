"""
Tests for PCF (Product Carbon Footprint) schemas.
TDD: Tests written first.
"""

import pytest
from pydantic import ValidationError as PydanticValidationError


def test_pcf_activity_basic_fields():
    """PCFActivity should have core activity data fields."""
    from app.schemas.pcf import PCFActivity

    activity = PCFActivity(
        id="act-001",
        name="Electricity consumption",
        category="scope2",
        quantity=1000.0,
        unit="kWh",
        factor_value=0.42,
        factor_unit="kg CO2e/kWh",
        factor_source="EPA 2024",
    )

    assert activity.id == "act-001"
    assert activity.name == "Electricity consumption"
    assert activity.category == "scope2"
    assert activity.quantity == 1000.0
    assert activity.unit == "kWh"
    assert activity.factor_value == 0.42
    assert activity.factor_unit == "kg CO2e/kWh"
    assert activity.factor_source == "EPA 2024"


def test_pcf_activity_co2e_field():
    """PCFActivity should have computed co2e_kg field."""
    from app.schemas.pcf import PCFActivity

    activity = PCFActivity(
        id="act-002",
        name="Transport",
        category="scope3",
        quantity=500,
        unit="km",
        factor_value=0.1,
        factor_unit="kg CO2e/km",
        co2e_kg=50.0,
    )

    assert activity.co2e_kg == 50.0


def test_pcf_activity_category_validation():
    """PCFActivity category must be scope1, scope2, or scope3."""
    from app.schemas.pcf import PCFActivity

    # Valid categories should work
    for cat in ("scope1", "scope2", "scope3"):
        activity = PCFActivity(
            id="test",
            name="Test",
            category=cat,
            quantity=100,
            unit="kg",
            factor_value=1.0,
            factor_unit="kg CO2e/kg",
        )
        assert activity.category == cat

    # Invalid category should fail
    with pytest.raises(PydanticValidationError):
        PCFActivity(
            id="test",
            name="Test",
            category="invalid",
            quantity=100,
            unit="kg",
            factor_value=1.0,
            factor_unit="kg CO2e/kg",
        )


def test_pcf_calculate_request():
    """PCFCalculateRequest should contain activities list."""
    from app.schemas.pcf import PCFActivity, PCFCalculateRequest

    request = PCFCalculateRequest(
        activities=[
            PCFActivity(
                id="a1",
                name="Energy",
                category="scope2",
                quantity=100,
                unit="kWh",
                factor_value=0.5,
                factor_unit="kg CO2e/kWh",
            )
        ]
    )

    assert len(request.activities) == 1
    assert request.activities[0].id == "a1"


def test_pcf_calculate_response():
    """PCFCalculateResponse should have activities with co2e and totals."""
    from app.schemas.pcf import PCFActivity, PCFCalculateResponse

    response = PCFCalculateResponse(
        activities=[
            PCFActivity(
                id="a1",
                name="Energy",
                category="scope2",
                quantity=100,
                unit="kWh",
                factor_value=0.5,
                factor_unit="kg CO2e/kWh",
                co2e_kg=50.0,
            )
        ],
        total_co2e_kg=50.0,
        warnings=["Factor may be outdated"],
    )

    assert response.total_co2e_kg == 50.0
    assert len(response.warnings) == 1
    assert response.activities[0].co2e_kg == 50.0


def test_pcf_validation_rule():
    """PCFValidationRule should have severity error or warning."""
    from app.schemas.pcf import PCFValidationRule

    error_rule = PCFValidationRule(
        rule_id="pcf_co2eq_required",
        field="PcfCO2eq",
        severity="error",
        message="PcfCO2eq is required",
        code="required_field",
    )

    warning_rule = PCFValidationRule(
        rule_id="method_recommended",
        field="PcfCalculationMethod",
        severity="warning",
        message="Calculation method is recommended",
        code="recommended_field",
    )

    assert error_rule.severity == "error"
    assert warning_rule.severity == "warning"


def test_pcf_validation_rule_severity_validation():
    """PCFValidationRule severity must be error or warning."""
    from app.schemas.pcf import PCFValidationRule

    with pytest.raises(PydanticValidationError):
        PCFValidationRule(
            rule_id="test",
            field="TestField",
            severity="invalid",
            message="Test",
            code="test",
        )


def test_pcf_validate_response():
    """PCFValidateResponse should contain valid flag, errors, warnings, and completeness."""
    from app.schemas.pcf import PCFValidateResponse, PCFValidationRule

    response = PCFValidateResponse(
        valid=False,
        errors=[
            PCFValidationRule(
                rule_id="pcf_required",
                field="PcfCO2eq",
                severity="error",
                message="Required",
                code="required",
            )
        ],
        warnings=[
            PCFValidationRule(
                rule_id="method_rec",
                field="PcfCalculationMethod",
                severity="warning",
                message="Recommended",
                code="recommended",
            )
        ],
        completeness_score=0.75,
    )

    assert response.valid is False
    assert len(response.errors) == 1
    assert len(response.warnings) == 1
    assert response.completeness_score == 0.75


def test_emission_factor():
    """EmissionFactor should have lookup fields."""
    from app.schemas.pcf import EmissionFactor

    factor = EmissionFactor(
        id="ef-001",
        name="Grid electricity - US average",
        factor_value=0.42,
        factor_unit="kg CO2e/kWh",
        source="EPA eGRID 2024",
        region="US",
        year=2024,
    )

    assert factor.id == "ef-001"
    assert factor.factor_value == 0.42
    assert factor.source == "EPA eGRID 2024"
    assert factor.region == "US"
    assert factor.year == 2024


def test_pcf_validate_request():
    """PCFValidateRequest should contain form_data and template_schema."""
    from app.schemas.pcf import PCFValidateRequest

    request = PCFValidateRequest(
        form_data={"elements": {"PcfCO2eq": {"value": "100.5"}}},
        template_schema={"elements": []},
    )

    assert request.form_data is not None
    assert request.template_schema is not None
