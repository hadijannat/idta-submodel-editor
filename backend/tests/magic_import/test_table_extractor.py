"""Tests for table extractor module."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import fitz
import pytest

from app.services.magic_import.table_extractor import (
    TableExtractor,
    TableExtractionResult,
)
from app.schemas.magic_import import BBox, ExtractedTable, ExtractedTableCell


class TestTableExtractionResult:
    """Tests for TableExtractionResult class."""

    def test_empty_result(self):
        """Test creating an empty result."""
        result = TableExtractionResult()
        assert result.total_tables == 0
        assert result.tables == []
        assert result.pages_with_tables == []
        assert result.has_key_value_tables is False

    def test_from_tables(self):
        """Test creating result from a list of tables."""
        tables = [
            ExtractedTable(
                table_id="1",
                page=0,
                bbox=BBox(x0=0.1, y0=0.1, x1=0.9, y1=0.5),
                rows=3,
                cols=2,  # Key-value format
                cells=[],
                headers=[],
                accuracy=0.9,
                method="LATTICE",
            ),
            ExtractedTable(
                table_id="2",
                page=2,
                bbox=BBox(x0=0.1, y0=0.5, x1=0.9, y1=0.9),
                rows=5,
                cols=4,
                cells=[],
                headers=[],
                accuracy=0.8,
                method="STREAM",
            ),
        ]
        result = TableExtractionResult.from_tables(tables)
        assert result.total_tables == 2
        assert result.pages_with_tables == [0, 2]
        assert result.has_key_value_tables is True

    def test_serialization(self):
        """Test result can be serialized and deserialized."""
        tables = [
            ExtractedTable(
                table_id="1",
                page=0,
                bbox=BBox(x0=0.1, y0=0.1, x1=0.9, y1=0.5),
                rows=3,
                cols=2,
                cells=[ExtractedTableCell(row=0, col=0, text="Header")],
                headers=["Header"],
                accuracy=0.9,
                method="LATTICE",
            ),
        ]
        result = TableExtractionResult.from_tables(tables)
        
        # Serialize
        data = result.model_dump()
        assert "tables" in data
        assert "total_tables" in data
        
        # Deserialize
        restored = TableExtractionResult(**data)
        assert restored.total_tables == result.total_tables
        assert len(restored.tables) == len(result.tables)


class TestTableExtractor:
    """Tests for TableExtractor class."""

    @pytest.fixture
    def extractor(self):
        """Create a TableExtractor instance."""
        return TableExtractor()

    def test_init(self, extractor):
        """Test default initialization."""
        assert extractor.MIN_ROWS == 2
        assert extractor.MIN_COLS == 2
        assert "vertical_strategy" in extractor.TABLE_SETTINGS
        assert "vertical_strategy" in extractor.STREAM_SETTINGS

    def test_calculate_overlap_no_overlap(self, extractor):
        """Test IoU calculation with no overlap."""
        box1 = BBox(x0=0.0, y0=0.0, x1=0.3, y1=0.3)
        box2 = BBox(x0=0.5, y0=0.5, x1=0.8, y1=0.8)
        overlap = extractor._calculate_overlap(box1, box2)
        assert overlap == 0.0

    def test_calculate_overlap_full_overlap(self, extractor):
        """Test IoU calculation with identical boxes."""
        box = BBox(x0=0.2, y0=0.2, x1=0.6, y1=0.6)
        overlap = extractor._calculate_overlap(box, box)
        assert abs(overlap - 1.0) < 0.001

    def test_calculate_overlap_partial(self, extractor):
        """Test IoU calculation with partial overlap."""
        box1 = BBox(x0=0.0, y0=0.0, x1=0.5, y1=0.5)
        box2 = BBox(x0=0.25, y0=0.25, x1=0.75, y1=0.75)
        overlap = extractor._calculate_overlap(box1, box2)
        assert 0.1 < overlap < 0.2

    def test_deduplicate_tables_no_overlap(self, extractor):
        """Test deduplication with non-overlapping tables."""
        table1 = ExtractedTable(
            table_id="1",
            page=0,
            bbox=BBox(x0=0.0, y0=0.0, x1=0.4, y1=0.3),
            rows=3,
            cols=2,
            cells=[],
            headers=[],
            accuracy=0.8,
            method="LATTICE",
        )
        table2 = ExtractedTable(
            table_id="2",
            page=0,
            bbox=BBox(x0=0.5, y0=0.5, x1=0.9, y1=0.8),
            rows=3,
            cols=2,
            cells=[],
            headers=[],
            accuracy=0.9,
            method="LATTICE",
        )
        result = extractor._deduplicate_tables([table1, table2])
        assert len(result) == 2

    def test_deduplicate_tables_with_overlap(self, extractor):
        """Test deduplication removes highly overlapping tables."""
        table1 = ExtractedTable(
            table_id="1",
            page=0,
            bbox=BBox(x0=0.1, y0=0.1, x1=0.5, y1=0.5),
            rows=3,
            cols=2,
            cells=[],
            headers=[],
            accuracy=0.9,
            method="LATTICE",
        )
        table2 = ExtractedTable(
            table_id="2",
            page=0,
            bbox=BBox(x0=0.12, y0=0.12, x1=0.52, y1=0.52),
            rows=3,
            cols=2,
            cells=[],
            headers=[],
            accuracy=0.7,
            method="STREAM",
        )
        result = extractor._deduplicate_tables([table1, table2])
        assert len(result) == 1
        assert result[0].accuracy == 0.9

    def test_deduplicate_tables_different_pages(self, extractor):
        """Test deduplication keeps tables from different pages."""
        table1 = ExtractedTable(
            table_id="1",
            page=0,
            bbox=BBox(x0=0.1, y0=0.1, x1=0.5, y1=0.5),
            rows=3,
            cols=2,
            cells=[],
            headers=[],
            accuracy=0.8,
            method="LATTICE",
        )
        table2 = ExtractedTable(
            table_id="2",
            page=1,
            bbox=BBox(x0=0.1, y0=0.1, x1=0.5, y1=0.5),
            rows=3,
            cols=2,
            cells=[],
            headers=[],
            accuracy=0.9,
            method="LATTICE",
        )
        result = extractor._deduplicate_tables([table1, table2])
        assert len(result) == 2

    def test_get_table_as_text(self, extractor):
        """Test converting table to text representation."""
        cells = [
            ExtractedTableCell(row=0, col=0, text="Header1", is_header=True),
            ExtractedTableCell(row=0, col=1, text="Header2", is_header=True),
            ExtractedTableCell(row=1, col=0, text="Value1"),
            ExtractedTableCell(row=1, col=1, text="Value2"),
        ]
        table = ExtractedTable(
            table_id="test",
            page=0,
            bbox=BBox(x0=0.1, y0=0.1, x1=0.9, y1=0.9),
            rows=2,
            cols=2,
            cells=cells,
            headers=["Header1", "Header2"],
            accuracy=0.95,
            method="LATTICE",
        )
        text = extractor.get_table_as_text(table)
        assert "Header1 | Header2" in text
        assert "Value1 | Value2" in text

    def test_table_to_snippets_uses_dense_rows(self, extractor):
        """Test converting a table into retrieval snippets."""
        cells = [
            ExtractedTableCell(row=0, col=0, text="Header1", is_header=True),
            ExtractedTableCell(row=0, col=1, text="Header2", is_header=True),
            ExtractedTableCell(row=1, col=0, text="Value1"),
            ExtractedTableCell(row=1, col=1, text="Value2"),
            ExtractedTableCell(row=2, col=0, text="Value3"),
            ExtractedTableCell(row=2, col=1, text="Value4"),
        ]
        table = ExtractedTable(
            table_id="test",
            page=0,
            bbox=BBox(x0=0.1, y0=0.1, x1=0.9, y1=0.9),
            rows=3,
            cols=2,
            cells=cells,
            headers=["Header1", "Header2"],
            accuracy=0.95,
            method="LATTICE",
        )

        snippets = extractor.table_to_snippets(table, max_rows=2)

        assert snippets == ["Header1 | Header2\nValue1 | Value2"]

    def test_get_table_as_text_empty(self, extractor):
        """Test converting empty table to text."""
        table = ExtractedTable(
            table_id="test",
            page=0,
            bbox=BBox(x0=0.1, y0=0.1, x1=0.9, y1=0.9),
            rows=0,
            cols=0,
            cells=[],
            headers=[],
            accuracy=0.0,
            method="LATTICE",
        )
        text = extractor.get_table_as_text(table)
        assert text == ""

    def test_search_table_for_value_exact(self, extractor):
        """Test exact match search in table."""
        cells = [
            ExtractedTableCell(row=0, col=0, text="Name"),
            ExtractedTableCell(row=0, col=1, text="John Doe"),
            ExtractedTableCell(row=1, col=0, text="Age"),
            ExtractedTableCell(row=1, col=1, text="30"),
        ]
        table = ExtractedTable(
            table_id="test",
            page=0,
            bbox=BBox(x0=0.1, y0=0.1, x1=0.9, y1=0.9),
            rows=2,
            cols=2,
            cells=cells,
            headers=[],
            accuracy=0.95,
            method="LATTICE",
        )
        results = extractor.search_table_for_value(table, "John Doe", fuzzy=False)
        assert len(results) == 1
        assert results[0][0].text == "John Doe"
        assert results[0][1] == 1.0

    def test_search_table_for_value_substring(self, extractor):
        """Test substring match search in table."""
        cells = [
            ExtractedTableCell(row=0, col=0, text="Product Name"),
            ExtractedTableCell(row=0, col=1, text="Motor Controller XYZ-100"),
        ]
        table = ExtractedTable(
            table_id="test",
            page=0,
            bbox=BBox(x0=0.1, y0=0.1, x1=0.9, y1=0.9),
            rows=1,
            cols=2,
            cells=cells,
            headers=[],
            accuracy=0.95,
            method="LATTICE",
        )
        results = extractor.search_table_for_value(table, "motor", fuzzy=False)
        assert len(results) == 1
        assert "Motor" in results[0][0].text

    def test_search_table_for_value_fuzzy_typo(self, extractor):
        """Test fuzzy match handles table value typos."""
        cells = [
            ExtractedTableCell(row=0, col=0, text="Product Name"),
            ExtractedTableCell(row=0, col=1, text="Motor Controller XYZ-100"),
        ]
        table = ExtractedTable(
            table_id="test",
            page=0,
            bbox=BBox(x0=0.1, y0=0.1, x1=0.9, y1=0.9),
            rows=1,
            cols=2,
            cells=cells,
            headers=[],
            accuracy=0.95,
            method="LATTICE",
        )

        typo_query = "Mtor Controller XYZ100"

        non_fuzzy_results = extractor.search_table_for_value(table, typo_query, fuzzy=False)
        assert non_fuzzy_results == []

        fuzzy_results = extractor.search_table_for_value(table, typo_query, fuzzy=True)
        assert len(fuzzy_results) == 1
        assert fuzzy_results[0][0].text == "Motor Controller XYZ-100"
        assert fuzzy_results[0][1] > 0.6

    def test_get_key_value_pairs(self, extractor):
        """Test extracting key-value pairs from 2-column table."""
        cells = [
            ExtractedTableCell(row=0, col=0, text="Parameter", is_header=True),
            ExtractedTableCell(row=0, col=1, text="Value", is_header=True),
            ExtractedTableCell(row=1, col=0, text="Manufacturer"),
            ExtractedTableCell(row=1, col=1, text="ACME Corp"),
            ExtractedTableCell(row=2, col=0, text="Weight"),
            ExtractedTableCell(row=2, col=1, text="5.2 kg"),
        ]
        table = ExtractedTable(
            table_id="test",
            page=0,
            bbox=BBox(x0=0.1, y0=0.1, x1=0.9, y1=0.9),
            rows=3,
            cols=2,
            cells=cells,
            headers=["Parameter", "Value"],
            accuracy=0.95,
            method="LATTICE",
        )
        pairs = extractor.get_key_value_pairs(table)
        assert len(pairs) == 2
        keys = [p[0] for p in pairs]
        assert "Manufacturer" in keys
        assert "Weight" in keys

    def test_get_key_value_pairs_single_column(self, extractor):
        """Test key-value extraction fails gracefully for single column."""
        cells = [
            ExtractedTableCell(row=0, col=0, text="Only Column"),
        ]
        table = ExtractedTable(
            table_id="test",
            page=0,
            bbox=BBox(x0=0.1, y0=0.1, x1=0.9, y1=0.9),
            rows=1,
            cols=1,
            cells=cells,
            headers=[],
            accuracy=0.95,
            method="LATTICE",
        )
        pairs = extractor.get_key_value_pairs(table)
        assert pairs == []

    def test_extract_tables_uses_real_pdfplumber_contract(self, extractor, tmp_path: Path):
        """Exercise pdfplumber.open/find_tables/extract against a small real PDF."""
        pdf_path = tmp_path / "table.pdf"
        doc = fitz.open()
        page = doc.new_page(width=300, height=200)
        for x in (50, 150, 250):
            page.draw_line((x, 50), (x, 150), color=(0, 0, 0), width=1)
        for y in (50, 100, 150):
            page.draw_line((50, y), (250, y), color=(0, 0, 0), width=1)
        page.insert_text((65, 80), "Field", fontsize=10)
        page.insert_text((165, 80), "Value", fontsize=10)
        page.insert_text((65, 130), "Serial", fontsize=10)
        page.insert_text((165, 130), "SN-123", fontsize=10)
        doc.save(pdf_path)
        doc.close()

        result = extractor.extract_tables(pdf_path)

        assert result.total_tables == 1
        assert result.pages_with_tables == [0]
        table = result.tables[0]
        assert table.rows == 2
        assert table.cols == 2
        assert table.headers == ["Field", "Value"]
        assert "Serial | SN-123" in extractor.get_table_as_text(table)

    def test_extract_tables_handles_missing_pdfplumber(self, extractor, monkeypatch, tmp_path: Path):
        """Test extraction degrades gracefully when pdfplumber is unavailable."""
        real_pdfplumber = sys.modules.pop("pdfplumber", None)
        monkeypatch.setitem(sys.modules, "pdfplumber", None)
        try:
            result = extractor.extract_tables(tmp_path / "missing.pdf")
        finally:
            if real_pdfplumber is not None:
                monkeypatch.setitem(sys.modules, "pdfplumber", real_pdfplumber)

        assert result.total_tables == 0

    def test_extract_tables_uses_stream_fallback(self, extractor, monkeypatch, tmp_path: Path):
        """Test stream extraction is attempted when lattice extraction finds no tables."""
        mock_table = MagicMock()
        mock_table.extract.return_value = [["Field", "Value"], ["Serial", "SN-123"]]
        mock_table.bbox = (0, 0, 100, 100)

        mock_page = MagicMock(width=100, height=100)
        mock_page.find_tables.side_effect = [[], [mock_table]]

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__.return_value = mock_pdf
        mock_pdf.__exit__.return_value = None

        mock_pdfplumber = MagicMock()
        mock_pdfplumber.open.return_value = mock_pdf
        monkeypatch.setitem(sys.modules, "pdfplumber", mock_pdfplumber)

        result = extractor.extract_tables(tmp_path / "table.pdf")

        assert result.total_tables == 1
        assert result.tables[0].method == "STREAM"
        assert mock_page.find_tables.call_count == 2
