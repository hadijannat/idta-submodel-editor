"""Tests for Snippet Retriever."""

import pytest

from app.schemas.magic_import import (
    BBox,
    ExtractionHint,
    PDFIndex,
    PDFIndexInfo,
    PDFPageInfo,
    PDFWord,
)
from app.services.magic_import.retriever import SnippetRetriever


@pytest.fixture
def sample_index() -> PDFIndex:
    """Create a sample PDF index for testing."""
    words = []

    # Page 0: Technical data with serial number
    page0_text = "Technical Data Sheet Serial Number SN-12345 Manufacturer Siemens AG"
    for i, word in enumerate(page0_text.split()):
        words.append(
            PDFWord(
                text=word,
                page=0,
                bbox=BBox(
                    x0=0.1 + i * 0.05,
                    y0=0.1,
                    x1=0.14 + i * 0.05,
                    y1=0.15,
                ),
                confidence=1.0,
                method="TEXT",
            )
        )

    # Page 1: More product info
    page1_text = "Product Name Motor Controller Model X100 Voltage 230V Power 5kW"
    for i, word in enumerate(page1_text.split()):
        words.append(
            PDFWord(
                text=word,
                page=1,
                bbox=BBox(
                    x0=0.1 + i * 0.05,
                    y0=0.1,
                    x1=0.14 + i * 0.05,
                    y1=0.15,
                ),
                confidence=1.0,
                method="TEXT",
            )
        )

    return PDFIndex(
        job_id="test-job",
        pdf_path="test.pdf",
        info=PDFIndexInfo(
            total_pages=2,
            pages_with_text=2,
            pages_needing_ocr=0,
            total_words=len(words),
            language_detected=None,
        ),
        pages=[
            PDFPageInfo(
                page_number=0,
                width=612,
                height=792,
                has_text=True,
                needs_ocr=False,
                word_count=10,
            ),
            PDFPageInfo(
                page_number=1,
                width=612,
                height=792,
                has_text=True,
                needs_ocr=False,
                word_count=11,
            ),
        ],
        words=words,
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
            keywords=["serial", "number", "sn"],
            required=True,
        ),
        ExtractionHint(
            path="ManufacturerName",
            label="Manufacturer Name",
            element_type="Property",
            value_type="xs:string",
            keywords=["manufacturer", "company", "vendor"],
            required=True,
        ),
        ExtractionHint(
            path="Voltage",
            label="Voltage",
            element_type="Property",
            value_type="xs:string",
            keywords=["voltage", "v", "volt"],
            required=False,
        ),
    ]


class TestSnippetRetriever:
    """Test suite for SnippetRetriever."""

    def test_init(self):
        """Test retriever initialization."""
        retriever = SnippetRetriever()
        assert retriever.CONTEXT_WORDS == 50
        assert retriever.MIN_SCORE_THRESHOLD == 0.1

    def test_retrieve_snippets_basic(self, sample_index, sample_hints):
        """Test basic snippet retrieval."""
        retriever = SnippetRetriever()
        snippets = retriever.retrieve_snippets(sample_index, sample_hints)

        assert len(snippets) > 0
        # Should find serial number on page 0
        serial_snippets = [s for s in snippets if s.page == 0]
        assert len(serial_snippets) > 0

    def test_retrieve_empty_index(self, sample_hints):
        """Test retrieval with empty index."""
        retriever = SnippetRetriever()
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

        snippets = retriever.retrieve_snippets(empty_index, sample_hints)
        assert snippets == []

    def test_retrieve_empty_hints(self, sample_index):
        """Test retrieval with no hints."""
        retriever = SnippetRetriever()
        snippets = retriever.retrieve_snippets(sample_index, [])
        assert snippets == []

    def test_bm25_scoring(self, sample_index):
        """Test BM25 scoring produces reasonable scores."""
        retriever = SnippetRetriever()

        # Build documents
        page_docs = retriever._build_page_documents(sample_index)
        assert 0 in page_docs
        assert 1 in page_docs

        # Compute stats
        stats = retriever._compute_token_stats(page_docs)
        assert stats.total_docs == 2
        assert stats.avg_doc_len > 0

        # Score pages
        page_scores = retriever._score_pages(
            ["serial", "number"],
            page_docs,
            stats,
        )

        # Page 0 should score higher for "serial number"
        assert len(page_scores) > 0
        assert page_scores[0][0] == 0  # Page 0 is most relevant

    def test_snippet_deduplication(self):
        """Test that overlapping snippets are deduplicated."""
        retriever = SnippetRetriever()

        from app.schemas.magic_import import Snippet

        snippets = [
            Snippet(
                text="Hello world",
                page=0,
                start_word_idx=0,
                end_word_idx=5,
                score=0.9,
            ),
            Snippet(
                text="Hello world again",
                page=0,
                start_word_idx=0,
                end_word_idx=6,
                score=0.8,
            ),
            Snippet(
                text="Different text",
                page=1,
                start_word_idx=0,
                end_word_idx=3,
                score=0.7,
            ),
        ]

        deduped = retriever._deduplicate_snippets(snippets)

        # Should keep highest-scored overlapping snippet
        assert len(deduped) == 2
        assert deduped[0].score == 0.9
        assert deduped[1].score == 0.7

    def test_keyword_normalization_matches_punctuated_terms(self):
        """Ensure keyword matching handles punctuation like E-mail -> email."""
        retriever = SnippetRetriever()

        words = [
            PDFWord(
                text="E-mail",
                page=0,
                bbox=BBox(x0=0.1, y0=0.1, x1=0.2, y1=0.2),
                confidence=1.0,
                method="TEXT",
            ),
            PDFWord(
                text="support@example.com",
                page=0,
                bbox=BBox(x0=0.21, y0=0.1, x1=0.5, y1=0.2),
                confidence=1.0,
                method="TEXT",
            ),
        ]

        index = PDFIndex(
            job_id="email-test",
            pdf_path="email.pdf",
            info=PDFIndexInfo(
                total_pages=1,
                pages_with_text=1,
                pages_needing_ocr=0,
                total_words=len(words),
                language_detected=None,
            ),
            pages=[
                PDFPageInfo(
                    page_number=0,
                    width=612,
                    height=792,
                    has_text=True,
                    needs_ocr=False,
                    word_count=len(words),
                )
            ],
            words=words,
        )

        page_words = [(idx, word) for idx, word in enumerate(index.words)]
        matches = retriever._find_keyword_matches(["email"], page_words)

        assert matches, "Expected keyword match for punctuated 'E-mail'"
