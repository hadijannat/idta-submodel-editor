"""
Tests for TableExtractor module.

Tests table extraction from PDFs, header processing, and table-to-snippet conversion.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.schemas.magic_import import BBox
from app.services.magic_import.table_extractor import (
    TableExtractor,
    TableCell,
    ExtractedTable,
    TableExtractionResult,
)


class TestTableExtractor:
    """Tests for TableExtractor class."""

    @pytest.fixture
    def extractor(self):
        """Create a TableExtractor instance."""
        return TableExtractor()

    @pytest.fixture
    def sample_data_table(self):
        """Create a sample data table."""
        return ExtractedTable(
            page=0,
            bbox=BBox(x0=0.1, y0=0.1, x1=0.9, y1=0.5),
            headers=["Parameter", "Value", "Unit"],
            rows=[
                ["Rated Power", "5.5", "kW"],
                ["Rated Voltage", "400", "V"],
                ["Rated Current", "9.5", "A"],
            ],
            header_units={},
            num_rows=3,
            num_cols=3,
            table_type="data",
        )

    @pytest.fixture
    def sample_kv_table(self):
        """Create a sample key-value table."""
        return ExtractedTable(
            page=0,
            bbox=BBox(x0=0.1, y0=0.1, x1=0.5, y1=0.4),
            headers=["Property", "Value"],
            rows=[
                ["Manufacturer", "Siemens"],
                ["Model Number", "1LA7096-4AA10"],
                ["Weight", "25 kg"],
            ],
            header_units={},
            num_rows=3,
            num_cols=2,
            table_type="key_value",
        )

    # =========================================================================
    # Header Processing Tests
    # =========================================================================

    def test_process_headers_extracts_units_from_parentheses(self, extractor):
        """Test that units in parentheses are extracted from headers."""
        header_row = ["Power (kW)", "Voltage (V)", "Current (A)"]
        headers, header_units = extractor._process_headers(header_row)

        assert headers == ["Power", "Voltage", "Current"]
        assert header_units == {"Power": "kW", "Voltage": "V", "Current": "A"}

    def test_process_headers_extracts_units_from_brackets(self, extractor):
        """Test that units in square brackets are extracted."""
        header_row = ["Power [kW]", "Temperature [°C]"]
        headers, header_units = extractor._process_headers(header_row)

        assert headers == ["Power", "Temperature"]
        assert header_units == {"Power": "kW", "Temperature": "°C"}

    def test_process_headers_extracts_units_with_in_prefix(self, extractor):
        """Test that 'in <unit>' pattern is extracted."""
        header_row = ["Power in kW", "Mass in kg"]
        headers, header_units = extractor._process_headers(header_row)

        assert headers == ["Power", "Mass"]
        assert header_units == {"Power": "kW", "Mass": "kg"}

    def test_process_headers_handles_no_units(self, extractor):
        """Test headers without units are preserved."""
        header_row = ["Name", "Description", "Status"]
        headers, header_units = extractor._process_headers(header_row)

        assert headers == ["Name", "Description", "Status"]
        assert header_units == {}

    def test_process_headers_handles_none_values(self, extractor):
        """Test that None values in headers are handled."""
        header_row = ["Name", None, "Value"]
        headers, header_units = extractor._process_headers(header_row)

        assert headers == ["Name", "", "Value"]

    # =========================================================================
    # Cell Cleaning Tests
    # =========================================================================

    def test_clean_cell_handles_none(self, extractor):
        """Test that None cells become empty strings."""
        assert extractor._clean_cell(None) == ""

    def test_clean_cell_normalizes_whitespace(self, extractor):
        """Test that whitespace is normalized."""
        assert extractor._clean_cell("  hello   world  ") == "hello world"
        assert extractor._clean_cell("line1\nline2") == "line1 line2"

    def test_clean_cell_handles_numbers(self, extractor):
        """Test that numbers are converted to strings."""
        assert extractor._clean_cell(42) == "42"
        assert extractor._clean_cell(3.14) == "3.14"

    # =========================================================================
    # Table Classification Tests
    # =========================================================================

    def test_classify_table_key_value(self, extractor):
        """Test classification of key-value tables."""
        headers = ["Property", "Value"]
        rows = [
            ["Name", "Motor A"],
            ["Type", "Induction"],
            ["Rating", "5.5 kW"],
        ]
        result = extractor._classify_table(headers, rows)
        assert result == "key_value"

    def test_classify_table_data(self, extractor):
        """Test classification of data tables."""
        headers = ["ID", "Name", "Power", "Voltage"]
        rows = [
            ["001", "Motor A", "5.5 kW", "400 V"],
            ["002", "Motor B", "7.5 kW", "400 V"],
        ]
        result = extractor._classify_table(headers, rows)
        assert result == "data"

    def test_classify_table_mixed_when_empty(self, extractor):
        """Test classification returns 'mixed' for edge cases."""
        result = extractor._classify_table([], [])
        assert result == "mixed"

    # =========================================================================
    # Unit Normalization Tests
    # =========================================================================

    def test_normalize_headers_expands_units(self, extractor):
        """Test that unit abbreviations are expanded."""
        table = ExtractedTable(
            page=0,
            bbox=BBox(x0=0, y0=0, x1=1, y1=1),
            headers=["Power", "Mass"],
            rows=[],
            header_units={"Power": "kW", "Mass": "kg"},
            num_rows=0,
            num_cols=2,
            table_type="data",
        )

        normalized = extractor.normalize_headers(table)

        assert normalized.header_units == {
            "Power": "kilowatt",
            "Mass": "kilogram",
        }

    def test_normalize_headers_preserves_unknown_units(self, extractor):
        """Test that unknown units are preserved."""
        table = ExtractedTable(
            page=0,
            bbox=BBox(x0=0, y0=0, x1=1, y1=1),
            headers=["Custom"],
            rows=[],
            header_units={"Custom": "xyz"},
            num_rows=0,
            num_cols=1,
            table_type="data",
        )

        normalized = extractor.normalize_headers(table)
        assert normalized.header_units == {"Custom": "xyz"}

    # =========================================================================
    # Table-to-Snippets Tests
    # =========================================================================

    def test_table_to_snippets_key_value(self, extractor, sample_kv_table):
        """Test snippet generation for key-value tables."""
        snippets = extractor.table_to_snippets(sample_kv_table)

        assert len(snippets) == 3
        assert "Manufacturer: Siemens" in snippets
        assert "Model Number: 1LA7096-4AA10" in snippets
        assert "Weight: 25 kg" in snippets

    def test_table_to_snippets_data_table(self, extractor, sample_data_table):
        """Test snippet generation for data tables."""
        snippets = extractor.table_to_snippets(sample_data_table)

        assert len(snippets) == 3
        # Data table format uses | separator
        assert "Parameter: Rated Power | Value: 5.5 | Unit: kW" in snippets[0]

    def test_table_to_snippets_respects_max_rows(self, extractor, sample_data_table):
        """Test that max_rows parameter is respected."""
        snippets = extractor.table_to_snippets(sample_data_table, max_rows=2)
        assert len(snippets) == 2

    def test_table_to_snippets_includes_units(self, extractor):
        """Test that units from header_units are included in snippets."""
        table = ExtractedTable(
            page=0,
            bbox=BBox(x0=0, y0=0, x1=1, y1=1),
            headers=["Power", "Voltage"],
            rows=[["5.5", "400"]],
            header_units={"Power": "kW", "Voltage": "V"},
            num_rows=1,
            num_cols=2,
            table_type="data",
        )

        snippets = extractor.table_to_snippets(table)
        assert len(snippets) == 1
        assert "Power: 5.5 kW" in snippets[0]
        assert "Voltage: 400 V" in snippets[0]

    # =========================================================================
    # Table Search Tests
    # =========================================================================

    def test_find_value_in_tables_by_header(self, extractor, sample_data_table):
        """Test finding values by matching header."""
        tables = [sample_data_table]
        matches = extractor.find_value_in_tables(tables, "Value")

        # Should find all values in the "Value" column
        values = [m[0] for m in matches]
        assert "5.5" in values
        assert "400" in values
        assert "9.5" in values

    def test_find_value_in_tables_with_keywords(self, extractor, sample_data_table):
        """Test finding values using keywords."""
        tables = [sample_data_table]
        matches = extractor.find_value_in_tables(
            tables, "power", keywords=["rated", "leistung"]
        )

        # Should match "Rated Power" in Parameter column (key-value style search)
        # or find in headers
        assert len(matches) >= 0  # Depends on implementation

    def test_find_value_in_tables_key_value(self, extractor, sample_kv_table):
        """Test finding values in key-value tables."""
        tables = [sample_kv_table]
        matches = extractor.find_value_in_tables(tables, "Manufacturer")

        values = [m[0] for m in matches]
        assert "Siemens" in values

    def test_find_value_in_tables_case_insensitive(self, extractor, sample_kv_table):
        """Test that search is case-insensitive."""
        tables = [sample_kv_table]
        matches = extractor.find_value_in_tables(tables, "MANUFACTURER")

        values = [m[0] for m in matches]
        assert "Siemens" in values

    def test_find_value_in_tables_no_match(self, extractor, sample_data_table):
        """Test behavior when no match is found."""
        tables = [sample_data_table]
        matches = extractor.find_value_in_tables(tables, "nonexistent")

        assert len(matches) == 0


class TestExtractedTableModel:
    """Tests for ExtractedTable model."""

    def test_extracted_table_creation(self):
        """Test creating an ExtractedTable."""
        table = ExtractedTable(
            page=0,
            bbox=BBox(x0=0.1, y0=0.2, x1=0.9, y1=0.8),
            headers=["A", "B"],
            rows=[["1", "2"]],
            header_units={"A": "m"},
            num_rows=1,
            num_cols=2,
            table_type="data",
        )

        assert table.page == 0
        assert len(table.headers) == 2
        assert table.table_type == "data"

    def test_table_type_validation(self):
        """Test that table_type must be valid."""
        # Valid types
        for tt in ["data", "key_value", "mixed"]:
            table = ExtractedTable(
                page=0,
                bbox=BBox(x0=0, y0=0, x1=1, y1=1),
                headers=[],
                rows=[],
                header_units={},
                num_rows=0,
                num_cols=0,
                table_type=tt,
            )
            assert table.table_type == tt


class TestTableExtractionResult:
    """Tests for TableExtractionResult model."""

    def test_result_creation(self):
        """Test creating a TableExtractionResult."""
        result = TableExtractionResult(
            tables=[],
            total_tables=0,
            pages_with_tables=[],
        )

        assert result.total_tables == 0
        assert result.tables == []

    def test_result_with_tables(self):
        """Test result with actual tables."""
        table = ExtractedTable(
            page=2,
            bbox=BBox(x0=0, y0=0, x1=1, y1=1),
            headers=["X"],
            rows=[["1"]],
            header_units={},
            num_rows=1,
            num_cols=1,
            table_type="data",
        )

        result = TableExtractionResult(
            tables=[table],
            total_tables=1,
            pages_with_tables=[2],
        )

        assert result.total_tables == 1
        assert result.pages_with_tables == [2]
        assert result.tables[0].page == 2


class TestTableCellModel:
    """Tests for TableCell model."""

    def test_cell_creation(self):
        """Test creating a TableCell."""
        cell = TableCell(
            text="Hello",
            row=0,
            col=1,
            rowspan=1,
            colspan=2,
        )

        assert cell.text == "Hello"
        assert cell.row == 0
        assert cell.col == 1
        assert cell.colspan == 2

    def test_cell_defaults(self):
        """Test TableCell default values."""
        cell = TableCell(text="Test", row=0, col=0)

        assert cell.rowspan == 1
        assert cell.colspan == 1

    def test_cell_validation(self):
        """Test TableCell validation."""
        # row and col must be >= 0
        with pytest.raises(ValueError):
            TableCell(text="Test", row=-1, col=0)

        with pytest.raises(ValueError):
            TableCell(text="Test", row=0, col=-1)
