"""
Schemas for PCF (Product Carbon Footprint) Calculator & Validator.

IDTA 02023 compliant CO2e calculation and validation schemas.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class PCFActivity(BaseModel):
    """A single emission activity for CO2e calculation."""

    id: str
    name: str
    category: Literal["scope1", "scope2", "scope3"]
    quantity: float
    unit: str
    factor_value: float
    factor_unit: str
    factor_id: str | None = None
    factor_name: str | None = None
    factor_source: str | None = None
    factor_region: str | None = None
    factor_year: int | None = None
    co2e_kg: float | None = None


class PCFCalculateRequest(BaseModel):
    """Request to calculate CO2e from activities."""

    activities: list[PCFActivity]


class PCFCalculateResponse(BaseModel):
    """Response with calculated CO2e values."""

    activities: list[PCFActivity]
    total_co2e_kg: float
    warnings: list[str] = Field(default_factory=list)


class PCFValidationRule(BaseModel):
    """A PCF-specific validation rule result."""

    rule_id: str
    field: str
    severity: Literal["error", "warning"]
    message: str
    code: str | None = None


class PCFValidateRequest(BaseModel):
    """Request to validate PCF form data."""

    form_data: dict[str, Any]
    template_schema: dict[str, Any]


class PCFValidateResponse(BaseModel):
    """Response from PCF validation."""

    valid: bool
    errors: list[PCFValidationRule] = Field(default_factory=list)
    warnings: list[PCFValidationRule] = Field(default_factory=list)
    completeness_score: float = 0.0


class EmissionFactor(BaseModel):
    """An emission factor for CO2e calculation."""

    id: str
    name: str
    factor_value: float
    factor_unit: str
    source: str
    region: str | None = None
    year: int | None = None
