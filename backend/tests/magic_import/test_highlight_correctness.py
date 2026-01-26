"""
Tests for highlight/bounding box correctness in the localizer.

Verifies that evidence localization produces accurate bounding boxes
that correctly highlight the extracted text in the PDF.
"""

import pytest

from app.schemas.magic_import import (
    BBox,
    EvidenceRef,
    FieldExtraction,
    LLMFieldExtraction,
    PDFIndex,
    PDFIndexInfo,
    PDFPageInfo,
    PDFWord,
)
from app.services.magic_import.localizer import EvidenceLocalizer


@pytest.fixture
def localizer():
    """Create an EvidenceLocalizer instance."""
    return EvidenceLocalizer()


@pytest.fixture
def simple_pdf_index():
    """Create a simple PDFIndex for testing."""
    return PDFIndex(
        job_id="test-highlight-1",
        pdf_path="/tmp/test.pdf",
        info=PDFIndexInfo(
            total_pages=1,
            pages_with_text=1,
            pages_needing_ocr=0,
            total_words=10,
            language_detected="en",
        ),
        pages=[
            PDFPageInfo(
                page_number=0,
                width=612,
                height=792,
                has_text=True,
                needs_ocr=False,
                word_count=10,
            )
        ],
        words=[
            PDFWord(text="Manufacturer:", page=0, bbox=BBox(x0=0.1, y0=0.1, x1=0.25, y1=0.12), confidence=1.0, method="TEXT"),
            PDFWord(text="ACME", page=0, bbox=BBox(x0=0.3, y0=0.1, x1=0.4, y1=0.12), confidence=1.0, method="TEXT"),
            PDFWord(text="Industrial", page=0, bbox=BBox(x0=0.42, y0=0.1, x1=0.55, y1=0.12), confidence=1.0, method="TEXT"),
            PDFWord(text="GmbH", page=0, bbox=BBox(x0=0.57, y0=0.1, x1=0.65, y1=0.12), confidence=1.0, method="TEXT"),
            PDFWord(text="Serial:", page=0, bbox=BBox(x0=0.1, y0=0.15, x1=0.2, y1=0.17), confidence=1.0, method="TEXT"),
            PDFWord(text="SN-2024-001234", page=0, bbox=BBox(x0=0.25, y0=0.15, x1=0.45, y1=0.17), confidence=1.0, method="TEXT"),
            PDFWord(text="Voltage:", page=0, bbox=BBox(x0=0.1, y0=0.2, x1=0.22, y1=0.22), confidence=1.0, method="TEXT"),
            PDFWord(text="24", page=0, bbox=BBox(x0=0.25, y0=0.2, x1=0.28, y1=0.22), confidence=1.0, method="TEXT"),
            PDFWord(text="V", page=0, bbox=BBox(x0=0.29, y0=0.2, x1=0.32, y1=0.22), confidence=1.0, method="TEXT"),
            PDFWord(text="DC", page=0, bbox=BBox(x0=0.33, y0=0.2, x1=0.37, y1=0.22), confidence=1.0, method="TEXT"),
        ],
    )


class TestBBoxValidation:
    """Tests for bounding box validation."""

    def test_bbox_coordinates_normalized(self):
        """Test that bbox coordinates are normalized between 0 and 1."""
        # Valid bbox
        valid_bbox = BBox(x0=0.1, y0=0.2, x1=0.3, y1=0.4)
        assert 0 <= valid_bbox.x0 <= 1
        assert 0 <= valid_bbox.y0 <= 1
        assert 0 <= valid_bbox.x1 <= 1
        assert 0 <= valid_bbox.y1 <= 1

    def test_bbox_x1_greater_than_x0(self):
        """Test that x1 > x0 for valid bbox."""
        bbox = BBox(x0=0.1, y0=0.2, x1=0.3, y1=0.4)
        assert bbox.x1 > bbox.x0

    def test_bbox_y1_greater_than_y0(self):
        """Test that y1 > y0 for valid bbox."""
        bbox = BBox(x0=0.1, y0=0.2, x1=0.3, y1=0.4)
        assert bbox.y1 > bbox.y0

    def test_bbox_contains_point(self):
        """Test helper function to check if bbox contains a point."""
        bbox = BBox(x0=0.1, y0=0.2, x1=0.3, y1=0.4)

        def bbox_contains(bbox: BBox, x: float, y: float) -> bool:
            return bbox.x0 <= x <= bbox.x1 and bbox.y0 <= y <= bbox.y1

        assert bbox_contains(bbox, 0.2, 0.3) is True
        assert bbox_contains(bbox, 0.05, 0.3) is False
        assert bbox_contains(bbox, 0.2, 0.5) is False


class TestBBoxMerging:
    """Tests for multi-word bounding box merging."""

    def test_merge_adjacent_boxes_horizontal(self):
        """Test merging horizontally adjacent bounding boxes."""
        boxes = [
            BBox(x0=0.1, y0=0.2, x1=0.2, y1=0.25),
            BBox(x0=0.22, y0=0.2, x1=0.3, y1=0.25),
            BBox(x0=0.32, y0=0.2, x1=0.4, y1=0.25),
        ]

        # Merge function
        def merge_boxes(boxes: list[BBox]) -> BBox:
            if not boxes:
                raise ValueError("Cannot merge empty list")
            return BBox(
                x0=min(b.x0 for b in boxes),
                y0=min(b.y0 for b in boxes),
                x1=max(b.x1 for b in boxes),
                y1=max(b.y1 for b in boxes),
            )

        merged = merge_boxes(boxes)
        assert merged.x0 == 0.1
        assert merged.y0 == 0.2
        assert merged.x1 == 0.4
        assert merged.y1 == 0.25

    def test_merge_handles_vertical_offset(self):
        """Test merging boxes with slight vertical offset."""
        boxes = [
            BBox(x0=0.1, y0=0.20, x1=0.2, y1=0.25),
            BBox(x0=0.22, y0=0.21, x1=0.3, y1=0.26),  # Slight offset
        ]

        def merge_boxes(boxes: list[BBox]) -> BBox:
            return BBox(
                x0=min(b.x0 for b in boxes),
                y0=min(b.y0 for b in boxes),
                x1=max(b.x1 for b in boxes),
                y1=max(b.y1 for b in boxes),
            )

        merged = merge_boxes(boxes)
        assert merged.y0 == 0.20  # Takes minimum y0
        assert merged.y1 == 0.26  # Takes maximum y1


class TestEvidenceQuoteContainsValue:
    """Tests for evidence quote containing extracted value."""

    def test_evidence_quote_contains_extracted_value(self):
        """Test that evidence quote contains the extracted value."""
        extraction = FieldExtraction(
            path="ManufacturerName",
            value_type="xs:string",
            value_raw="ACME Industrial GmbH",
            value_normalized="ACME Industrial GmbH",
            confidence=0.9,
            confidence_breakdown=None,
            confidence_reasons=[],
            evidence=EvidenceRef(
                page=0,
                quote="Manufacturer: ACME Industrial GmbH",
                boxes=[BBox(x0=0.3, y0=0.1, x1=0.65, y1=0.12)],
                method="TEXT",
                locator_score=0.95,
            ),
            needs_review=False,
            user_edited=False,
            user_approved=False,
        )

        # Value should be in quote
        assert extraction.value_raw in extraction.evidence.quote

    def test_evidence_quote_case_insensitive_match(self):
        """Test case-insensitive matching of value in quote."""
        evidence_quote = "The MANUFACTURER is ACME Corp"
        value = "acme corp"

        assert value.lower() in evidence_quote.lower()

    def test_evidence_partial_value_match(self):
        """Test partial value matching in quote."""
        evidence_quote = "Model: A-100"
        value = "A-100"

        assert value in evidence_quote


class TestLocalizerIntegration:
    """Integration tests for EvidenceLocalizer."""

    def test_localize_single_word_value(self, localizer, simple_pdf_index):
        """Test localizing a single-word value."""
        llm_extraction = LLMFieldExtraction(
            path="SerialNumber",
            value="SN-2024-001234",
            evidence_quote="Serial: SN-2024-001234",
            confidence=0.8,
        )

        # localize_all returns a list of FieldExtractions
        results = localizer.localize_all([llm_extraction], simple_pdf_index)

        assert len(results) == 1
        result = results[0]
        assert result.evidence is not None
        assert result.evidence.page == 0
        assert "SN-2024-001234" in result.evidence.quote
        assert len(result.evidence.boxes) >= 1

    def test_localize_multi_word_value(self, localizer, simple_pdf_index):
        """Test localizing a multi-word value."""
        llm_extraction = LLMFieldExtraction(
            path="ManufacturerName",
            value="ACME Industrial GmbH",
            evidence_quote="Manufacturer: ACME Industrial GmbH",
            confidence=0.8,
        )

        results = localizer.localize_all([llm_extraction], simple_pdf_index)

        assert len(results) == 1
        result = results[0]
        assert result.evidence is not None
        assert result.evidence.page == 0
        # Should contain all words
        assert "ACME" in result.evidence.quote
        assert "Industrial" in result.evidence.quote
        assert "GmbH" in result.evidence.quote

    def test_localize_numeric_value(self, localizer, simple_pdf_index):
        """Test localizing a numeric value with unit."""
        llm_extraction = LLMFieldExtraction(
            path="Voltage",
            value="24",
            evidence_quote="Voltage: 24 V DC",
            confidence=0.8,
        )

        results = localizer.localize_all([llm_extraction], simple_pdf_index)

        assert len(results) == 1
        result = results[0]
        assert result.evidence is not None
        assert "24" in result.evidence.quote

    def test_localize_not_found_returns_none_evidence(self, localizer, simple_pdf_index):
        """Test that localization returns None evidence when value not found."""
        llm_extraction = LLMFieldExtraction(
            path="UnknownField",
            value="NonExistentValue12345",
            evidence_quote="This text does not exist in the PDF at all xyz123",
            confidence=0.5,
        )

        results = localizer.localize_all([llm_extraction], simple_pdf_index)

        assert len(results) == 1
        result = results[0]
        # Evidence should be None or have low locator_score
        if result.evidence is not None:
            assert result.evidence.locator_score < 0.5


class TestCoordinateNormalization:
    """Tests for coordinate normalization."""

    def test_absolute_to_normalized_coords(self):
        """Test converting absolute coords to normalized (0-1)."""
        page_width = 612
        page_height = 792

        # Absolute coords
        abs_x0, abs_y0 = 100, 200
        abs_x1, abs_y1 = 200, 220

        # Normalize
        norm_x0 = abs_x0 / page_width
        norm_y0 = abs_y0 / page_height
        norm_x1 = abs_x1 / page_width
        norm_y1 = abs_y1 / page_height

        assert 0 <= norm_x0 <= 1
        assert 0 <= norm_y0 <= 1
        assert 0 <= norm_x1 <= 1
        assert 0 <= norm_y1 <= 1
        assert norm_x1 > norm_x0
        assert norm_y1 > norm_y0

    def test_normalized_to_absolute_coords(self):
        """Test converting normalized coords back to absolute."""
        page_width = 612
        page_height = 792

        # Normalized bbox
        bbox = BBox(x0=0.1, y0=0.2, x1=0.3, y1=0.25)

        # Convert to absolute
        abs_x0 = int(bbox.x0 * page_width)
        abs_y0 = int(bbox.y0 * page_height)
        abs_x1 = int(bbox.x1 * page_width)
        abs_y1 = int(bbox.y1 * page_height)

        assert abs_x0 == 61
        assert abs_y0 == 158
        assert abs_x1 == 183
        assert abs_y1 == 198
