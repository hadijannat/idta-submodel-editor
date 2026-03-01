"""Tests for OCR processor."""

from __future__ import annotations

import io
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.schemas.magic_import import PDFIndex, PDFIndexInfo, PDFPageInfo


def _png_bytes(width: int = 100, height: int = 200) -> bytes:
    from PIL import Image

    image = Image.new("RGB", (width, height), color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _base_index() -> PDFIndex:
    return PDFIndex(
        job_id="job-1",
        pdf_path="test.pdf",
        info=PDFIndexInfo(
            total_pages=1,
            pages_with_text=0,
            pages_needing_ocr=1,
            total_words=0,
            language_detected="eng",
        ),
        pages=[
            PDFPageInfo(
                page_number=0,
                width=612,
                height=792,
                has_text=False,
                needs_ocr=True,
                word_count=0,
            )
        ],
        words=[],
    )


@patch("app.services.magic_import.ocr.get_settings")
def test_process_scanned_pages_extracts_words_and_updates_index(mock_get_settings):
    mock_get_settings.return_value = SimpleNamespace(
        magic_import_ocr_enabled=True,
        magic_import_ocr_language="eng",
        magic_import_ocr_dpi=300,
    )
    from app.services.magic_import.ocr import OCRProcessor

    processor = OCRProcessor()
    processor._tesseract_available = True

    mock_pix = MagicMock()
    mock_pix.tobytes.return_value = _png_bytes()

    mock_page = MagicMock()
    mock_page.get_pixmap.return_value = mock_pix

    mock_doc = MagicMock()
    mock_doc.__getitem__.return_value = mock_page

    mock_fitz = MagicMock()
    mock_fitz.open.return_value = mock_doc
    mock_fitz.Matrix.side_effect = lambda x, y: (x, y)

    mock_pytesseract = MagicMock()
    mock_pytesseract.Output = SimpleNamespace(DICT="DICT")
    mock_pytesseract.image_to_data.return_value = {
        "text": [" Hello ", "World", " ", "Skip"],
        "conf": ["98", "50", "70", "not-a-number"],
        "left": [10, 40, 0, 5],
        "top": [20, 50, 0, 5],
        "width": [20, 20, 0, 10],
        "height": [10, 20, 0, 10],
    }

    with patch.dict(sys.modules, {"fitz": mock_fitz, "pytesseract": mock_pytesseract}):
        updated = processor.process_scanned_pages(Path("test.pdf"), _base_index())

    assert updated.info.total_words == 2
    assert updated.info.pages_needing_ocr == 0

    assert len(updated.words) == 2
    first_word = updated.words[0]
    assert first_word.text == "Hello"
    assert first_word.method == "OCR"
    assert first_word.confidence == pytest.approx(0.98)
    assert first_word.bbox.x0 == pytest.approx(0.10)
    assert first_word.bbox.y0 == pytest.approx(0.10)
    assert first_word.bbox.x1 == pytest.approx(0.30)
    assert first_word.bbox.y1 == pytest.approx(0.15)

    assert len(updated.pages) == 1
    assert updated.pages[0].needs_ocr is False
    assert updated.pages[0].word_count == 2
    assert updated.pages[0].has_text is False
    mock_doc.close.assert_called_once()


@patch("app.services.magic_import.ocr.get_settings")
def test_ocr_single_page_returns_words_and_average_confidence(mock_get_settings):
    mock_get_settings.return_value = SimpleNamespace(
        magic_import_ocr_enabled=True,
        magic_import_ocr_language="eng",
        magic_import_ocr_dpi=300,
    )
    from app.services.magic_import.ocr import OCRProcessor

    processor = OCRProcessor()
    processor._tesseract_available = True

    mock_pix = MagicMock()
    mock_pix.tobytes.return_value = _png_bytes()

    mock_page = MagicMock()
    mock_page.get_pixmap.return_value = mock_pix

    mock_doc = MagicMock()
    mock_doc.__getitem__.return_value = mock_page

    mock_fitz = MagicMock()
    mock_fitz.open.return_value = mock_doc
    mock_fitz.Matrix.side_effect = lambda x, y: (x, y)

    mock_pytesseract = MagicMock()
    mock_pytesseract.Output = SimpleNamespace(DICT="DICT")
    mock_pytesseract.image_to_data.return_value = {
        "text": ["One", "Two", ""],
        "conf": ["80", "100", "0"],
        "left": [10, 50, 0],
        "top": [20, 40, 0],
        "width": [20, 20, 0],
        "height": [10, 20, 0],
    }

    with patch.dict(sys.modules, {"fitz": mock_fitz, "pytesseract": mock_pytesseract}):
        words, avg_conf = processor.ocr_single_page(Path("test.pdf"), 0)

    assert len(words) == 2
    assert words[0].method == "OCR"
    assert words[1].method == "OCR"
    assert words[0].bbox.x0 == pytest.approx(0.10)
    assert words[1].bbox.x1 == pytest.approx(0.70)
    assert avg_conf == pytest.approx(0.9)
    mock_doc.close.assert_called_once()


@patch("app.services.magic_import.ocr.get_settings")
def test_ocr_single_page_returns_empty_when_tesseract_unavailable(mock_get_settings):
    mock_get_settings.return_value = SimpleNamespace(
        magic_import_ocr_enabled=True,
        magic_import_ocr_language="eng",
        magic_import_ocr_dpi=300,
    )
    from app.services.magic_import.ocr import OCRProcessor

    processor = OCRProcessor()
    processor._tesseract_available = False

    words, avg_conf = processor.ocr_single_page(Path("test.pdf"), 0)

    assert words == []
    assert avg_conf == 0.0
