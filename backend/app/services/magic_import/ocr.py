"""
OCR module - Optical Character Recognition for scanned PDFs.

Uses Tesseract via pytesseract for OCR processing.
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
    PDFIndex,
    PDFPageInfo,
    PDFWord,
)
from app.services.magic_import.pymupdf_guard import assert_pymupdf_allowed

logger = logging.getLogger(__name__)


class OCRProcessor:
    """Process scanned PDF pages using Tesseract OCR."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._tesseract_available: bool | None = None

    @property
    def is_available(self) -> bool:
        """Check if Tesseract is available."""
        if self._tesseract_available is None:
            self._tesseract_available = self._check_tesseract()
        return self._tesseract_available

    def _check_tesseract(self) -> bool:
        """Check if Tesseract is installed and accessible."""
        try:
            import pytesseract

            pytesseract.get_tesseract_version()
            return True
        except Exception as e:
            logger.warning("Tesseract not available: %s", e)
            return False

    def process_scanned_pages(self, pdf_path: Path, index: PDFIndex) -> PDFIndex:
        """
        Process pages that need OCR and update the index.

        Args:
            pdf_path: Path to the PDF file
            index: Existing PDF index with pages marked as needing OCR

        Returns:
            Updated PDFIndex with OCR results
        """
        if not self.settings.magic_import_ocr_enabled:
            logger.info("OCR disabled in settings")
            return index

        if not self.is_available:
            logger.warning("OCR requested but Tesseract not available")
            return index

        assert_pymupdf_allowed()

        import fitz  # PyMuPDF
        import pytesseract
        from PIL import Image
        import io

        pages_needing_ocr = [p for p in index.pages if p.needs_ocr]
        if not pages_needing_ocr:
            logger.info("No pages need OCR")
            return index

        logger.info("Processing %d pages with OCR", len(pages_needing_ocr))

        doc = fitz.open(pdf_path)
        new_words: list[PDFWord] = list(index.words)  # Copy existing words
        updated_pages: list[PDFPageInfo] = []

        try:
            for page_info in index.pages:
                if not page_info.needs_ocr:
                    updated_pages.append(page_info)
                    continue

                page_num = page_info.page_number
                page = doc[page_num]

                # Render page to image at specified DPI
                dpi = self.settings.magic_import_ocr_dpi
                zoom = dpi / 72  # 72 is default PDF DPI
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)

                # Convert to PIL Image
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))

                # Run OCR with word-level bounding boxes
                ocr_data = pytesseract.image_to_data(
                    img,
                    lang=self.settings.magic_import_ocr_language,
                    output_type=pytesseract.Output.DICT,
                )

                # Extract words with positions
                page_word_count = 0
                img_width, img_height = img.size

                for i in range(len(ocr_data["text"])):
                    text = ocr_data["text"][i]
                    conf_raw = ocr_data["conf"][i]
                    try:
                        conf = float(conf_raw)
                    except (TypeError, ValueError):
                        conf = -1.0

                    # Skip empty or low-confidence results
                    if not text or not text.strip() or conf < 0:
                        continue

                    # Get bounding box
                    x = ocr_data["left"][i]
                    y = ocr_data["top"][i]
                    w = ocr_data["width"][i]
                    h = ocr_data["height"][i]

                    # Normalize to 0..1
                    word_confidence = max(0.0, min(1.0, conf / 100.0))
                    bbox = BBox(
                        x0=max(0.0, min(1.0, x / img_width)),
                        y0=max(0.0, min(1.0, y / img_height)),
                        x1=max(0.0, min(1.0, (x + w) / img_width)),
                        y1=max(0.0, min(1.0, (y + h) / img_height)),
                        word_confidence=word_confidence,
                    )

                    new_words.append(
                        PDFWord(
                            text=text.strip(),
                            page=page_num,
                            bbox=bbox,
                            confidence=word_confidence,
                            method="OCR",
                        )
                    )
                    page_word_count += 1

                # Update page info
                updated_pages.append(
                    PDFPageInfo(
                        page_number=page_num,
                        width=page_info.width,
                        height=page_info.height,
                        has_text=page_word_count >= 10,
                        needs_ocr=False,  # OCR complete
                        word_count=page_word_count,
                    )
                )

                logger.debug(
                    "OCR page %d: extracted %d words",
                    page_num,
                    page_word_count,
                )

        finally:
            doc.close()

        # Update index statistics
        total_words = len(new_words)
        pages_with_text = sum(1 for p in updated_pages if p.has_text)

        updated_info = index.info.model_copy(
            update={
                "total_words": total_words,
                "pages_with_text": pages_with_text,
                "pages_needing_ocr": 0,
            }
        )

        logger.info(
            "OCR complete: %d total words from %d pages",
            total_words,
            len(updated_pages),
        )

        return PDFIndex(
            job_id=index.job_id,
            pdf_path=index.pdf_path,
            info=updated_info,
            pages=updated_pages,
            words=new_words,
        )

    def ocr_single_page(
        self, pdf_path: Path, page_num: int
    ) -> tuple[list[PDFWord], float]:
        """
        OCR a single page and return words with average confidence.

        Returns:
            Tuple of (words, average_confidence)
        """
        if not self.is_available:
            return [], 0.0

        assert_pymupdf_allowed()

        import fitz
        import pytesseract
        from PIL import Image
        import io

        doc = fitz.open(pdf_path)
        try:
            page = doc[page_num]
            dpi = self.settings.magic_import_ocr_dpi
            zoom = dpi / 72
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)

            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))

            ocr_data = pytesseract.image_to_data(
                img,
                lang=self.settings.magic_import_ocr_language,
                output_type=pytesseract.Output.DICT,
            )

            words: list[PDFWord] = []
            total_conf = 0.0
            img_width, img_height = img.size

            for i in range(len(ocr_data["text"])):
                text = ocr_data["text"][i]
                conf_raw = ocr_data["conf"][i]
                try:
                    conf = float(conf_raw)
                except (TypeError, ValueError):
                    conf = -1.0

                if not text or not text.strip() or conf < 0:
                    continue

                x = ocr_data["left"][i]
                y = ocr_data["top"][i]
                w = ocr_data["width"][i]
                h = ocr_data["height"][i]

                word_confidence = max(0.0, min(1.0, conf / 100.0))
                bbox = BBox(
                    x0=max(0.0, min(1.0, x / img_width)),
                    y0=max(0.0, min(1.0, y / img_height)),
                    x1=max(0.0, min(1.0, (x + w) / img_width)),
                    y1=max(0.0, min(1.0, (y + h) / img_height)),
                    word_confidence=word_confidence,
                )
                words.append(
                    PDFWord(
                        text=text.strip(),
                        page=page_num,
                        bbox=bbox,
                        confidence=word_confidence,
                        method="OCR",
                    )
                )
                total_conf += word_confidence

            avg_conf = total_conf / len(words) if words else 0.0
            return words, avg_conf

        finally:
            doc.close()
