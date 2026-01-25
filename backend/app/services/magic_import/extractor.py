"""
Extractor - Orchestrates LLM-based field extraction.

Coordinates between the LLM provider and handles extraction batching
for large documents.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from app.config import get_settings
from app.schemas.magic_import import (
    ExtractionHint,
    LLMExtractionResponse,
    LLMFieldExtraction,
    Snippet,
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
            except Exception as e:
                logger.warning("Batch extraction failed: %s", e)
                continue

        # Deduplicate extractions (same path)
        unique_extractions = self._deduplicate_extractions(all_extractions)

        return LLMExtractionResponse(
            extractions=unique_extractions,
            tokens_used=total_tokens,
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
