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

    def test_contact_anchor_snippets(self):
        """Ensure contact anchors generate snippets on pages with tel/fax/email."""
        retriever = SnippetRetriever()

        words = [
            PDFWord(
                text="Contact",
                page=0,
                bbox=BBox(x0=0.1, y0=0.1, x1=0.2, y1=0.2),
                confidence=1.0,
                method="TEXT",
            ),
            PDFWord(
                text="Tel.",
                page=0,
                bbox=BBox(x0=0.21, y0=0.1, x1=0.3, y1=0.2),
                confidence=1.0,
                method="TEXT",
            ),
            PDFWord(
                text="+31-152-610-900",
                page=0,
                bbox=BBox(x0=0.31, y0=0.1, x1=0.5, y1=0.2),
                confidence=1.0,
                method="TEXT",
            ),
        ]

        index = PDFIndex(
            job_id="contact-anchor-test",
            pdf_path="contact.pdf",
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

        anchors = retriever._collect_contact_anchor_positions(index)
        snippets = retriever._extract_snippets_for_anchors(index, anchors, limit=2)

        assert anchors, "Expected contact anchors"
        assert snippets, "Expected anchor snippets"

    def test_cluster_indices_empty(self):
        """Test clustering with empty list."""
        retriever = SnippetRetriever()
        clusters = retriever._cluster_indices([])
        assert clusters == []

    def test_cluster_indices_single(self):
        """Test clustering with single index."""
        retriever = SnippetRetriever()
        clusters = retriever._cluster_indices([5])
        assert clusters == [[5]]

    def test_cluster_indices_close_together(self):
        """Test that indices within max_gap are clustered together."""
        retriever = SnippetRetriever()
        # Indices 5, 10, 15 are all within 20 of each other
        clusters = retriever._cluster_indices([5, 10, 15], max_gap=20)
        assert len(clusters) == 1
        assert clusters[0] == [5, 10, 15]

    def test_cluster_indices_far_apart(self):
        """Test that indices beyond max_gap form separate clusters."""
        retriever = SnippetRetriever()
        # Index 5 and 50 are more than 20 apart
        clusters = retriever._cluster_indices([5, 50], max_gap=20)
        assert len(clusters) == 2
        assert clusters[0] == [5]
        assert clusters[1] == [50]

    def test_cluster_indices_mixed(self):
        """Test mixed clustering with multiple groups."""
        retriever = SnippetRetriever()
        # [5, 10, 20] forms one cluster, [100, 110] forms another
        clusters = retriever._cluster_indices([5, 10, 20, 100, 110], max_gap=20)
        assert len(clusters) == 2
        assert clusters[0] == [5, 10, 20]
        assert clusters[1] == [100, 110]

    def test_cluster_indices_unsorted_input(self):
        """Test that clustering works with unsorted input."""
        retriever = SnippetRetriever()
        clusters = retriever._cluster_indices([100, 5, 110, 10], max_gap=20)
        assert len(clusters) == 2
        # First cluster should be sorted
        assert clusters[0] == [5, 10]
        assert clusters[1] == [100, 110]

    def test_contact_block_clustering(self):
        """Test that full contact blocks with multiple anchors are captured."""
        retriever = SnippetRetriever()

        # Simulates a header like:
        # "info@lenntech.com  Tel. +31-152-610-900  www.lenntech.com  Fax. +31-152-616-289"
        words = []
        contact_text = [
            "Lenntech",
            "Water",
            "Treatment",
            "info@lenntech.com",
            "Tel.",
            "+31-152-610-900",
            "www.lenntech.com",
            "Fax.",
            "+31-152-616-289",
        ]
        for i, text in enumerate(contact_text):
            words.append(
                PDFWord(
                    text=text,
                    page=0,
                    bbox=BBox(
                        x0=0.1 + i * 0.05,
                        y0=0.05,
                        x1=0.14 + i * 0.05,
                        y1=0.08,
                    ),
                    confidence=1.0,
                    method="TEXT",
                )
            )

        index = PDFIndex(
            job_id="contact-block-test",
            pdf_path="contact.pdf",
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

        anchors = retriever._collect_contact_anchor_positions(index)
        snippets = retriever._extract_snippets_for_anchors(index, anchors, limit=5)

        # Should find 4 anchors: email (@), Tel., www, Fax.
        assert len(anchors) >= 4, f"Expected at least 4 anchors, got {len(anchors)}"

        # Should create 1 snippet covering the entire cluster
        assert len(snippets) >= 1, "Expected at least 1 snippet for contact block"

        # The snippet should contain all contact info
        snippet_text = snippets[0].text
        assert "info@lenntech.com" in snippet_text
        assert "Tel." in snippet_text
        assert "www.lenntech.com" in snippet_text
        assert "Fax." in snippet_text
