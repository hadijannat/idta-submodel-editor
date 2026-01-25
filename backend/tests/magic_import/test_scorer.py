"""Tests for Confidence Scorer."""

import pytest

from app.schemas.magic_import import (
    BBox,
    EvidenceRef,
    FieldExtraction,
    PDFIndex,
    PDFIndexInfo,
    PDFWord,
)
from app.services.magic_import.scorer import ConfidenceScorer


@pytest.fixture
def sample_index() -> PDFIndex:
    """Create a sample PDF index."""
    return PDFIndex(
        job_id="test",
        pdf_path="test.pdf",
        info=PDFIndexInfo(
            total_pages=1,
            pages_with_text=1,
            pages_needing_ocr=0,
            total_words=100,
        ),
        pages=[],
        words=[
            PDFWord(
                text="test",
                page=0,
                bbox=BBox(x0=0.1, y0=0.1, x1=0.2, y1=0.15),
                confidence=1.0,
                method="TEXT",
            )
        ],
    )


@pytest.fixture
def high_confidence_extraction() -> FieldExtraction:
    """Create a high-confidence extraction."""
    return FieldExtraction(
        path="SerialNumber",
        value_raw="SN-12345",
        value_normalized=None,
        confidence=0.95,
        evidence=EvidenceRef(
            page=0,
            quote="Serial Number SN-12345",
            boxes=[BBox(x0=0.1, y0=0.1, x1=0.3, y1=0.15)],
            method="TEXT",
            locator_score=0.98,
        ),
        needs_review=False,
    )


@pytest.fixture
def low_confidence_extraction() -> FieldExtraction:
    """Create a low-confidence extraction."""
    return FieldExtraction(
        path="Weight",
        value_raw="maybe 5kg",
        value_normalized=None,
        confidence=0.4,
        evidence=EvidenceRef(
            page=0,
            quote="weight approximately 5kg",
            boxes=[BBox(x0=0.1, y0=0.2, x1=0.3, y1=0.25)],
            method="OCR",
            locator_score=0.5,
        ),
        needs_review=False,
    )


class TestConfidenceScorer:
    """Test suite for ConfidenceScorer."""

    def test_init(self):
        """Test scorer initialization."""
        scorer = ConfidenceScorer()
        assert scorer.WEIGHT_LLM == 0.35
        assert scorer.WEIGHT_LOCALIZER == 0.40
        assert scorer.WEIGHT_OCR == 0.15
        assert scorer.WEIGHT_RULES == 0.10

    def test_score_high_confidence(
        self, sample_index, high_confidence_extraction
    ):
        """Test scoring a high-confidence extraction."""
        scorer = ConfidenceScorer()

        results = scorer.score_all(
            [high_confidence_extraction],
            sample_index,
            confidence_threshold=0.80,
        )

        assert len(results) == 1
        result = results[0]

        # High LLM + high localizer should give high confidence
        assert result.confidence > 0.8
        assert result.needs_review is False
        assert result.confidence_breakdown is not None
        assert result.confidence_breakdown.llm == 0.95
        assert result.confidence_breakdown.localizer == 0.98

    def test_score_low_confidence(
        self, sample_index, low_confidence_extraction
    ):
        """Test scoring a low-confidence extraction."""
        scorer = ConfidenceScorer()

        results = scorer.score_all(
            [low_confidence_extraction],
            sample_index,
            confidence_threshold=0.80,
        )

        assert len(results) == 1
        result = results[0]

        # Low LLM + low localizer should give low confidence
        assert result.confidence < 0.8
        assert result.needs_review is True

    def test_value_normalization(self):
        """Test value normalization."""
        scorer = ConfidenceScorer()

        # Integer
        assert scorer._normalize_value("42") == 42

        # Float
        assert scorer._normalize_value("3.14") == 3.14

        # Boolean
        assert scorer._normalize_value("true") is True
        assert scorer._normalize_value("false") is False
        assert scorer._normalize_value("yes") is True
        assert scorer._normalize_value("no") is False

        # Date (kept as string)
        assert scorer._normalize_value("2024-01-15") == "2024-01-15"

        # Plain string
        assert scorer._normalize_value("hello world") == "hello world"

    def test_format_validation(self):
        """Test format validation scoring."""
        scorer = ConfidenceScorer()

        # Normal value
        assert scorer._validate_format("Siemens AG") == 1.0

        # Very long value (suspicious)
        long_value = "a" * 600
        assert scorer._validate_format(long_value) < 1.0

        # Many special characters (suspicious)
        assert scorer._validate_format("@#$%^&*()!@#$%") < 1.0

    def test_recalculate_after_edit(self, high_confidence_extraction):
        """Test recalculation after user edit."""
        scorer = ConfidenceScorer()

        edited = scorer.recalculate_after_edit(
            high_confidence_extraction,
            "SN-99999",
        )

        assert edited.value_raw == "SN-99999"
        assert edited.confidence == 1.0
        assert edited.user_edited is True
        assert edited.needs_review is False

    def test_mark_approved(self, low_confidence_extraction):
        """Test marking extraction as approved."""
        scorer = ConfidenceScorer()

        approved = scorer.mark_approved(low_confidence_extraction)

        assert approved.user_approved is True
        assert approved.needs_review is False

    def test_type_validation(self):
        """Test value type validation."""
        scorer = ConfidenceScorer()

        # Valid integer
        assert scorer.validate_against_type("42", "xs:int") == 1.0
        assert scorer.validate_against_type("abc", "xs:int") == 0.5

        # Valid boolean
        assert scorer.validate_against_type("true", "xs:boolean") == 1.0
        assert scorer.validate_against_type("maybe", "xs:boolean") == 0.5

        # Valid date
        assert scorer.validate_against_type("2024-01-15", "xs:date") == 1.0

        # String accepts anything
        assert scorer.validate_against_type("anything", "xs:string") == 1.0

        # Comma decimal + thousands
        assert scorer.validate_against_type("1.234,56", "xs:decimal") == 1.0
        assert scorer.validate_against_type("1 234,56", "xsd:float") == 1.0

        # DateTime variants
        assert scorer.validate_against_type("2024-01-15T10:20:30Z", "xs:dateTime") == 1.0
        assert scorer.validate_against_type("2024-01-15 10:20:30+02:00", "xs:dateTime") == 1.0

        # gYear / gYearMonth
        assert scorer.validate_against_type("2024", "xs:gYear") == 1.0
        assert scorer.validate_against_type("2024-05", "xs:gYearMonth") == 1.0

        # duration
        assert scorer.validate_against_type("P3Y6M4DT12H30M5S", "xs:duration") == 1.0

        # anyURI (urn + fragment)
        assert scorer.validate_against_type("urn:example:foo", "xs:anyURI") == 1.0
        assert scorer.validate_against_type("#section-1", "xs:anyURI") >= 0.7

        # hexBinary + base64Binary
        assert scorer.validate_against_type("0A0B0C", "xs:hexBinary") == 1.0
        assert scorer.validate_against_type("TWFu", "xs:base64Binary") >= 0.8

    def test_ocr_quality_calculation(self):
        """Test OCR quality calculation."""
        scorer = ConfidenceScorer()

        # All native text
        native_index = PDFIndex(
            job_id="test",
            pdf_path="test.pdf",
            info=PDFIndexInfo(
                total_pages=1,
                pages_with_text=1,
                pages_needing_ocr=0,
                total_words=2,
            ),
            pages=[],
            words=[
                PDFWord(
                    text="hello",
                    page=0,
                    bbox=BBox(x0=0.1, y0=0.1, x1=0.2, y1=0.15),
                    confidence=1.0,
                    method="TEXT",
                ),
                PDFWord(
                    text="world",
                    page=0,
                    bbox=BBox(x0=0.3, y0=0.1, x1=0.4, y1=0.15),
                    confidence=1.0,
                    method="TEXT",
                ),
            ],
        )

        assert scorer._calculate_ocr_quality(native_index) == 1.0

        # Mixed OCR
        mixed_index = PDFIndex(
            job_id="test",
            pdf_path="test.pdf",
            info=PDFIndexInfo(
                total_pages=1,
                pages_with_text=1,
                pages_needing_ocr=0,
                total_words=2,
            ),
            pages=[],
            words=[
                PDFWord(
                    text="hello",
                    page=0,
                    bbox=BBox(x0=0.1, y0=0.1, x1=0.2, y1=0.15),
                    confidence=0.8,
                    method="OCR",
                ),
                PDFWord(
                    text="world",
                    page=0,
                    bbox=BBox(x0=0.3, y0=0.1, x1=0.4, y1=0.15),
                    confidence=0.9,
                    method="OCR",
                ),
            ],
        )

        quality = scorer._calculate_ocr_quality(mixed_index)
        assert quality == pytest.approx(0.85)  # Average of 0.8 and 0.9
