"""
PCF CO2e Calculator.

Calculates CO2e emissions from activity data using the formula:
    CO2e (kg) = quantity × emission_factor

Handles unit conversions and aggregates totals.
"""

from __future__ import annotations

from app.schemas.pcf import (
    PCFActivity,
    PCFCalculateRequest,
    PCFCalculateResponse,
)


def convert_to_kg(value: float, unit: str) -> float:
    """
    Convert quantity to base unit (kg for mass, passthrough for others).

    For mass units: converts tonnes to kg.
    For other units (kWh, MJ, km, m3): no conversion needed since
    emission factors are expressed in those units.
    """
    unit_lower = unit.lower().strip()

    # Tonne to kg conversions
    if unit_lower in ("t", "tonne", "tonnes", "metric ton", "metric tons"):
        return value * 1000.0

    # kg already - passthrough
    if unit_lower in ("kg", "kilogram", "kilograms"):
        return value

    # Other units (kWh, MJ, km, m3, etc.) - passthrough
    # These match emission factor denominators directly
    return value


def calculate_co2e(request: PCFCalculateRequest) -> PCFCalculateResponse:
    """
    Calculate CO2e for all activities.

    Formula: CO2e (kg) = quantity × factor_value

    Returns activities with computed co2e_kg and total.
    """
    if not request.activities:
        return PCFCalculateResponse(
            activities=[],
            total_co2e_kg=0.0,
            warnings=[],
        )

    calculated_activities: list[PCFActivity] = []
    total_co2e = 0.0
    warnings: list[str] = []

    for activity in request.activities:
        # Always recalculate - don't use preset co2e_kg
        co2e_kg = activity.quantity * activity.factor_value

        # Check for negative quantities (carbon offsets/credits)
        if activity.quantity < 0:
            warnings.append(
                f"Activity '{activity.name}' has negative quantity ({activity.quantity}). "
                "This may represent a carbon offset or credit."
            )

        # Create new activity with calculated value
        calculated_activity = PCFActivity(
            id=activity.id,
            name=activity.name,
            category=activity.category,
            quantity=activity.quantity,
            unit=activity.unit,
            factor_value=activity.factor_value,
            factor_unit=activity.factor_unit,
            factor_source=activity.factor_source,
            co2e_kg=co2e_kg,
        )

        calculated_activities.append(calculated_activity)
        total_co2e += co2e_kg

    return PCFCalculateResponse(
        activities=calculated_activities,
        total_co2e_kg=total_co2e,
        warnings=warnings,
    )
