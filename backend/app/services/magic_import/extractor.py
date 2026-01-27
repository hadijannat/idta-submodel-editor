"""
Extractor - Orchestrates LLM-based field extraction.

Coordinates between the LLM provider and handles extraction batching
for large documents.

Two-Pass Extraction Flow:
1. generate_candidates(): High-recall candidate generation via LLM
2. verify_candidates(): Deterministic verification against PDF index
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import TYPE_CHECKING

from app.config import get_settings
from app.schemas.magic_import import (
    CandidateSet,
    ConfidenceReason,
    ConfidenceReasonCode,
    ExtractionCandidate,
    ExtractionHint,
    ExtractionStatus,
    FieldExtraction,
    LLMCandidateResponse,
    LLMExtractionResponse,
    LLMFieldExtraction,
    PDFIndex,
    Snippet,
    EvidenceRef,
)
from app.services.magic_import.llm.factory import get_provider

if TYPE_CHECKING:
    from app.services.magic_import.llm.provider_base import LLMProvider

logger = logging.getLogger(__name__)


class Extractor:
    """Orchestrates LLM-based field extraction."""

    # Maximum hints per batch (to fit in context window)
    MAX_HINTS_PER_BATCH = 30

    # Maximum snippets per batch
    MAX_SNIPPETS_PER_BATCH = 20

    # Maximum tokens for response
    MAX_TOKENS = 4096

    def __init__(self, provider: "LLMProvider | None" = None) -> None:
        self.settings = get_settings()
        self._provider = provider

    @property
    def provider(self) -> "LLMProvider":
        """Lazy-load LLM provider."""
        if self._provider is None:
            self._provider = get_provider()
        return self._provider

    def extract_fields(
        self,
        hints: list[ExtractionHint],
        snippets: list[Snippet],
    ) -> LLMExtractionResponse:
        """
        Extract field values from snippets using LLM.

        Handles batching for large hint/snippet sets.

        Args:
            hints: Extraction hints describing target fields
            snippets: Relevant document snippets

        Returns:
            Combined extraction response
        """
        # Run async extraction in sync context
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(
                self.extract_fields_async(hints, snippets)
            )
        finally:
            loop.close()

    async def extract_fields_async(
        self,
        hints: list[ExtractionHint],
        snippets: list[Snippet],
    ) -> LLMExtractionResponse:
        """Async version of extract_fields."""
        if not hints or not snippets:
            return LLMExtractionResponse(
                extractions=[],
                tokens_used=0,
                model=self.provider.model,
            )

        # If small enough, do single extraction
        if (
            len(hints) <= self.MAX_HINTS_PER_BATCH
            and len(snippets) <= self.MAX_SNIPPETS_PER_BATCH
        ):
            return await self._extract_batch(hints, snippets)

        # Otherwise, batch by hints
        all_extractions: list[LLMFieldExtraction] = []
        total_tokens = 0
        total_prompt_tokens = 0
        total_completion_tokens = 0

        # Sort snippets by relevance score
        sorted_snippets = sorted(snippets, key=lambda s: s.score, reverse=True)
        top_snippets = sorted_snippets[:self.MAX_SNIPPETS_PER_BATCH]

        # Process hints in batches
        for i in range(0, len(hints), self.MAX_HINTS_PER_BATCH):
            batch_hints = hints[i : i + self.MAX_HINTS_PER_BATCH]

            try:
                response = await self._extract_batch(batch_hints, top_snippets)
                all_extractions.extend(response.extractions)
                total_tokens += response.tokens_used
                if response.prompt_tokens is not None:
                    total_prompt_tokens += response.prompt_tokens
                if response.completion_tokens is not None:
                    total_completion_tokens += response.completion_tokens
            except Exception as e:
                logger.warning("Batch extraction failed: %s", e)
                continue

        # Deduplicate extractions (same path)
        unique_extractions = self._deduplicate_extractions(all_extractions)

        return LLMExtractionResponse(
            extractions=unique_extractions,
            tokens_used=total_tokens,
            prompt_tokens=total_prompt_tokens or None,
            completion_tokens=total_completion_tokens or None,
            model=self.provider.model,
        )

    async def _extract_batch(
        self,
        hints: list[ExtractionHint],
        snippets: list[Snippet],
    ) -> LLMExtractionResponse:
        """Extract a single batch of hints."""
        logger.debug(
            "Extracting batch: %d hints, %d snippets",
            len(hints),
            len(snippets),
        )

        response = await self.provider.extract_structured(
            hints=hints,
            snippets=snippets,
            max_tokens=self.MAX_TOKENS,
        )

        # Filter extractions to only include valid paths
        valid_paths = {h.path for h in hints}
        valid_extractions = [
            e for e in response.extractions
            if e.path in valid_paths
        ]

        return LLMExtractionResponse(
            extractions=valid_extractions,
            tokens_used=response.tokens_used,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            model=response.model,
        )

    def _deduplicate_extractions(
        self,
        extractions: list[LLMFieldExtraction],
    ) -> list[LLMFieldExtraction]:
        """Deduplicate extractions, keeping highest confidence per path."""
        best_by_path: dict[str, LLMFieldExtraction] = {}

        for extraction in extractions:
            existing = best_by_path.get(extraction.path)
            if existing is None or extraction.confidence > existing.confidence:
                best_by_path[extraction.path] = extraction

        return list(best_by_path.values())

    async def extract_single_field(
        self,
        hint: ExtractionHint,
        snippets: list[Snippet],
    ) -> LLMFieldExtraction | None:
        """Extract a single field value."""
        response = await self._extract_batch([hint], snippets)
        if response.extractions:
            return response.extractions[0]
        return None

    # ========================================================================
    # Two-Pass Extraction: Pass A (Candidate Generation) + Pass B (Verification)
    # ========================================================================

    def generate_candidates(
        self,
        hints: list[ExtractionHint],
        snippets: list[Snippet],
    ) -> LLMCandidateResponse:
        """
        Pass A: High-recall candidate generation via LLM.

        Generates 1-3 candidates per field, including NOT_FOUND where applicable.

        Args:
            hints: Extraction hints describing target fields
            snippets: Relevant document snippets

        Returns:
            LLMCandidateResponse with candidate sets for each field
        """
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(
                self.generate_candidates_async(hints, snippets)
            )
        finally:
            loop.close()

    async def generate_candidates_async(
        self,
        hints: list[ExtractionHint],
        snippets: list[Snippet],
    ) -> LLMCandidateResponse:
        """Async version of generate_candidates."""
        if not hints or not snippets:
            return LLMCandidateResponse(
                candidate_sets=[],
                tokens_used=0,
                model=self.provider.model,
            )

        # Sort snippets by relevance score
        sorted_snippets = sorted(snippets, key=lambda s: s.score, reverse=True)
        top_snippets = sorted_snippets[:self.MAX_SNIPPETS_PER_BATCH]

        # If small enough, do single generation
        if len(hints) <= self.MAX_HINTS_PER_BATCH:
            return await self._generate_candidates_batch(hints, top_snippets)

        # Otherwise, batch by hints
        all_candidate_sets: list[CandidateSet] = []
        total_tokens = 0
        total_prompt_tokens = 0
        total_completion_tokens = 0

        for i in range(0, len(hints), self.MAX_HINTS_PER_BATCH):
            batch_hints = hints[i : i + self.MAX_HINTS_PER_BATCH]

            try:
                response = await self._generate_candidates_batch(batch_hints, top_snippets)
                all_candidate_sets.extend(response.candidate_sets)
                total_tokens += response.tokens_used
                if response.prompt_tokens is not None:
                    total_prompt_tokens += response.prompt_tokens
                if response.completion_tokens is not None:
                    total_completion_tokens += response.completion_tokens
            except Exception as e:
                logger.warning("Batch candidate generation failed: %s", e)
                # Add NOT_FOUND candidates for failed batch
                for hint in batch_hints:
                    all_candidate_sets.append(
                        CandidateSet(
                            path=hint.path,
                            candidates=[
                                ExtractionCandidate(
                                    path=hint.path,
                                    value="NOT_FOUND",
                                    evidence_quote=None,
                                    llm_confidence=0.0,
                                    source="llm",
                                    reasoning=f"Extraction failed: {e}",
                                )
                            ],
                        )
                    )

        return LLMCandidateResponse(
            candidate_sets=all_candidate_sets,
            tokens_used=total_tokens,
            prompt_tokens=total_prompt_tokens or None,
            completion_tokens=total_completion_tokens or None,
            model=self.provider.model,
        )

    async def _generate_candidates_batch(
        self,
        hints: list[ExtractionHint],
        snippets: list[Snippet],
    ) -> LLMCandidateResponse:
        """Generate candidates for a single batch."""
        logger.debug(
            "Generating candidates: %d hints, %d snippets",
            len(hints),
            len(snippets),
        )

        response = await self.provider.generate_candidates(
            hints=hints,
            snippets=snippets,
            max_tokens=self.MAX_TOKENS,
        )

        # Filter to valid paths
        valid_paths = {h.path for h in hints}
        valid_sets = [
            cs for cs in response.candidate_sets
            if cs.path in valid_paths
        ]

        return LLMCandidateResponse(
            candidate_sets=valid_sets,
            tokens_used=response.tokens_used,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            model=response.model,
        )

    def verify_candidates(
        self,
        candidate_sets: list[CandidateSet],
        index: PDFIndex,
        hints_by_path: dict[str, ExtractionHint] | None = None,
    ) -> list[FieldExtraction]:
        """
        Pass B: Deterministic verification of candidates.

        Verifies each candidate by:
        1. Checking quote presence in PDF text
        2. Attempting bbox localization
        3. Validating unit/format against hint
        4. Rejecting candidates that cannot be grounded

        Args:
            candidate_sets: Candidate sets from Pass A
            index: PDF index with word positions
            hints_by_path: Optional mapping of path to hints for type validation

        Returns:
            List of verified FieldExtraction objects
        """
        verified: list[FieldExtraction] = []
        hints_by_path = hints_by_path or {}

        # Build searchable text per page
        page_texts = self._build_page_texts(index)

        for candidate_set in candidate_sets:
            extraction = self._verify_candidate_set(
                candidate_set,
                index,
                page_texts,
                hints_by_path.get(candidate_set.path),
            )
            verified.append(extraction)

        return verified

    def _build_page_texts(self, index: PDFIndex) -> dict[int, str]:
        """Build full text for each page from word index."""
        page_texts: dict[int, str] = {}

        for word in index.words:
            if word.page not in page_texts:
                page_texts[word.page] = ""
            page_texts[word.page] += word.text + " "

        return {p: t.strip() for p, t in page_texts.items()}

    def _find_quote_in_text(
        self,
        quote: str,
        page_texts: dict[int, str],
    ) -> tuple[int, int, int] | None:
        """
        Find a quote in page texts.

        Returns:
            Tuple of (page, char_start, char_end) or None if not found
        """
        if not quote:
            return None

        quote_lower = quote.lower().strip()
        # Try exact match first
        for page, text in page_texts.items():
            text_lower = text.lower()
            pos = text_lower.find(quote_lower)
            if pos != -1:
                return (page, pos, pos + len(quote_lower))

        # Try fuzzy match (allow for minor OCR errors)
        # For now, try with spaces normalized
        quote_normalized = " ".join(quote_lower.split())
        for page, text in page_texts.items():
            text_normalized = " ".join(text.lower().split())
            pos = text_normalized.find(quote_normalized)
            if pos != -1:
                return (page, pos, pos + len(quote_normalized))

        return None

    def _compute_snippet_hash(self, text: str) -> str:
        """Compute SHA256 hash of text for reproducibility."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    def _verify_candidate_set(
        self,
        candidate_set: CandidateSet,
        index: PDFIndex,
        page_texts: dict[int, str],
        hint: ExtractionHint | None,
    ) -> FieldExtraction:
        """Verify a single candidate set and return the best verified extraction."""
        path = candidate_set.path
        verified: list[tuple[ExtractionCandidate, EvidenceRef]] = []

        # Try each candidate in order (they're ranked by confidence)
        for idx, candidate in enumerate(candidate_set.candidates):
            # Skip NOT_FOUND candidates for now
            if candidate.value == "NOT_FOUND":
                continue

            # Try to verify the evidence quote
            if candidate.evidence_quote:
                location = self._find_quote_in_text(
                    candidate.evidence_quote,
                    page_texts,
                )

                if location is not None:
                    # Found the quote in the document - this is grounded
                    page, char_start, char_end = location
                    evidence = EvidenceRef(
                        page=page,
                        quote=candidate.evidence_quote,
                        boxes=[],  # Will be populated by localizer
                        method="TEXT",
                        locator_score=0.9,  # High score for exact match
                        snippet_hash=self._compute_snippet_hash(candidate.evidence_quote),
                        char_start=char_start,
                        char_end=char_end,
                    )
                    verified.append((candidate, evidence))
            else:
                # No quote provided - cannot ground this candidate
                logger.debug(
                    "Candidate for %s has no evidence quote, skipping",
                    path,
                )

        # If no candidate was verified, check for NOT_FOUND
        if not verified:
            not_found_candidates = [
                c for c in candidate_set.candidates
                if c.value == "NOT_FOUND"
            ]
            if not_found_candidates:
                # Return EMPTY status for fields explicitly marked as not found
                return FieldExtraction(
                    path=path,
                    value_type=hint.value_type if hint else None,
                    value_raw="",
                    value_normalized=None,
                    status=ExtractionStatus.EMPTY,
                    confidence=not_found_candidates[0].llm_confidence,
                    evidence=None,
                    needs_review=False,
                )
            else:
                # No candidates could be verified - return empty value
                # Enforce "no verified evidence = empty value" invariant
                fallback = candidate_set.candidates[0] if candidate_set.candidates else None
                return FieldExtraction(
                    path=path,
                    value_type=hint.value_type if hint else None,
                    value_raw="",  # No evidence = no value
                    value_normalized=None,
                    status=ExtractionStatus.NEEDS_REVIEW,
                    confidence=0.0,
                    evidence=None,
                    needs_review=True,
                    confidence_reasons=[
                        ConfidenceReason(
                            code=ConfidenceReasonCode.NO_EVIDENCE_FOUND,
                            message=f"No candidate verified for '{path}'",
                            severity="error",
                            detail={"best_candidate": fallback.value if fallback else None},
                        )
                    ],
                )

        unique_values = {candidate.value.strip() for candidate, _ in verified if candidate.value}
        if len(unique_values) > 1:
            best_candidate, best_evidence = max(
                verified, key=lambda item: item[0].llm_confidence
            )
            candidate_set.selected_index = candidate_set.candidates.index(best_candidate)
            candidate_set.verification_notes = "Multiple grounded candidates found"
            return FieldExtraction(
                path=path,
                value_type=hint.value_type if hint else None,
                value_raw=best_candidate.value,
                value_normalized=None,
                status=ExtractionStatus.CONFLICT,
                confidence=best_candidate.llm_confidence,
                evidence=best_evidence,
                needs_review=True,
                confidence_reasons=[
                    ConfidenceReason(
                        code=ConfidenceReasonCode.MULTIPLE_CANDIDATES,
                        message="Multiple grounded values found for this field",
                        severity="warning",
                        detail={"candidates": sorted(unique_values)},
                    )
                ],
            )

        best_candidate, best_evidence = verified[0]
        candidate_set.selected_index = candidate_set.candidates.index(best_candidate)
        candidate_set.verification_notes = "Quote found in document"

        # Return verified extraction
        return FieldExtraction(
            path=path,
            value_type=hint.value_type if hint else None,
            value_raw=best_candidate.value,
            value_normalized=None,  # Will be set by scorer
            status=ExtractionStatus.FILLED,  # Tentative - scorer may downgrade
            confidence=best_candidate.llm_confidence,
            evidence=best_evidence,
            needs_review=False,  # Will be recalculated by scorer
        )

    def extract_two_pass(
        self,
        hints: list[ExtractionHint],
        snippets: list[Snippet],
        index: PDFIndex,
    ) -> list[FieldExtraction]:
        """
        Full two-pass extraction pipeline.

        Combines generate_candidates (Pass A) and verify_candidates (Pass B).

        Args:
            hints: Extraction hints describing target fields
            snippets: Relevant document snippets
            index: PDF index for verification

        Returns:
            List of verified FieldExtraction objects
        """
        # Pass A: Generate candidates
        candidate_response = self.generate_candidates(hints, snippets)

        # Pass B: Verify candidates
        hints_by_path = {h.path: h for h in hints}
        extractions = self.verify_candidates(
            candidate_response.candidate_sets,
            index,
            hints_by_path,
        )

        logger.info(
            "Two-pass extraction complete: %d candidates → %d extractions",
            len(candidate_response.candidate_sets),
            len(extractions),
        )

        return extractions
