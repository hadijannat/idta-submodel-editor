"""
Document Classifier - Analyze PDF documents to determine type and quality.

Classifies documents as text-based, scanned, or mixed based on
extraction method statistics. Also detects tables and language.
"""

from __future__ import annotations

import logging
import re
from collections import Counter

from app.schemas.magic_import import DocumentClassification, PDFIndex

logger = logging.getLogger(__name__)


class DocumentClassifier:
    """Classify PDF documents based on extraction characteristics."""

    # Thresholds for classification
    TEXT_PAGE_RATIO_THRESHOLD = 0.8  # >80% text pages = text document
    SCANNED_PAGE_RATIO_THRESHOLD = 0.8  # >80% OCR pages = scanned document
    MIN_WORDS_FOR_QUALITY = 50  # Minimum words to assess quality
    TABLE_PATTERN_THRESHOLD = 3  # Min aligned numeric patterns for table detection

    # Common table indicators
    TABLE_KEYWORDS = {"table", "row", "column", "header", "cell", "total", "sum"}

    def classify(self, index: PDFIndex) -> DocumentClassification:
        """
        Classify a PDF document based on its index.

        Args:
            index: PDFIndex with word and page information

        Returns:
            DocumentClassification with type, language, tables, and quality
        """
        # Calculate page statistics
        total_pages = index.info.total_pages
        text_pages = index.info.pages_with_text
        ocr_pages = index.info.pages_needing_ocr

        # Determine document type
        doc_type = self._determine_doc_type(total_pages, text_pages, ocr_pages)

        # Detect language
        language = self._detect_language(index)

        # Check for tables
        has_tables = self._detect_tables(index)

        # Calculate quality score
        quality_score = self._calculate_quality(index, doc_type)

        # Calculate OCR confidence if applicable
        avg_ocr_confidence = self._calculate_ocr_confidence(index)

        # Text density
        text_density = (
            index.info.total_words / total_pages if total_pages > 0 else 0.0
        )

        classification = DocumentClassification(
            doc_type=doc_type,
            language=language,
            has_tables=has_tables,
            quality_score=quality_score,
            avg_ocr_confidence=avg_ocr_confidence,
            text_density=text_density,
        )

        logger.info(
            "Classified document: type=%s, language=%s, tables=%s, quality=%.2f",
            doc_type,
            language,
            has_tables,
            quality_score,
        )

        return classification

    def _determine_doc_type(
        self, total_pages: int, text_pages: int, ocr_pages: int
    ) -> str:
        """Determine if document is text, scanned, or mixed."""
        if total_pages == 0:
            return "text"

        text_ratio = text_pages / total_pages
        ocr_ratio = ocr_pages / total_pages

        if text_ratio >= self.TEXT_PAGE_RATIO_THRESHOLD:
            return "text"
        elif ocr_ratio >= self.SCANNED_PAGE_RATIO_THRESHOLD:
            return "scanned"
        else:
            return "mixed"

    def _detect_language(self, index: PDFIndex) -> str | None:
        """Detect the primary language of the document."""
        # Use language from index if already detected
        if index.info.language_detected:
            return index.info.language_detected

        # Simple language detection based on word patterns
        if not index.words:
            return None

        # Get all words
        words = [w.text.lower() for w in index.words if len(w.text) > 2]

        if not words:
            return None

        # Count common words for language detection
        word_counts = Counter(words)

        # Simple heuristics based on common words
        english_indicators = {"the", "and", "for", "with", "this", "that", "from"}
        german_indicators = {"der", "die", "das", "und", "für", "mit", "von"}
        french_indicators = {"les", "des", "pour", "avec", "dans", "sur"}

        en_score = sum(word_counts.get(w, 0) for w in english_indicators)
        de_score = sum(word_counts.get(w, 0) for w in german_indicators)
        fr_score = sum(word_counts.get(w, 0) for w in french_indicators)

        max_score = max(en_score, de_score, fr_score)
        if max_score == 0:
            return None

        if en_score == max_score:
            return "en"
        elif de_score == max_score:
            return "de"
        elif fr_score == max_score:
            return "fr"

        return None

    def _detect_tables(self, index: PDFIndex) -> bool:
        """Detect if the document contains tables."""
        if not index.words:
            return False

        # Check for table keywords
        text_lower = " ".join(w.text.lower() for w in index.words[:500])
        keyword_count = sum(1 for kw in self.TABLE_KEYWORDS if kw in text_lower)

        if keyword_count >= 2:
            return True

        # Check for aligned numeric patterns (common in tables)
        # Group words by page and check for vertical alignment
        for page_info in index.pages:
            page_words = [w for w in index.words if w.page == page_info.page_number]

            # Look for multiple numbers in vertical alignment
            numeric_words = [
                w for w in page_words if re.match(r"^\d+[\d.,]*$", w.text)
            ]

            if len(numeric_words) >= self.TABLE_PATTERN_THRESHOLD:
                # Check for x-position clustering (aligned columns)
                x_positions = [w.bbox.x0 for w in numeric_words]
                x_clusters = self._count_clusters(x_positions, tolerance=0.05)

                if x_clusters >= 2:
                    return True

        return False

    def _count_clusters(self, values: list[float], tolerance: float) -> int:
        """Count number of distinct value clusters."""
        if not values:
            return 0

        sorted_values = sorted(values)
        clusters = 1

        for i in range(1, len(sorted_values)):
            if sorted_values[i] - sorted_values[i - 1] > tolerance:
                clusters += 1

        return min(clusters, len(values))

    def _calculate_quality(self, index: PDFIndex, doc_type: str) -> float:
        """Calculate overall document quality score."""
        if not index.words:
            return 0.0

        scores = []

        # Word count score (more words = more content to work with)
        word_score = min(1.0, index.info.total_words / 1000)
        scores.append(word_score * 0.3)

        # Text extraction method score
        if doc_type == "text":
            method_score = 1.0
        elif doc_type == "mixed":
            method_score = 0.7
        else:  # scanned
            method_score = 0.5
        scores.append(method_score * 0.3)

        # OCR confidence score (if applicable)
        ocr_words = [w for w in index.words if w.method == "OCR"]
        if ocr_words:
            avg_ocr = sum(w.confidence for w in ocr_words) / len(ocr_words)
            scores.append(avg_ocr * 0.2)
        else:
            scores.append(0.2)  # Full score if no OCR needed

        # Text density score (words per page)
        if index.info.total_pages > 0:
            density = index.info.total_words / index.info.total_pages
            density_score = min(1.0, density / 200)  # Normalize to ~200 words/page
            scores.append(density_score * 0.2)
        else:
            scores.append(0.0)

        return min(1.0, sum(scores))

    def _calculate_ocr_confidence(self, index: PDFIndex) -> float | None:
        """Calculate average OCR confidence for scanned pages."""
        ocr_words = [w for w in index.words if w.method == "OCR"]

        if not ocr_words:
            return None

        avg_confidence = sum(w.confidence for w in ocr_words) / len(ocr_words)
        # Round to avoid floating-point artifacts in tests and UI.
        return round(avg_confidence, 3)
