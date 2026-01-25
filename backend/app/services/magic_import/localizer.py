"""
Evidence Localizer - Map LLM evidence quotes to PDF word bounding boxes.

Provides lightweight quote-to-bbox matching so UI can highlight source text.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from typing import Iterable

try:
    from rapidfuzz import fuzz
except ImportError:
    fuzz = None  # type: ignore[assignment]

from app.schemas.magic_import import (
    BBox,
    EvidenceRef,
    FieldExtraction,
    LLMFieldExtraction,
    PDFIndex,
    PDFWord,
)

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return [m.group(0).lower() for m in _TOKEN_RE.finditer(text or "")]


def _normalize_word(text: str) -> str:
    """Normalize a word by lowercasing."""
    return text.lower().strip() if text else ""


def _build_page_word_map(index: PDFIndex) -> dict[int, list[tuple[int, PDFWord, str]]]:
    """Build a map of page number to list of (index, word, normalized_text)."""
    pages: dict[int, list[tuple[int, PDFWord, str]]] = {}
    for idx, word in enumerate(index.words):
        norm = _normalize_word(word.text)
        if not norm:
            continue
        pages.setdefault(word.page, []).append((idx, word, norm))
    return pages


def _find_sequence(haystack: list[str], needle: list[str]) -> int | None:
    """Find needle sequence in haystack, return start index or None."""
    if not needle or len(needle) > len(haystack):
        return None
    for i in range(0, len(haystack) - len(needle) + 1):
        if haystack[i : i + len(needle)] == needle:
            return i
    return None


def _normalize_quote_to_words(quote: str) -> list[str]:
    """Normalize a quote into lowercase words for matching."""
    return [w.lower() for w in quote.split() if w.strip()]


def _boxes_from_words(words: Iterable[PDFWord]) -> list[BBox]:
    return [w.bbox for w in words]


class EvidenceLocalizer:
    """Locate evidence quotes within a PDF index."""

    # Minimum score for a quote match to be considered valid
    MIN_MATCH_SCORE = 0.6
    MIN_TOKEN_MATCHES = 3

    def __init__(self) -> None:
        pass

    def _normalize_text(self, text: str) -> str:
        """Normalize text for matching: lowercase and collapse whitespace."""
        return " ".join(text.lower().split())

    def _merge_boxes(self, boxes: list[BBox]) -> list[BBox]:
        """Merge adjacent bounding boxes on the same line."""
        if not boxes:
            return []

        # Group boxes by approximate y position (same line)
        LINE_TOLERANCE = 0.05
        lines: dict[float, list[BBox]] = {}

        for box in boxes:
            # Find existing line or create new one
            found_line = None
            for line_y in lines:
                if abs(box.y0 - line_y) < LINE_TOLERANCE:
                    found_line = line_y
                    break

            if found_line is not None:
                lines[found_line].append(box)
            else:
                lines[box.y0] = [box]

        # Merge boxes on each line
        merged: list[BBox] = []
        for line_boxes in lines.values():
            # Sort by x position
            sorted_boxes = sorted(line_boxes, key=lambda b: b.x0)
            # Merge into single box per line
            merged.append(
                BBox(
                    x0=sorted_boxes[0].x0,
                    y0=min(b.y0 for b in sorted_boxes),
                    x1=sorted_boxes[-1].x1,
                    y1=max(b.y1 for b in sorted_boxes),
                )
            )

        return merged

    def _localize_quote(
        self,
        quote: str,
        index: PDFIndex,
    ) -> tuple[EvidenceRef | None, float]:
        """
        Locate a quote within the PDF index.

        Returns:
            Tuple of (EvidenceRef or None, match_score)
        """
        if not quote or not quote.strip():
            return None, 0.0

        if not index.words:
            return None, 0.0

        quote_normalized = self._normalize_text(quote)
        quote_words = _normalize_quote_to_words(quote)
        quote_tokens = _tokenize(quote)

        if not quote_words:
            return None, 0.0

        pages = _build_page_word_map(index)
        best_match: tuple[EvidenceRef | None, float] = (None, 0.0)

        for page_num, word_entries in pages.items():
            norms = [entry[2] for entry in word_entries]

            # Try exact word sequence match first
            match_start = _find_sequence(norms, quote_words)
            if match_start is not None:
                matched_entries = word_entries[match_start : match_start + len(quote_words)]
                matched_words = [entry[1] for entry in matched_entries]
                method = "OCR" if any(w.method == "OCR" for w in matched_words) else "TEXT"

                evidence = EvidenceRef(
                    page=page_num,
                    quote=" ".join(w.text for w in matched_words),
                    boxes=self._merge_boxes(_boxes_from_words(matched_words)),
                    method=method,  # type: ignore[arg-type]
                    locator_score=1.0,
                )
                return evidence, 1.0

            # Try fuzzy match if rapidfuzz is available
            if fuzz is not None:
                # Build text from consecutive words and check similarity
                page_text = " ".join(norms)
                ratio = fuzz.partial_ratio(quote_normalized, page_text) / 100.0

                if ratio > best_match[1] and ratio >= self.MIN_MATCH_SCORE:
                    # Find approximate location
                    for i in range(len(word_entries)):
                        window_size = len(quote_words)
                        if i + window_size > len(word_entries):
                            break
                        window_entries = word_entries[i : i + window_size]
                        window_text = " ".join(entry[2] for entry in window_entries)
                        window_ratio = fuzz.ratio(quote_normalized, window_text) / 100.0

                        if window_ratio > best_match[1]:
                            matched_words = [entry[1] for entry in window_entries]
                            method = "OCR" if any(w.method == "OCR" for w in matched_words) else "TEXT"

                            evidence = EvidenceRef(
                                page=page_num,
                                quote=" ".join(w.text for w in matched_words),
                                boxes=self._merge_boxes(_boxes_from_words(matched_words)),
                                method=method,  # type: ignore[arg-type]
                                locator_score=window_ratio,
                            )
                            best_match = (evidence, window_ratio)

        if best_match[0] is not None and best_match[1] >= self.MIN_MATCH_SCORE:
            return best_match

        # Fallback: token-overlap window match (no rapidfuzz dependency)
        for page_num, word_entries in pages.items():
            window_match = self._best_token_window(word_entries, quote_tokens)
            if window_match is None:
                continue
            start_idx, end_idx, score = window_match
            matched_words = [entry[1] for entry in word_entries[start_idx:end_idx]]
            method = "OCR" if any(w.method == "OCR" for w in matched_words) else "TEXT"
            evidence = EvidenceRef(
                page=page_num,
                quote=" ".join(w.text for w in matched_words),
                boxes=self._merge_boxes(_boxes_from_words(matched_words)),
                method=method,  # type: ignore[arg-type]
                locator_score=score,
            )
            if score > best_match[1]:
                best_match = (evidence, score)

        return best_match

    def _best_token_window(
        self,
        word_entries: list[tuple[int, PDFWord, str]],
        quote_tokens: list[str],
    ) -> tuple[int, int, float] | None:
        """Find the best token-overlap window on a page."""
        if not word_entries or not quote_tokens:
            return None

        tokens = [entry[2] for entry in word_entries]
        if not tokens:
            return None

        q_counts = Counter(quote_tokens)
        q_len = len(quote_tokens)
        window_size = min(len(tokens), max(q_len, 6))
        min_matches = min(q_len, self.MIN_TOKEN_MATCHES)

        window_counts = Counter(tokens[:window_size])

        def match_count(counts: Counter[str]) -> int:
            return sum(min(counts[t], q_counts[t]) for t in q_counts)

        best_count = match_count(window_counts)
        best_start = 0

        for start in range(1, len(tokens) - window_size + 1):
            out_token = tokens[start - 1]
            in_token = tokens[start + window_size - 1]
            window_counts[out_token] -= 1
            if window_counts[out_token] <= 0:
                del window_counts[out_token]
            window_counts[in_token] += 1

            current_count = match_count(window_counts)
            if current_count > best_count:
                best_count = current_count
                best_start = start

        score = best_count / q_len if q_len else 0.0
        if best_count < min_matches or score < self.MIN_MATCH_SCORE:
            return None

        return best_start, best_start + window_size, score

    def localize_all(
        self,
        extractions: list[LLMFieldExtraction],
        index: PDFIndex,
    ) -> list[FieldExtraction]:
        """Localize all LLM extractions and return FieldExtractions with evidence."""
        results: list[FieldExtraction] = []

        for extraction in extractions:
            evidence, _score = self._localize_quote(
                extraction.evidence_quote or "",
                index,
            )

            results.append(
                FieldExtraction(
                    path=extraction.path,
                    value_raw=str(extraction.value),
                    value_normalized=None,
                    confidence=float(extraction.confidence),
                    confidence_breakdown=None,
                    evidence=evidence,
                    needs_review=False,
                    user_edited=False,
                    user_approved=False,
                )
            )

        return results
