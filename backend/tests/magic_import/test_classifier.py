"""Tests for DocumentClassifier."""

import pytest

from app.schemas.magic_import import (
    BBox,
    DocumentClassification,
    PDFIndex,
    PDFIndexInfo,
    PDFPageInfo,
    PDFWord,
)
from app.services.magic_import.classifier import DocumentClassifier


@pytest.fixture
def classifier():
    """Create a DocumentClassifier instance."""
    return DocumentClassifier()


@pytest.fixture
def text_pdf_index():
    """Create a PDFIndex for a text-based PDF."""
    return PDFIndex(
        job_id="test-job-1",
        pdf_path="/tmp/test.pdf",
        info=PDFIndexInfo(
            total_pages=5,
            pages_with_text=5,
            pages_needing_ocr=0,
            total_words=500,
            language_detected="en",
        ),
        pages=[
            PDFPageInfo(page_number=i, width=612, height=792, has_text=True, needs_ocr=False, word_count=100)
            for i in range(5)
        ],
        words=[
            PDFWord(
                text=f"word{i}",
                page=i % 5,
                bbox=BBox(x0=0.1, y0=0.1, x1=0.2, y1=0.15),
                confidence=1.0,
                method="TEXT",
            )
            for i in range(500)
        ],
    )


@pytest.fixture
def scanned_pdf_index():
    """Create a PDFIndex for a scanned PDF."""
    return PDFIndex(
        job_id="test-job-2",
        pdf_path="/tmp/scanned.pdf",
        info=PDFIndexInfo(
            total_pages=3,
            pages_with_text=0,
            pages_needing_ocr=3,
            total_words=300,
            language_detected=None,
        ),
        pages=[
            PDFPageInfo(page_number=i, width=612, height=792, has_text=False, needs_ocr=True, word_count=100)
            for i in range(3)
        ],
        words=[
            PDFWord(
                text=f"word{i}",
                page=i % 3,
                bbox=BBox(x0=0.1, y0=0.1, x1=0.2, y1=0.15),
                confidence=0.85,
                method="OCR",
            )
            for i in range(300)
        ],
    )


@pytest.fixture
def mixed_pdf_index():
    """Create a PDFIndex for a mixed text/scanned PDF."""
    return PDFIndex(
        job_id="test-job-3",
        pdf_path="/tmp/mixed.pdf",
        info=PDFIndexInfo(
            total_pages=4,
            pages_with_text=2,
            pages_needing_ocr=2,
            total_words=400,
            language_detected="de",
        ),
        pages=[
            PDFPageInfo(page_number=0, width=612, height=792, has_text=True, needs_ocr=False, word_count=100),
            PDFPageInfo(page_number=1, width=612, height=792, has_text=True, needs_ocr=False, word_count=100),
            PDFPageInfo(page_number=2, width=612, height=792, has_text=False, needs_ocr=True, word_count=100),
            PDFPageInfo(page_number=3, width=612, height=792, has_text=False, needs_ocr=True, word_count=100),
        ],
        words=[
            PDFWord(
                text=f"word{i}",
                page=i % 4,
                bbox=BBox(x0=0.1, y0=0.1, x1=0.2, y1=0.15),
                confidence=1.0 if i % 4 < 2 else 0.8,
                method="TEXT" if i % 4 < 2 else "OCR",
            )
            for i in range(400)
        ],
    )


class TestDocumentClassifier:
    """Tests for DocumentClassifier."""

    def test_classify_text_document(self, classifier, text_pdf_index):
        """Test classification of a text-based PDF."""
        result = classifier.classify(text_pdf_index)

        assert isinstance(result, DocumentClassification)
        assert result.doc_type == "text"
        assert result.language == "en"
        assert result.quality_score > 0.5
        assert result.avg_ocr_confidence is None
        assert result.text_density == 100.0  # 500 words / 5 pages

    def test_classify_scanned_document(self, classifier, scanned_pdf_index):
        """Test classification of a scanned PDF."""
        result = classifier.classify(scanned_pdf_index)

        assert result.doc_type == "scanned"
        assert result.avg_ocr_confidence == 0.85
        assert result.text_density == 100.0  # 300 words / 3 pages

    def test_classify_mixed_document(self, classifier, mixed_pdf_index):
        """Test classification of a mixed PDF."""
        result = classifier.classify(mixed_pdf_index)

        assert result.doc_type == "mixed"
        assert result.language == "de"
        assert result.avg_ocr_confidence is not None
        assert result.avg_ocr_confidence == 0.8

    def test_quality_score_bounds(self, classifier, text_pdf_index):
        """Test that quality score is within valid bounds."""
        result = classifier.classify(text_pdf_index)

        assert 0.0 <= result.quality_score <= 1.0

    def test_empty_document(self, classifier):
        """Test classification of an empty PDF."""
        empty_index = PDFIndex(
            job_id="test-empty",
            pdf_path="/tmp/empty.pdf",
            info=PDFIndexInfo(
                total_pages=1,
                pages_with_text=0,
                pages_needing_ocr=0,
                total_words=0,
                language_detected=None,
            ),
            pages=[PDFPageInfo(page_number=0, width=612, height=792, has_text=False, needs_ocr=False, word_count=0)],
            words=[],
        )

        result = classifier.classify(empty_index)

        # Empty document with no text pages and no OCR pages is classified as "mixed"
        # because neither ratio exceeds the threshold
        assert result.doc_type == "mixed"
        assert result.quality_score == 0.0
        assert result.text_density == 0.0


class TestTableDetection:
    """Tests for table detection."""

    def test_detect_tables_with_keywords(self, classifier):
        """Test table detection with table-related keywords."""
        index = PDFIndex(
            job_id="test-tables",
            pdf_path="/tmp/tables.pdf",
            info=PDFIndexInfo(
                total_pages=1,
                pages_with_text=1,
                pages_needing_ocr=0,
                total_words=50,
                language_detected="en",
            ),
            pages=[PDFPageInfo(page_number=0, width=612, height=792, has_text=True, needs_ocr=False, word_count=50)],
            words=[
                PDFWord(text="Table", page=0, bbox=BBox(x0=0.1, y0=0.1, x1=0.2, y1=0.15), confidence=1.0, method="TEXT"),
                PDFWord(text="1:", page=0, bbox=BBox(x0=0.2, y0=0.1, x1=0.25, y1=0.15), confidence=1.0, method="TEXT"),
                PDFWord(text="Header", page=0, bbox=BBox(x0=0.1, y0=0.2, x1=0.2, y1=0.25), confidence=1.0, method="TEXT"),
                PDFWord(text="Row", page=0, bbox=BBox(x0=0.1, y0=0.3, x1=0.2, y1=0.35), confidence=1.0, method="TEXT"),
                PDFWord(text="Column", page=0, bbox=BBox(x0=0.2, y0=0.3, x1=0.3, y1=0.35), confidence=1.0, method="TEXT"),
            ],
        )

        result = classifier.classify(index)
        assert result.has_tables is True

    def test_no_tables_detected(self, classifier, text_pdf_index):
        """Test that tables are not detected in regular text."""
        result = classifier.classify(text_pdf_index)
        assert result.has_tables is False


class TestLanguageDetection:
    """Tests for language detection."""

    def test_english_detection(self, classifier):
        """Test English language detection."""
        index = PDFIndex(
            job_id="test-en",
            pdf_path="/tmp/en.pdf",
            info=PDFIndexInfo(
                total_pages=1,
                pages_with_text=1,
                pages_needing_ocr=0,
                total_words=20,
                language_detected=None,
            ),
            pages=[PDFPageInfo(page_number=0, width=612, height=792, has_text=True, needs_ocr=False, word_count=20)],
            words=[
                PDFWord(text=word, page=0, bbox=BBox(x0=0.1, y0=0.1, x1=0.2, y1=0.15), confidence=1.0, method="TEXT")
                for word in ["the", "and", "for", "with", "this", "that", "from", "have", "test", "document"]
            ],
        )

        result = classifier.classify(index)
        assert result.language == "en"

    def test_german_detection(self, classifier):
        """Test German language detection."""
        index = PDFIndex(
            job_id="test-de",
            pdf_path="/tmp/de.pdf",
            info=PDFIndexInfo(
                total_pages=1,
                pages_with_text=1,
                pages_needing_ocr=0,
                total_words=20,
                language_detected=None,
            ),
            pages=[PDFPageInfo(page_number=0, width=612, height=792, has_text=True, needs_ocr=False, word_count=20)],
            words=[
                PDFWord(text=word, page=0, bbox=BBox(x0=0.1, y0=0.1, x1=0.2, y1=0.15), confidence=1.0, method="TEXT")
                for word in ["der", "die", "das", "und", "für", "mit", "von", "Dokument", "Test", "Seite"]
            ],
        )

        result = classifier.classify(index)
        assert result.language == "de"

    def test_uses_predetected_language(self, classifier, text_pdf_index):
        """Test that pre-detected language is used."""
        result = classifier.classify(text_pdf_index)
        assert result.language == "en"  # From index.info.language_detected
