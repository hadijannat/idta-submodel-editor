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

_UNIT_NORMALIZATION = {
    "kg": "kg",
    "kilogram": "kg",
    "kilograms": "kg",
    "t": "t",
    "tonne": "t",
    "tonnes": "t",
    "metric ton": "t",
    "metric tons": "t",
    "tco2e": "tco2e",
    "kwh": "kwh",
    "mj": "mj",
    "km": "km",
    "l": "l",
    "liter": "l",
    "litre": "l",
    "liters": "l",
    "litres": "l",
    "m3": "m3",
    "m^3": "m3",
    "m³": "m3",
    "tkm": "tkm",
}


def convert_to_kg(value: float, unit: str) -> float:
    """
    Convert quantity to base unit (kg for mass, passthrough for others).

    For mass units: converts tonnes to kg.
    For other units (kWh, MJ, km, m3): no conversion needed since
    emission factors are expressed in those units.
    """
    unit_lower = normalize_unit(unit)

    # Tonne to kg conversions
    if unit_lower in ("t", "tco2e"):
        return value * 1000.0

    # kg already - passthrough
    if unit_lower == "kg":
        return value

    # Other units (kWh, MJ, km, m3, etc.) - passthrough
    # These match emission factor denominators directly
    return value


def normalize_unit(unit: str) -> str:
    normalized = unit.lower().strip()
    return _UNIT_NORMALIZATION.get(normalized, normalized)


def parse_factor_unit_denominator(factor_unit: str) -> str | None:
    if not factor_unit:
        return None
    parts = factor_unit.split("/")
    if len(parts) < 2:
        return None
    denominator = parts[-1].strip()
    if not denominator:
        return None
    return normalize_unit(denominator)


def convert_quantity(value: float, from_unit: str, to_unit: str) -> tuple[float, bool]:
    if from_unit == to_unit:
        return value, True
    if to_unit == "kg" and from_unit in ("t", "tco2e"):
        return value * 1000.0, True
    if from_unit == "kg" and to_unit in ("t", "tco2e"):
        return value / 1000.0, True
    return value, False


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
        factor_denom = parse_factor_unit_denominator(activity.factor_unit)
        activity_unit = normalize_unit(activity.unit)

        quantity = activity.quantity
        if factor_denom:
            quantity, compatible = convert_quantity(quantity, activity_unit, factor_denom)
            if not compatible:
                warnings.append(
                    f"Activity '{activity.name}' unit '{activity.unit}' does not match "
                    f"factor unit '{activity.factor_unit}'. Calculation skipped."
                )
                calculated_activities.append(
                    PCFActivity(
                        id=activity.id,
                        name=activity.name,
                        category=activity.category,
                        quantity=activity.quantity,
                        unit=activity.unit,
                        factor_value=activity.factor_value,
                        factor_unit=activity.factor_unit,
                        factor_id=activity.factor_id,
                        factor_name=activity.factor_name,
                        factor_source=activity.factor_source,
                        factor_region=activity.factor_region,
                        factor_year=activity.factor_year,
                        co2e_kg=None,
                    )
                )
                continue
        else:
            warnings.append(
                f"Activity '{activity.name}' has unparseable factor unit "
                f"'{activity.factor_unit}'. Calculation uses raw quantity."
            )

        co2e_kg = quantity * activity.factor_value

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
            factor_id=activity.factor_id,
            factor_name=activity.factor_name,
            factor_source=activity.factor_source,
            factor_region=activity.factor_region,
            factor_year=activity.factor_year,
            co2e_kg=co2e_kg,
        )

        calculated_activities.append(calculated_activity)
        total_co2e += co2e_kg

    return PCFCalculateResponse(
        activities=calculated_activities,
        total_co2e_kg=total_co2e,
        warnings=warnings,
    )
