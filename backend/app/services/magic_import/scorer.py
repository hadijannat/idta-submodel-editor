"""
Confidence Scorer - Combine LLM and localization signals into final confidence.

Produces ConfidenceBreakdown and sets needs_review based on threshold.
"""

from __future__ import annotations

import re
from typing import Any

from app.schemas.magic_import import ConfidenceBreakdown, FieldExtraction, PDFIndex


class ConfidenceScorer:
    """Compute confidence scores for extracted fields."""

    # Weight for each signal in the final confidence score
    WEIGHT_LLM = 0.35
    WEIGHT_LOCALIZER = 0.40
    WEIGHT_OCR = 0.15
    WEIGHT_RULES = 0.10

    def __init__(self) -> None:
        pass

    def _normalize_value(self, value: str) -> int | float | bool | str:
        """Normalize a string value to its appropriate type."""
        if not value:
            return value

        value_stripped = value.strip()

        # Check for boolean
        if value_stripped.lower() in ("true", "yes", "1"):
            return True
        if value_stripped.lower() in ("false", "no", "0"):
            return False

        # Check for integer
        try:
            return int(value_stripped)
        except ValueError:
            pass

        # Check for float
        try:
            return float(value_stripped)
        except ValueError:
            pass

        # Return as string
        return value_stripped

    def _validate_format(self, value: str) -> float:
        """Validate value format and return a score between 0 and 1."""
        if not value:
            return 1.0

        # Penalize very long values
        if len(value) > 500:
            return 0.5

        # Penalize values with too many special characters
        special_chars = sum(1 for c in value if not c.isalnum() and not c.isspace())
        if special_chars > len(value) * 0.3:
            return 0.7

        return 1.0

    def _value_in_evidence(self, value: str, evidence_quote: str | None) -> bool:
        """Check whether the extracted value appears in the evidence quote."""
        if not value or not evidence_quote:
            return False
        return value.strip().lower() in evidence_quote.strip().lower()

    def validate_against_type(self, value: str, value_type: str) -> float:
        """Validate a value against an expected XSD type."""
        if not value:
            return 1.0

        value_clean = value.strip()
        value_lower = value_clean.lower()
        type_clean = (value_type or "").strip()
        if type_clean.startswith("xsd:"):
            type_clean = "xs:" + type_clean[4:]

        # xs:string accepts anything
        if type_clean in ("xs:string", "string"):
            return 1.0

        def normalize_number(raw: str) -> str:
            # Remove spaces and apostrophes used as thousands separators
            cleaned = raw.replace(" ", "").replace("'", "")
            if "," in cleaned and "." in cleaned:
                last_comma = cleaned.rfind(",")
                last_dot = cleaned.rfind(".")
                if last_comma > last_dot:
                    cleaned = cleaned.replace(".", "")
                    cleaned = cleaned.replace(",", ".")
                else:
                    cleaned = cleaned.replace(",", "")
            elif "," in cleaned and "." not in cleaned:
                cleaned = cleaned.replace(",", ".")
            return cleaned

        # xs:int / xs:integer
        if type_clean in ("xs:int", "xs:integer", "int", "integer"):
            try:
                normalized = normalize_number(value_clean)
                number = float(normalized)
                if not number.is_integer():
                    return 0.5
                return 1.0
            except ValueError:
                return 0.5

        # xs:float / xs:double / xs:decimal
        if type_clean in ("xs:float", "xs:double", "xs:decimal", "float", "double", "decimal"):
            try:
                normalized = normalize_number(value_clean)
                float(normalized)
                return 1.0
            except ValueError:
                return 0.5

        # xs:boolean
        if type_clean in ("xs:boolean", "boolean"):
            if value_lower in ("true", "false", "yes", "no", "1", "0"):
                return 1.0
            return 0.5

        # xs:date
        if type_clean in ("xs:date", "date"):
            # Simple date pattern check
            if re.match(r"^\d{4}-\d{2}-\d{2}$", value_clean):
                return 1.0
            return 0.5

        # xs:time
        if type_clean in ("xs:time", "time"):
            iso = value_clean.replace("Z", "+00:00")
            try:
                from datetime import time

                time.fromisoformat(iso)
                return 1.0
            except ValueError:
                return 0.5

        # xs:dateTime
        if type_clean in ("xs:dateTime", "dateTime"):
            # Accept ISO with optional milliseconds and timezone
            iso = value_clean.replace(" ", "T").replace("Z", "+00:00")
            try:
                from datetime import datetime

                datetime.fromisoformat(iso)
                return 1.0
            except ValueError:
                pass
            if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", value_clean):
                return 1.0
            return 0.5

        # xs:gYear
        if type_clean in ("xs:gYear", "gYear"):
            if re.match(r"^\d{4}(?:Z|[+-]\d{2}:\d{2})?$", value_clean):
                return 1.0
            return 0.5

        # xs:gYearMonth
        if type_clean in ("xs:gYearMonth", "gYearMonth"):
            if re.match(r"^\d{4}-\d{2}(?:Z|[+-]\d{2}:\d{2})?$", value_clean):
                return 1.0
            return 0.5

        # xs:gMonthDay
        if type_clean in ("xs:gMonthDay", "gMonthDay"):
            if re.match(r"^--\d{2}-\d{2}(?:Z|[+-]\d{2}:\d{2})?$", value_clean):
                return 1.0
            return 0.5

        # xs:gMonth
        if type_clean in ("xs:gMonth", "gMonth"):
            if re.match(r"^--\d{2}(?:Z|[+-]\d{2}:\d{2})?$", value_clean):
                return 1.0
            return 0.5

        # xs:gDay
        if type_clean in ("xs:gDay", "gDay"):
            if re.match(r"^---\d{2}(?:Z|[+-]\d{2}:\d{2})?$", value_clean):
                return 1.0
            return 0.5

        # xs:duration (ISO 8601 duration)
        if type_clean in ("xs:duration", "duration"):
            if re.match(
                r"^P(?!$)(\d+Y)?(\d+M)?(\d+D)?(T(\d+H)?(\d+M)?(\d+(\.\d+)?S)?)?$",
                value_clean,
            ):
                return 1.0
            return 0.5

        # xs:anyURI
        if type_clean in ("xs:anyURI", "anyURI"):
            try:
                from urllib.parse import urlparse

                parsed = urlparse(value_clean)
                if parsed.scheme and parsed.netloc:
                    return 1.0
                # Accept URN/URN-like identifiers
                if value_lower.startswith("urn:"):
                    return 1.0
                # Accept relative/fragment URIs as weak signal
                if value_clean.startswith("#"):
                    return 0.7
                return 0.5
            except Exception:
                return 0.5

        # xs:hexBinary
        if type_clean in ("xs:hexBinary", "hexBinary"):
            if re.match(r"^[0-9A-Fa-f]+$", value_clean) and len(value_clean) % 2 == 0:
                return 1.0
            return 0.5

        # xs:base64Binary
        if type_clean in ("xs:base64Binary", "base64Binary"):
            # Accept standard/base64url with optional padding
            if re.match(r"^[A-Za-z0-9+/_-]*={0,2}$", value_clean):
                return 0.8
            return 0.5

        # Default: accept
        return 1.0

    def _calculate_ocr_quality(self, index: PDFIndex) -> float:
        """Calculate overall OCR quality from the PDF index."""
        if not index.words:
            return 1.0

        ocr_words = [w for w in index.words if w.method == "OCR"]
        if not ocr_words:
            return 1.0

        # Average confidence of OCR words
        total_confidence = sum(w.confidence for w in ocr_words)
        return total_confidence / len(ocr_words)

    def recalculate_after_edit(
        self,
        extraction: FieldExtraction,
        new_value: str,
    ) -> FieldExtraction:
        """Recalculate scores after user edits a value."""
        return extraction.model_copy(
            update={
                "value_raw": new_value,
                "confidence": 1.0,  # User-edited values are fully trusted
                "user_edited": True,
                "needs_review": False,
            }
        )

    def mark_approved(self, extraction: FieldExtraction) -> FieldExtraction:
        """Mark an extraction as user-approved."""
        return extraction.model_copy(
            update={
                "user_approved": True,
                "needs_review": False,
            }
        )

    def score_all(
        self,
        extractions: list[FieldExtraction],
        index: PDFIndex,
        confidence_threshold: float = 0.80,
    ) -> list[FieldExtraction]:
        """Score all extractions and mark those below threshold for review."""
        ocr_quality = self._calculate_ocr_quality(index)
        scored: list[FieldExtraction] = []

        for extraction in extractions:
            normalized_value = self._normalize_value(extraction.value_raw)

            # Get component scores
            llm_score = float(extraction.confidence or 0.5)

            localizer_score = (
                extraction.evidence.locator_score
                if extraction.evidence is not None
                else 0.5
            )

            # OCR score based on method and quality
            if extraction.evidence is not None and extraction.evidence.method == "OCR":
                ocr_score = ocr_quality
            else:
                ocr_score = 1.0

            # Rules score based on format validation + optional type validation
            rules_score = self._validate_format(extraction.value_raw)
            if extraction.value_type:
                rules_score *= self.validate_against_type(
                    extraction.value_raw, extraction.value_type
                )
            if extraction.value_raw and extraction.value_raw.strip().lower() in (
                "n/a",
                "na",
                "unknown",
                "not available",
                "-",
            ):
                rules_score *= 0.4

            if extraction.evidence is not None:
                if not self._value_in_evidence(
                    extraction.value_raw, extraction.evidence.quote
                ):
                    rules_score *= 0.6
            else:
                rules_score *= 0.7

            # Weighted combination
            overall = (
                self.WEIGHT_LLM * llm_score
                + self.WEIGHT_LOCALIZER * localizer_score
                + self.WEIGHT_OCR * ocr_score
                + self.WEIGHT_RULES * rules_score
            )

            breakdown = ConfidenceBreakdown(
                llm=llm_score,
                localizer=localizer_score,
                ocr=ocr_score,
                rules=rules_score,
            )

            scored.append(
                extraction.model_copy(
                    update={
                        "confidence": round(overall, 3),
                        "confidence_breakdown": breakdown,
                        "needs_review": overall < confidence_threshold,
                        "value_normalized": normalized_value,
                    }
                )
            )

        return scored
