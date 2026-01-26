"""
Rules Engine - Cross-field consistency validation for Magic Import.

Detects inconsistencies between related extracted fields:
- Unit compatibility checks
- Range plausibility validation
- Coupled field relationships (e.g., P = U × I)
- Cardinality compliance
"""

from __future__ import annotations

import logging
import re
from typing import Callable, Literal

from pydantic import BaseModel, Field

from app.schemas.magic_import import (
    ConfidenceReason,
    ConfidenceReasonCode,
    ExtractionHint,
    FieldExtraction,
)

logger = logging.getLogger(__name__)


class ConsistencyWarning(BaseModel):
    """Warning about cross-field inconsistency."""

    paths: list[str] = Field(description="Affected field paths")
    rule: str = Field(description="Rule identifier that triggered warning")
    message: str = Field(description="Human-readable warning message")
    severity: Literal["info", "warning", "error"] = Field(default="warning")
    expected: str | None = Field(default=None, description="Expected value/relationship")
    actual: str | None = Field(default=None, description="Actual value/relationship")


# Type alias for rule functions
RuleFunction = Callable[[dict[str, FieldExtraction], dict[str, ExtractionHint]], list[ConsistencyWarning]]


class RulesEngine:
    """
    Cross-field consistency validation engine.

    Checks extracted values against physical laws, plausibility bounds,
    and semantic constraints to detect potential extraction errors.
    """

    # Plausibility ranges for common physical quantities
    # Format: (min_value, max_value) in SI base units
    PLAUSIBILITY_RULES: dict[str, tuple[float, float]] = {
        # Electrical
        "voltage": (0, 100_000),  # V (up to 100kV)
        "current": (0, 10_000),  # A
        "power": (0, 1e9),  # W (up to 1GW)
        "frequency": (0, 1e12),  # Hz (up to THz)
        "resistance": (0, 1e12),  # Ohm

        # Mechanical
        "mass": (0, 1e9),  # kg
        "length": (0, 1e9),  # m
        "force": (0, 1e12),  # N
        "torque": (0, 1e9),  # Nm
        "pressure": (0, 1e12),  # Pa

        # Thermal
        "temperature": (-273.15, 10_000),  # °C (absolute zero to very high)

        # Ratios
        "efficiency": (0, 100),  # %
        "percentage": (0, 100),  # %

        # Time
        "duration": (0, 1e9),  # seconds
    }

    # Keywords to identify field types for plausibility checking
    FIELD_TYPE_KEYWORDS: dict[str, list[str]] = {
        "voltage": ["voltage", "volt", "spannung", "tension", "emf"],
        "current": ["current", "ampere", "strom", "courant"],
        "power": ["power", "watt", "leistung", "puissance", "rated power"],
        "frequency": ["frequency", "frequenz", "freq", "hz"],
        "resistance": ["resistance", "ohm", "widerstand"],
        "mass": ["mass", "weight", "masse", "gewicht", "poids"],
        "length": ["length", "width", "height", "depth", "dimension", "size"],
        "force": ["force", "kraft", "newton"],
        "torque": ["torque", "drehmoment", "moment"],
        "pressure": ["pressure", "druck", "pascal", "bar"],
        "temperature": ["temperature", "temp", "temperatur", "celsius", "fahrenheit"],
        "efficiency": ["efficiency", "wirkungsgrad", "eta", "rendement"],
        "percentage": ["percent", "prozent", "ratio", "anteil"],
        "duration": ["duration", "time", "dauer", "zeit", "period"],
    }

    # Coupled field relationships: (field1, field2, field3, validation_func)
    # validation_func(v1, v2, v3) → True if relationship holds
    COUPLED_FIELDS: list[tuple[str, str, str, Callable[[float, float, float], bool]]] = [
        # Power = Voltage × Current (with 10% tolerance)
        (
            "RatedPower",
            "RatedVoltage",
            "RatedCurrent",
            lambda p, u, i: abs(p - u * i) < p * 0.10 if p > 0 else True,
        ),
        (
            "Power",
            "Voltage",
            "Current",
            lambda p, u, i: abs(p - u * i) < p * 0.10 if p > 0 else True,
        ),
        # Efficiency relationship (output/input)
        (
            "OutputPower",
            "InputPower",
            "Efficiency",
            lambda out, inp, eff: abs(out / inp * 100 - eff) < 5 if inp > 0 else True,
        ),
    ]

    def __init__(self) -> None:
        self._custom_rules: list[RuleFunction] = []

    def register_rule(self, rule: RuleFunction) -> None:
        """Register a custom validation rule."""
        self._custom_rules.append(rule)

    def check_consistency(
        self,
        extractions: list[FieldExtraction],
        hints: list[ExtractionHint],
    ) -> list[ConsistencyWarning]:
        """
        Run all consistency checks on extractions.

        Args:
            extractions: List of extracted field values
            hints: Extraction hints with field metadata

        Returns:
            List of consistency warnings
        """
        warnings: list[ConsistencyWarning] = []

        # Build lookup dictionaries
        extractions_by_path = {e.path: e for e in extractions}
        hints_by_path = {h.path: h for h in hints}

        # Run built-in checks
        warnings.extend(self._check_unit_compatibility(extractions_by_path, hints_by_path))
        warnings.extend(self._check_range_plausibility(extractions_by_path, hints_by_path))
        warnings.extend(self._check_coupled_fields(extractions_by_path))
        warnings.extend(self._check_cardinality(extractions_by_path, hints_by_path))

        # Run custom rules
        for rule in self._custom_rules:
            try:
                warnings.extend(rule(extractions_by_path, hints_by_path))
            except Exception as e:
                logger.warning("Custom rule failed: %s", e)

        logger.info(
            "Consistency check complete: %d warnings from %d extractions",
            len(warnings),
            len(extractions),
        )

        return warnings

    def _check_unit_compatibility(
        self,
        extractions: dict[str, FieldExtraction],
        hints: dict[str, ExtractionHint],
    ) -> list[ConsistencyWarning]:
        """Check that extracted values have compatible units with hints."""
        warnings: list[ConsistencyWarning] = []

        # Common unit categories for compatibility checking
        unit_categories = {
            "length": ["m", "cm", "mm", "km", "in", "ft", "meter", "centimeter"],
            "mass": ["kg", "g", "mg", "lb", "oz", "kilogram", "gram"],
            "time": ["s", "ms", "min", "h", "second", "minute", "hour"],
            "power": ["W", "kW", "MW", "watt", "kilowatt"],
            "voltage": ["V", "kV", "mV", "volt"],
            "current": ["A", "mA", "ampere"],
            "temperature": ["°C", "°F", "K", "celsius", "fahrenheit", "kelvin"],
        }

        for path, extraction in extractions.items():
            if not extraction.value_raw:
                continue

            hint = hints.get(path)
            if not hint:
                continue

            # Extract unit from value
            extracted_unit = self._extract_unit_from_value(extraction.value_raw)
            if not extracted_unit:
                continue

            # Check if hint has expected unit info (from semantic label or keywords)
            expected_category = None
            for category, units in unit_categories.items():
                if any(u.lower() in (hint.semantic_label or "").lower() for u in units):
                    expected_category = category
                    break
                if any(u.lower() in " ".join(hint.keywords).lower() for u in units):
                    expected_category = category
                    break

            if expected_category:
                # Check if extracted unit is in the expected category
                category_units = unit_categories.get(expected_category, [])
                if not any(u.lower() in extracted_unit.lower() for u in category_units):
                    # Also check if extracted unit is in any other category
                    for other_cat, other_units in unit_categories.items():
                        if other_cat != expected_category and any(
                            u.lower() in extracted_unit.lower() for u in other_units
                        ):
                            warnings.append(
                                ConsistencyWarning(
                                    paths=[path],
                                    rule="unit_compatibility",
                                    message=f"Unit mismatch: found '{extracted_unit}' ({other_cat}) but expected {expected_category}",
                                    severity="warning",
                                    expected=expected_category,
                                    actual=extracted_unit,
                                )
                            )
                            break

        return warnings

    def _extract_unit_from_value(self, value: str) -> str | None:
        """Extract unit suffix from a value string."""
        if not value:
            return None

        # Pattern: number followed by unit
        match = re.search(r"[\d.,]+\s*([a-zA-Z°%/]+(?:\s*[a-zA-Z°%/]+)?)\s*$", value)
        if match:
            return match.group(1).strip()
        return None

    def _check_range_plausibility(
        self,
        extractions: dict[str, FieldExtraction],
        hints: dict[str, ExtractionHint],
    ) -> list[ConsistencyWarning]:
        """Check that numeric values fall within plausible ranges."""
        warnings: list[ConsistencyWarning] = []

        for path, extraction in extractions.items():
            if not extraction.value_raw:
                continue

            # Try to parse numeric value
            numeric_value = self._parse_numeric_value(extraction.value_raw)
            if numeric_value is None:
                continue

            # Determine field type from path and hints
            field_type = self._infer_field_type(path, hints.get(path))
            if not field_type or field_type not in self.PLAUSIBILITY_RULES:
                continue

            min_val, max_val = self.PLAUSIBILITY_RULES[field_type]

            if numeric_value < min_val or numeric_value > max_val:
                severity = "error" if numeric_value < 0 and min_val >= 0 else "warning"
                warnings.append(
                    ConsistencyWarning(
                        paths=[path],
                        rule="range_plausibility",
                        message=f"Value {numeric_value} outside plausible range [{min_val}, {max_val}] for {field_type}",
                        severity=severity,
                        expected=f"[{min_val}, {max_val}]",
                        actual=str(numeric_value),
                    )
                )

        return warnings

    def _parse_numeric_value(self, value: str) -> float | None:
        """Parse numeric value from string, handling various formats."""
        if not value:
            return None

        # Remove common non-numeric suffixes
        cleaned = re.sub(r"[a-zA-Z°%]+\s*$", "", value).strip()
        # Handle European decimal notation
        cleaned = cleaned.replace(" ", "").replace("'", "")

        # Handle comma as decimal separator
        if "," in cleaned and "." not in cleaned:
            cleaned = cleaned.replace(",", ".")
        elif "," in cleaned and "." in cleaned:
            # Assume comma is thousands separator
            cleaned = cleaned.replace(",", "")

        try:
            return float(cleaned)
        except ValueError:
            return None

    def _infer_field_type(
        self, path: str, hint: ExtractionHint | None
    ) -> str | None:
        """Infer the physical quantity type from path and hint."""
        search_text = path.lower()
        if hint:
            search_text += " " + (hint.semantic_label or "").lower()
            search_text += " " + " ".join(hint.keywords).lower()

        for field_type, keywords in self.FIELD_TYPE_KEYWORDS.items():
            if any(kw in search_text for kw in keywords):
                return field_type

        return None

    def _check_coupled_fields(
        self,
        extractions: dict[str, FieldExtraction],
    ) -> list[ConsistencyWarning]:
        """Check relationships between coupled fields (e.g., P = U × I)."""
        warnings: list[ConsistencyWarning] = []

        for field1, field2, field3, validator in self.COUPLED_FIELDS:
            # Find matching extractions (case-insensitive suffix match)
            ext1 = self._find_extraction_by_suffix(extractions, field1)
            ext2 = self._find_extraction_by_suffix(extractions, field2)
            ext3 = self._find_extraction_by_suffix(extractions, field3)

            if not all([ext1, ext2, ext3]):
                continue

            # Parse numeric values
            val1 = self._parse_numeric_value(ext1.value_raw)
            val2 = self._parse_numeric_value(ext2.value_raw)
            val3 = self._parse_numeric_value(ext3.value_raw)

            if val1 is None or val2 is None or val3 is None:
                continue

            # Check relationship
            try:
                if not validator(val1, val2, val3):
                    warnings.append(
                        ConsistencyWarning(
                            paths=[ext1.path, ext2.path, ext3.path],
                            rule="coupled_fields",
                            message=f"Coupled field relationship violated: {field1}={val1}, {field2}={val2}, {field3}={val3}",
                            severity="warning",
                            expected=f"{field1} = {field2} × {field3}",
                            actual=f"{val1} ≠ {val2} × {val3}",
                        )
                    )
            except Exception as e:
                logger.debug("Coupled field check failed: %s", e)

        return warnings

    def _find_extraction_by_suffix(
        self,
        extractions: dict[str, FieldExtraction],
        suffix: str,
    ) -> FieldExtraction | None:
        """Find extraction whose path ends with given suffix (case-insensitive)."""
        suffix_lower = suffix.lower()
        for path, extraction in extractions.items():
            if path.lower().endswith(suffix_lower):
                return extraction
        return None

    def _check_cardinality(
        self,
        extractions: dict[str, FieldExtraction],
        hints: dict[str, ExtractionHint],
    ) -> list[ConsistencyWarning]:
        """Check that extractions respect cardinality constraints from hints."""
        warnings: list[ConsistencyWarning] = []

        for path, hint in hints.items():
            extraction = extractions.get(path)

            # Check required fields
            if hint.required:
                if not extraction or not extraction.value_raw:
                    warnings.append(
                        ConsistencyWarning(
                            paths=[path],
                            rule="cardinality_required",
                            message=f"Required field '{hint.label}' has no extracted value",
                            severity="warning",
                        )
                    )

        return warnings

    def apply_warnings_to_extractions(
        self,
        extractions: list[FieldExtraction],
        warnings: list[ConsistencyWarning],
    ) -> list[FieldExtraction]:
        """
        Apply consistency warnings to extraction confidence reasons.

        Args:
            extractions: Original extractions
            warnings: Consistency warnings to apply

        Returns:
            Updated extractions with warning reasons added
        """
        # Build path → warnings mapping
        warnings_by_path: dict[str, list[ConsistencyWarning]] = {}
        for warning in warnings:
            for path in warning.paths:
                warnings_by_path.setdefault(path, []).append(warning)

        updated: list[FieldExtraction] = []
        for extraction in extractions:
            path_warnings = warnings_by_path.get(extraction.path, [])

            if not path_warnings:
                updated.append(extraction)
                continue

            # Add warning reasons
            new_reasons = list(extraction.confidence_reasons)
            for warning in path_warnings:
                new_reasons.append(
                    ConfidenceReason(
                        code=ConfidenceReasonCode.SEMANTIC_CONSTRAINT_VIOLATION,
                        message=warning.message,
                        severity=warning.severity,
                        detail={
                            "rule": warning.rule,
                            "expected": warning.expected,
                            "actual": warning.actual,
                        },
                    )
                )

            updated.append(
                extraction.model_copy(update={"confidence_reasons": new_reasons})
            )

        return updated
