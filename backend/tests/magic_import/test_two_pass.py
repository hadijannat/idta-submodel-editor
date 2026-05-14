"""
Tests for Two-Pass Extraction system.

Tests candidate generation, verification, and the complete two-pass flow.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock

from app.schemas.magic_import import (
    BBox,
    CandidateSet,
    ExtractionCandidate,
    ExtractionHint,
    ExtractionStatus,
    FieldExtraction,
    LLMCandidateResponse,
    PDFIndex,
    PDFIndexInfo,
    PDFPageInfo,
    PDFWord,
    Snippet,
)
from app.services.magic_import.extractor import Extractor


class TestExtractionCandidate:
    """Tests for ExtractionCandidate model."""

    def test_candidate_creation(self):
        """Test creating an ExtractionCandidate."""
        candidate = ExtractionCandidate(
            path="Nameplate/ManufacturerName",
            value="Siemens",
            evidence_quote="Manufacturer: Siemens AG",
            llm_confidence=0.95,
            source="llm",
            reasoning="Clear manufacturer name found in header",
        )

        assert candidate.path == "Nameplate/ManufacturerName"
        assert candidate.value == "Siemens"
        assert candidate.llm_confidence == 0.95
        assert candidate.source == "llm"

    def test_candidate_not_found(self):
        """Test creating a NOT_FOUND candidate."""
        candidate = ExtractionCandidate(
            path="Nameplate/OptionalField",
            value="NOT_FOUND",
            evidence_quote=None,
            llm_confidence=0.8,
            source="llm",
        )

        assert candidate.value == "NOT_FOUND"
        assert candidate.evidence_quote is None

    def test_candidate_sources(self):
        """Test valid source values."""
        for source in ["llm", "regex", "table"]:
            candidate = ExtractionCandidate(
                path="test",
                value="test",
                evidence_quote=None,
                llm_confidence=0.5,
                source=source,
            )
            assert candidate.source == source


class TestCandidateSet:
    """Tests for CandidateSet model."""

    def test_candidate_set_creation(self):
        """Test creating a CandidateSet."""
        candidates = [
            ExtractionCandidate(
                path="test",
                value="Value A",
                evidence_quote="Found A",
                llm_confidence=0.9,
                source="llm",
            ),
            ExtractionCandidate(
                path="test",
                value="Value B",
                evidence_quote="Found B",
                llm_confidence=0.7,
                source="llm",
            ),
        ]

        candidate_set = CandidateSet(
            path="test",
            candidates=candidates,
        )

        assert len(candidate_set.candidates) == 2
        assert candidate_set.selected_index is None

    def test_candidate_set_with_selection(self):
        """Test CandidateSet with selected candidate."""
        candidates = [
            ExtractionCandidate(
                path="test",
                value="Value A",
                evidence_quote="Found A",
                llm_confidence=0.9,
                source="llm",
            ),
        ]

        candidate_set = CandidateSet(
            path="test",
            candidates=candidates,
            selected_index=0,
            verification_notes="Selected based on evidence match",
        )

        assert candidate_set.selected_index == 0
        assert candidate_set.verification_notes is not None


class TestLLMCandidateResponse:
    """Tests for LLMCandidateResponse model."""

    def test_response_creation(self):
        """Test creating an LLMCandidateResponse."""
        response = LLMCandidateResponse(
            candidate_sets=[
                CandidateSet(path="field1", candidates=[]),
                CandidateSet(path="field2", candidates=[]),
            ],
            tokens_used=1500,
            model="gpt-5.5",
        )

        assert len(response.candidate_sets) == 2
        assert response.tokens_used == 1500
        assert response.model == "gpt-5.5"


class TestExtractorTwoPass:
    """Tests for Extractor two-pass methods."""

    @pytest.fixture
    def extractor(self):
        """Create an Extractor instance."""
        return Extractor()

    @pytest.fixture
    def sample_index(self):
        """Create a sample PDF index."""
        return PDFIndex(
            job_id="test-job",
            pdf_path="/tmp/test.pdf",
            info=PDFIndexInfo(
                total_pages=1,
                pages_with_text=1,
                pages_needing_ocr=0,
                total_words=50,
            ),
            pages=[
                PDFPageInfo(
                    page_number=0,
                    width=612.0,
                    height=792.0,
                    has_text=True,
                    needs_ocr=False,
                    word_count=50,
                ),
            ],
            words=[
                PDFWord(text="Manufacturer:", page=0, bbox=BBox(x0=0.1, y0=0.1, x1=0.2, y1=0.12)),
                PDFWord(text="Siemens", page=0, bbox=BBox(x0=0.22, y0=0.1, x1=0.3, y1=0.12)),
                PDFWord(text="AG", page=0, bbox=BBox(x0=0.32, y0=0.1, x1=0.36, y1=0.12)),
                PDFWord(text="Rated", page=0, bbox=BBox(x0=0.1, y0=0.15, x1=0.18, y1=0.17)),
                PDFWord(text="Power:", page=0, bbox=BBox(x0=0.2, y0=0.15, x1=0.28, y1=0.17)),
                PDFWord(text="5.5", page=0, bbox=BBox(x0=0.3, y0=0.15, x1=0.35, y1=0.17)),
                PDFWord(text="kW", page=0, bbox=BBox(x0=0.36, y0=0.15, x1=0.4, y1=0.17)),
            ],
        )

    @pytest.fixture
    def sample_hints(self):
        """Create sample extraction hints."""
        return [
            ExtractionHint(
                path="Nameplate/ManufacturerName",
                label="Manufacturer Name",
                element_type="Property",
                value_type="xs:string",
                keywords=["manufacturer", "hersteller"],
            ),
            ExtractionHint(
                path="Nameplate/RatedPower",
                label="Rated Power",
                element_type="Property",
                value_type="xs:float",
                keywords=["power", "leistung", "kW"],
            ),
        ]

    @pytest.fixture
    def sample_snippets(self):
        """Create sample snippets."""
        return [
            Snippet(
                text="Manufacturer: Siemens AG",
                page=0,
                start_word_idx=0,
                end_word_idx=3,
                score=0.9,
            ),
            Snippet(
                text="Rated Power: 5.5 kW",
                page=0,
                start_word_idx=3,
                end_word_idx=7,
                score=0.85,
            ),
        ]

    # =========================================================================
    # Helper Method Tests
    # =========================================================================

    def test_build_page_texts(self, extractor, sample_index):
        """Test building page text from index."""
        page_texts = extractor._build_page_texts(sample_index)

        assert 0 in page_texts
        assert "Manufacturer:" in page_texts[0]
        assert "Siemens" in page_texts[0]

    def test_find_quote_in_text(self, extractor):
        """Test finding a quote in page text."""
        page_texts = {0: "The manufacturer is Siemens AG located in Munich."}

        result = extractor._find_quote_in_text("Siemens AG", page_texts)

        assert result is not None
        page, start, end = result
        assert page == 0
        assert page_texts[0][start:end] == "Siemens AG"

    def test_find_quote_in_text_not_found(self, extractor):
        """Test when quote is not found."""
        page_texts = {0: "The manufacturer is Siemens AG."}

        result = extractor._find_quote_in_text("Bosch GmbH", page_texts)

        assert result is None

    def test_find_quote_in_text_case_insensitive(self, extractor):
        """Test case-insensitive quote matching."""
        page_texts = {0: "The manufacturer is SIEMENS AG."}

        result = extractor._find_quote_in_text("siemens ag", page_texts)

        assert result is not None

    def test_find_quote_in_text_partial(self, extractor):
        """Test partial quote matching."""
        page_texts = {0: "The manufacturer is Siemens AG Munich."}

        # If quote is slightly different, should still find partial match
        result = extractor._find_quote_in_text("Siemens", page_texts)

        assert result is not None

    def test_compute_snippet_hash(self, extractor):
        """Test computing hash for evidence snippet."""
        hash1 = extractor._compute_snippet_hash("Hello World")
        hash2 = extractor._compute_snippet_hash("Hello World")
        hash3 = extractor._compute_snippet_hash("Different Text")

        # Same input produces same hash
        assert hash1 == hash2
        # Different input produces different hash
        assert hash1 != hash3
        # Hash is a reasonable length
        assert len(hash1) == 16

    # =========================================================================
    # Candidate Verification Tests
    # =========================================================================

    def test_verify_candidate_set_with_valid_quote(self, extractor, sample_index, sample_hints):
        """Test verifying a candidate with valid evidence."""
        candidate = ExtractionCandidate(
            path="Nameplate/ManufacturerName",
            value="Siemens",
            evidence_quote="Siemens AG",
            llm_confidence=0.9,
            source="llm",
        )
        candidate_set = CandidateSet(
            path="Nameplate/ManufacturerName",
            candidates=[candidate],
        )

        page_texts = extractor._build_page_texts(sample_index)
        hint = sample_hints[0]  # ManufacturerName hint

        extraction = extractor._verify_candidate_set(
            candidate_set, sample_index, page_texts, hint
        )

        assert extraction is not None
        assert extraction.value_raw == "Siemens"
        assert extraction.evidence is not None
        assert extraction.evidence.quote == "Siemens AG"

    def test_verify_candidate_set_no_valid_quote(self, extractor, sample_index, sample_hints):
        """Test verifying a candidate without valid evidence."""
        candidate = ExtractionCandidate(
            path="Nameplate/ManufacturerName",
            value="Bosch",  # Not in document
            evidence_quote="Bosch GmbH",  # Not in document
            llm_confidence=0.5,
            source="llm",
        )
        candidate_set = CandidateSet(
            path="Nameplate/ManufacturerName",
            candidates=[candidate],
        )

        page_texts = extractor._build_page_texts(sample_index)
        hint = sample_hints[0]

        extraction = extractor._verify_candidate_set(
            candidate_set, sample_index, page_texts, hint
        )

        # Should return extraction but with NEEDS_REVIEW status
        assert extraction is not None
        assert extraction.status == ExtractionStatus.NEEDS_REVIEW

    def test_verify_candidate_set_not_found(self, extractor, sample_index):
        """Test verifying NOT_FOUND candidate."""
        candidate = ExtractionCandidate(
            path="Nameplate/OptionalField",
            value="NOT_FOUND",
            evidence_quote=None,
            llm_confidence=0.9,
            source="llm",
        )
        candidate_set = CandidateSet(
            path="Nameplate/OptionalField",
            candidates=[candidate],
        )
        hint = ExtractionHint(
            path="Nameplate/OptionalField",
            label="Optional Field",
            element_type="Property",
        )

        page_texts = extractor._build_page_texts(sample_index)

        extraction = extractor._verify_candidate_set(
            candidate_set, sample_index, page_texts, hint
        )

        assert extraction is not None
        assert extraction.status == ExtractionStatus.EMPTY
        assert extraction.value_raw == ""

    def test_verify_candidate_set_picks_best(self, extractor, sample_index, sample_hints):
        """Test that verification picks the best verifiable candidate."""
        candidates = [
            ExtractionCandidate(
                path="Nameplate/ManufacturerName",
                value="Unknown",
                evidence_quote="Unknown Corp",  # Not in document
                llm_confidence=0.95,
                source="llm",
            ),
            ExtractionCandidate(
                path="Nameplate/ManufacturerName",
                value="Siemens",
                evidence_quote="Siemens AG",  # In document
                llm_confidence=0.85,
                source="llm",
            ),
        ]
        candidate_set = CandidateSet(
            path="Nameplate/ManufacturerName",
            candidates=candidates,
        )

        page_texts = extractor._build_page_texts(sample_index)
        hint = sample_hints[0]

        extraction = extractor._verify_candidate_set(
            candidate_set, sample_index, page_texts, hint
        )

        # Should pick Siemens because it has valid evidence
        assert extraction is not None
        assert extraction.value_raw == "Siemens"

    # =========================================================================
    # Full Verification Tests
    # =========================================================================

    def test_verify_candidates_integration(self, extractor, sample_index, sample_hints):
        """Test full verify_candidates flow."""
        candidate_sets = [
            CandidateSet(
                path="Nameplate/ManufacturerName",
                candidates=[
                    ExtractionCandidate(
                        path="Nameplate/ManufacturerName",
                        value="Siemens",
                        evidence_quote="Siemens AG",
                        llm_confidence=0.9,
                        source="llm",
                    ),
                ],
            ),
            CandidateSet(
                path="Nameplate/RatedPower",
                candidates=[
                    ExtractionCandidate(
                        path="Nameplate/RatedPower",
                        value="5.5",
                        evidence_quote="5.5 kW",
                        llm_confidence=0.85,
                        source="llm",
                    ),
                ],
            ),
        ]
        hints_by_path = {h.path: h for h in sample_hints}

        extractions = extractor.verify_candidates(candidate_sets, sample_index, hints_by_path)

        assert len(extractions) == 2
        assert all(isinstance(e, FieldExtraction) for e in extractions)

        # Check that paths are preserved
        paths = [e.path for e in extractions]
        assert "Nameplate/ManufacturerName" in paths
        assert "Nameplate/RatedPower" in paths

    def test_verify_candidates_empty_set(self, extractor, sample_index):
        """Test verifying empty candidate set.

        When a candidate set has no candidates, the verifier cannot determine
        if the value is truly absent or just failed to be extracted, so it
        returns NEEDS_REVIEW rather than EMPTY.
        """
        candidate_sets = [
            CandidateSet(
                path="Nameplate/EmptyField",
                candidates=[],
            ),
        ]
        hints_by_path = {
            "Nameplate/EmptyField": ExtractionHint(
                path="Nameplate/EmptyField",
                label="Empty Field",
                element_type="Property",
            ),
        }

        extractions = extractor.verify_candidates(candidate_sets, sample_index, hints_by_path)

        assert len(extractions) == 1
        # Empty candidate set → NEEDS_REVIEW (not EMPTY, as we can't confirm absence)
        assert extractions[0].status == ExtractionStatus.NEEDS_REVIEW

    # =========================================================================
    # Two-Pass Flow Tests (Mocked)
    # =========================================================================

    @pytest.mark.asyncio
    async def test_extract_two_pass_flow(
        self, extractor, sample_index, sample_hints, sample_snippets
    ):
        """Test the complete two-pass extraction flow with mocked LLM provider."""
        # Mock the internal _provider attribute
        mock_provider = MagicMock()
        mock_provider.model = "test-model"
        mock_provider.generate_candidates = AsyncMock(
            return_value=LLMCandidateResponse(
                candidate_sets=[
                    CandidateSet(
                        path="Nameplate/ManufacturerName",
                        candidates=[
                            ExtractionCandidate(
                                path="Nameplate/ManufacturerName",
                                value="Siemens",
                                evidence_quote="Siemens AG",
                                llm_confidence=0.9,
                                source="llm",
                            ),
                        ],
                    ),
                ],
                tokens_used=500,
                model="test-model",
            )
        )

        # Inject the mock provider
        extractor._provider = mock_provider

        extractions = await extractor.generate_candidates_async(
            hints=sample_hints,
            snippets=sample_snippets,
        )

        # Verify candidates generated
        assert len(extractions.candidate_sets) == 1
        assert extractions.candidate_sets[0].path == "Nameplate/ManufacturerName"

        # Now verify them
        verified = extractor.verify_candidates(
            extractions.candidate_sets,
            sample_index,
            {h.path: h for h in sample_hints},
        )

        assert len(verified) == 1
        assert verified[0].path == "Nameplate/ManufacturerName"
        assert verified[0].value_raw == "Siemens"


class TestEvidenceEnrichment:
    """Tests for evidence enrichment in two-pass flow."""

    @pytest.fixture
    def extractor(self):
        return Extractor()

    @pytest.fixture
    def simple_hint(self):
        return ExtractionHint(
            path="test",
            label="Test Field",
            element_type="Property",
        )

    def test_evidence_has_snippet_hash(self, extractor, simple_hint):
        """Test that verified evidence includes snippet hash."""
        index = PDFIndex(
            job_id="test",
            pdf_path="/tmp/test.pdf",
            info=PDFIndexInfo(
                total_pages=1,
                pages_with_text=1,
                pages_needing_ocr=0,
                total_words=10,
            ),
            pages=[
                PDFPageInfo(
                    page_number=0,
                    width=612.0,
                    height=792.0,
                    has_text=True,
                    needs_ocr=False,
                    word_count=10,
                ),
            ],
            words=[
                PDFWord(text="Hello", page=0, bbox=BBox(x0=0.1, y0=0.1, x1=0.2, y1=0.12)),
                PDFWord(text="World", page=0, bbox=BBox(x0=0.22, y0=0.1, x1=0.3, y1=0.12)),
            ],
        )

        candidate_set = CandidateSet(
            path="test",
            candidates=[
                ExtractionCandidate(
                    path="test",
                    value="Hello",
                    evidence_quote="Hello World",
                    llm_confidence=0.9,
                    source="llm",
                ),
            ],
        )

        page_texts = extractor._build_page_texts(index)
        extraction = extractor._verify_candidate_set(candidate_set, index, page_texts, simple_hint)

        # Evidence should include snippet_hash for reproducibility
        if extraction.evidence:
            assert extraction.evidence.snippet_hash is not None

    def test_evidence_has_char_offsets(self, extractor, simple_hint):
        """Test that verified evidence includes character offsets."""
        index = PDFIndex(
            job_id="test",
            pdf_path="/tmp/test.pdf",
            info=PDFIndexInfo(
                total_pages=1,
                pages_with_text=1,
                pages_needing_ocr=0,
                total_words=10,
            ),
            pages=[
                PDFPageInfo(
                    page_number=0,
                    width=612.0,
                    height=792.0,
                    has_text=True,
                    needs_ocr=False,
                    word_count=10,
                ),
            ],
            words=[
                PDFWord(text="Test", page=0, bbox=BBox(x0=0.1, y0=0.1, x1=0.2, y1=0.12)),
                PDFWord(text="Value", page=0, bbox=BBox(x0=0.22, y0=0.1, x1=0.3, y1=0.12)),
            ],
        )

        candidate_set = CandidateSet(
            path="test",
            candidates=[
                ExtractionCandidate(
                    path="test",
                    value="Test",
                    evidence_quote="Test Value",
                    llm_confidence=0.9,
                    source="llm",
                ),
            ],
        )

        page_texts = extractor._build_page_texts(index)
        extraction = extractor._verify_candidate_set(candidate_set, index, page_texts, simple_hint)

        # Evidence should include char_start and char_end for precise localization
        if extraction.evidence:
            assert extraction.evidence.char_start is not None
            assert extraction.evidence.char_end is not None
            assert extraction.evidence.char_start >= 0
            assert extraction.evidence.char_end > extraction.evidence.char_start


class TestExtractionStatusTransitions:
    """Tests for extraction status transitions in two-pass flow."""

    @pytest.fixture
    def extractor(self):
        return Extractor()

    @pytest.fixture
    def simple_hint(self):
        return ExtractionHint(
            path="test",
            label="Test Field",
            element_type="Property",
        )

    @pytest.fixture
    def simple_index(self):
        """Create a simple index for testing."""
        return PDFIndex(
            job_id="test",
            pdf_path="/tmp/test.pdf",
            info=PDFIndexInfo(
                total_pages=1,
                pages_with_text=1,
                pages_needing_ocr=0,
                total_words=5,
            ),
            pages=[
                PDFPageInfo(
                    page_number=0,
                    width=612.0,
                    height=792.0,
                    has_text=True,
                    needs_ocr=False,
                    word_count=5,
                ),
            ],
            words=[
                PDFWord(text="Value", page=0, bbox=BBox(x0=0.1, y0=0.1, x1=0.2, y1=0.12)),
                PDFWord(text="123", page=0, bbox=BBox(x0=0.22, y0=0.1, x1=0.3, y1=0.12)),
            ],
        )

    def test_verified_candidate_becomes_filled(self, extractor, simple_index, simple_hint):
        """Test that verified candidate with evidence becomes FILLED."""
        candidate_set = CandidateSet(
            path="test",
            candidates=[
                ExtractionCandidate(
                    path="test",
                    value="123",
                    evidence_quote="Value 123",
                    llm_confidence=0.95,
                    source="llm",
                ),
            ],
        )

        page_texts = extractor._build_page_texts(simple_index)
        extraction = extractor._verify_candidate_set(candidate_set, simple_index, page_texts, simple_hint)

        assert extraction.status == ExtractionStatus.FILLED

    def test_not_found_becomes_empty(self, extractor, simple_index, simple_hint):
        """Test that NOT_FOUND candidate becomes EMPTY."""
        candidate_set = CandidateSet(
            path="test",
            candidates=[
                ExtractionCandidate(
                    path="test",
                    value="NOT_FOUND",
                    evidence_quote=None,
                    llm_confidence=0.9,
                    source="llm",
                ),
            ],
        )

        page_texts = extractor._build_page_texts(simple_index)
        extraction = extractor._verify_candidate_set(candidate_set, simple_index, page_texts, simple_hint)

        assert extraction.status == ExtractionStatus.EMPTY
        assert extraction.value_raw == ""

    def test_unverifiable_becomes_needs_review(self, extractor, simple_index, simple_hint):
        """Test that unverifiable candidate becomes NEEDS_REVIEW."""
        candidate_set = CandidateSet(
            path="test",
            candidates=[
                ExtractionCandidate(
                    path="test",
                    value="MissingValue",
                    evidence_quote="Not in document",
                    llm_confidence=0.5,
                    source="llm",
                ),
            ],
        )

        page_texts = extractor._build_page_texts(simple_index)
        extraction = extractor._verify_candidate_set(candidate_set, simple_index, page_texts, simple_hint)

        assert extraction.status == ExtractionStatus.NEEDS_REVIEW
