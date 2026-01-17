"""
Emission factors database and search functionality.

Loads emission factors from a versioned dataset file for PCF calculations.
Sources include EPA, DEFRA, IEA, and other recognized authorities.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from app.schemas.pcf import EmissionFactor

PCF_FACTORS_ENV_VAR = "PCF_FACTORS_PATH"
DEFAULT_FACTORS_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "pcf_emission_factors.json"
)


def _resolve_factors_path() -> Path:
    env_path = os.getenv(PCF_FACTORS_ENV_VAR)
    if env_path:
        return Path(env_path).expanduser()
    return DEFAULT_FACTORS_PATH


class EmissionFactorDB:
    """In-memory emission factors database."""

    def __init__(self) -> None:
        dataset = _load_dataset(_resolve_factors_path())
        self.version = dataset.get("version")
        self.sources = dataset.get("sources", [])
        self.factors = [EmissionFactor(**f) for f in dataset.get("factors", [])]
        if not self.factors:
            raise ValueError("PCF emission factors dataset is empty.")
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


def _load_dataset(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(
            f"PCF emission factors dataset not found: {path}"
        )
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("PCF emission factors dataset must be a JSON object.")
    return payload


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


def get_emission_factors_metadata() -> dict:
    """Return metadata about the emission factors dataset."""
    db = _get_db()
    return {
        "version": db.version,
        "sources": db.sources,
        "count": len(db.factors),
    }
