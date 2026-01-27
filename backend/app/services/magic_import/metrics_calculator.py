"""
MetricsCalculator - Compute comprehensive quality metrics for Magic Import extractions.

This service computes per-field and aggregate quality metrics after confidence scoring,
including:
- Field type classification (Q10)
- Evidence quality classification (Q4)
- Template mismatch detection (Q6)
- Auto-apply eligibility analysis (Q8)
- Weighted confidence for required vs optional fields (Q3)
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Literal

from app.schemas.magic_import import (
    AutoApplyThresholds,
    EvidenceQuality,
    ExtractionHint,
    ExtractionStatus,
    FieldExtraction,
    FieldMetrics,
    FieldTypeCategory,
    PDFIndex,
    QualityMetrics,
    TemplateMismatchMetrics,
)
from app.services.magic_import.table_extractor import TableExtractionResult

logger = logging.getLogger(__name__)


class MetricsCalculator:
    """
    Compute comprehensive quality metrics for Magic Import extraction jobs.

    This calculator analyzes extractions to produce detailed quality metrics
    that help assess extraction quality, detect template mismatches, and
    determine auto-apply eligibility.
    """

    # Field type classification patterns
    # Maps field name patterns to FieldTypeCategory

    # Identifier patterns
    IDENTIFIER_PATTERNS = re.compile(
        r"(serial\s*number|serialnumber|serial_number|serial|"
        r"\bid\b|identifier|code|sku|part\s*number|partnumber|"
        r"batch|lot|ean|gtin|upc|isbn|uuid|guid)",
        re.IGNORECASE,
    )

    # Date/time patterns
    DATE_TIME_PATTERNS = re.compile(
        r"(date|time|timestamp|year|month|day|week|"
        r"period|duration|created|updated|modified|"
        r"start|end|expiry|expiration|valid\s*until|"
        r"manufactured|production)",
        re.IGNORECASE,
    )

    # Contact patterns
    CONTACT_PATTERNS = re.compile(
        r"(email|e-mail|phone|telephone|tel\b|fax|"
        r"website|web|url|uri|http|www|"
        r"address|street|city|zip|postal|country)",
        re.IGNORECASE,
    )

    # Enum/choice patterns
    ENUM_CHOICE_PATTERNS = re.compile(
        r"(type|status|state|category|class\b|"
        r"mode|level|kind|sort|classification|"
        r"variant|option|selection|choice)",
        re.IGNORECASE,
    )

    # Boolean patterns
    BOOLEAN_PATTERNS = re.compile(
        r"(boolean|flag|is_|has_|can_|should_|"
        r"enabled|disabled|active|inactive|"
        r"approved|verified|certified)",
        re.IGNORECASE,
    )

    # Numeric with units patterns - requires word boundaries to avoid false matches
    NUMERIC_UNIT_PATTERNS = re.compile(
        r"(\bkg\b|\bkilogram|\bgram\b|\bmg\b|\bton\b|\btonne\b|\blb\b|\bpound|\bounce\b|"
        r"\bmm\b|\bcm\b|\bdm\b|\bmeter|\bmetre|\bkm\b|\binch|\bfoot|\bfeet|\byard|\bmile\b|"
        r"\bml\b|\bliter|\blitre|\bgallon|"
        r"\bwatt|\bkilowatt|\bmegawatt|"
        r"\bvolt|\bvoltage|"
        r"\bamp\b|\bampere|\bcurrent\b|"
        r"\bhertz|\bfrequency|"
        r"°c|°f|\bcelsius|\bfahrenheit|\bkelvin|\btemperature|"
        r"\bpascal|\bpressure|"
        r"\bnewton|\bforce\b|"
        r"\btorque|"
        r"\bjoule|\benergy|"
        r"\bkwh\b|\bmwh\b|"
        r"\bspeed|\bvelocity|"
        r"\barea\b|\bvolume\b|"
        r"\bpercent|\bratio\b|"
        r"\bweight\b|\bmass\b|\blength\b|\bwidth\b|\bheight\b|\bdimension)",
        re.IGNORECASE,
    )

    # Reference/semantic patterns
    REFERENCE_PATTERNS = re.compile(
        r"(semantic_id|semanticid|semantic|"
        r"reference|ref\b|aas|submodel|asset|"
        r"concept\s*description|irdi|iri|urn)",
        re.IGNORECASE,
    )

    # Text long indicators
    TEXT_LONG_PATTERNS = re.compile(
        r"(description|comment|note|remark|"
        r"summary|abstract|text|content|body|"
        r"multiline|multi-line|freetext)",
        re.IGNORECASE,
    )

    # Default auto-apply thresholds
    DEFAULT_THRESHOLDS = AutoApplyThresholds(
        min_confidence=0.95,
        min_evidence_ratio=0.9,
        require_grounding=True,
        allowed_evidence_qualities=[
            EvidenceQuality.TABLE_STRUCTURED,
            EvidenceQuality.TABLE_KEY_VALUE,
            EvidenceQuality.TEXT_GROUNDED,
            EvidenceQuality.OCR_HIGH,
        ],
        blocked_field_types=[],
    )

    def __init__(self, thresholds: AutoApplyThresholds | None = None) -> None:
        """
        Initialize the MetricsCalculator.

        Args:
            thresholds: Optional custom thresholds for auto-apply eligibility.
                        If None, uses default thresholds.
        """
        self.thresholds = thresholds or self.DEFAULT_THRESHOLDS

    def calculate(
        self,
        job_id: str,
        template_name: str,
        extractions: list[FieldExtraction],
        hints: list[ExtractionHint],
        index: PDFIndex,
        tables: TableExtractionResult,
        llm_provider: str,
        llm_model: str,
        llm_tokens: int,
        llm_latency_ms: int,
        retrieval_diagnostics: list[dict] | None = None,
    ) -> QualityMetrics:
        """
        Compute comprehensive quality metrics for an extraction job.

        This is the main entry point that computes all metrics including:
        - Per-field metrics (type, confidence, evidence quality)
        - Aggregate confidence metrics (overall, weighted)
        - Coverage metrics (required, optional fields)
        - Mismatch detection metrics
        - Auto-apply eligibility counts

        Args:
            job_id: The job ID
            template_name: Name of the template used
            extractions: List of field extractions from the job
            hints: List of extraction hints from schema resolution
            index: The PDF index with word positions
            tables: Table extraction results
            llm_provider: LLM provider name (e.g., "openai", "anthropic")
            llm_model: LLM model name (e.g., "gpt-4")
            llm_tokens: Total tokens used by LLM
            llm_latency_ms: LLM latency in milliseconds
            retrieval_diagnostics: Optional retrieval diagnostics from snippet retrieval

        Returns:
            QualityMetrics with comprehensive quality analysis
        """
        # Build lookup maps
        hints_by_path = {hint.path: hint for hint in hints}
        extractions_by_path = {e.path: e for e in extractions}

        # Compute per-field metrics
        field_metrics = self._compute_field_metrics(
            extractions, hints_by_path, tables, llm_provider, llm_model
        )

        # Compute aggregate confidence metrics
        overall_confidence = self._compute_overall_confidence(extractions)
        weighted_confidence = self._compute_weighted_confidence(extractions, hints_by_path)

        # Compute evidence metrics
        evidence_metrics = self._compute_evidence_metrics(extractions, field_metrics)

        # Compute coverage metrics
        coverage_metrics = self._compute_coverage_metrics(
            extractions_by_path, hints_by_path
        )

        # Compute mismatch metrics
        mismatch_metrics = self._compute_mismatch_metrics(
            extractions, hints, retrieval_diagnostics
        )

        # Compute auto-apply eligibility
        auto_apply_eligible = self._compute_auto_apply_eligibility(field_metrics)

        # Compute error rates by field type
        error_rates = self._compute_error_rates_by_type(field_metrics)

        return QualityMetrics(
            job_id=job_id,
            template_name=template_name,
            computed_at=datetime.now(timezone.utc),
            # Overall confidence
            overall_confidence=overall_confidence,
            weighted_confidence=weighted_confidence,
            # Evidence metrics
            evidence_ratio=evidence_metrics["evidence_ratio"],
            table_evidence_ratio=evidence_metrics["table_evidence_ratio"],
            text_evidence_ratio=evidence_metrics["text_evidence_ratio"],
            high_confidence_no_evidence_count=evidence_metrics[
                "high_confidence_no_evidence_count"
            ],
            grounding_rate=evidence_metrics["grounding_rate"],
            # Coverage metrics
            required_field_total=coverage_metrics["required_total"],
            required_field_extracted=coverage_metrics["required_extracted"],
            required_field_coverage=coverage_metrics["required_coverage"],
            optional_field_coverage=coverage_metrics["optional_coverage"],
            # Per-field metrics
            field_metrics=field_metrics,
            # Error analysis
            error_rates_by_type=error_rates,
            # Mismatch detection
            mismatch_metrics=mismatch_metrics,
            # LLM usage
            llm_provider=llm_provider,
            llm_model=llm_model,
            llm_tokens_used=llm_tokens,
            # Auto-apply
            auto_apply_eligible_count=auto_apply_eligible,
            auto_apply_thresholds_used=self.thresholds,
        )

    def _compute_field_metrics(
        self,
        extractions: list[FieldExtraction],
        hints_by_path: dict[str, ExtractionHint],
        tables: TableExtractionResult,
        llm_provider: str,
        llm_model: str,
    ) -> list[FieldMetrics]:
        """
        Compute detailed metrics for each extracted field.

        Args:
            extractions: List of field extractions
            hints_by_path: Mapping of path to ExtractionHint
            tables: Table extraction results
            llm_provider: LLM provider name
            llm_model: LLM model name

        Returns:
            List of FieldMetrics, one per extraction
        """
        field_metrics: list[FieldMetrics] = []

        # Build set of pages with tables for source detection
        table_pages = set(tables.pages_with_tables) if tables else set()

        for extraction in extractions:
            hint = hints_by_path.get(extraction.path)
            is_required = hint.required if hint else False

            # Classify field type
            field_type = self._classify_field_type(extraction, hint)

            # Classify evidence quality
            evidence_quality = self._classify_evidence_quality(extraction, tables)

            # Compute evidence ratio (value supported by evidence)
            evidence_ratio = self._compute_evidence_ratio(extraction)

            # Determine extraction sources
            source_table = False
            source_text = False
            source_ocr = False

            if extraction.evidence:
                if extraction.evidence.method == "OCR":
                    source_ocr = True
                else:
                    source_text = True

                # Check if evidence page has tables
                if extraction.evidence.page in table_pages:
                    # Check if value appears to come from structured data
                    if evidence_quality in (
                        EvidenceQuality.TABLE_STRUCTURED,
                        EvidenceQuality.TABLE_KEY_VALUE,
                    ):
                        source_table = True

            # Determine if grounding is verified
            grounding_verified = (
                extraction.evidence is not None
                and extraction.status == ExtractionStatus.FILLED
                and self._value_in_evidence(extraction.value_raw, extraction.evidence.quote)
            )

            field_metrics.append(
                FieldMetrics(
                    path=extraction.path,
                    field_type_category=field_type,
                    is_required=is_required,
                    confidence=extraction.confidence,
                    evidence_ratio=evidence_ratio,
                    evidence_quality=evidence_quality,
                    source_table=source_table,
                    source_text=source_text,
                    source_ocr=source_ocr,
                    grounding_verified=grounding_verified,
                    llm_provider=llm_provider,
                    llm_model=llm_model,
                )
            )

        return field_metrics

    def _classify_field_type(
        self,
        extraction: FieldExtraction,
        hint: ExtractionHint | None,
    ) -> FieldTypeCategory:
        """
        Classify the field type based on path, label, and value patterns.

        Uses pattern matching on field path, label, and keywords to determine
        the most appropriate category for analysis.

        Args:
            extraction: The field extraction
            hint: Optional extraction hint with additional metadata

        Returns:
            FieldTypeCategory enum value
        """
        # Build search string from available metadata
        search_parts = [extraction.path]
        if hint:
            search_parts.append(hint.label)
            if hint.keywords:
                search_parts.extend(hint.keywords)
            if hint.semantic_label:
                search_parts.append(hint.semantic_label)

        search_text = " ".join(search_parts)

        # Also check value type hint
        value_type = extraction.value_type or (hint.value_type if hint else None)

        # Check patterns in order of specificity

        # 1. Boolean - check value type and patterns
        if value_type and "boolean" in value_type.lower():
            return FieldTypeCategory.BOOLEAN
        if self.BOOLEAN_PATTERNS.search(search_text):
            return FieldTypeCategory.BOOLEAN

        # 2. Reference - semantic/AAS patterns
        if self.REFERENCE_PATTERNS.search(search_text):
            return FieldTypeCategory.REFERENCE

        # 3. Date/time
        if value_type and any(
            t in value_type.lower()
            for t in ["date", "time", "gyear", "gmonth", "gday", "duration"]
        ):
            return FieldTypeCategory.DATE_TIME
        if self.DATE_TIME_PATTERNS.search(search_text):
            return FieldTypeCategory.DATE_TIME

        # 4. Contact information
        if self.CONTACT_PATTERNS.search(search_text):
            return FieldTypeCategory.CONTACT

        # 5. Identifier
        if self.IDENTIFIER_PATTERNS.search(search_text):
            return FieldTypeCategory.IDENTIFIER

        # 6. Enum/choice
        if self.ENUM_CHOICE_PATTERNS.search(search_text):
            return FieldTypeCategory.ENUM_CHOICE

        # 7. Numeric with units - check both search text and actual value
        value_text = extraction.value_raw or ""
        if self.NUMERIC_UNIT_PATTERNS.search(search_text) or self.NUMERIC_UNIT_PATTERNS.search(
            value_text
        ):
            return FieldTypeCategory.NUMERIC_UNIT

        # 8. Pure numeric - check value type
        if value_type and any(
            t in value_type.lower()
            for t in ["int", "integer", "float", "double", "decimal", "number"]
        ):
            return FieldTypeCategory.NUMERIC_PURE

        # 9. Text long - descriptions, comments
        if self.TEXT_LONG_PATTERNS.search(search_text):
            return FieldTypeCategory.TEXT_LONG

        # 10. Default to short text
        return FieldTypeCategory.TEXT_SHORT

    def _classify_evidence_quality(
        self,
        extraction: FieldExtraction,
        tables: TableExtractionResult,
    ) -> EvidenceQuality:
        """
        Classify the quality of evidence supporting an extraction.

        Evidence quality classification:
        - TABLE_STRUCTURED: From structured table with headers
        - TABLE_KEY_VALUE: From key-value pair table
        - TEXT_GROUNDED: Exact text match in document
        - TEXT_INFERRED: Value inferred from surrounding context
        - OCR_HIGH: OCR extraction with high confidence
        - OCR_LOW: OCR extraction with low confidence
        - NONE: No evidence available

        Args:
            extraction: The field extraction
            tables: Table extraction results

        Returns:
            EvidenceQuality enum value
        """
        if extraction.evidence is None:
            return EvidenceQuality.NONE

        evidence = extraction.evidence

        # Check for OCR-based extraction
        if evidence.method == "OCR":
            # Use locator score as proxy for OCR confidence
            if evidence.locator_score >= 0.7:
                return EvidenceQuality.OCR_HIGH
            return EvidenceQuality.OCR_LOW

        # TEXT method - check for table source
        if tables and evidence.page in tables.pages_with_tables:
            # Check if the evidence quote looks like table data
            quote = evidence.quote or ""

            # Key-value pattern: "Key: Value" or "Key | Value"
            if re.search(r"^[^:|\n]+[:|\|][^:|\n]+$", quote.strip()):
                return EvidenceQuality.TABLE_KEY_VALUE

            # Structured table: multiple columns with separators
            if "|" in quote or "\t" in quote or "  " in quote:
                return EvidenceQuality.TABLE_STRUCTURED

        # Check for grounded vs inferred text
        value = extraction.value_raw or ""
        quote = evidence.quote or ""

        if self._value_in_evidence(value, quote):
            return EvidenceQuality.TEXT_GROUNDED

        return EvidenceQuality.TEXT_INFERRED

    def _compute_mismatch_metrics(
        self,
        extractions: list[FieldExtraction],
        hints: list[ExtractionHint],
        retrieval_diagnostics: list[dict] | None,
    ) -> TemplateMismatchMetrics:
        """
        Compute template/document mismatch detection metrics.

        Uses heuristics to detect when a PDF document doesn't match
        the selected template:
        - keyword_match_ratio < 0.1 → +0.4 to mismatch score
        - extraction_yield < 0.1 → +0.3 to mismatch score
        - evidence_rate < 0.1 → +0.3 to mismatch score
        - Score >= 0.7 → "abort", >= 0.4 → "warn", else → "proceed"

        Args:
            extractions: List of field extractions
            hints: List of extraction hints
            retrieval_diagnostics: Optional diagnostics from snippet retrieval

        Returns:
            TemplateMismatchMetrics with mismatch analysis
        """
        indicators: list[str] = []
        mismatch_score = 0.0

        # 1. Compute keyword match ratio from retrieval diagnostics
        keyword_match_ratio = 1.0
        if retrieval_diagnostics:
            total_diags = len(retrieval_diagnostics)
            if total_diags > 0:
                matched = sum(
                    1
                    for d in retrieval_diagnostics
                    if d.get("match_count", 0) > 0 or d.get("anchor_match_count", 0) > 0
                )
                keyword_match_ratio = matched / total_diags

        if keyword_match_ratio < 0.1:
            mismatch_score += 0.4
            indicators.append(
                f"Very low keyword match ratio ({keyword_match_ratio:.1%})"
            )
        elif keyword_match_ratio < 0.3:
            mismatch_score += 0.2
            indicators.append(f"Low keyword match ratio ({keyword_match_ratio:.1%})")

        # 2. Compute extraction yield
        extraction_yield = 0.0
        if extractions:
            filled = sum(
                1
                for e in extractions
                if e.value_raw and e.value_raw.strip() and e.status != ExtractionStatus.EMPTY
            )
            extraction_yield = filled / len(extractions) if extractions else 0.0

        if extraction_yield < 0.1:
            mismatch_score += 0.3
            indicators.append(f"Very low extraction yield ({extraction_yield:.1%})")
        elif extraction_yield < 0.3:
            mismatch_score += 0.15
            indicators.append(f"Low extraction yield ({extraction_yield:.1%})")

        # 3. Compute evidence localization rate
        evidence_rate = 0.0
        if extractions:
            with_evidence = sum(1 for e in extractions if e.evidence is not None)
            evidence_rate = with_evidence / len(extractions) if extractions else 0.0

        if evidence_rate < 0.1:
            mismatch_score += 0.3
            indicators.append(
                f"Very low evidence localization rate ({evidence_rate:.1%})"
            )
        elif evidence_rate < 0.3:
            mismatch_score += 0.15
            indicators.append(f"Low evidence localization rate ({evidence_rate:.1%})")

        # 4. Determine recommended action
        if mismatch_score >= 0.7:
            recommended_action: Literal["proceed", "warn", "abort"] = "abort"
        elif mismatch_score >= 0.4:
            recommended_action = "warn"
        else:
            recommended_action = "proceed"

        return TemplateMismatchMetrics(
            keyword_match_ratio=keyword_match_ratio,
            extraction_yield=extraction_yield,
            evidence_localization_rate=evidence_rate,
            mismatch_score=min(1.0, mismatch_score),
            mismatch_indicators=indicators,
            recommended_action=recommended_action,
        )

    def _compute_auto_apply_eligibility(
        self,
        field_metrics: list[FieldMetrics],
    ) -> int:
        """
        Compute how many fields are eligible for automatic application.

        A field is eligible for auto-apply if it meets all threshold criteria:
        - Confidence >= min_confidence
        - Evidence ratio >= min_evidence_ratio
        - Grounding verified (if required)
        - Evidence quality in allowed list
        - Field type not in blocked list

        Args:
            field_metrics: List of per-field metrics

        Returns:
            Count of auto-apply eligible fields
        """
        eligible_count = 0

        for fm in field_metrics:
            # Check confidence threshold
            if fm.confidence < self.thresholds.min_confidence:
                continue

            # Check evidence ratio threshold
            if fm.evidence_ratio < self.thresholds.min_evidence_ratio:
                continue

            # Check grounding requirement
            if self.thresholds.require_grounding and not fm.grounding_verified:
                continue

            # Check evidence quality
            if fm.evidence_quality not in self.thresholds.allowed_evidence_qualities:
                continue

            # Check blocked field types
            if fm.field_type_category in self.thresholds.blocked_field_types:
                continue

            eligible_count += 1

        return eligible_count

    def _compute_weighted_confidence(
        self,
        extractions: list[FieldExtraction],
        hints_by_path: dict[str, ExtractionHint],
    ) -> float:
        """
        Compute weighted confidence where required fields count 2x.

        This gives more weight to the confidence of required fields,
        which are more critical for template compliance.

        Args:
            extractions: List of field extractions
            hints_by_path: Mapping of path to ExtractionHint

        Returns:
            Weighted average confidence (0.0 to 1.0)
        """
        if not extractions:
            return 0.0

        total_weight = 0.0
        weighted_sum = 0.0

        for extraction in extractions:
            hint = hints_by_path.get(extraction.path)
            is_required = hint.required if hint else False

            # Required fields count 2x
            weight = 2.0 if is_required else 1.0
            total_weight += weight
            weighted_sum += extraction.confidence * weight

        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def _compute_overall_confidence(
        self,
        extractions: list[FieldExtraction],
    ) -> float:
        """
        Compute simple average confidence across all extractions.

        Args:
            extractions: List of field extractions

        Returns:
            Average confidence (0.0 to 1.0)
        """
        if not extractions:
            return 0.0

        return sum(e.confidence for e in extractions) / len(extractions)

    def _compute_evidence_ratio(
        self,
        extraction: FieldExtraction,
    ) -> float:
        """
        Compute ratio of value supported by evidence.

        Args:
            extraction: The field extraction

        Returns:
            Evidence ratio (0.0 to 1.0)
        """
        if not extraction.evidence or not extraction.value_raw:
            return 0.0

        value = extraction.value_raw.strip().lower()
        quote = (extraction.evidence.quote or "").strip().lower()

        if not value or not quote:
            return 0.0

        # Simple containment check
        if value in quote:
            return 1.0

        # Partial match - check how much of value appears in quote
        value_words = set(value.split())
        quote_words = set(quote.split())

        if not value_words:
            return 0.0

        matching = len(value_words & quote_words)
        return matching / len(value_words)

    def _compute_evidence_metrics(
        self,
        extractions: list[FieldExtraction],
        field_metrics: list[FieldMetrics],
    ) -> dict:
        """
        Compute aggregate evidence-related metrics.

        Args:
            extractions: List of field extractions
            field_metrics: List of per-field metrics

        Returns:
            Dictionary with evidence metrics
        """
        if not extractions:
            return {
                "evidence_ratio": 0.0,
                "table_evidence_ratio": 0.0,
                "text_evidence_ratio": 0.0,
                "high_confidence_no_evidence_count": 0,
                "grounding_rate": 0.0,
            }

        n = len(extractions)

        # Count extractions with evidence
        with_evidence = sum(1 for e in extractions if e.evidence is not None)
        evidence_ratio = with_evidence / n

        # Count by source type
        table_count = sum(1 for fm in field_metrics if fm.source_table)
        text_count = sum(1 for fm in field_metrics if fm.source_text and not fm.source_table)

        # High confidence (>= 0.8) but no evidence - suspicious
        high_conf_no_evidence = sum(
            1 for e in extractions if e.confidence >= 0.8 and e.evidence is None
        )

        # Grounding rate
        grounded = sum(1 for fm in field_metrics if fm.grounding_verified)
        grounding_rate = grounded / n

        return {
            "evidence_ratio": evidence_ratio,
            "table_evidence_ratio": table_count / n,
            "text_evidence_ratio": text_count / n,
            "high_confidence_no_evidence_count": high_conf_no_evidence,
            "grounding_rate": grounding_rate,
        }

    def _compute_coverage_metrics(
        self,
        extractions_by_path: dict[str, FieldExtraction],
        hints_by_path: dict[str, ExtractionHint],
    ) -> dict:
        """
        Compute field coverage metrics for required and optional fields.

        Args:
            extractions_by_path: Mapping of path to FieldExtraction
            hints_by_path: Mapping of path to ExtractionHint

        Returns:
            Dictionary with coverage metrics
        """
        required_total = 0
        required_extracted = 0
        optional_total = 0
        optional_extracted = 0

        for path, hint in hints_by_path.items():
            extraction = extractions_by_path.get(path)
            has_value = (
                extraction is not None
                and extraction.value_raw
                and extraction.value_raw.strip()
                and extraction.status != ExtractionStatus.EMPTY
            )

            if hint.required:
                required_total += 1
                if has_value:
                    required_extracted += 1
            else:
                optional_total += 1
                if has_value:
                    optional_extracted += 1

        required_coverage = (
            required_extracted / required_total if required_total > 0 else 1.0
        )
        optional_coverage = (
            optional_extracted / optional_total if optional_total > 0 else 1.0
        )

        return {
            "required_total": required_total,
            "required_extracted": required_extracted,
            "required_coverage": required_coverage,
            "optional_coverage": optional_coverage,
        }

    def _compute_error_rates_by_type(
        self,
        field_metrics: list[FieldMetrics],
    ) -> dict[str, float]:
        """
        Compute error rates grouped by field type category.

        Error is defined as low confidence (< 0.7) or poor evidence quality.

        Args:
            field_metrics: List of per-field metrics

        Returns:
            Dictionary mapping field type to error rate
        """
        type_counts: dict[str, int] = {}
        type_errors: dict[str, int] = {}

        for fm in field_metrics:
            type_name = fm.field_type_category.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1

            # Define error conditions
            is_error = (
                fm.confidence < 0.7
                or fm.evidence_quality
                in (EvidenceQuality.NONE, EvidenceQuality.OCR_LOW, EvidenceQuality.TEXT_INFERRED)
            )

            if is_error:
                type_errors[type_name] = type_errors.get(type_name, 0) + 1

        # Compute rates
        error_rates: dict[str, float] = {}
        for type_name, count in type_counts.items():
            errors = type_errors.get(type_name, 0)
            error_rates[type_name] = errors / count if count > 0 else 0.0

        return error_rates

    def _value_in_evidence(self, value: str | None, quote: str | None) -> bool:
        """
        Check whether the extracted value appears in the evidence quote.

        Args:
            value: The extracted value
            quote: The evidence quote

        Returns:
            True if value is found in quote
        """
        if not value or not quote:
            return False
        return value.strip().lower() in quote.strip().lower()
