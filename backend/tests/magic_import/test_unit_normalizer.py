"""Tests for UnitNormalizer."""

import pytest

from app.services.magic_import.unit_normalizer import UnitNormalizer


@pytest.fixture
def normalizer():
    """Create a UnitNormalizer instance."""
    return UnitNormalizer()


class TestUnitNormalization:
    """Tests for unit normalization."""

    def test_normalize_torque_nm(self, normalizer):
        """Test normalization of torque units."""
        result = normalizer.normalize("100 Nm")
        assert result.canonical_unit == "N·m"
        assert result.numeric_value == 100.0
        assert result.normalization_applied is True

    def test_normalize_torque_variations(self, normalizer):
        """Test various torque unit formats."""
        variations = ["Nm", "N m", "N-m", "N*m", "N.m"]
        for variant in variations:
            result = normalizer.normalize(f"50 {variant}")
            assert result.canonical_unit == "N·m", f"Failed for {variant}"

    def test_normalize_voltage(self, normalizer):
        """Test voltage normalization."""
        result = normalizer.normalize("24 Volt")
        assert result.canonical_unit == "V"
        assert result.numeric_value == 24.0

    def test_normalize_mass_kg(self, normalizer):
        """Test mass normalization."""
        assert normalizer.normalize("100 kg").canonical_unit == "kg"
        assert normalizer.normalize("100 KG").canonical_unit == "kg"
        assert normalizer.normalize("100 kilogram").canonical_unit == "kg"

    def test_normalize_temperature(self, normalizer):
        """Test temperature normalization."""
        assert normalizer.normalize("25°C").canonical_unit == "°C"
        assert normalizer.normalize("25 deg C").canonical_unit == "°C"
        assert normalizer.normalize("-10 degrees Celsius").canonical_unit == "°C"

    def test_normalize_pressure(self, normalizer):
        """Test pressure normalization."""
        assert normalizer.normalize("1.5 bar").canonical_unit == "bar"
        assert normalizer.normalize("100 kPa").canonical_unit == "kPa"
        assert normalizer.normalize("14.7 psi").canonical_unit == "psi"

    def test_normalize_electrical(self, normalizer):
        """Test electrical unit normalization."""
        assert normalizer.normalize("230V").canonical_unit == "V"
        assert normalizer.normalize("500 mA").canonical_unit == "mA"
        assert normalizer.normalize("1.5 kW").canonical_unit == "kW"
        assert normalizer.normalize("50 Hz").canonical_unit == "Hz"

    def test_normalize_length(self, normalizer):
        """Test length normalization."""
        assert normalizer.normalize("100 mm").canonical_unit == "mm"
        assert normalizer.normalize("2.5 meters").canonical_unit == "m"
        assert normalizer.normalize("10 cm").canonical_unit == "cm"

    def test_normalize_area(self, normalizer):
        """Test area normalization."""
        assert normalizer.normalize("100 m2").canonical_unit == "m²"
        assert normalizer.normalize("50 mm^2").canonical_unit == "mm²"

    def test_normalize_speed(self, normalizer):
        """Test speed normalization."""
        assert normalizer.normalize("1500 RPM").canonical_unit == "rpm"
        assert normalizer.normalize("100 km/h").canonical_unit == "km/h"


class TestValueParsing:
    """Tests for value parsing."""

    def test_parse_integer_with_unit(self, normalizer):
        """Test parsing integer values."""
        result = normalizer.normalize("100 kg")
        assert result.numeric_value == 100.0
        assert result.original_unit == "kg"

    def test_parse_decimal_with_unit(self, normalizer):
        """Test parsing decimal values."""
        result = normalizer.normalize("25.5 °C")
        assert result.numeric_value == 25.5
        assert result.canonical_unit == "°C"

    def test_parse_negative_value(self, normalizer):
        """Test parsing negative values."""
        result = normalizer.normalize("-40 °C")
        assert result.numeric_value == -40.0

    def test_parse_thousands_separator(self, normalizer):
        """Test parsing values with thousands separator."""
        result = normalizer.normalize("1,234.56 mm")
        assert result.numeric_value == 1234.56

    def test_parse_no_space(self, normalizer):
        """Test parsing value without space."""
        result = normalizer.normalize("24V")
        assert result.numeric_value == 24.0
        assert result.canonical_unit == "V"

    def test_parse_unit_only(self, normalizer):
        """Test parsing unit without value."""
        result = normalizer.normalize("kg")
        assert result.numeric_value is None
        assert result.canonical_unit == "kg"

    def test_parse_percentage(self, normalizer):
        """Test parsing percentage values."""
        result = normalizer.normalize("95%")
        assert result.numeric_value == 95.0
        assert result.canonical_unit == "%"


class TestConfidence:
    """Tests for confidence calculation."""

    def test_confidence_with_expected_match(self, normalizer):
        """Test confidence when expected unit matches."""
        result = normalizer.normalize("24 V", expected_unit="V")
        assert result.confidence >= 0.9

    def test_confidence_with_expected_mismatch(self, normalizer):
        """Test confidence when expected unit doesn't match."""
        result = normalizer.normalize("24 V", expected_unit="A")
        assert result.confidence < 0.5

    def test_confidence_with_compatible_units(self, normalizer):
        """Test confidence when units are compatible."""
        result = normalizer.normalize("24 mV", expected_unit="V")
        assert 0.5 <= result.confidence <= 0.9

    def test_confidence_no_unit(self, normalizer):
        """Test confidence when no unit found."""
        result = normalizer.normalize("100")
        assert result.confidence < 1.0


class TestNormalizeUnit:
    """Tests for direct unit normalization."""

    def test_normalize_unit_direct(self, normalizer):
        """Test direct unit normalization method."""
        assert normalizer.normalize_unit("Nm") == "N·m"
        assert normalizer.normalize_unit("kg") == "kg"
        assert normalizer.normalize_unit("V") == "V"

    def test_normalize_unknown_unit(self, normalizer):
        """Test normalization of unknown unit."""
        result = normalizer.normalize_unit("unknown_unit")
        assert result == "unknown_unit"  # Returns original if not found


class TestUnitCategory:
    """Tests for unit categorization."""

    def test_get_category_length(self, normalizer):
        """Test length category."""
        assert normalizer.get_unit_category("m") == "length"
        assert normalizer.get_unit_category("mm") == "length"

    def test_get_category_mass(self, normalizer):
        """Test mass category."""
        assert normalizer.get_unit_category("kg") == "mass"

    def test_get_category_temperature(self, normalizer):
        """Test temperature category."""
        assert normalizer.get_unit_category("°C") == "temperature"

    def test_get_category_electrical(self, normalizer):
        """Test electrical categories."""
        assert normalizer.get_unit_category("V") == "voltage"
        assert normalizer.get_unit_category("A") == "current"
        assert normalizer.get_unit_category("W") == "power"

    def test_get_category_unknown(self, normalizer):
        """Test unknown unit category."""
        assert normalizer.get_unit_category("unknown") is None


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_string(self, normalizer):
        """Test empty string input."""
        result = normalizer.normalize("")
        assert result.numeric_value is None
        assert result.canonical_unit is None

    def test_whitespace_only(self, normalizer):
        """Test whitespace-only input."""
        result = normalizer.normalize("   ")
        assert result.numeric_value is None

    def test_special_characters(self, normalizer):
        """Test special character handling."""
        # Different multiplication dots should normalize
        result = normalizer.normalize("100 N·m")
        assert result.canonical_unit == "N·m"

    def test_unicode_degree(self, normalizer):
        """Test unicode degree symbol variations."""
        result = normalizer.normalize("25°C")
        assert result.canonical_unit == "°C"
