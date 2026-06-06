"""
PDF Indexer - Extract text and word bounding boxes from PDFs.

Uses PyMuPDF (fitz) for native PDF text extraction.
Falls back to OCR for scanned pages.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from app.config import get_settings
from app.schemas.magic_import import (
    BBox,
    ExtractedTable,
    PDFIndex,
    PDFIndexInfo,
    PDFPageInfo,
    PDFWord,
)
from app.services.magic_import.pymupdf_guard import assert_pymupdf_allowed
from app.services.magic_import.table_extractor import TableExtractor

logger = logging.getLogger(__name__)


class PDFIndexer:
    """Extract text and word positions from PDF documents."""

    # Minimum words per page to consider it "has text"
    MIN_WORDS_THRESHOLD = 10

    def __init__(self) -> None:
        self.settings = get_settings()
        self.table_extractor = TableExtractor()

    def index_pdf(self, pdf_path: Path, job_id: str) -> PDFIndex:
        """
        Index a PDF document, extracting text with word-level bounding boxes.

        Args:
            pdf_path: Path to the PDF file
            job_id: Job ID for tracking

        Returns:
            PDFIndex with all words and page information
        """
        assert_pymupdf_allowed()

        import fitz  # PyMuPDF

        doc = fitz.open(pdf_path)
        pages: list[PDFPageInfo] = []
        words: list[PDFWord] = []

        total_words = 0
        pages_with_text = 0
        pages_needing_ocr = 0

        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_rect = page.rect
                page_width = page_rect.width
                page_height = page_rect.height

                # Extract words with positions
                word_list = page.get_text("words")
                page_word_count = len(word_list)

                has_text = page_word_count >= self.MIN_WORDS_THRESHOLD
                needs_ocr = not has_text

                if has_text:
                    pages_with_text += 1
                if needs_ocr:
                    pages_needing_ocr += 1

                pages.append(
                    PDFPageInfo(
                        page_number=page_num,
                        width=page_width,
                        height=page_height,
                        has_text=has_text,
                        needs_ocr=needs_ocr,
                        word_count=page_word_count,
                    )
                )

                # Add words to index with normalized bounding boxes
                for word_data in word_list:
                    # word_data: (x0, y0, x1, y1, text, block_no, line_no, word_no)
                    x0, y0, x1, y1, text, *_ = word_data

                    # Skip empty or whitespace-only text
                    if not text or not text.strip():
                        continue

                    # Normalize coordinates to 0..1
                    bbox = BBox(
                        x0=max(0.0, min(1.0, x0 / page_width)),
                        y0=max(0.0, min(1.0, y0 / page_height)),
                        x1=max(0.0, min(1.0, x1 / page_width)),
                        y1=max(0.0, min(1.0, y1 / page_height)),
                    )

                    words.append(
                        PDFWord(
                            text=text.strip(),
                            page=page_num,
                            bbox=bbox,
                            confidence=1.0,
                            method="TEXT",
                        )
                    )
                    total_words += 1

        finally:
            doc.close()

        info = PDFIndexInfo(
            total_pages=len(pages),
            pages_with_text=pages_with_text,
            pages_needing_ocr=pages_needing_ocr,
            total_words=total_words,
            language_detected=None,  # Could add language detection later
        )

        # Extract tables from the PDF
        tables: list[ExtractedTable] = []
        try:
            table_result = self.table_extractor.extract_tables(pdf_path)
            tables = table_result.tables
            logger.info(
                "Extracted %d tables from PDF %s",
                table_result.total_tables,
                pdf_path.name,
            )
        except Exception as e:
            logger.warning("Table extraction failed for %s: %s", pdf_path.name, e)

        logger.info(
            "Indexed PDF %s: %d pages, %d words, %d tables, %d pages need OCR",
            pdf_path.name,
            len(pages),
            total_words,
            len(tables),
            pages_needing_ocr,
        )

        return PDFIndex(
            job_id=job_id,
            pdf_path=str(pdf_path),
            info=info,
            pages=pages,
            words=words,
            tables=tables,
        )

    def get_text_for_page(self, pdf_path: Path, page_num: int) -> str:
        """Get full text content for a specific page."""
        assert_pymupdf_allowed()

        import fitz

        doc = fitz.open(pdf_path)
        try:
            if page_num < 0 or page_num >= len(doc):
                return ""
            page = doc[page_num]
            return page.get_text("text")
        finally:
            doc.close()

    def get_full_text(self, index: PDFIndex) -> str:
        """Reconstruct full document text from word index."""
        if not index.words:
            return ""

        # Group words by page
        pages: dict[int, list[PDFWord]] = {}
        for word in index.words:
            pages.setdefault(word.page, []).append(word)

        # Sort words within each page by position (top-to-bottom, left-to-right)
        result_parts: list[str] = []
        for page_num in sorted(pages.keys()):
            page_words = pages[page_num]
            # Sort by y (top to bottom), then x (left to right)
            page_words.sort(key=lambda w: (w.bbox.y0, w.bbox.x0))
            result_parts.append(" ".join(w.text for w in page_words))

        return "\n\n".join(result_parts)

    def find_words_on_page(
        self, index: PDFIndex, page: int, text_query: str
    ) -> list[PDFWord]:
        """Find words on a specific page that match a text query."""
        query_lower = text_query.lower()
        matching = []
        for word in index.words:
            if word.page == page and query_lower in word.text.lower():
                matching.append(word)
        return matching

    def get_words_in_region(
        self,
        index: PDFIndex,
        page: int,
        bbox: BBox,
        tolerance: float = 0.01,
    ) -> list[PDFWord]:
        """Get all words within a bounding box region."""
        matching = []
        for word in index.words:
            if word.page != page:
                continue
            # Check if word overlaps with region
            if (
                word.bbox.x0 <= bbox.x1 + tolerance
                and word.bbox.x1 >= bbox.x0 - tolerance
                and word.bbox.y0 <= bbox.y1 + tolerance
                and word.bbox.y1 >= bbox.y0 - tolerance
            ):
                matching.append(word)
        return matching
