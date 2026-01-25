"""
Retriever - Extract relevant document snippets for LLM extraction.

Uses BM25-style keyword matching to find relevant text regions.
Only snippets (not full documents) are sent to the LLM for privacy.
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from dataclasses import dataclass

from app.schemas.magic_import import (
    ExtractionHint,
    PDFIndex,
    PDFWord,
    Snippet,
)

logger = logging.getLogger(__name__)


@dataclass
class TokenStats:
    """Statistics for BM25 scoring."""

    doc_freq: dict[str, int]  # Number of documents containing each term
    total_docs: int
    avg_doc_len: float


class SnippetRetriever:
    """Retrieve relevant text snippets from PDF index."""

    # BM25 parameters
    K1 = 1.2  # Term frequency saturation
    B = 0.75  # Length normalization

    # Snippet parameters
    CONTEXT_WORDS = 50  # Words of context on each side
    MIN_SNIPPET_WORDS = 20
    MAX_SNIPPET_WORDS = 200
    MAX_SNIPPETS_PER_FIELD = 3
    MIN_SCORE_THRESHOLD = 0.1

    def __init__(self) -> None:
        pass

    def retrieve_snippets(
        self,
        index: PDFIndex,
        hints: list[ExtractionHint],
        max_total_snippets: int = 50,
    ) -> list[Snippet]:
        """
        Retrieve relevant snippets for all extraction hints.

        Args:
            index: PDF word index
            hints: Extraction hints with keywords
            max_total_snippets: Maximum total snippets to return

        Returns:
            List of snippets with relevance scores
        """
        if not index.words or not hints:
            return []

        # Build document model (treat each page as a document)
        page_docs = self._build_page_documents(index)
        token_stats = self._compute_token_stats(page_docs)

        all_snippets: list[Snippet] = []

        for hint in hints:
            if not hint.keywords:
                continue

            # Find relevant pages using BM25
            page_scores = self._score_pages(
                hint.keywords, page_docs, token_stats
            )

            # Extract snippets from top pages
            hint_snippets = self._extract_snippets_for_hint(
                hint, page_scores, index, page_docs
            )

            all_snippets.extend(hint_snippets)

        # Deduplicate overlapping snippets
        all_snippets = self._deduplicate_snippets(all_snippets)

        # Sort by score and limit
        all_snippets.sort(key=lambda s: s.score, reverse=True)
        all_snippets = all_snippets[:max_total_snippets]

        logger.info(
            "Retrieved %d snippets for %d hints",
            len(all_snippets),
            len(hints),
        )

        return all_snippets

    def _build_page_documents(
        self, index: PDFIndex
    ) -> dict[int, list[str]]:
        """Build tokenized documents for each page."""
        page_docs: dict[int, list[str]] = {}

        for word in index.words:
            page = word.page
            if page not in page_docs:
                page_docs[page] = []
            # Normalize token
            token = word.text.lower().strip()
            if token and len(token) > 1:
                page_docs[page].append(token)

        return page_docs

    def _compute_token_stats(
        self, page_docs: dict[int, list[str]]
    ) -> TokenStats:
        """Compute document frequency statistics for BM25."""
        doc_freq: dict[str, int] = Counter()
        total_len = 0

        for tokens in page_docs.values():
            unique_tokens = set(tokens)
            for token in unique_tokens:
                doc_freq[token] += 1
            total_len += len(tokens)

        total_docs = len(page_docs)
        avg_doc_len = total_len / total_docs if total_docs > 0 else 0

        return TokenStats(
            doc_freq=dict(doc_freq),
            total_docs=total_docs,
            avg_doc_len=avg_doc_len,
        )

    def _score_pages(
        self,
        keywords: list[str],
        page_docs: dict[int, list[str]],
        stats: TokenStats,
    ) -> list[tuple[int, float]]:
        """Score pages using BM25."""
        page_scores: list[tuple[int, float]] = []

        for page, tokens in page_docs.items():
            if not tokens:
                continue

            score = self._bm25_score(keywords, tokens, stats)
            if score > self.MIN_SCORE_THRESHOLD:
                page_scores.append((page, score))

        # Sort by score descending
        page_scores.sort(key=lambda x: x[1], reverse=True)
        return page_scores

    def _bm25_score(
        self,
        query_terms: list[str],
        doc_tokens: list[str],
        stats: TokenStats,
    ) -> float:
        """Calculate BM25 score for a document."""
        score = 0.0
        doc_len = len(doc_tokens)
        term_freq = Counter(doc_tokens)

        for term in query_terms:
            term_lower = term.lower()
            tf = term_freq.get(term_lower, 0)
            if tf == 0:
                continue

            df = stats.doc_freq.get(term_lower, 0)
            if df == 0:
                continue

            # IDF component
            idf = math.log(
                (stats.total_docs - df + 0.5) / (df + 0.5) + 1.0
            )

            # TF component with length normalization
            tf_norm = (tf * (self.K1 + 1)) / (
                tf + self.K1 * (1 - self.B + self.B * doc_len / stats.avg_doc_len)
            )

            score += idf * tf_norm

        return score

    def _extract_snippets_for_hint(
        self,
        hint: ExtractionHint,
        page_scores: list[tuple[int, float]],
        index: PDFIndex,
        page_docs: dict[int, list[str]],
    ) -> list[Snippet]:
        """Extract snippets from top-scoring pages for a hint."""
        snippets: list[Snippet] = []

        # Get words by page for efficient lookup
        words_by_page: dict[int, list[tuple[int, PDFWord]]] = {}
        for idx, word in enumerate(index.words):
            if word.page not in words_by_page:
                words_by_page[word.page] = []
            words_by_page[word.page].append((idx, word))

        for page, page_score in page_scores[:5]:  # Top 5 pages
            if page not in words_by_page:
                continue

            page_words = words_by_page[page]

            # Find keyword matches on this page
            match_positions = self._find_keyword_matches(
                hint.keywords, page_words
            )

            if not match_positions:
                continue

            # Extract snippets around matches
            for match_idx in match_positions[:self.MAX_SNIPPETS_PER_FIELD]:
                snippet = self._extract_snippet_at(
                    page_words,
                    match_idx,
                    page,
                    page_score,
                    index,
                )
                if snippet:
                    snippets.append(snippet)

        return snippets

    def _find_keyword_matches(
        self,
        keywords: list[str],
        page_words: list[tuple[int, PDFWord]],
    ) -> list[int]:
        """Find positions of keyword matches on a page."""
        matches: list[int] = []
        keyword_set = {kw.lower() for kw in keywords}

        for local_idx, (global_idx, word) in enumerate(page_words):
            word_lower = word.text.lower()
            # Check for exact match or substring match
            if word_lower in keyword_set or any(
                kw in word_lower or word_lower in kw
                for kw in keyword_set
            ):
                matches.append(local_idx)

        return matches

    def _extract_snippet_at(
        self,
        page_words: list[tuple[int, PDFWord]],
        center_idx: int,
        page: int,
        score: float,
        index: PDFIndex,
    ) -> Snippet | None:
        """Extract a snippet centered at a match position."""
        n_words = len(page_words)
        if n_words == 0:
            return None

        # Calculate window bounds
        start_idx = max(0, center_idx - self.CONTEXT_WORDS)
        end_idx = min(n_words, center_idx + self.CONTEXT_WORDS + 1)

        # Ensure minimum size
        if end_idx - start_idx < self.MIN_SNIPPET_WORDS:
            # Expand window
            expand = (self.MIN_SNIPPET_WORDS - (end_idx - start_idx)) // 2
            start_idx = max(0, start_idx - expand)
            end_idx = min(n_words, end_idx + expand)

        # Cap at maximum size
        if end_idx - start_idx > self.MAX_SNIPPET_WORDS:
            end_idx = start_idx + self.MAX_SNIPPET_WORDS

        # Extract text
        window_words = page_words[start_idx:end_idx]
        text = " ".join(w.text for _, w in window_words)

        # Get context before and after
        context_before = ""
        if start_idx > 0:
            before_words = page_words[max(0, start_idx - 10):start_idx]
            context_before = " ".join(w.text for _, w in before_words)

        context_after = ""
        if end_idx < n_words:
            after_words = page_words[end_idx:min(n_words, end_idx + 10)]
            context_after = " ".join(w.text for _, w in after_words)

        # Get global word indices
        global_start = window_words[0][0] if window_words else 0
        global_end = window_words[-1][0] if window_words else 0

        return Snippet(
            text=text,
            page=page,
            start_word_idx=global_start,
            end_word_idx=global_end,
            score=score,
            context_before=context_before,
            context_after=context_after,
        )

    def _deduplicate_snippets(
        self, snippets: list[Snippet]
    ) -> list[Snippet]:
        """Remove overlapping snippets, keeping higher-scored ones."""
        if not snippets:
            return []

        # Sort by score descending
        sorted_snippets = sorted(snippets, key=lambda s: s.score, reverse=True)
        result: list[Snippet] = []

        for snippet in sorted_snippets:
            # Check for overlap with existing snippets
            is_overlapping = False
            for existing in result:
                if self._snippets_overlap(snippet, existing):
                    is_overlapping = True
                    break

            if not is_overlapping:
                result.append(snippet)

        return result

    @staticmethod
    def _snippets_overlap(a: Snippet, b: Snippet) -> bool:
        """Check if two snippets overlap."""
        if a.page != b.page:
            return False

        # Check word index overlap
        return not (
            a.end_word_idx < b.start_word_idx or
            b.end_word_idx < a.start_word_idx
        )

    def retrieve_for_single_hint(
        self,
        index: PDFIndex,
        hint: ExtractionHint,
    ) -> list[Snippet]:
        """Retrieve snippets for a single hint."""
        return self.retrieve_snippets(index, [hint], max_total_snippets=5)
