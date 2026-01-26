"""
Unit Normalizer - Normalize engineering unit representations.

Handles common unit variations and aliases found in technical documents.
Normalizes to canonical forms for consistent comparison and validation.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)


@dataclass
class NormalizedValue:
    """Result of unit normalization."""

    original_value: str
    original_unit: str | None
    canonical_unit: str | None
    numeric_value: float | None
    normalization_applied: bool
    confidence: float  # 0-1, how confident we are in the normalization


class UnitNormalizer:
    """Normalize engineering unit representations."""

    # Canonical units mapped to their aliases
    # Format: canonical -> [aliases]
    UNIT_ALIASES: dict[str, list[str]] = {
        # Torque
        "N·m": ["Nm", "N m", "N-m", "N*m", "Newton meter", "Newton-meter", "N.m"],
        "kN·m": ["kNm", "kN m", "kN-m", "kN*m"],
        # Force
        "N": ["Newton", "Newtons"],
        "kN": ["kilo Newton", "kilonewton", "kilo-newton"],
        "MN": ["mega Newton", "meganewton"],
        # Mass
        "kg": ["kilogram", "kilograms", "KG", "Kg", "kilo"],
        "g": ["gram", "grams", "G"],
        "mg": ["milligram", "milligrams"],
        "t": ["tonne", "tonnes", "metric ton", "metric tons"],
        # Length
        "m": ["meter", "meters", "metre", "metres"],
        "mm": ["millimeter", "millimeters", "millimetre", "millimetres"],
        "cm": ["centimeter", "centimeters", "centimetre", "centimetres"],
        "km": ["kilometer", "kilometers", "kilometre", "kilometres"],
        "in": ["inch", "inches", '"'],
        "ft": ["foot", "feet", "'"],
        # Area
        "m²": ["m2", "m^2", "sq m", "square meter", "square meters"],
        "mm²": ["mm2", "mm^2", "sq mm", "square millimeter"],
        "cm²": ["cm2", "cm^2", "sq cm", "square centimeter"],
        # Volume
        "m³": ["m3", "m^3", "cubic meter", "cubic meters"],
        "L": ["l", "liter", "liters", "litre", "litres"],
        "mL": ["ml", "milliliter", "milliliters"],
        # Temperature
        "°C": ["C", "deg C", "degrees C", "degrees Celsius", "Celsius", "degC"],
        "°F": ["F", "deg F", "degrees F", "degrees Fahrenheit", "Fahrenheit", "degF"],
        "K": ["Kelvin", "kelvins"],
        # Pressure
        "Pa": ["pascal", "pascals"],
        "kPa": ["kilopascal", "kilopascals"],
        "MPa": ["megapascal", "megapascals"],
        "bar": ["Bar", "BAR"],
        "psi": ["PSI", "lb/in²", "lb/in2"],
        # Electrical
        "V": ["volt", "volts", "Volt", "Volts"],
        "mV": ["millivolt", "millivolts"],
        "kV": ["kilovolt", "kilovolts"],
        "A": ["amp", "amps", "ampere", "amperes", "Ampere", "Amperes"],
        "mA": ["milliamp", "milliamps", "milliampere"],
        "W": ["watt", "watts", "Watt", "Watts"],
        "kW": ["kilowatt", "kilowatts", "KW"],
        "MW": ["megawatt", "megawatts"],
        "Ω": ["ohm", "ohms", "Ohm", "Ohms"],
        "kΩ": ["kohm", "kilohm", "kilo-ohm"],
        "Hz": ["hertz", "Hertz", "hz", "HZ"],
        "kHz": ["kilohertz", "KHz", "khz"],
        "MHz": ["megahertz", "MHZ", "mhz"],
        # Time
        "s": ["sec", "second", "seconds"],
        "ms": ["millisecond", "milliseconds", "msec"],
        "min": ["minute", "minutes"],
        "h": ["hr", "hour", "hours"],
        # Speed
        "m/s": ["meters per second", "m per s", "mps"],
        "km/h": ["kmh", "km/hr", "kilometers per hour", "kph"],
        "rpm": ["RPM", "r/min", "rev/min", "revolutions per minute"],
        # Angle
        "°": ["deg", "degree", "degrees"],
        "rad": ["radian", "radians"],
        # Percentage
        "%": ["percent", "pct", "percentage"],
        # Dimensionless
        "ppm": ["parts per million"],
        "ppb": ["parts per billion"],
    }

    # Build reverse lookup: alias -> canonical
    _alias_to_canonical: dict[str, str] = {}

    def __init__(self) -> None:
        # Build reverse lookup on init
        if not UnitNormalizer._alias_to_canonical:
            for canonical, aliases in self.UNIT_ALIASES.items():
                for alias in aliases:
                    UnitNormalizer._alias_to_canonical[alias.lower()] = canonical
                # Also map canonical to itself
                UnitNormalizer._alias_to_canonical[canonical.lower()] = canonical

    def normalize(
        self,
        value: str,
        expected_unit: str | None = None,
    ) -> NormalizedValue:
        """
        Normalize a value with its unit.

        Args:
            value: The raw value string (e.g., "24 Volt", "100kg", "25.5 °C")
            expected_unit: Optional expected unit for validation

        Returns:
            NormalizedValue with normalized unit and numeric value
        """
        original_value = value.strip()

        # Parse numeric value and unit from string
        numeric, unit = self._parse_value_unit(original_value)

        # Normalize the unit
        canonical = self._normalize_unit(unit) if unit else None

        # Calculate confidence
        confidence = self._calculate_confidence(
            unit, canonical, expected_unit, numeric
        )

        # Check if normalization was actually applied
        normalization_applied = (
            canonical is not None and unit is not None and unit != canonical
        )

        return NormalizedValue(
            original_value=original_value,
            original_unit=unit,
            canonical_unit=canonical,
            numeric_value=numeric,
            normalization_applied=normalization_applied,
            confidence=confidence,
        )

    def normalize_unit(self, unit: str) -> str:
        """
        Normalize a unit string to its canonical form.

        Args:
            unit: The unit string to normalize

        Returns:
            Canonical unit string
        """
        return self._normalize_unit(unit) or unit

    def _parse_value_unit(self, value: str) -> tuple[float | None, str | None]:
        """Parse numeric value and unit from a string."""
        if not value:
            return None, None

        # Pattern to match number followed by optional unit
        # Handles: "24V", "24 V", "24.5 kg", "-10°C", "1,234.56 mm", "1500 RPM"
        # Use non-greedy patterns and put simpler pattern first
        pattern = r"^([+-]?\d+(?:,\d{3})*(?:\.\d+)?)\s*(.*)$"
        match = re.match(pattern, value.strip())

        if match:
            num_str = match.group(1).replace(",", "")
            unit_str = match.group(2).strip()

            try:
                numeric = float(num_str)
            except ValueError:
                numeric = None

            return numeric, unit_str if unit_str else None

        # Try reverse: unit followed by number (less common)
        pattern_reverse = r"^([A-Za-z°]+)\s*([+-]?\d+(?:\.\d+)?)$"
        match_reverse = re.match(pattern_reverse, value.strip())

        if match_reverse:
            unit_str = match_reverse.group(1).strip()
            num_str = match_reverse.group(2)

            try:
                numeric = float(num_str)
            except ValueError:
                numeric = None

            return numeric, unit_str

        # If no number found, treat entire string as unit or unknown
        # Check if it looks like a unit
        if self._looks_like_unit(value):
            return None, value

        return None, None

    def _looks_like_unit(self, value: str) -> bool:
        """Check if a string looks like a unit."""
        # Known units
        if value.lower() in self._alias_to_canonical:
            return True

        # Short alphanumeric strings are likely units
        if len(value) <= 10 and re.match(r"^[A-Za-z°²³/·\-\s]+$", value):
            return True

        return False

    def _normalize_unit(self, unit: str | None) -> str | None:
        """Normalize a unit to its canonical form."""
        if not unit:
            return None

        # Direct lookup
        canonical = self._alias_to_canonical.get(unit.lower())
        if canonical:
            return canonical

        # Try with normalized whitespace and special chars
        normalized = self._normalize_special_chars(unit)
        canonical = self._alias_to_canonical.get(normalized.lower())
        if canonical:
            return canonical

        # Try without spaces
        no_spaces = unit.replace(" ", "")
        canonical = self._alias_to_canonical.get(no_spaces.lower())
        if canonical:
            return canonical

        # Return original if no normalization found
        return unit

    def _normalize_special_chars(self, unit: str) -> str:
        """Normalize special characters in units."""
        # Normalize multiplication dots
        unit = re.sub(r"[·•*×]", "·", unit)
        # Normalize degree symbols
        unit = unit.replace("º", "°").replace("˚", "°")
        # Normalize superscripts
        unit = unit.replace("²", "2").replace("³", "3")
        # Normalize hyphens
        unit = re.sub(r"[–—−]", "-", unit)

        return unit

    def _calculate_confidence(
        self,
        original_unit: str | None,
        canonical_unit: str | None,
        expected_unit: str | None,
        numeric_value: float | None,
    ) -> float:
        """Calculate confidence in the normalization."""
        confidence = 1.0

        # No unit found
        if not canonical_unit:
            confidence *= 0.5

        # If expected unit provided, check match
        if expected_unit:
            expected_canonical = self._normalize_unit(expected_unit)
            if canonical_unit and expected_canonical:
                if canonical_unit.lower() == expected_canonical.lower():
                    confidence *= 1.0  # Perfect match
                elif self._units_compatible(canonical_unit, expected_canonical):
                    confidence *= 0.8  # Compatible but not exact
                else:
                    confidence *= 0.3  # Mismatch

        # If original unit was normalized, slight penalty
        if original_unit and canonical_unit and original_unit != canonical_unit:
            confidence *= 0.95

        # No numeric value is suspicious
        if numeric_value is None:
            confidence *= 0.7

        return min(1.0, max(0.0, confidence))

    def _units_compatible(self, unit1: str, unit2: str) -> bool:
        """Check if two units are compatible (same dimension)."""
        # Simple compatibility check based on base units
        base_units = {
            "length": {"m", "mm", "cm", "km", "in", "ft"},
            "mass": {"kg", "g", "mg", "t"},
            "time": {"s", "ms", "min", "h"},
            "temperature": {"°C", "°F", "K"},
            "voltage": {"V", "mV", "kV"},
            "current": {"A", "mA"},
            "power": {"W", "kW", "MW"},
            "pressure": {"Pa", "kPa", "MPa", "bar", "psi"},
            "torque": {"N·m", "kN·m"},
        }

        for category, units in base_units.items():
            if unit1 in units and unit2 in units:
                return True

        return False

    def get_unit_category(self, unit: str) -> str | None:
        """Get the category of a unit (e.g., 'length', 'mass')."""
        canonical = self._normalize_unit(unit)
        if not canonical:
            return None

        categories = {
            "length": {"m", "mm", "cm", "km", "in", "ft"},
            "area": {"m²", "mm²", "cm²"},
            "volume": {"m³", "L", "mL"},
            "mass": {"kg", "g", "mg", "t"},
            "time": {"s", "ms", "min", "h"},
            "temperature": {"°C", "°F", "K"},
            "voltage": {"V", "mV", "kV"},
            "current": {"A", "mA"},
            "power": {"W", "kW", "MW"},
            "resistance": {"Ω", "kΩ"},
            "frequency": {"Hz", "kHz", "MHz"},
            "pressure": {"Pa", "kPa", "MPa", "bar", "psi"},
            "force": {"N", "kN", "MN"},
            "torque": {"N·m", "kN·m"},
            "speed": {"m/s", "km/h", "rpm"},
            "angle": {"°", "rad"},
            "ratio": {"%", "ppm", "ppb"},
        }

        for category, units in categories.items():
            if canonical in units:
                return category

        return None
