"""
Emission factors database and search functionality.

Provides a local database of common emission factors for PCF calculations.
Sources include EPA, DEFRA, IEA, and other recognized authorities.
"""

from __future__ import annotations

from app.schemas.pcf import EmissionFactor


# Sample emission factors database
# In production, this could be loaded from a JSON/CSV file or external service
EMISSION_FACTORS_DATA = [
    # Electricity (Scope 2)
    {
        "id": "ef-electricity-us-avg",
        "name": "Electricity - US Average Grid",
        "factor_value": 0.417,
        "factor_unit": "kg CO2e/kWh",
        "source": "EPA eGRID 2022",
        "region": "US",
        "year": 2022,
    },
    {
        "id": "ef-electricity-eu-avg",
        "name": "Electricity - EU Average Grid",
        "factor_value": 0.295,
        "factor_unit": "kg CO2e/kWh",
        "source": "EEA 2022",
        "region": "EU",
        "year": 2022,
    },
    {
        "id": "ef-electricity-germany",
        "name": "Electricity - Germany Grid",
        "factor_value": 0.366,
        "factor_unit": "kg CO2e/kWh",
        "source": "UBA 2022",
        "region": "Germany",
        "year": 2022,
    },
    {
        "id": "ef-electricity-uk",
        "name": "Electricity - UK Grid",
        "factor_value": 0.212,
        "factor_unit": "kg CO2e/kWh",
        "source": "DEFRA 2023",
        "region": "UK",
        "year": 2023,
    },
    # Natural Gas (Scope 1)
    {
        "id": "ef-natural-gas-kwh",
        "name": "Natural Gas Combustion",
        "factor_value": 0.185,
        "factor_unit": "kg CO2e/kWh",
        "source": "EPA 2022",
        "region": None,
        "year": 2022,
    },
    {
        "id": "ef-natural-gas-m3",
        "name": "Natural Gas Combustion",
        "factor_value": 2.02,
        "factor_unit": "kg CO2e/m³",
        "source": "EPA 2022",
        "region": None,
        "year": 2022,
    },
    # Diesel (Scope 1)
    {
        "id": "ef-diesel-liter",
        "name": "Diesel Combustion",
        "factor_value": 2.68,
        "factor_unit": "kg CO2e/L",
        "source": "EPA 2022",
        "region": None,
        "year": 2022,
    },
    {
        "id": "ef-diesel-kg",
        "name": "Diesel Combustion",
        "factor_value": 3.16,
        "factor_unit": "kg CO2e/kg",
        "source": "DEFRA 2023",
        "region": "UK",
        "year": 2023,
    },
    # Gasoline/Petrol (Scope 1)
    {
        "id": "ef-gasoline-liter",
        "name": "Gasoline/Petrol Combustion",
        "factor_value": 2.31,
        "factor_unit": "kg CO2e/L",
        "source": "EPA 2022",
        "region": None,
        "year": 2022,
    },
    # Transport (Scope 3)
    {
        "id": "ef-road-freight-truck",
        "name": "Road Freight - Heavy Truck",
        "factor_value": 0.107,
        "factor_unit": "kg CO2e/tkm",
        "source": "DEFRA 2023",
        "region": "UK",
        "year": 2023,
    },
    {
        "id": "ef-road-freight-van",
        "name": "Road Freight - Van",
        "factor_value": 0.612,
        "factor_unit": "kg CO2e/tkm",
        "source": "DEFRA 2023",
        "region": "UK",
        "year": 2023,
    },
    {
        "id": "ef-air-freight-long",
        "name": "Air Freight - Long Haul",
        "factor_value": 0.602,
        "factor_unit": "kg CO2e/tkm",
        "source": "DEFRA 2023",
        "region": None,
        "year": 2023,
    },
    {
        "id": "ef-sea-freight-container",
        "name": "Sea Freight - Container Ship",
        "factor_value": 0.016,
        "factor_unit": "kg CO2e/tkm",
        "source": "DEFRA 2023",
        "region": None,
        "year": 2023,
    },
    # Materials (Scope 3)
    {
        "id": "ef-steel-primary",
        "name": "Steel - Primary Production",
        "factor_value": 2.1,
        "factor_unit": "kg CO2e/kg",
        "source": "ecoinvent 3.9",
        "region": "Global",
        "year": 2022,
    },
    {
        "id": "ef-steel-recycled",
        "name": "Steel - Recycled",
        "factor_value": 0.4,
        "factor_unit": "kg CO2e/kg",
        "source": "ecoinvent 3.9",
        "region": "Global",
        "year": 2022,
    },
    {
        "id": "ef-aluminum-primary",
        "name": "Aluminum - Primary Production",
        "factor_value": 11.5,
        "factor_unit": "kg CO2e/kg",
        "source": "ecoinvent 3.9",
        "region": "Global",
        "year": 2022,
    },
    {
        "id": "ef-aluminum-recycled",
        "name": "Aluminum - Recycled",
        "factor_value": 0.5,
        "factor_unit": "kg CO2e/kg",
        "source": "ecoinvent 3.9",
        "region": "Global",
        "year": 2022,
    },
    {
        "id": "ef-plastic-hdpe",
        "name": "Plastic - HDPE",
        "factor_value": 1.9,
        "factor_unit": "kg CO2e/kg",
        "source": "ecoinvent 3.9",
        "region": "Global",
        "year": 2022,
    },
    {
        "id": "ef-plastic-pet",
        "name": "Plastic - PET",
        "factor_value": 2.7,
        "factor_unit": "kg CO2e/kg",
        "source": "ecoinvent 3.9",
        "region": "Global",
        "year": 2022,
    },
    # Water
    {
        "id": "ef-water-supply",
        "name": "Water Supply",
        "factor_value": 0.344,
        "factor_unit": "kg CO2e/m³",
        "source": "DEFRA 2023",
        "region": "UK",
        "year": 2023,
    },
    {
        "id": "ef-water-treatment",
        "name": "Water Treatment",
        "factor_value": 0.708,
        "factor_unit": "kg CO2e/m³",
        "source": "DEFRA 2023",
        "region": "UK",
        "year": 2023,
    },
]


class EmissionFactorDB:
    """In-memory emission factors database."""

    def __init__(self) -> None:
        self.factors = [EmissionFactor(**f) for f in EMISSION_FACTORS_DATA]
        self._by_id = {f.id: f for f in self.factors}

    def search(self, query: str, limit: int = 20) -> list[EmissionFactor]:
        """
        Search emission factors by name or source.

        Args:
            query: Search query (case-insensitive)
            limit: Maximum number of results

        Returns:
            List of matching emission factors
        """
        query_lower = query.lower()

        if not query_lower:
            return self.factors[:limit]

        results = []
        for factor in self.factors:
            if (
                query_lower in factor.name.lower()
                or query_lower in factor.source.lower()
                or (factor.region and query_lower in factor.region.lower())
            ):
                results.append(factor)
                if len(results) >= limit:
                    break

        return results

    def get_by_id(self, factor_id: str) -> EmissionFactor | None:
        """Get an emission factor by its ID."""
        return self._by_id.get(factor_id)


# Singleton instance
_db: EmissionFactorDB | None = None


def _get_db() -> EmissionFactorDB:
    """Get or create the emission factors database."""
    global _db
    if _db is None:
        _db = EmissionFactorDB()
    return _db


def search_emission_factors(query: str, limit: int = 20) -> list[EmissionFactor]:
    """
    Search emission factors by name, source, or region.

    Args:
        query: Search query (case-insensitive)
        limit: Maximum number of results

    Returns:
        List of matching emission factors
    """
    return _get_db().search(query, limit)


def get_emission_factor_by_id(factor_id: str) -> EmissionFactor | None:
    """
    Get an emission factor by its ID.

    Args:
        factor_id: The unique factor ID

    Returns:
        EmissionFactor if found, None otherwise
    """
    return _get_db().get_by_id(factor_id)
