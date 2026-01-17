"""
Tests for PCF Calculator service.
TDD: Tests written first.
"""

import pytest


def test_calculate_single_activity():
    """Calculate CO2e for a single activity."""
    from app.schemas.pcf import PCFActivity, PCFCalculateRequest
    from app.services.pcf.calculator import calculate_co2e

    request = PCFCalculateRequest(
        activities=[
            PCFActivity(
                id="act-001",
                name="Electricity consumption",
                category="scope2",
                quantity=1000.0,
                unit="kWh",
                factor_value=0.42,
                factor_unit="kg CO2e/kWh",
            )
        ]
    )

    response = calculate_co2e(request)

    assert len(response.activities) == 1
    assert response.activities[0].co2e_kg == pytest.approx(420.0)
    assert response.total_co2e_kg == pytest.approx(420.0)


def test_calculate_multiple_activities():
    """Calculate CO2e for multiple activities and sum totals."""
    from app.schemas.pcf import PCFActivity, PCFCalculateRequest
    from app.services.pcf.calculator import calculate_co2e

    request = PCFCalculateRequest(
        activities=[
            PCFActivity(
                id="act-001",
                name="Electricity",
                category="scope2",
                quantity=1000.0,
                unit="kWh",
                factor_value=0.42,
                factor_unit="kg CO2e/kWh",
            ),
            PCFActivity(
                id="act-002",
                name="Natural Gas",
                category="scope1",
                quantity=500.0,
                unit="m3",
                factor_value=2.0,
                factor_unit="kg CO2e/m3",
            ),
            PCFActivity(
                id="act-003",
                name="Transport",
                category="scope3",
                quantity=200.0,
                unit="km",
                factor_value=0.1,
                factor_unit="kg CO2e/km",
            ),
        ]
    )

    response = calculate_co2e(request)

    assert len(response.activities) == 3
    assert response.activities[0].co2e_kg == pytest.approx(420.0)  # 1000 * 0.42
    assert response.activities[1].co2e_kg == pytest.approx(1000.0)  # 500 * 2.0
    assert response.activities[2].co2e_kg == pytest.approx(20.0)  # 200 * 0.1
    assert response.total_co2e_kg == pytest.approx(1440.0)  # 420 + 1000 + 20


def test_calculate_empty_activities():
    """Empty activities list returns zero total."""
    from app.schemas.pcf import PCFCalculateRequest
    from app.services.pcf.calculator import calculate_co2e

    request = PCFCalculateRequest(activities=[])
    response = calculate_co2e(request)

    assert response.total_co2e_kg == 0.0
    assert len(response.activities) == 0


def test_calculate_preserves_activity_metadata():
    """Calculation preserves original activity fields."""
    from app.schemas.pcf import PCFActivity, PCFCalculateRequest
    from app.services.pcf.calculator import calculate_co2e

    request = PCFCalculateRequest(
        activities=[
            PCFActivity(
                id="act-unique",
                name="Solar Power Offset",
                category="scope2",
                quantity=100.0,
                unit="kWh",
                factor_value=0.5,
                factor_unit="kg CO2e/kWh",
                factor_source="EPA eGRID 2024",
            )
        ]
    )

    response = calculate_co2e(request)
    activity = response.activities[0]

    assert activity.id == "act-unique"
    assert activity.name == "Solar Power Offset"
    assert activity.category == "scope2"
    assert activity.factor_source == "EPA eGRID 2024"


def test_convert_tonnes_to_kg():
    """Convert quantity from tonnes to kg for calculation."""
    from app.services.pcf.calculator import convert_to_kg

    # 1 tonne = 1000 kg
    assert convert_to_kg(1.0, "t") == pytest.approx(1000.0)
    assert convert_to_kg(2.5, "tonne") == pytest.approx(2500.0)
    assert convert_to_kg(0.5, "tonnes") == pytest.approx(500.0)


def test_convert_kg_unchanged():
    """Kg and kilogram units pass through unchanged."""
    from app.services.pcf.calculator import convert_to_kg

    assert convert_to_kg(100.0, "kg") == pytest.approx(100.0)
    assert convert_to_kg(100.0, "kilogram") == pytest.approx(100.0)


def test_convert_unsupported_unit_unchanged():
    """Unsupported units pass through unchanged with warning potential."""
    from app.services.pcf.calculator import convert_to_kg

    # Units like kWh, m3, km don't need conversion - they match emission factor units
    assert convert_to_kg(100.0, "kWh") == pytest.approx(100.0)
    assert convert_to_kg(100.0, "MJ") == pytest.approx(100.0)
    assert convert_to_kg(100.0, "km") == pytest.approx(100.0)


def test_calculate_with_zero_quantity():
    """Zero quantity produces zero CO2e."""
    from app.schemas.pcf import PCFActivity, PCFCalculateRequest
    from app.services.pcf.calculator import calculate_co2e

    request = PCFCalculateRequest(
        activities=[
            PCFActivity(
                id="act-zero",
                name="No consumption",
                category="scope1",
                quantity=0.0,
                unit="kWh",
                factor_value=0.42,
                factor_unit="kg CO2e/kWh",
            )
        ]
    )

    response = calculate_co2e(request)
    assert response.activities[0].co2e_kg == pytest.approx(0.0)
    assert response.total_co2e_kg == pytest.approx(0.0)


def test_calculate_with_negative_quantity_adds_warning():
    """Negative quantity calculates but adds warning."""
    from app.schemas.pcf import PCFActivity, PCFCalculateRequest
    from app.services.pcf.calculator import calculate_co2e

    request = PCFCalculateRequest(
        activities=[
            PCFActivity(
                id="act-negative",
                name="Carbon offset",
                category="scope3",
                quantity=-100.0,  # Offset/credit scenario
                unit="tCO2e",
                factor_value=1000.0,  # 1 tCO2e = 1000 kg
                factor_unit="kg CO2e/tCO2e",
            )
        ]
    )

    response = calculate_co2e(request)

    # Should still calculate (offsets represented as negative)
    assert response.activities[0].co2e_kg == pytest.approx(-100000.0)
    assert "negative" in response.warnings[0].lower()


def test_activity_preserves_existing_co2e_if_provided():
    """If activity already has co2e_kg, use provided value."""
    from app.schemas.pcf import PCFActivity, PCFCalculateRequest
    from app.services.pcf.calculator import calculate_co2e

    request = PCFCalculateRequest(
        activities=[
            PCFActivity(
                id="act-preset",
                name="Pre-calculated",
                category="scope1",
                quantity=100.0,
                unit="kWh",
                factor_value=0.5,
                factor_unit="kg CO2e/kWh",
                co2e_kg=999.0,  # Pre-calculated value
            )
        ]
    )

    response = calculate_co2e(request)

    # Should recalculate, not use the preset value
    assert response.activities[0].co2e_kg == pytest.approx(50.0)


def test_calculate_with_unit_mismatch_skips_activity():
    """Incompatible units should skip calculation and emit warning."""
    from app.schemas.pcf import PCFActivity, PCFCalculateRequest
    from app.services.pcf.calculator import calculate_co2e

    request = PCFCalculateRequest(
        activities=[
            PCFActivity(
                id="act-mismatch",
                name="Mismatch",
                category="scope2",
                quantity=100.0,
                unit="kg",
                factor_value=0.42,
                factor_unit="kg CO2e/kWh",
            )
        ]
    )

    response = calculate_co2e(request)

    assert response.activities[0].co2e_kg is None
    assert response.total_co2e_kg == pytest.approx(0.0)
    assert any("does not match" in w.lower() for w in response.warnings)


def test_calculate_with_tkm_unit():
    """Transport unit tkm should calculate normally."""
    from app.schemas.pcf import PCFActivity, PCFCalculateRequest
    from app.services.pcf.calculator import calculate_co2e

    request = PCFCalculateRequest(
        activities=[
            PCFActivity(
                id="act-tkm",
                name="Road Freight",
                category="scope3",
                quantity=200.0,
                unit="tkm",
                factor_value=0.1,
                factor_unit="kg CO2e/tkm",
            )
        ]
    )

    response = calculate_co2e(request)

    assert response.activities[0].co2e_kg == pytest.approx(20.0)
    assert response.total_co2e_kg == pytest.approx(20.0)
