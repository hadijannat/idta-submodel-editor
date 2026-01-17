"""
PCF (Product Carbon Footprint) Calculator & Validator API endpoints.

IDTA 02023 compliant CO2e calculation and validation.
"""

from fastapi import APIRouter, HTTPException

from app.schemas.pcf import (
    EmissionFactor,
    PCFCalculateRequest,
    PCFCalculateResponse,
    PCFValidateRequest,
    PCFValidateResponse,
)
from app.services.pcf.calculator import calculate_co2e
from app.services.pcf.emission_factors import (
    get_emission_factor_by_id,
    get_emission_factors_metadata,
    search_emission_factors,
)
from app.services.pcf.validator import validate_pcf

router = APIRouter(prefix="/api/pcf", tags=["pcf"])


@router.post("/calculate", response_model=PCFCalculateResponse)
def calculate_emissions(
    request: PCFCalculateRequest,
) -> PCFCalculateResponse:
    """
    Calculate CO2e emissions from activity data.

    Formula: CO2e (kg) = quantity × emission_factor

    Returns activities with computed co2e_kg values and total.
    """
    return calculate_co2e(request)


@router.post("/validate", response_model=PCFValidateResponse)
def validate_pcf_data(
    request: PCFValidateRequest,
) -> PCFValidateResponse:
    """
    Validate PCF form data against IDTA 02023 rules.

    Returns validation result with:
    - valid: True if no blocking errors
    - errors: Required field violations (block export)
    - warnings: Recommended field suggestions
    - completeness_score: 0.0-1.0 ratio of filled fields
    """
    return validate_pcf(request)


@router.get("/health")
def health_check() -> dict:
    """
    Check PCF service health status.

    Returns status of calculator and validator services.
    """
    return {
        "status": "healthy",
        "services": {
            "calculator": "available",
            "validator": "available",
            "factors": "available",
        },
        "factors": get_emission_factors_metadata(),
    }


@router.get("/factors/search", response_model=list[EmissionFactor])
def search_factors(
    query: str = "",
    limit: int = 20,
) -> list[EmissionFactor]:
    """
    Search emission factors by name, source, or region.

    Args:
        query: Search query (case-insensitive)
        limit: Maximum number of results (default 20)

    Returns:
        List of matching emission factors.
    """
    return search_emission_factors(query, limit)


@router.get("/factors/{factor_id}", response_model=EmissionFactor)
def get_factor(factor_id: str) -> EmissionFactor:
    """
    Get an emission factor by its ID.

    Args:
        factor_id: The unique factor ID

    Returns:
        EmissionFactor if found

    Raises:
        HTTPException: 404 if factor not found
    """
    factor = get_emission_factor_by_id(factor_id)
    if factor is None:
        raise HTTPException(status_code=404, detail=f"Factor not found: {factor_id}")
    return factor
