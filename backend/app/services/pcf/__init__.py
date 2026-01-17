"""
PCF (Product Carbon Footprint) Calculator & Validator services.

IDTA 02023 compliant CO2e calculation and validation.
"""

from app.services.pcf.calculator import calculate_co2e, convert_to_kg
from app.services.pcf.emission_factors import (
    get_emission_factor_by_id,
    search_emission_factors,
)
from app.services.pcf.validator import is_pcf_template, validate_pcf

__all__ = [
    "calculate_co2e",
    "convert_to_kg",
    "get_emission_factor_by_id",
    "is_pcf_template",
    "search_emission_factors",
    "validate_pcf",
]
