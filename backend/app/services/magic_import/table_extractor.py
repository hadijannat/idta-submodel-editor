"""
Table Extractor - Extract structured tables from PDF documents.

Uses pdfplumber for table detection and extraction. Provides structured
table data that can be used for more accurate field extraction.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.magic_import import (
    BBox,
    ExtractedTable,
    ExtractedTableCell,
)

logger = logging.getLogger(__name__)


class TableExtractionResult(BaseModel):
    """Result of table extraction from a PDF document."""

    tables: list[ExtractedTable] = Field(default_factory=list, description="Extracted tables")
    total_tables: int = Field(default=0, description="Total number of tables found")
    pages_with_tables: list[int] = Field(
        default_factory=list, description="0-indexed page numbers containing tables"
    )
    has_key_value_tables: bool = Field(
        default=False, description="Whether any tables appear to be key-value format"
    )

    @classmethod
    def from_tables(cls, tables: list[ExtractedTable]) -> "TableExtractionResult":
        """Create a result from a list of extracted tables."""
        pages_with_tables = sorted(set(t.page for t in tables))
        has_key_value = any(t.cols == 2 for t in tables)
        return cls(
            tables=tables,
            total_tables=len(tables),
            pages_with_tables=pages_with_tables,
            has_key_value_tables=has_key_value,
        )


class TableExtractor:
    """Extract structured tables from PDF pages using pdfplumber."""

    # Minimum table dimensions to consider valid
    MIN_ROWS = 2
    MIN_COLS = 2

    # Table detection settings for pdfplumber
    TABLE_SETTINGS = {
        "vertical_strategy": "lines_strict",
        "horizontal_strategy": "lines_strict",
        "snap_tolerance": 3,
        "join_tolerance": 3,
        "edge_min_length": 3,
        "min_words_vertical": 3,
        "min_words_horizontal": 1,
    }

    # Fallback settings for borderless tables
    STREAM_SETTINGS = {
        "vertical_strategy": "text",
        "horizontal_strategy": "text",
        "snap_tolerance": 5,
        "join_tolerance": 5,
    }

    def extract_tables(
        self,
        pdf_path: Path,
        pages: list[int] | None = None,
    ) -> TableExtractionResult:
        """
        Extract all tables from a PDF document.

        Args:
            pdf_path: Path to the PDF file
            pages: Optional list of 0-indexed page numbers to process.
                   If None, processes all pages.

        Returns:
            TableExtractionResult containing all extracted tables
        """
        try:
            import pdfplumber
        except ImportError:
            logger.warning("pdfplumber not installed, skipping table extraction")
            return TableExtractionResult()

        tables: list[ExtractedTable] = []

        try:
            with pdfplumber.open(pdf_path) as pdf:
                page_nums = pages if pages is not None else range(len(pdf.pages))

                for page_num in page_nums:
                    if page_num < 0 or page_num >= len(pdf.pages):
                        continue

                    page = pdf.pages[page_num]
                    page_tables = self._extract_tables_from_page(page, page_num)
                    tables.extend(page_tables)

        except Exception as e:
            logger.error("Failed to extract tables from %s: %s", pdf_path, e)

        logger.info(
            "Extracted %d tables from %s",
            len(tables),
            pdf_path.name if isinstance(pdf_path, Path) else pdf_path,
        )
        return TableExtractionResult.from_tables(tables)

    def _extract_tables_from_page(
        self,
        page: Any,  # pdfplumber.Page
        page_num: int,
    ) -> list[ExtractedTable]:
        """Extract tables from a single page."""
        tables: list[ExtractedTable] = []
        page_width = float(page.width)
        page_height = float(page.height)

        # Try strict lattice mode first (bordered tables)
        try:
            lattice_tables = page.find_tables(table_settings=self.TABLE_SETTINGS)
            for table in lattice_tables:
                extracted = self._convert_table(
                    table, page_num, page_width, page_height, method="LATTICE"
                )
                if extracted:
                    tables.append(extracted)
        except Exception as e:
            logger.debug("Lattice table extraction failed on page %d: %s", page_num, e)

        # If no tables found, try stream mode (borderless tables)
        if not tables:
            try:
                stream_tables = page.find_tables(table_settings=self.STREAM_SETTINGS)
                for table in stream_tables:
                    extracted = self._convert_table(
                        table, page_num, page_width, page_height, method="STREAM"
                    )
                    if extracted:
                        tables.append(extracted)
            except Exception as e:
                logger.debug("Stream table extraction failed on page %d: %s", page_num, e)

        # Deduplicate overlapping tables
        return self._deduplicate_tables(tables)

    def _convert_table(
        self,
        table: Any,  # pdfplumber.Table
        page_num: int,
        page_width: float,
        page_height: float,
        method: str,
    ) -> ExtractedTable | None:
        """Convert a pdfplumber table to ExtractedTable schema."""
        try:
            # Get table data
            data = table.extract()
            if not data or len(data) < self.MIN_ROWS:
                return None

            # Count actual columns
            max_cols = max(len(row) for row in data)
            if max_cols < self.MIN_COLS:
                return None

            # Get bounding box
            bbox_raw = table.bbox  # (x0, top, x1, bottom)
            bbox = BBox(
                x0=max(0.0, min(1.0, bbox_raw[0] / page_width)),
                y0=max(0.0, min(1.0, bbox_raw[1] / page_height)),
                x1=max(0.0, min(1.0, bbox_raw[2] / page_width)),
                y1=max(0.0, min(1.0, bbox_raw[3] / page_height)),
            )

            # Extract cells
            cells: list[ExtractedTableCell] = []
            headers: list[str] = []

            for row_idx, row in enumerate(data):
                for col_idx, cell_text in enumerate(row):
                    text = str(cell_text).strip() if cell_text else ""

                    # First row is typically header
                    is_header = row_idx == 0

                    cells.append(
                        ExtractedTableCell(
                            row=row_idx,
                            col=col_idx,
                            text=text,
                            is_header=is_header,
                        )
                    )

                    # Collect headers
                    if is_header and text:
                        headers.append(text)

            # Calculate accuracy based on cell fill rate
            total_cells = len(data) * max_cols
            filled_cells = sum(1 for c in cells if c.text)
            accuracy = filled_cells / total_cells if total_cells > 0 else 0.0

            return ExtractedTable(
                table_id=str(uuid.uuid4()),
                page=page_num,
                bbox=bbox,
                rows=len(data),
                cols=max_cols,
                cells=cells,
                headers=headers,
                accuracy=accuracy,
                method=method,  # type: ignore
            )

        except Exception as e:
            logger.debug("Failed to convert table: %s", e)
            return None

    def _deduplicate_tables(
        self,
        tables: list[ExtractedTable],
        overlap_threshold: float = 0.7,
    ) -> list[ExtractedTable]:
        """Remove duplicate/overlapping tables, keeping higher accuracy ones."""
        if len(tables) <= 1:
            return tables

        # Sort by accuracy descending
        sorted_tables = sorted(tables, key=lambda t: t.accuracy, reverse=True)
        result: list[ExtractedTable] = []

        for table in sorted_tables:
            # Check if this table overlaps significantly with any already kept
            overlaps = False
            for kept in result:
                if kept.page != table.page:
                    continue
                overlap = self._calculate_overlap(table.bbox, kept.bbox)
                if overlap > overlap_threshold:
                    overlaps = True
                    break

            if not overlaps:
                result.append(table)

        return result

    @staticmethod
    def _calculate_overlap(box1: BBox, box2: BBox) -> float:
        """Calculate IoU (Intersection over Union) between two bounding boxes."""
        # Calculate intersection
        x_left = max(box1.x0, box2.x0)
        y_top = max(box1.y0, box2.y0)
        x_right = min(box1.x1, box2.x1)
        y_bottom = min(box1.y1, box2.y1)

        if x_right < x_left or y_bottom < y_top:
            return 0.0

        intersection = (x_right - x_left) * (y_bottom - y_top)

        # Calculate union
        area1 = (box1.x1 - box1.x0) * (box1.y1 - box1.y0)
        area2 = (box2.x1 - box2.x0) * (box2.y1 - box2.y0)
        union = area1 + area2 - intersection

        return intersection / union if union > 0 else 0.0

    def get_table_as_text(self, table: ExtractedTable) -> str:
        """Convert an extracted table to a text representation."""
        rows = self.get_table_rows(table)
        if not rows:
            return ""

        lines = [" | ".join(row).rstrip() for row in rows]
        return "\n".join(lines).strip()

    def get_table_rows(self, table: ExtractedTable) -> list[list[str]]:
        """Return table cells as a dense row/column matrix."""
        if not table.cells or table.rows <= 0 or table.cols <= 0:
            return []

        rows = [["" for _ in range(table.cols)] for _ in range(table.rows)]
        for cell in table.cells:
            if 0 <= cell.row < table.rows and 0 <= cell.col < table.cols:
                rows[cell.row][cell.col] = cell.text

        return rows

    def table_to_snippets(
        self,
        table: ExtractedTable,
        max_rows: int = 15,
    ) -> list[str]:
        """Convert a table into text snippets suitable for retrieval/LLM prompts."""
        rows = self.get_table_rows(table)
        if not rows:
            return []

        snippet_rows = rows[:max_rows]
        lines = [" | ".join(row).rstrip() for row in snippet_rows]
        text = "\n".join(line for line in lines if line.strip()).strip()
        if not text:
            return []

        return [text]

    def search_table_for_value(
        self,
        table: ExtractedTable,
        query: str,
        fuzzy: bool = True,
    ) -> list[tuple[ExtractedTableCell, float]]:
        """
        Search a table for cells matching a query.

        Args:
            table: The table to search
            query: Search query
            fuzzy: Whether to use fuzzy matching

        Returns:
            List of (cell, score) tuples sorted by relevance
        """
        query_lower = query.lower()
        results: list[tuple[ExtractedTableCell, float]] = []

        for cell in table.cells:
            if not cell.text:
                continue

            cell_lower = cell.text.lower()

            # Exact match
            if query_lower == cell_lower:
                results.append((cell, 1.0))
            # Substring match
            elif query_lower in cell_lower:
                score = len(query_lower) / len(cell_lower)
                results.append((cell, score))
            # Fuzzy match (if enabled)
            elif fuzzy:
                try:
                    from rapidfuzz import fuzz

                    ratio = fuzz.ratio(query_lower, cell_lower) / 100.0
                    if ratio > 0.6:
                        results.append((cell, ratio))
                except ImportError:
                    pass

        # Sort by score descending
        return sorted(results, key=lambda x: x[1], reverse=True)

    def get_key_value_pairs(
        self,
        table: ExtractedTable,
    ) -> list[tuple[str, str, float]]:
        """
        Extract key-value pairs from a 2-column table.

        Returns:
            List of (key, value, confidence) tuples
        """
        if table.cols < 2:
            return []

        pairs: list[tuple[str, str, float]] = []

        for cell in table.cells:
            # Skip headers and non-first-column cells
            if cell.is_header or cell.col != 0:
                continue

            key = cell.text.strip()
            if not key:
                continue

            # Find corresponding value cell
            value = ""
            for other in table.cells:
                if other.row == cell.row and other.col == 1:
                    value = other.text.strip()
                    break

            if value:
                # Confidence based on cell text quality
                confidence = 0.9 if len(key) > 3 and len(value) > 0 else 0.7
                pairs.append((key, value, confidence))

        return pairs
