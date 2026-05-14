"""
Tests for MetricsCalculator service.

Tests comprehensive quality metrics computation for Magic Import extractions,
including field type classification, evidence quality, mismatch detection,
auto-apply eligibility, and weighted confidence.
"""

import pytest

from app.schemas.magic_import import (
    AutoApplyThresholds,
    BBox,
    EvidenceQuality,
    EvidenceRef,
    ExtractionHint,
    ExtractionStatus,
    FieldExtraction,
    FieldMetrics,
    FieldTypeCategory,
    PDFIndex,
    PDFIndexInfo,
    PDFPageInfo,
    PDFWord,
)
from app.services.magic_import.metrics_calculator import MetricsCalculator
from app.services.magic_import.table_extractor import (
    ExtractedTable,
    TableExtractionResult,
)


@pytest.fixture
def sample_index() -> PDFIndex:
    """Create a sample PDF index."""
    return PDFIndex(
        job_id="test-job",
        pdf_path="test.pdf",
        info=PDFIndexInfo(
            total_pages=2,
            pages_with_text=2,
            pages_needing_ocr=0,
            total_words=200,
        ),
        pages=[
            PDFPageInfo(
                page_number=0,
                width=612,
                height=792,
                has_text=True,
                needs_ocr=False,
                word_count=100,
            ),
            PDFPageInfo(
                page_number=1,
                width=612,
                height=792,
                has_text=True,
                needs_ocr=False,
                word_count=100,
            ),
        ],
        words=[
            PDFWord(
                text="serial",
                page=0,
                bbox=BBox(x0=0.1, y0=0.1, x1=0.2, y1=0.15),
                confidence=1.0,
                method="TEXT",
            ),
            PDFWord(
                text="number",
                page=0,
                bbox=BBox(x0=0.21, y0=0.1, x1=0.3, y1=0.15),
                confidence=1.0,
                method="TEXT",
            ),
        ],
    )


@pytest.fixture
def sample_tables() -> TableExtractionResult:
    """Create sample table extraction results."""
    from app.schemas.magic_import import ExtractedTableCell

    return TableExtractionResult(
        tables=[
            ExtractedTable(
                table_id="test-table-1",
                page=0,
                bbox=BBox(x0=0.1, y0=0.2, x1=0.9, y1=0.5),
                rows=3,
                cols=2,
                cells=[
                    ExtractedTableCell(row=0, col=0, text="Property", is_header=True),
                    ExtractedTableCell(row=0, col=1, text="Value", is_header=True),
                    ExtractedTableCell(row=1, col=0, text="Serial Number"),
                    ExtractedTableCell(row=1, col=1, text="SN-12345"),
                    ExtractedTableCell(row=2, col=0, text="Weight"),
                    ExtractedTableCell(row=2, col=1, text="5.5 kg"),
                ],
                headers=["Property", "Value"],
                accuracy=0.95,
                method="LATTICE",
            ),
        ],
        total_tables=1,
        pages_with_tables=[0],
    )


@pytest.fixture
def empty_tables() -> TableExtractionResult:
    """Create empty table extraction results."""
    return TableExtractionResult(
        tables=[],
        total_tables=0,
        pages_with_tables=[],
    )


@pytest.fixture
def sample_hints() -> list[ExtractionHint]:
    """Create sample extraction hints."""
    return [
        ExtractionHint(
            path="SerialNumber",
            label="Serial Number",
            element_type="Property",
            value_type="xs:string",
            semantic_id="0173-1#02-AAB001#001",
            keywords=["serial", "number", "identifier"],
            required=True,
        ),
        ExtractionHint(
            path="Weight",
            label="Weight",
            element_type="Property",
            value_type="xs:float",
            semantic_label="Weight (kg)",
            keywords=["weight", "mass"],
            required=True,
        ),
        ExtractionHint(
            path="Description",
            label="Description",
            element_type="Property",
            value_type="xs:string",
            keywords=["description", "text"],
            required=False,
        ),
        ExtractionHint(
            path="Email",
            label="Email Address",
            element_type="Property",
            value_type="xs:string",
            keywords=["email", "contact"],
            required=False,
        ),
    ]


@pytest.fixture
def high_quality_extractions() -> list[FieldExtraction]:
    """Create high-quality extractions with evidence."""
    return [
        FieldExtraction(
            path="SerialNumber",
            value_type="xs:string",
            value_raw="SN-12345",
            status=ExtractionStatus.FILLED,
            confidence=0.95,
            evidence=EvidenceRef(
                page=0,
                quote="Serial Number: SN-12345",
                boxes=[BBox(x0=0.1, y0=0.1, x1=0.3, y1=0.15)],
                method="TEXT",
                locator_score=0.98,
            ),
            needs_review=False,
        ),
        FieldExtraction(
            path="Weight",
            value_type="xs:float",
            value_raw="5.5 kg",
            status=ExtractionStatus.FILLED,
            confidence=0.92,
            evidence=EvidenceRef(
                page=0,
                quote="Weight: 5.5 kg",
                boxes=[BBox(x0=0.1, y0=0.2, x1=0.3, y1=0.25)],
                method="TEXT",
                locator_score=0.95,
            ),
            needs_review=False,
        ),
        FieldExtraction(
            path="Description",
            value_type="xs:string",
            value_raw="A high-quality product",
            status=ExtractionStatus.FILLED,
            confidence=0.88,
            evidence=EvidenceRef(
                page=1,
                quote="Description: A high-quality product with many features",
                boxes=[BBox(x0=0.1, y0=0.3, x1=0.9, y1=0.35)],
                method="TEXT",
                locator_score=0.90,
            ),
            needs_review=False,
        ),
    ]


@pytest.fixture
def mixed_quality_extractions() -> list[FieldExtraction]:
    """Create mixed-quality extractions."""
    return [
        FieldExtraction(
            path="SerialNumber",
            value_type="xs:string",
            value_raw="SN-12345",
            status=ExtractionStatus.FILLED,
            confidence=0.95,
            evidence=EvidenceRef(
                page=0,
                quote="Serial Number: SN-12345",
                boxes=[BBox(x0=0.1, y0=0.1, x1=0.3, y1=0.15)],
                method="TEXT",
                locator_score=0.98,
            ),
            needs_review=False,
        ),
        FieldExtraction(
            path="Weight",
            value_type="xs:float",
            value_raw="5.5 kg",
            status=ExtractionStatus.NEEDS_REVIEW,
            confidence=0.60,  # Low confidence
            evidence=EvidenceRef(
                page=0,
                quote="approximately 5 kg",  # Value not exact match
                boxes=[BBox(x0=0.1, y0=0.2, x1=0.3, y1=0.25)],
                method="OCR",
                locator_score=0.50,
            ),
            needs_review=True,
        ),
        FieldExtraction(
            path="Description",
            value_type="xs:string",
            value_raw="Unknown",
            status=ExtractionStatus.NEEDS_REVIEW,
            confidence=0.40,
            evidence=None,  # No evidence
            needs_review=True,
        ),
    ]


class TestMetricsCalculator:
    """Test suite for MetricsCalculator."""

    def test_init_default_thresholds(self):
        """Test initialization with default thresholds."""
        calculator = MetricsCalculator()

        assert calculator.thresholds.min_confidence == 0.95
        assert calculator.thresholds.min_evidence_ratio == 0.9
        assert calculator.thresholds.require_grounding is True
        assert EvidenceQuality.TABLE_STRUCTURED in calculator.thresholds.allowed_evidence_qualities

    def test_init_custom_thresholds(self):
        """Test initialization with custom thresholds."""
        custom = AutoApplyThresholds(
            min_confidence=0.8,
            min_evidence_ratio=0.7,
            require_grounding=False,
        )
        calculator = MetricsCalculator(thresholds=custom)

        assert calculator.thresholds.min_confidence == 0.8
        assert calculator.thresholds.require_grounding is False

    def test_calculate_basic(
        self,
        sample_index,
        sample_tables,
        sample_hints,
        high_quality_extractions,
    ):
        """Test basic calculate() functionality."""
        calculator = MetricsCalculator()

        metrics = calculator.calculate(
            job_id="test-job",
            template_name="TestTemplate",
            extractions=high_quality_extractions,
            hints=sample_hints,
            index=sample_index,
            tables=sample_tables,
            llm_provider="openai",
            llm_model="gpt-5.5",
            llm_tokens=1500,
            llm_latency_ms=2500,
        )

        assert metrics.job_id == "test-job"
        assert metrics.template_name == "TestTemplate"
        assert metrics.llm_provider == "openai"
        assert metrics.llm_model == "gpt-5.5"
        assert metrics.llm_tokens_used == 1500
        assert metrics.computed_at is not None

        # Check overall confidence is computed
        assert 0.0 <= metrics.overall_confidence <= 1.0
        assert 0.0 <= metrics.weighted_confidence <= 1.0

        # Check per-field metrics were computed
        assert len(metrics.field_metrics) == len(high_quality_extractions)

        # Check mismatch metrics
        assert metrics.mismatch_metrics is not None

    def test_calculate_empty_extractions(
        self,
        sample_index,
        empty_tables,
        sample_hints,
    ):
        """Test calculate() with empty extractions."""
        calculator = MetricsCalculator()

        metrics = calculator.calculate(
            job_id="test-job",
            template_name="TestTemplate",
            extractions=[],
            hints=sample_hints,
            index=sample_index,
            tables=empty_tables,
            llm_provider="openai",
            llm_model="gpt-5.5",
            llm_tokens=0,
            llm_latency_ms=0,
        )

        assert metrics.overall_confidence == 0.0
        assert metrics.weighted_confidence == 0.0
        assert len(metrics.field_metrics) == 0
        assert metrics.evidence_ratio == 0.0


class TestFieldTypeClassification:
    """Test suite for field type classification."""

    @pytest.fixture
    def calculator(self):
        return MetricsCalculator()

    def test_classify_identifier(self, calculator):
        """Test identifier field classification."""
        extraction = FieldExtraction(
            path="SerialNumber",
            value_raw="SN-12345",
            status=ExtractionStatus.FILLED,
            confidence=0.9,
        )
        hint = ExtractionHint(
            path="SerialNumber",
            label="Serial Number",
            element_type="Property",
            keywords=["serial", "id"],
        )

        result = calculator._classify_field_type(extraction, hint)
        assert result == FieldTypeCategory.IDENTIFIER

    def test_classify_datetime(self, calculator):
        """Test date/time field classification."""
        extraction = FieldExtraction(
            path="ProductionDate",
            value_type="xs:date",
            value_raw="2024-01-15",
            status=ExtractionStatus.FILLED,
            confidence=0.9,
        )
        hint = ExtractionHint(
            path="ProductionDate",
            label="Production Date",
            element_type="Property",
            value_type="xs:date",
            keywords=["date", "production"],
        )

        result = calculator._classify_field_type(extraction, hint)
        assert result == FieldTypeCategory.DATE_TIME

    def test_classify_contact_email(self, calculator):
        """Test contact (email) field classification."""
        extraction = FieldExtraction(
            path="ContactEmail",
            value_raw="info@example.com",
            status=ExtractionStatus.FILLED,
            confidence=0.9,
        )
        hint = ExtractionHint(
            path="ContactEmail",
            label="Email Address",
            element_type="Property",
            keywords=["email", "contact"],
        )

        result = calculator._classify_field_type(extraction, hint)
        assert result == FieldTypeCategory.CONTACT

    def test_classify_enum_choice(self, calculator):
        """Test enum/choice field classification."""
        extraction = FieldExtraction(
            path="ProductType",
            value_raw="Sensor",
            status=ExtractionStatus.FILLED,
            confidence=0.9,
        )
        hint = ExtractionHint(
            path="ProductType",
            label="Product Type",
            element_type="Property",
            keywords=["type", "category"],
        )

        result = calculator._classify_field_type(extraction, hint)
        assert result == FieldTypeCategory.ENUM_CHOICE

    def test_classify_numeric_with_unit(self, calculator):
        """Test numeric with unit field classification."""
        extraction = FieldExtraction(
            path="Weight",
            value_raw="5.5 kg",
            status=ExtractionStatus.FILLED,
            confidence=0.9,
        )
        hint = ExtractionHint(
            path="Weight",
            label="Weight",
            element_type="Property",
            semantic_label="Weight (kg)",
            keywords=["weight", "mass"],
        )

        result = calculator._classify_field_type(extraction, hint)
        assert result == FieldTypeCategory.NUMERIC_UNIT

    def test_classify_numeric_pure(self, calculator):
        """Test pure numeric field classification."""
        extraction = FieldExtraction(
            path="Quantity",
            value_type="xs:int",
            value_raw="42",
            status=ExtractionStatus.FILLED,
            confidence=0.9,
        )
        hint = ExtractionHint(
            path="Quantity",
            label="Quantity",  # Avoid "count" which might trigger other patterns
            element_type="Property",
            value_type="xs:int",
        )

        result = calculator._classify_field_type(extraction, hint)
        assert result == FieldTypeCategory.NUMERIC_PURE

    def test_classify_boolean(self, calculator):
        """Test boolean field classification."""
        extraction = FieldExtraction(
            path="IsActive",
            value_type="xs:boolean",
            value_raw="true",
            status=ExtractionStatus.FILLED,
            confidence=0.9,
        )
        hint = ExtractionHint(
            path="IsActive",
            label="Is Active",
            element_type="Property",
            value_type="xs:boolean",
        )

        result = calculator._classify_field_type(extraction, hint)
        assert result == FieldTypeCategory.BOOLEAN

    def test_classify_text_long(self, calculator):
        """Test long text field classification."""
        extraction = FieldExtraction(
            path="Remarks",
            value_raw="A detailed description of the product with multiline content...",
            status=ExtractionStatus.FILLED,
            confidence=0.9,
        )
        hint = ExtractionHint(
            path="Remarks",
            label="Remarks",  # Use a clear long text indicator
            element_type="Property",
            keywords=["remark", "note", "multiline"],
        )

        result = calculator._classify_field_type(extraction, hint)
        assert result == FieldTypeCategory.TEXT_LONG

    def test_classify_reference(self, calculator):
        """Test reference field classification."""
        extraction = FieldExtraction(
            path="SemanticId",
            value_raw="0173-1#02-AAB123#001",
            status=ExtractionStatus.FILLED,
            confidence=0.9,
        )
        hint = ExtractionHint(
            path="SemanticId",
            label="Semantic ID",
            element_type="Property",
            keywords=["semantic", "reference"],
        )

        result = calculator._classify_field_type(extraction, hint)
        assert result == FieldTypeCategory.REFERENCE

    def test_classify_default_text_short(self, calculator):
        """Test default to short text classification."""
        extraction = FieldExtraction(
            path="BrandName",
            value_raw="Acme Corp",
            status=ExtractionStatus.FILLED,
            confidence=0.9,
        )
        hint = ExtractionHint(
            path="BrandName",
            label="Brand Name",
            element_type="Property",
            keywords=["brand"],  # No patterns that match other categories
        )

        result = calculator._classify_field_type(extraction, hint)
        assert result == FieldTypeCategory.TEXT_SHORT


class TestEvidenceQualityClassification:
    """Test suite for evidence quality classification."""

    @pytest.fixture
    def calculator(self):
        return MetricsCalculator()

    @pytest.fixture
    def tables_with_pages(self) -> TableExtractionResult:
        return TableExtractionResult(
            tables=[],
            total_tables=1,
            pages_with_tables=[0],
        )

    def test_classify_no_evidence(self, calculator, empty_tables):
        """Test NONE classification when no evidence."""
        extraction = FieldExtraction(
            path="Field",
            value_raw="value",
            status=ExtractionStatus.NEEDS_REVIEW,
            confidence=0.5,
            evidence=None,
        )

        result = calculator._classify_evidence_quality(extraction, empty_tables)
        assert result == EvidenceQuality.NONE

    def test_classify_ocr_high(self, calculator, empty_tables):
        """Test OCR_HIGH classification."""
        extraction = FieldExtraction(
            path="Field",
            value_raw="value",
            status=ExtractionStatus.FILLED,
            confidence=0.9,
            evidence=EvidenceRef(
                page=0,
                quote="value",
                boxes=[],
                method="OCR",
                locator_score=0.85,
            ),
        )

        result = calculator._classify_evidence_quality(extraction, empty_tables)
        assert result == EvidenceQuality.OCR_HIGH

    def test_classify_ocr_low(self, calculator, empty_tables):
        """Test OCR_LOW classification."""
        extraction = FieldExtraction(
            path="Field",
            value_raw="value",
            status=ExtractionStatus.NEEDS_REVIEW,
            confidence=0.5,
            evidence=EvidenceRef(
                page=0,
                quote="value",
                boxes=[],
                method="OCR",
                locator_score=0.4,
            ),
        )

        result = calculator._classify_evidence_quality(extraction, empty_tables)
        assert result == EvidenceQuality.OCR_LOW

    def test_classify_table_key_value(self, calculator, tables_with_pages):
        """Test TABLE_KEY_VALUE classification."""
        extraction = FieldExtraction(
            path="Field",
            value_raw="value",
            status=ExtractionStatus.FILLED,
            confidence=0.9,
            evidence=EvidenceRef(
                page=0,
                quote="Key: value",
                boxes=[],
                method="TEXT",
                locator_score=0.9,
            ),
        )

        result = calculator._classify_evidence_quality(extraction, tables_with_pages)
        assert result == EvidenceQuality.TABLE_KEY_VALUE

    def test_classify_table_structured(self, calculator, tables_with_pages):
        """Test TABLE_STRUCTURED classification."""
        extraction = FieldExtraction(
            path="Field",
            value_raw="value",
            status=ExtractionStatus.FILLED,
            confidence=0.9,
            evidence=EvidenceRef(
                page=0,
                quote="Header1 | value | extra",
                boxes=[],
                method="TEXT",
                locator_score=0.9,
            ),
        )

        result = calculator._classify_evidence_quality(extraction, tables_with_pages)
        assert result == EvidenceQuality.TABLE_STRUCTURED

    def test_classify_text_grounded(self, calculator, empty_tables):
        """Test TEXT_GROUNDED classification."""
        extraction = FieldExtraction(
            path="Field",
            value_raw="exact value",
            status=ExtractionStatus.FILLED,
            confidence=0.9,
            evidence=EvidenceRef(
                page=0,
                quote="The exact value is here",
                boxes=[],
                method="TEXT",
                locator_score=0.9,
            ),
        )

        result = calculator._classify_evidence_quality(extraction, empty_tables)
        assert result == EvidenceQuality.TEXT_GROUNDED

    def test_classify_text_inferred(self, calculator, empty_tables):
        """Test TEXT_INFERRED classification."""
        extraction = FieldExtraction(
            path="Field",
            value_raw="inferred",
            status=ExtractionStatus.FILLED,
            confidence=0.7,
            evidence=EvidenceRef(
                page=0,
                quote="Some completely different text",
                boxes=[],
                method="TEXT",
                locator_score=0.6,
            ),
        )

        result = calculator._classify_evidence_quality(extraction, empty_tables)
        assert result == EvidenceQuality.TEXT_INFERRED


class TestMismatchMetrics:
    """Test suite for template mismatch detection."""

    @pytest.fixture
    def calculator(self):
        return MetricsCalculator()

    @pytest.fixture
    def good_diagnostics(self):
        """Diagnostics with good keyword matches."""
        return [
            {"match_count": 5, "anchor_match_count": 2},
            {"match_count": 3, "anchor_match_count": 1},
            {"match_count": 4, "anchor_match_count": 3},
        ]

    @pytest.fixture
    def poor_diagnostics(self):
        """Diagnostics with no keyword matches."""
        return [
            {"match_count": 0, "anchor_match_count": 0},
            {"match_count": 0, "anchor_match_count": 0},
            {"match_count": 0, "anchor_match_count": 0},
        ]

    def test_mismatch_proceed_good_extractions(
        self, calculator, sample_hints, high_quality_extractions, good_diagnostics
    ):
        """Test 'proceed' recommendation with good extractions."""
        metrics = calculator._compute_mismatch_metrics(
            high_quality_extractions, sample_hints, good_diagnostics
        )

        assert metrics.recommended_action == "proceed"
        assert metrics.mismatch_score < 0.4
        assert metrics.keyword_match_ratio == 1.0  # All matched

    def test_mismatch_abort_no_matches(
        self, calculator, sample_hints, poor_diagnostics
    ):
        """Test 'abort' recommendation with no keyword matches and empty extractions."""
        empty_extractions = [
            FieldExtraction(
                path="Field",
                value_raw="",
                status=ExtractionStatus.EMPTY,
                confidence=0.0,
            ),
        ]

        metrics = calculator._compute_mismatch_metrics(
            empty_extractions, sample_hints, poor_diagnostics
        )

        assert metrics.recommended_action == "abort"
        assert metrics.mismatch_score >= 0.7
        assert metrics.keyword_match_ratio < 0.1
        assert len(metrics.mismatch_indicators) >= 2

    def test_mismatch_warn_partial_matches(self, calculator, sample_hints):
        """Test 'warn' recommendation with partial matches."""
        # Some extractions filled, some empty
        partial_extractions = [
            FieldExtraction(
                path="Field1",
                value_raw="value",
                status=ExtractionStatus.FILLED,
                confidence=0.8,
                evidence=None,
            ),
            FieldExtraction(
                path="Field2",
                value_raw="",
                status=ExtractionStatus.EMPTY,
                confidence=0.0,
            ),
            FieldExtraction(
                path="Field3",
                value_raw="",
                status=ExtractionStatus.EMPTY,
                confidence=0.0,
            ),
        ]

        # Partial keyword matches
        partial_diagnostics = [
            {"match_count": 1, "anchor_match_count": 0},
            {"match_count": 0, "anchor_match_count": 0},
            {"match_count": 0, "anchor_match_count": 0},
            {"match_count": 0, "anchor_match_count": 0},
            {"match_count": 0, "anchor_match_count": 0},
        ]

        metrics = calculator._compute_mismatch_metrics(
            partial_extractions, sample_hints, partial_diagnostics
        )

        # Should be warn or abort depending on exact values
        assert metrics.recommended_action in ("warn", "abort")
        assert metrics.mismatch_score >= 0.4

    def test_mismatch_no_diagnostics(self, calculator, sample_hints, high_quality_extractions):
        """Test mismatch detection with no retrieval diagnostics."""
        metrics = calculator._compute_mismatch_metrics(
            high_quality_extractions, sample_hints, None
        )

        # Without diagnostics, keyword match ratio is unavailable
        assert metrics.keyword_match_ratio == 0.0
        assert "Keyword match ratio unavailable" in metrics.mismatch_indicators
        assert metrics.extraction_yield > 0


class TestAutoApplyEligibility:
    """Test suite for auto-apply eligibility computation."""

    @pytest.fixture
    def calculator(self):
        return MetricsCalculator()

    def test_eligible_high_quality(self, calculator, sample_tables):
        """Test that high-quality fields are eligible."""
        field_metrics = [
            FieldMetrics(
                path="Field",
                field_type_category=FieldTypeCategory.IDENTIFIER,
                is_required=True,
                confidence=0.98,
                evidence_ratio=0.95,
                evidence_quality=EvidenceQuality.TABLE_STRUCTURED,
                grounding_verified=True,
            ),
        ]

        count = calculator._compute_auto_apply_eligibility(field_metrics)
        assert count == 1

    def test_ineligible_low_confidence(self, calculator):
        """Test that low confidence fields are ineligible."""
        field_metrics = [
            FieldMetrics(
                path="Field",
                field_type_category=FieldTypeCategory.IDENTIFIER,
                is_required=True,
                confidence=0.80,  # Below 0.95 threshold
                evidence_ratio=0.95,
                evidence_quality=EvidenceQuality.TABLE_STRUCTURED,
                grounding_verified=True,
            ),
        ]

        count = calculator._compute_auto_apply_eligibility(field_metrics)
        assert count == 0

    def test_ineligible_no_grounding(self, calculator):
        """Test that ungrounded fields are ineligible."""
        field_metrics = [
            FieldMetrics(
                path="Field",
                field_type_category=FieldTypeCategory.IDENTIFIER,
                is_required=True,
                confidence=0.98,
                evidence_ratio=0.95,
                evidence_quality=EvidenceQuality.TEXT_GROUNDED,
                grounding_verified=False,  # Not grounded
            ),
        ]

        count = calculator._compute_auto_apply_eligibility(field_metrics)
        assert count == 0

    def test_ineligible_poor_evidence_quality(self, calculator):
        """Test that poor evidence quality makes field ineligible."""
        field_metrics = [
            FieldMetrics(
                path="Field",
                field_type_category=FieldTypeCategory.IDENTIFIER,
                is_required=True,
                confidence=0.98,
                evidence_ratio=0.95,
                evidence_quality=EvidenceQuality.TEXT_INFERRED,  # Not in allowed list
                grounding_verified=True,
            ),
        ]

        count = calculator._compute_auto_apply_eligibility(field_metrics)
        assert count == 0

    def test_custom_thresholds(self):
        """Test eligibility with custom thresholds."""
        custom = AutoApplyThresholds(
            min_confidence=0.7,  # Lower threshold
            min_evidence_ratio=0.5,
            require_grounding=False,
            allowed_evidence_qualities=[
                EvidenceQuality.TEXT_GROUNDED,
                EvidenceQuality.TEXT_INFERRED,
            ],
        )
        calculator = MetricsCalculator(thresholds=custom)

        field_metrics = [
            FieldMetrics(
                path="Field",
                field_type_category=FieldTypeCategory.IDENTIFIER,
                is_required=True,
                confidence=0.75,  # Would fail default, passes custom
                evidence_ratio=0.6,
                evidence_quality=EvidenceQuality.TEXT_INFERRED,  # Allowed in custom
                grounding_verified=False,  # Not required in custom
            ),
        ]

        count = calculator._compute_auto_apply_eligibility(field_metrics)
        assert count == 1


class TestWeightedConfidence:
    """Test suite for weighted confidence computation."""

    @pytest.fixture
    def calculator(self):
        return MetricsCalculator()

    def test_weighted_required_higher(self, calculator):
        """Test that required fields are weighted higher."""
        extractions = [
            FieldExtraction(
                path="Required",
                value_raw="value",
                status=ExtractionStatus.FILLED,
                confidence=0.90,
            ),
            FieldExtraction(
                path="Optional",
                value_raw="value",
                status=ExtractionStatus.FILLED,
                confidence=0.50,
            ),
        ]

        hints = {
            "Required": ExtractionHint(
                path="Required",
                label="Required Field",
                element_type="Property",
                required=True,
            ),
            "Optional": ExtractionHint(
                path="Optional",
                label="Optional Field",
                element_type="Property",
                required=False,
            ),
        }

        weighted = calculator._compute_weighted_confidence(extractions, hints)
        overall = calculator._compute_overall_confidence(extractions)

        # Weighted should be higher than simple average because
        # high-confidence required field is weighted 2x
        # Overall = (0.90 + 0.50) / 2 = 0.70
        # Weighted = (0.90 * 2 + 0.50 * 1) / 3 = 2.30 / 3 = 0.767
        assert weighted > overall
        assert weighted == pytest.approx(0.767, rel=0.01)

    def test_weighted_all_required(self, calculator):
        """Test weighted confidence when all fields are required."""
        extractions = [
            FieldExtraction(
                path="Field1",
                value_raw="value",
                status=ExtractionStatus.FILLED,
                confidence=0.80,
            ),
            FieldExtraction(
                path="Field2",
                value_raw="value",
                status=ExtractionStatus.FILLED,
                confidence=0.90,
            ),
        ]

        hints = {
            "Field1": ExtractionHint(
                path="Field1",
                label="Field 1",
                element_type="Property",
                required=True,
            ),
            "Field2": ExtractionHint(
                path="Field2",
                label="Field 2",
                element_type="Property",
                required=True,
            ),
        }

        weighted = calculator._compute_weighted_confidence(extractions, hints)
        overall = calculator._compute_overall_confidence(extractions)

        # When all fields are required, weighted equals overall
        assert weighted == pytest.approx(overall)

    def test_weighted_empty_extractions(self, calculator):
        """Test weighted confidence with empty extractions."""
        weighted = calculator._compute_weighted_confidence([], {})
        assert weighted == 0.0


class TestCoverageMetrics:
    """Test suite for coverage metrics computation."""

    @pytest.fixture
    def calculator(self):
        return MetricsCalculator()

    def test_coverage_all_extracted(self, calculator):
        """Test coverage when all fields are extracted."""
        extractions = {
            "Required1": FieldExtraction(
                path="Required1",
                value_raw="value1",
                status=ExtractionStatus.FILLED,
                confidence=0.9,
            ),
            "Optional1": FieldExtraction(
                path="Optional1",
                value_raw="value2",
                status=ExtractionStatus.FILLED,
                confidence=0.9,
            ),
        }

        hints = {
            "Required1": ExtractionHint(
                path="Required1",
                label="Required 1",
                element_type="Property",
                required=True,
            ),
            "Optional1": ExtractionHint(
                path="Optional1",
                label="Optional 1",
                element_type="Property",
                required=False,
            ),
        }

        coverage = calculator._compute_coverage_metrics(extractions, hints)

        assert coverage["required_total"] == 1
        assert coverage["required_extracted"] == 1
        assert coverage["required_coverage"] == 1.0
        assert coverage["optional_coverage"] == 1.0

    def test_coverage_partial(self, calculator):
        """Test coverage with partial extraction."""
        extractions = {
            "Required1": FieldExtraction(
                path="Required1",
                value_raw="value1",
                status=ExtractionStatus.FILLED,
                confidence=0.9,
            ),
        }

        hints = {
            "Required1": ExtractionHint(
                path="Required1",
                label="Required 1",
                element_type="Property",
                required=True,
            ),
            "Required2": ExtractionHint(
                path="Required2",
                label="Required 2",
                element_type="Property",
                required=True,
            ),
            "Optional1": ExtractionHint(
                path="Optional1",
                label="Optional 1",
                element_type="Property",
                required=False,
            ),
        }

        coverage = calculator._compute_coverage_metrics(extractions, hints)

        assert coverage["required_total"] == 2
        assert coverage["required_extracted"] == 1
        assert coverage["required_coverage"] == 0.5
        assert coverage["optional_coverage"] == 0.0

    def test_coverage_no_hints(self, calculator):
        """Test coverage with no hints."""
        coverage = calculator._compute_coverage_metrics({}, {})

        # With no hints, coverage defaults to 1.0 (nothing required)
        assert coverage["required_coverage"] == 1.0
        assert coverage["optional_coverage"] == 1.0


class TestEvidenceMetrics:
    """Test suite for evidence metrics computation."""

    @pytest.fixture
    def calculator(self):
        return MetricsCalculator()

    def test_evidence_all_with_evidence(self, calculator):
        """Test evidence metrics when all extractions have evidence."""
        extractions = [
            FieldExtraction(
                path="Field1",
                value_raw="value",
                status=ExtractionStatus.FILLED,
                confidence=0.9,
                evidence=EvidenceRef(
                    page=0,
                    quote="value",
                    boxes=[],
                    method="TEXT",
                    locator_score=0.9,
                ),
            ),
        ]

        field_metrics = [
            FieldMetrics(
                path="Field1",
                field_type_category=FieldTypeCategory.TEXT_SHORT,
                is_required=True,
                confidence=0.9,
                evidence_ratio=1.0,
                evidence_quality=EvidenceQuality.TEXT_GROUNDED,
                source_text=True,
                grounding_verified=True,
            ),
        ]

        metrics = calculator._compute_evidence_metrics(extractions, field_metrics)

        assert metrics["evidence_ratio"] == 1.0
        assert metrics["text_evidence_ratio"] == 1.0
        assert metrics["grounding_rate"] == 1.0
        assert metrics["high_confidence_no_evidence_count"] == 0

    def test_evidence_high_confidence_no_evidence(self, calculator):
        """Test detection of high confidence without evidence."""
        extractions = [
            FieldExtraction(
                path="Field1",
                value_raw="value",
                status=ExtractionStatus.NEEDS_REVIEW,
                confidence=0.85,  # High confidence
                evidence=None,  # But no evidence!
            ),
        ]

        field_metrics = [
            FieldMetrics(
                path="Field1",
                field_type_category=FieldTypeCategory.TEXT_SHORT,
                is_required=True,
                confidence=0.85,
                evidence_ratio=0.0,
                evidence_quality=EvidenceQuality.NONE,
                grounding_verified=False,
            ),
        ]

        metrics = calculator._compute_evidence_metrics(extractions, field_metrics)

        assert metrics["evidence_ratio"] == 0.0
        assert metrics["high_confidence_no_evidence_count"] == 1


class TestErrorRatesByType:
    """Test suite for error rates by field type."""

    @pytest.fixture
    def calculator(self):
        return MetricsCalculator()

    def test_error_rates_computation(self, calculator):
        """Test error rate computation by field type."""
        field_metrics = [
            # Good identifier
            FieldMetrics(
                path="ID1",
                field_type_category=FieldTypeCategory.IDENTIFIER,
                is_required=True,
                confidence=0.9,
                evidence_ratio=1.0,
                evidence_quality=EvidenceQuality.TEXT_GROUNDED,
                grounding_verified=True,
            ),
            # Bad identifier (low confidence)
            FieldMetrics(
                path="ID2",
                field_type_category=FieldTypeCategory.IDENTIFIER,
                is_required=True,
                confidence=0.5,
                evidence_ratio=0.5,
                evidence_quality=EvidenceQuality.TEXT_INFERRED,
                grounding_verified=False,
            ),
            # Good numeric
            FieldMetrics(
                path="Num1",
                field_type_category=FieldTypeCategory.NUMERIC_UNIT,
                is_required=False,
                confidence=0.85,
                evidence_ratio=1.0,
                evidence_quality=EvidenceQuality.TABLE_STRUCTURED,
                grounding_verified=True,
            ),
        ]

        error_rates = calculator._compute_error_rates_by_type(field_metrics)

        # Identifiers: 1 error out of 2 = 50%
        assert error_rates["identifier"] == 0.5
        # Numeric with unit: 0 errors out of 1 = 0%
        assert error_rates["numeric_unit"] == 0.0


class TestIntegration:
    """Integration tests for MetricsCalculator."""

    def test_full_pipeline(
        self,
        sample_index,
        sample_tables,
        sample_hints,
        mixed_quality_extractions,
    ):
        """Test full metrics calculation pipeline."""
        calculator = MetricsCalculator()

        diagnostics = [
            {"match_count": 3, "anchor_match_count": 1},
            {"match_count": 2, "anchor_match_count": 0},
            {"match_count": 0, "anchor_match_count": 0},
        ]

        metrics = calculator.calculate(
            job_id="integration-test",
            template_name="TestTemplate",
            extractions=mixed_quality_extractions,
            hints=sample_hints,
            index=sample_index,
            tables=sample_tables,
            llm_provider="anthropic",
            llm_model="claude-3-opus",
            llm_tokens=2000,
            llm_latency_ms=3000,
            retrieval_diagnostics=diagnostics,
        )

        # Verify structure
        assert metrics.job_id == "integration-test"
        assert metrics.template_name == "TestTemplate"
        assert len(metrics.field_metrics) == 3

        # Verify mismatch detection
        assert metrics.mismatch_metrics is not None
        assert metrics.mismatch_metrics.keyword_match_ratio > 0

        # Verify coverage
        assert metrics.required_field_total > 0

        # Verify thresholds are stored
        assert metrics.auto_apply_thresholds_used is not None

        # Verify error rates
        assert isinstance(metrics.error_rates_by_type, dict)
