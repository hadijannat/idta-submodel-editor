"""Tests for Evidence Localizer."""

import pytest

from app.schemas.magic_import import (
    BBox,
    LLMFieldExtraction,
    PDFIndex,
    PDFIndexInfo,
    PDFWord,
)
from app.services.magic_import.localizer import EvidenceLocalizer


@pytest.fixture
def sample_index() -> PDFIndex:
    """Create a sample PDF index for testing."""
    words = []

    # Page 0: "Serial Number SN-12345 manufactured by Siemens AG"
    text = "Serial Number SN-12345 manufactured by Siemens AG"
    x_offset = 0.1
    for i, word in enumerate(text.split()):
        words.append(
            PDFWord(
                text=word,
                page=0,
                bbox=BBox(
                    x0=x_offset,
                    y0=0.1,
                    x1=x_offset + 0.08,
                    y1=0.15,
                ),
                confidence=1.0,
                method="TEXT",
            )
        )
        x_offset += 0.1

    return PDFIndex(
        job_id="test",
        pdf_path="test.pdf",
        info=PDFIndexInfo(
            total_pages=1,
            pages_with_text=1,
            pages_needing_ocr=0,
            total_words=len(words),
        ),
        pages=[],
        words=words,
    )


class TestEvidenceLocalizer:
    """Test suite for EvidenceLocalizer."""

    def test_init(self):
        """Test localizer initialization."""
        localizer = EvidenceLocalizer()
        assert localizer.MIN_MATCH_SCORE == 0.6

    def test_localize_exact_match(self, sample_index):
        """Test localizing an exact quote match."""
        localizer = EvidenceLocalizer()

        evidence, score = localizer._localize_quote(
            "Serial Number SN-12345",
            sample_index,
        )

        assert evidence is not None
        assert evidence.page == 0
        assert score >= 0.9
        assert len(evidence.boxes) > 0
        assert "Serial" in evidence.quote or "serial" in evidence.quote.lower()

    def test_localize_partial_match(self, sample_index):
        """Test localizing a partial/fuzzy match."""
        localizer = EvidenceLocalizer()

        # Slightly different wording
        evidence, score = localizer._localize_quote(
            "serial number",
            sample_index,
        )

        assert evidence is not None
        assert evidence.page == 0
        assert score >= 0.6

    def test_localize_token_overlap_fallback(self, sample_index):
        """Test token-overlap fallback when exact match fails."""
        localizer = EvidenceLocalizer()

        # Tokens overlap but not exact sequence
        evidence, score = localizer._localize_quote(
            "Serial Number manufactured",
            sample_index,
        )

        assert evidence is not None
        assert evidence.page == 0
        assert score >= localizer.MIN_MATCH_SCORE

    def test_localize_no_match(self, sample_index):
        """Test localizing a quote that doesn't exist."""
        localizer = EvidenceLocalizer()

        evidence, score = localizer._localize_quote(
            "this text does not exist in document",
            sample_index,
        )

        # Should return None or very low score
        if evidence is not None:
            assert score < 0.6

    def test_localize_all(self, sample_index):
        """Test localizing all LLM extractions."""
        localizer = EvidenceLocalizer()

        llm_extractions = [
            LLMFieldExtraction(
                path="SerialNumber",
                value="SN-12345",
                evidence_quote="Serial Number SN-12345",
                confidence=0.95,
            ),
            LLMFieldExtraction(
                path="ManufacturerName",
                value="Siemens AG",
                evidence_quote="manufactured by Siemens AG",
                confidence=0.9,
            ),
        ]

        results = localizer.localize_all(llm_extractions, sample_index)

        assert len(results) == 2
        assert results[0].path == "SerialNumber"
        assert results[0].value_raw == "SN-12345"
        assert results[1].path == "ManufacturerName"

        # At least one should have evidence
        has_evidence = sum(1 for r in results if r.evidence is not None)
        assert has_evidence >= 1

    def test_bbox_merging(self):
        """Test merging adjacent bounding boxes."""
        localizer = EvidenceLocalizer()

        boxes = [
            BBox(x0=0.1, y0=0.1, x1=0.2, y1=0.15),
            BBox(x0=0.2, y0=0.1, x1=0.3, y1=0.15),  # Same line
            BBox(x0=0.1, y0=0.3, x1=0.3, y1=0.35),  # Different line
        ]

        merged = localizer._merge_boxes(boxes)

        # Should merge first two into one line, keep third separate
        assert len(merged) == 2

    def test_normalize_text(self):
        """Test text normalization."""
        localizer = EvidenceLocalizer()

        assert localizer._normalize_text("  Hello   World  ") == "hello world"
        assert localizer._normalize_text("UPPERCASE") == "uppercase"
        assert localizer._normalize_text("Multiple   Spaces") == "multiple spaces"

    def test_empty_quote(self, sample_index):
        """Test handling of empty quote."""
        localizer = EvidenceLocalizer()

        evidence, score = localizer._localize_quote("", sample_index)
        assert evidence is None
        assert score == 0.0

    def test_empty_index(self):
        """Test handling of empty index."""
        localizer = EvidenceLocalizer()

        empty_index = PDFIndex(
            job_id="empty",
            pdf_path="empty.pdf",
            info=PDFIndexInfo(
                total_pages=0,
                pages_with_text=0,
                pages_needing_ocr=0,
                total_words=0,
            ),
            pages=[],
            words=[],
        )

        evidence, score = localizer._localize_quote("some text", empty_index)
        assert evidence is None
        assert score == 0.0
