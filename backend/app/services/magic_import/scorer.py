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

        # xs:string accepts anything
        if value_type in ("xs:string", "string"):
            return 1.0

        # xs:int / xs:integer
        if value_type in ("xs:int", "xs:integer", "int", "integer"):
            try:
                int(value.strip())
                return 1.0
            except ValueError:
                return 0.5

        # xs:float / xs:double / xs:decimal
        if value_type in ("xs:float", "xs:double", "xs:decimal", "float", "double", "decimal"):
            try:
                float(value.strip())
                return 1.0
            except ValueError:
                return 0.5

        # xs:boolean
        if value_type in ("xs:boolean", "boolean"):
            if value.strip().lower() in ("true", "false", "yes", "no", "1", "0"):
                return 1.0
            return 0.5

        # xs:date
        if value_type in ("xs:date", "date"):
            # Simple date pattern check
            if re.match(r"^\d{4}-\d{2}-\d{2}$", value.strip()):
                return 1.0
            return 0.5

        # xs:dateTime
        if value_type in ("xs:dateTime", "dateTime"):
            if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", value.strip()):
                return 1.0
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

            # Rules score based on format validation
            rules_score = self._validate_format(extraction.value_raw)
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
