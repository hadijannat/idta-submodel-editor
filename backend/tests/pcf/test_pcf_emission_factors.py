"""
Tests for emission factors search functionality.
"""

from app.services.pcf.emission_factors import (
    search_emission_factors,
    get_emission_factor_by_id,
    EmissionFactorDB,
)
from app.schemas.pcf import EmissionFactor


class TestEmissionFactorsSearch:
    """Tests for emission factors search."""

    def test_search_returns_matching_factors(self):
        """Search should return factors matching the query."""
        results = search_emission_factors("electricity")
        assert len(results) > 0
        assert all("electricity" in r.name.lower() for r in results)

    def test_search_is_case_insensitive(self):
        """Search should be case insensitive."""
        results_lower = search_emission_factors("electricity")
        results_upper = search_emission_factors("ELECTRICITY")
        assert len(results_lower) == len(results_upper)

    def test_search_returns_empty_for_no_match(self):
        """Search should return empty list when no matches."""
        results = search_emission_factors("xyznonexistent123")
        assert results == []

    def test_search_limits_results(self):
        """Search should respect the limit parameter."""
        # First check if we have enough factors
        all_results = search_emission_factors("", limit=100)
        if len(all_results) > 5:
            limited = search_emission_factors("", limit=5)
            assert len(limited) == 5

    def test_search_by_source(self):
        """Search should match factors by source."""
        results = search_emission_factors("EPA")
        # Should match factors from EPA source
        assert any("epa" in r.source.lower() for r in results)


class TestEmissionFactorById:
    """Tests for getting emission factor by ID."""

    def test_get_existing_factor(self):
        """Should return factor when ID exists."""
        # First get some factors to find a valid ID
        factors = search_emission_factors("", limit=1)
        if factors:
            factor = get_emission_factor_by_id(factors[0].id)
            assert factor is not None
            assert factor.id == factors[0].id

    def test_get_nonexistent_factor_returns_none(self):
        """Should return None for non-existent ID."""
        result = get_emission_factor_by_id("nonexistent-id-12345")
        assert result is None


class TestEmissionFactorDB:
    """Tests for the emission factor database."""

    def test_db_has_factors(self):
        """Database should contain emission factors."""
        db = EmissionFactorDB()
        assert len(db.factors) > 0

    def test_factors_have_required_fields(self):
        """All factors should have required fields."""
        db = EmissionFactorDB()
        for factor in db.factors:
            assert factor.id
            assert factor.name
            assert factor.factor_value > 0
            assert factor.factor_unit
            assert factor.source

    def test_factors_are_valid_pydantic_models(self):
        """All factors should be valid EmissionFactor models."""
        db = EmissionFactorDB()
        for factor in db.factors:
            assert isinstance(factor, EmissionFactor)
