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


@dataclass
class TaggedSnippet:
    """Snippet with associated field paths for field-aware deduplication."""

    snippet: Snippet
    field_paths: set[str]  # Which fields need this snippet


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
        max_snippets_per_field: int = 5,
    ) -> list[Snippet]:
        """
        Retrieve relevant snippets for all extraction hints.

        Uses field-aware deduplication: overlapping snippets are allowed
        when they serve different fields.

        Args:
            index: PDF word index
            hints: Extraction hints with keywords
            max_total_snippets: Maximum total snippets to return
            max_snippets_per_field: Maximum snippets per field (default: 5)

        Returns:
            List of snippets with relevance scores
        """
        if not index.words or not hints:
            return []

        # Build document model (treat each page as a document)
        page_docs = self._build_page_documents(index)
        token_stats = self._compute_token_stats(page_docs)

        # Track snippets with their associated fields
        tagged_snippets: list[TaggedSnippet] = []

        contact_anchors = self._collect_contact_anchor_positions(index)

        for hint in hints:
            if not hint.keywords:
                continue

            # Find relevant pages using BM25
            page_scores = self._score_pages(
                hint.keywords, page_docs, token_stats
            )

            # Extract snippets from top pages (limited per field)
            hint_snippets = self._extract_snippets_for_hint(
                hint, page_scores, index, page_docs
            )[:max_snippets_per_field]

            # Contact-aware anchor snippets - boosted score to survive deduplication
            if self._is_contact_hint(hint) and contact_anchors:
                anchor_snippets = self._extract_snippets_for_anchors(
                    index,
                    contact_anchors,
                    limit=max_snippets_per_field,
                )
                # Boost scores to ensure contact snippets survive deduplication
                for snippet in anchor_snippets:
                    snippet.score = max(snippet.score, 1.5)
                hint_snippets.extend(anchor_snippets)

            # Tag snippets with field path
            for snippet in hint_snippets:
                tagged_snippets.append(
                    TaggedSnippet(snippet=snippet, field_paths={hint.path})
                )

        # Field-aware deduplication
        all_snippets = self._deduplicate_snippets_field_aware(tagged_snippets)

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
            token = self._normalize_token(word.text)
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
        keyword_set = set()
        for kw in keywords:
            keyword_set.update(self._keyword_variants(kw))

        for local_idx, (global_idx, word) in enumerate(page_words):
            word_lower = word.text.lower()
            word_norm = self._normalize_token(word.text)
            # Check for exact match or substring match
            if (
                word_lower in keyword_set
                or word_norm in keyword_set
                or any(
                    kw in word_lower
                    or word_lower in kw
                    or (word_norm and (kw in word_norm or word_norm in kw))
                    for kw in keyword_set
                )
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
        extra_before: int = 0,
        extra_after: int = 0,
    ) -> Snippet | None:
        """Extract a snippet centered at a match position.

        Args:
            page_words: List of (global_idx, PDFWord) tuples for the page
            center_idx: Local index of the center word
            page: Page number
            score: Relevance score
            index: PDF index (for metadata)
            extra_before: Additional words to include before center (for clusters)
            extra_after: Additional words to include after center (for clusters)
        """
        n_words = len(page_words)
        if n_words == 0:
            return None

        # Calculate window bounds - expand for anchor clusters
        context_before = self.CONTEXT_WORDS + extra_before
        context_after = self.CONTEXT_WORDS + extra_after
        start_idx = max(0, center_idx - context_before)
        end_idx = min(n_words, center_idx + context_after + 1)

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

    def _deduplicate_snippets_field_aware(
        self, tagged_snippets: list[TaggedSnippet]
    ) -> list[Snippet]:
        """
        Field-aware deduplication: merge overlapping snippets that serve different fields.

        Unlike the legacy deduplication, this allows overlapping snippets when they
        serve different extraction hints. Only exact duplicates are removed.
        """
        if not tagged_snippets:
            return []

        # Sort by score descending
        sorted_tagged = sorted(
            tagged_snippets, key=lambda ts: ts.snippet.score, reverse=True
        )
        result: list[TaggedSnippet] = []

        for tagged in sorted_tagged:
            snippet = tagged.snippet
            merged = False

            for existing in result:
                # Check for exact duplicate (same page and word range)
                if (
                    snippet.page == existing.snippet.page
                    and snippet.start_word_idx == existing.snippet.start_word_idx
                    and snippet.end_word_idx == existing.snippet.end_word_idx
                ):
                    # Merge field paths into existing
                    existing.field_paths.update(tagged.field_paths)
                    merged = True
                    break

                # Check for overlap - if fields are different, keep both
                if self._snippets_overlap(snippet, existing.snippet):
                    # If same fields, skip (deduplicate)
                    if tagged.field_paths == existing.field_paths:
                        merged = True
                        break
                    # Different fields: don't deduplicate, but merge paths
                    # into existing if it has significantly better coverage
                    if existing.snippet.score >= snippet.score * 1.2:
                        existing.field_paths.update(tagged.field_paths)
                        merged = True
                        break

            if not merged:
                result.append(tagged)

        return [ts.snippet for ts in result]

    def _deduplicate_snippets(
        self, snippets: list[Snippet]
    ) -> list[Snippet]:
        """Remove overlapping snippets, keeping higher-scored ones (legacy method)."""
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

    def collect_retrieval_diagnostics(
        self,
        index: PDFIndex,
        hints: list[ExtractionHint],
        top_pages: int = 3,
    ) -> list[dict]:
        """Collect retrieval diagnostics for each hint."""
        if not index.words or not hints:
            return []

        page_docs = self._build_page_documents(index)
        token_stats = self._compute_token_stats(page_docs)

        words_by_page: dict[int, list[tuple[int, PDFWord]]] = {}
        for idx, word in enumerate(index.words):
            words_by_page.setdefault(word.page, []).append((idx, word))

        diagnostics: list[dict] = []
        contact_anchors = self._collect_contact_anchor_positions(index)

        for hint in hints:
            if not hint.keywords:
                continue

            page_scores = self._score_pages(hint.keywords, page_docs, token_stats)
            top_page_scores = page_scores[:top_pages]

            match_count = 0
            for page, _score in top_page_scores:
                page_words = words_by_page.get(page, [])
                match_count += len(self._find_keyword_matches(hint.keywords, page_words))

            diagnostics.append(
                {
                    "path": hint.path,
                    "keyword_count": len(hint.keywords),
                    "match_count": match_count,
                    "anchor_match_count": (
                        len(contact_anchors) if self._is_contact_hint(hint) else 0
                    ),
                    "anchor_pages": (
                        sorted({p for p, _ in contact_anchors})
                        if self._is_contact_hint(hint)
                        else []
                    ),
                    "top_pages": [
                        {"page": page, "score": score}
                        for page, score in top_page_scores
                    ],
                }
            )

        return diagnostics

    @staticmethod
    def _normalize_token(text: str) -> str:
        """Normalize tokens for robust matching (e.g., E-mail -> email)."""
        if not text:
            return ""
        token = text.lower().strip()
        # Normalize unicode hyphens to ASCII hyphen
        token = re.sub(r"[‐‑‒–—−]", "-", token)
        # Remove punctuation while keeping alphanumerics
        token = re.sub(r"[^a-z0-9]+", "", token)
        return token

    def _keyword_variants(self, keyword: str) -> set[str]:
        """Generate normalized variants for keyword matching."""
        variants = set()
        if not keyword:
            return variants
        kw = keyword.lower().strip()
        variants.add(kw)
        norm = self._normalize_token(keyword)
        if norm:
            variants.add(norm)
        # Remove trailing punctuation variants
        variants.add(kw.rstrip(":."))
        return {v for v in variants if v}

    @staticmethod
    def _is_contact_hint(hint: ExtractionHint) -> bool:
        return "contactinformation" in hint.path.lower()

    def _collect_contact_anchor_positions(
        self,
        index: PDFIndex,
    ) -> list[tuple[int, int]]:
        """Collect anchor positions for contact cues like tel/fax/email/www."""
        anchors: list[tuple[int, int]] = []
        for idx, word in enumerate(index.words):
            text = word.text.lower()
            norm = self._normalize_token(word.text)
            is_anchor = (
                "@" in text
                or "www" in text
                or re.search(r"\b(tel|fax|phone|email)\b", text) is not None
                or norm.startswith("tel")
                or norm.startswith("fax")
                or norm.startswith("email")
            )
            if is_anchor:
                anchors.append((word.page, idx))
        return anchors

    def _cluster_indices(self, indices: list[int], max_gap: int = 20) -> list[list[int]]:
        """Group indices into clusters where consecutive items are within max_gap.

        Contact blocks often have multiple anchors (email, tel, fax, www) close together.
        Clustering ensures we capture the entire block in one snippet.

        Args:
            indices: List of word indices to cluster
            max_gap: Maximum gap between consecutive indices in a cluster

        Returns:
            List of clusters, each cluster is a list of indices
        """
        if not indices:
            return []

        sorted_indices = sorted(indices)
        clusters: list[list[int]] = [[sorted_indices[0]]]

        for idx in sorted_indices[1:]:
            if idx - clusters[-1][-1] <= max_gap:
                clusters[-1].append(idx)
            else:
                clusters.append([idx])

        return clusters

    def _extract_snippets_for_anchors(
        self,
        index: PDFIndex,
        anchors: list[tuple[int, int]],
        limit: int = 5,
    ) -> list[Snippet]:
        """Extract snippets covering contact anchor clusters.

        Groups nearby anchors (email, tel, fax, www) into clusters and extracts
        snippets that span the entire cluster, ensuring complete contact blocks
        are captured in a single snippet.

        Args:
            index: PDF word index
            anchors: List of (page, global_word_idx) for contact anchors
            limit: Maximum number of snippets to return

        Returns:
            List of snippets covering contact anchor clusters
        """
        if not anchors:
            return []

        # Build page words lookup
        words_by_page: dict[int, list[tuple[int, PDFWord]]] = {}
        for idx, word in enumerate(index.words):
            words_by_page.setdefault(word.page, []).append((idx, word))

        # Group anchors by page
        anchors_by_page: dict[int, list[int]] = {}
        for page, global_idx in anchors:
            anchors_by_page.setdefault(page, []).append(global_idx)

        snippets: list[Snippet] = []

        for page, page_words in words_by_page.items():
            if page not in anchors_by_page:
                continue

            # Map global indices to local indices
            anchor_global_indices = set(anchors_by_page[page])
            local_indices: list[int] = []
            for li, (gi, _word) in enumerate(page_words):
                if gi in anchor_global_indices:
                    local_indices.append(li)

            if not local_indices:
                continue

            # Cluster nearby anchors (within 20 words of each other)
            clusters = self._cluster_indices(local_indices, max_gap=20)

            for cluster in clusters:
                # Extract snippet spanning the entire cluster
                cluster_min = min(cluster)
                cluster_max = max(cluster)
                center = (cluster_min + cluster_max) // 2

                # Calculate extra context to cover the full cluster
                extra_before = center - cluster_min
                extra_after = cluster_max - center

                snippet = self._extract_snippet_at(
                    page_words,
                    center,
                    page,
                    score=1.2,
                    index=index,
                    extra_before=extra_before,
                    extra_after=extra_after,
                )
                if snippet:
                    snippets.append(snippet)
                if len(snippets) >= limit:
                    return snippets

        return snippets

    def retrieve_for_single_hint(
        self,
        index: PDFIndex,
        hint: ExtractionHint,
    ) -> list[Snippet]:
        """Retrieve snippets for a single hint."""
        return self.retrieve_snippets(index, [hint], max_total_snippets=5)
