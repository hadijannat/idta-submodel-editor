"""Tests for PDF Indexer."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch


from app.schemas.magic_import import (
    BBox,
    ExtractedTable,
    PDFIndex,
    PDFIndexInfo,
    PDFWord,
)
from app.services.magic_import.table_extractor import TableExtractionResult


class TestPDFIndexer:
    """Test suite for PDFIndexer."""

    @patch("app.services.magic_import.pdf_indexer.get_settings")
    def test_init(self, mock_settings):
        """Test indexer initialization."""
        mock_settings.return_value = MagicMock()
        from app.services.magic_import.pdf_indexer import PDFIndexer

        indexer = PDFIndexer()
        assert indexer.MIN_WORDS_THRESHOLD == 10

    @patch("app.services.magic_import.pdf_indexer.get_settings")
    def test_index_pdf_basic(self, mock_settings):
        """Test basic PDF indexing."""
        mock_settings.return_value = MagicMock()

        # Setup mock fitz module
        mock_page = MagicMock()
        mock_page.rect.width = 612
        mock_page.rect.height = 792
        mock_page.get_text.return_value = [
            (10, 20, 50, 35, "Hello", 0, 0, 0),
            (60, 20, 100, 35, "World", 0, 0, 1),
        ]

        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=1)
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)

        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc

        # Patch fitz in sys.modules since it's imported inside the method
        with patch.dict(sys.modules, {"fitz": mock_fitz}):
            from app.services.magic_import.pdf_indexer import PDFIndexer

            indexer = PDFIndexer()
            index = indexer.index_pdf(Path("test.pdf"), "test-job-id")

            assert index.job_id == "test-job-id"
            assert index.info.total_pages == 1
            assert len(index.words) == 2
            assert index.words[0].text == "Hello"
            assert index.words[1].text == "World"

    @patch("app.services.magic_import.pdf_indexer.get_settings")
    def test_index_pdf_propagates_extracted_tables(self, mock_settings):
        """Test table extraction results are copied into the PDF index."""
        mock_settings.return_value = MagicMock()

        mock_page = MagicMock()
        mock_page.rect.width = 612
        mock_page.rect.height = 792
        mock_page.get_text.return_value = []

        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=1)
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)

        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc

        table = ExtractedTable(
            table_id="table-1",
            page=0,
            bbox=BBox(x0=0.1, y0=0.1, x1=0.9, y1=0.4),
            rows=2,
            cols=2,
            cells=[],
            headers=["Field", "Value"],
            accuracy=0.9,
            method="LATTICE",
        )

        with (
            patch.dict(sys.modules, {"fitz": mock_fitz}),
            patch(
                "app.services.magic_import.pdf_indexer.TableExtractor.extract_tables",
                return_value=TableExtractionResult.from_tables([table]),
            ),
        ):
            from app.services.magic_import.pdf_indexer import PDFIndexer

            indexer = PDFIndexer()
            index = indexer.index_pdf(Path("test.pdf"), "test-job-id")

        assert index.tables == [table]

    @patch("app.services.magic_import.pdf_indexer.get_settings")
    def test_index_pdf_handles_table_extraction_failure(self, mock_settings):
        """Test table extraction failures leave an otherwise valid index."""
        mock_settings.return_value = MagicMock()

        mock_page = MagicMock()
        mock_page.rect.width = 612
        mock_page.rect.height = 792
        mock_page.get_text.return_value = []

        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=1)
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)

        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc

        with (
            patch.dict(sys.modules, {"fitz": mock_fitz}),
            patch(
                "app.services.magic_import.pdf_indexer.TableExtractor.extract_tables",
                side_effect=RuntimeError("pdfplumber failed"),
            ),
        ):
            from app.services.magic_import.pdf_indexer import PDFIndexer

            indexer = PDFIndexer()
            index = indexer.index_pdf(Path("test.pdf"), "test-job-id")

        assert index.tables == []

    def test_bbox_normalization(self):
        """Test that bounding boxes are normalized to 0..1."""
        bbox = BBox(x0=0.1, y0=0.2, x1=0.3, y1=0.4)

        # Test to_absolute conversion
        abs_coords = bbox.to_absolute(100, 200)
        assert abs_coords == (10, 40, 30, 80)

    @patch("app.services.magic_import.pdf_indexer.get_settings")
    def test_get_full_text(self, mock_settings):
        """Test full text reconstruction from word index."""
        mock_settings.return_value = MagicMock()
        from app.services.magic_import.pdf_indexer import PDFIndexer

        indexer = PDFIndexer()

        index = PDFIndex(
            job_id="test",
            pdf_path="test.pdf",
            info=PDFIndexInfo(
                total_pages=1,
                pages_with_text=1,
                pages_needing_ocr=0,
                total_words=2,
            ),
            pages=[],
            words=[
                PDFWord(
                    text="Hello",
                    page=0,
                    bbox=BBox(x0=0.1, y0=0.1, x1=0.2, y1=0.15),
                    confidence=1.0,
                    method="TEXT",
                ),
                PDFWord(
                    text="World",
                    page=0,
                    bbox=BBox(x0=0.3, y0=0.1, x1=0.4, y1=0.15),
                    confidence=1.0,
                    method="TEXT",
                ),
            ],
        )

        text = indexer.get_full_text(index)
        assert "Hello" in text
        assert "World" in text


class TestBBox:
    """Test suite for BBox model."""

    def test_bbox_validation(self):
        """Test BBox coordinate validation."""
        # Valid bbox
        bbox = BBox(x0=0.0, y0=0.0, x1=1.0, y1=1.0)
        assert bbox.x0 == 0.0
        assert bbox.y1 == 1.0

    def test_bbox_to_absolute(self):
        """Test conversion to absolute coordinates."""
        bbox = BBox(x0=0.25, y0=0.5, x1=0.75, y1=0.75)
        abs_coords = bbox.to_absolute(800, 600)

        assert abs_coords[0] == 200  # x0
        assert abs_coords[1] == 300  # y0
        assert abs_coords[2] == 600  # x1
        assert abs_coords[3] == 450  # y1
