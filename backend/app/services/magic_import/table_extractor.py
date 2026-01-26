"""
Table Extractor - Extract structured tables from PDFs.

Uses PyMuPDF (fitz) for table detection and extraction.
Provides structured JSON output for LLM context enrichment.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.magic_import import BBox

logger = logging.getLogger(__name__)


class TableCell(BaseModel):
    """A single cell in a table."""

    text: str = Field(description="Cell text content")
    row: int = Field(ge=0, description="Row index (0-based)")
    col: int = Field(ge=0, description="Column index (0-based)")
    rowspan: int = Field(default=1, ge=1, description="Number of rows spanned")
    colspan: int = Field(default=1, ge=1, description="Number of columns spanned")


class ExtractedTable(BaseModel):
    """A table extracted from the PDF."""

    page: int = Field(ge=0, description="0-indexed page number")
    bbox: BBox = Field(description="Bounding box of the table")
    headers: list[str] = Field(default_factory=list, description="Column headers")
    rows: list[list[str]] = Field(default_factory=list, description="Data rows")
    header_units: dict[str, str] = Field(
        default_factory=dict, description="Detected units per column header"
    )
    num_rows: int = Field(default=0, description="Number of data rows")
    num_cols: int = Field(default=0, description="Number of columns")
    table_type: Literal["data", "key_value", "mixed"] = Field(
        default="data", description="Detected table structure type"
    )


class TableExtractionResult(BaseModel):
    """Result of table extraction for a document."""

    tables: list[ExtractedTable] = Field(default_factory=list)
    total_tables: int = Field(default=0)
    pages_with_tables: list[int] = Field(default_factory=list)


class TableExtractor:
    """Extract structured tables from PDF documents."""

    # Common unit patterns for header parsing
    UNIT_PATTERNS = [
        (r"\(([^)]+)\)$", 1),  # "Power (kW)" → "kW"
        (r"\[([^\]]+)\]$", 1),  # "Power [kW]" → "kW"
        (r"in\s+(\w+)$", 1),  # "Power in kW" → "kW"
        (r",\s*(\w+)$", 1),  # "Power, kW" → "kW"
    ]

    # Common unit abbreviations to expand
    UNIT_EXPANSIONS = {
        "kg": "kilogram",
        "g": "gram",
        "mg": "milligram",
        "m": "meter",
        "cm": "centimeter",
        "mm": "millimeter",
        "km": "kilometer",
        "kW": "kilowatt",
        "W": "watt",
        "MW": "megawatt",
        "V": "volt",
        "kV": "kilovolt",
        "A": "ampere",
        "mA": "milliampere",
        "Hz": "hertz",
        "kHz": "kilohertz",
        "MHz": "megahertz",
        "s": "second",
        "ms": "millisecond",
        "min": "minute",
        "h": "hour",
        "°C": "celsius",
        "°F": "fahrenheit",
        "K": "kelvin",
        "%": "percent",
        "Pa": "pascal",
        "kPa": "kilopascal",
        "MPa": "megapascal",
        "bar": "bar",
        "N": "newton",
        "kN": "kilonewton",
        "Nm": "newton_meter",
        "J": "joule",
        "kJ": "kilojoule",
        "MJ": "megajoule",
        "Wh": "watt_hour",
        "kWh": "kilowatt_hour",
    }

    def __init__(self) -> None:
        pass

    def extract_tables(self, pdf_path: Path) -> TableExtractionResult:
        """
        Extract all tables from a PDF document.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            TableExtractionResult with all extracted tables
        """
        import fitz

        tables: list[ExtractedTable] = []
        pages_with_tables: set[int] = set()

        doc = fitz.open(pdf_path)
        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_tables = self._extract_tables_from_page(page, page_num)

                if page_tables:
                    tables.extend(page_tables)
                    pages_with_tables.add(page_num)

        finally:
            doc.close()

        logger.info(
            "Extracted %d tables from %s across %d pages",
            len(tables),
            pdf_path.name,
            len(pages_with_tables),
        )

        return TableExtractionResult(
            tables=tables,
            total_tables=len(tables),
            pages_with_tables=sorted(pages_with_tables),
        )

    def _extract_tables_from_page(
        self, page, page_num: int
    ) -> list[ExtractedTable]:
        """Extract tables from a single page using PyMuPDF's table finder."""
        extracted: list[ExtractedTable] = []
        page_rect = page.rect
        page_width = page_rect.width
        page_height = page_rect.height

        try:
            # Use PyMuPDF's table finder (available in fitz 1.23.0+)
            tabs = page.find_tables()

            for tab in tabs:
                # Get table bounding box
                rect = tab.bbox
                bbox = BBox(
                    x0=max(0.0, min(1.0, rect[0] / page_width)),
                    y0=max(0.0, min(1.0, rect[1] / page_height)),
                    x1=max(0.0, min(1.0, rect[2] / page_width)),
                    y1=max(0.0, min(1.0, rect[3] / page_height)),
                )

                # Extract table data
                table_data = tab.extract()

                if not table_data or len(table_data) < 1:
                    continue

                # Process headers and rows
                headers, header_units = self._process_headers(table_data[0])
                rows = [
                    [self._clean_cell(cell) for cell in row]
                    for row in table_data[1:]
                ]

                # Determine table type
                table_type = self._classify_table(headers, rows)

                extracted.append(
                    ExtractedTable(
                        page=page_num,
                        bbox=bbox,
                        headers=headers,
                        rows=rows,
                        header_units=header_units,
                        num_rows=len(rows),
                        num_cols=len(headers) if headers else (len(rows[0]) if rows else 0),
                        table_type=table_type,
                    )
                )

        except Exception as e:
            # Table extraction may fail on complex layouts
            logger.debug("Table extraction failed on page %d: %s", page_num, e)

        return extracted

    def _process_headers(
        self, header_row: list
    ) -> tuple[list[str], dict[str, str]]:
        """
        Process header row to extract clean headers and units.

        Args:
            header_row: Raw header row from table

        Returns:
            Tuple of (clean headers, header→unit mapping)
        """
        headers: list[str] = []
        header_units: dict[str, str] = {}

        for cell in header_row:
            cell_text = self._clean_cell(cell)

            # Try to extract unit from header
            unit = None
            clean_header = cell_text

            for pattern, group in self.UNIT_PATTERNS:
                match = re.search(pattern, cell_text)
                if match:
                    unit = match.group(group).strip()
                    # Remove unit part from header
                    clean_header = re.sub(pattern, "", cell_text).strip()
                    break

            headers.append(clean_header)
            if unit:
                header_units[clean_header] = unit

        return headers, header_units

    def _clean_cell(self, cell) -> str:
        """Clean cell content, handling None and multi-line values."""
        if cell is None:
            return ""
        text = str(cell).strip()
        # Normalize whitespace
        text = " ".join(text.split())
        return text

    def _classify_table(
        self, headers: list[str], rows: list[list[str]]
    ) -> Literal["data", "key_value", "mixed"]:
        """
        Classify table structure type.

        - data: Regular tabular data with headers
        - key_value: Two-column key-value pairs
        - mixed: Complex structure
        """
        num_cols = len(headers) if headers else (len(rows[0]) if rows else 0)

        # Two columns with first column being labels → key_value
        if num_cols == 2 and rows:
            # Check if first column looks like labels (short text, no numbers)
            first_col_is_labels = all(
                len(row[0]) < 50 and not re.match(r"^\d+\.?\d*$", row[0])
                for row in rows
                if len(row) >= 2 and row[0]
            )
            if first_col_is_labels:
                return "key_value"

        # Standard data table
        if headers and rows:
            return "data"

        return "mixed"

    def normalize_headers(self, table: ExtractedTable) -> ExtractedTable:
        """
        Normalize table headers by expanding unit abbreviations.

        Args:
            table: Table to normalize

        Returns:
            Table with expanded units in header_units
        """
        expanded_units = {}
        for header, unit in table.header_units.items():
            expanded = self.UNIT_EXPANSIONS.get(unit, unit)
            expanded_units[header] = expanded

        return table.model_copy(update={"header_units": expanded_units})

    def table_to_snippets(
        self, table: ExtractedTable, max_rows: int = 10
    ) -> list[str]:
        """
        Convert table to text snippets for LLM context.

        Generates structured text representations that are easier
        for the LLM to parse than raw table data.

        Args:
            table: Extracted table
            max_rows: Maximum rows to include per snippet

        Returns:
            List of text snippets representing table data
        """
        snippets: list[str] = []

        if table.table_type == "key_value":
            # Key-value format: "Parameter: Value"
            for row in table.rows[:max_rows]:
                if len(row) >= 2 and row[0] and row[1]:
                    key = row[0]
                    value = row[1]
                    # Include unit if known
                    if key in table.header_units:
                        value = f"{value} {table.header_units[key]}"
                    snippets.append(f"{key}: {value}")

        else:
            # Data table format: structured rows
            for row in table.rows[:max_rows]:
                parts = []
                for i, cell in enumerate(row):
                    if i < len(table.headers) and table.headers[i]:
                        header = table.headers[i]
                        unit = table.header_units.get(header, "")
                        if unit:
                            parts.append(f"{header}: {cell} {unit}")
                        else:
                            parts.append(f"{header}: {cell}")
                    elif cell:
                        parts.append(cell)

                if parts:
                    snippets.append(" | ".join(parts))

        return snippets

    def find_value_in_tables(
        self,
        tables: list[ExtractedTable],
        field_name: str,
        keywords: list[str] | None = None,
    ) -> list[tuple[str, ExtractedTable, int, int]]:
        """
        Search tables for values matching a field name or keywords.

        Args:
            tables: List of tables to search
            field_name: Field name to search for
            keywords: Additional keywords to match

        Returns:
            List of (value, table, row_idx, col_idx) tuples
        """
        matches: list[tuple[str, ExtractedTable, int, int]] = []
        search_terms = [field_name.lower()]
        if keywords:
            search_terms.extend(k.lower() for k in keywords)

        for table in tables:
            # Search headers
            for col_idx, header in enumerate(table.headers):
                header_lower = header.lower()
                if any(term in header_lower for term in search_terms):
                    # Found matching column - return all values in that column
                    for row_idx, row in enumerate(table.rows):
                        if col_idx < len(row) and row[col_idx]:
                            matches.append((row[col_idx], table, row_idx, col_idx))

            # Search key-value tables
            if table.table_type == "key_value":
                for row_idx, row in enumerate(table.rows):
                    if len(row) >= 2:
                        key_lower = row[0].lower()
                        if any(term in key_lower for term in search_terms):
                            matches.append((row[1], table, row_idx, 1))

        return matches
