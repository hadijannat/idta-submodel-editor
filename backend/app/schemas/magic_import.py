"""
Schemas for Magic Import (PDF-to-AAS extraction).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Job processing status."""

    UPLOADED = "uploaded"
    INDEXING = "indexing"
    OCR = "ocr"
    EXTRACTING = "extracting"
    LOCALIZING = "localizing"
    SCORING = "scoring"
    DONE = "done"
    FAILED = "failed"


class BBox(BaseModel):
    """Bounding box with normalized coordinates (0..1)."""

    x0: float = Field(ge=0.0, le=1.0, description="Left edge (normalized)")
    y0: float = Field(ge=0.0, le=1.0, description="Top edge (normalized)")
    x1: float = Field(ge=0.0, le=1.0, description="Right edge (normalized)")
    y1: float = Field(ge=0.0, le=1.0, description="Bottom edge (normalized)")

    def to_absolute(self, width: float, height: float) -> tuple[float, float, float, float]:
        """Convert to absolute coordinates."""
        return (
            self.x0 * width,
            self.y0 * height,
            self.x1 * width,
            self.y1 * height,
        )


class EvidenceRef(BaseModel):
    """Reference to source evidence in the PDF."""

    page: int = Field(ge=0, description="0-indexed page number")
    quote: str = Field(description="Exact text quoted from PDF")
    boxes: list[BBox] = Field(default_factory=list, description="Bounding boxes for highlighting")
    method: Literal["TEXT", "OCR"] = Field(default="TEXT", description="Extraction method")
    locator_score: float = Field(
        ge=0.0, le=1.0, default=1.0, description="Quality of quote-to-bbox match"
    )


class ConfidenceBreakdown(BaseModel):
    """Breakdown of confidence score components."""

    llm: float = Field(ge=0.0, le=1.0, description="LLM self-confidence")
    localizer: float = Field(ge=0.0, le=1.0, description="Evidence match quality")
    ocr: float = Field(ge=0.0, le=1.0, default=1.0, description="Text extraction quality")
    rules: float = Field(ge=0.0, le=1.0, default=1.0, description="Format/type validation")


class FieldExtraction(BaseModel):
    """Extracted field value with evidence and confidence."""

    path: str = Field(description="idShortPath to target field")
    value_type: str | None = Field(
        default=None, description="Expected value type (XSD) when known"
    )
    value_raw: str = Field(description="Raw extracted value")
    value_normalized: str | int | float | bool | None = Field(
        default=None, description="Normalized/parsed value"
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Overall confidence score")
    confidence_breakdown: ConfidenceBreakdown | None = None
    evidence: EvidenceRef | None = None
    needs_review: bool = Field(default=False, description="True if confidence < threshold")
    user_edited: bool = Field(default=False, description="True if user modified this value")
    user_approved: bool = Field(default=False, description="True if user approved this value")


class PDFPageInfo(BaseModel):
    """Information about a PDF page."""

    page_number: int = Field(ge=0, description="0-indexed page number")
    width: float = Field(description="Page width in points")
    height: float = Field(description="Page height in points")
    has_text: bool = Field(description="Whether native text was extracted")
    needs_ocr: bool = Field(description="Whether OCR is needed for this page")
    word_count: int = Field(default=0, description="Number of words extracted")


class PDFIndexInfo(BaseModel):
    """Summary of PDF indexing results."""

    total_pages: int
    pages_with_text: int
    pages_needing_ocr: int
    total_words: int
    language_detected: str | None = None


class MagicImportJobCreate(BaseModel):
    """Request to create a new Magic Import job."""

    template_name: str
    template_status: Literal["published", "deprecated"] = "published"
    template_version: str | None = None


class MagicImportJob(BaseModel):
    """Magic Import job status and results."""

    job_id: str
    status: JobStatus
    template_name: str
    template_status: Literal["published", "deprecated"] = "published"
    template_version: str | None = None
    pdf_filename: str
    pdf_size_bytes: int
    created_at: datetime
    updated_at: datetime
    progress: float = Field(ge=0.0, le=1.0, default=0.0, description="Processing progress")
    progress_message: str | None = None
    error_message: str | None = None
    pdf_info: PDFIndexInfo | None = None


class MagicImportResult(BaseModel):
    """Complete extraction results for a Magic Import job."""

    job_id: str
    template_name: str
    extractions: list[FieldExtraction]
    fields_extracted: int
    fields_needing_review: int
    average_confidence: float
    llm_provider: str
    llm_model: str
    processing_time_seconds: float


class MagicImportApplyRequest(BaseModel):
    """Request to apply extractions to form."""

    job_id: str
    extractions: list[FieldExtraction]


class ExtractionHint(BaseModel):
    """Hints for extracting a specific field."""

    path: str = Field(description="idShortPath")
    label: str = Field(description="Human-readable label")
    element_type: str = Field(description="AAS element type")
    value_type: str | None = None
    semantic_id: str | None = None
    semantic_label: str | None = None
    keywords: list[str] = Field(default_factory=list, description="Search keywords")
    required: bool = False


class PDFWord(BaseModel):
    """A word extracted from PDF with position."""

    text: str
    page: int
    bbox: BBox
    confidence: float = 1.0
    method: Literal["TEXT", "OCR"] = "TEXT"


class PDFIndex(BaseModel):
    """Full index of a PDF document."""

    job_id: str
    pdf_path: str
    info: PDFIndexInfo
    pages: list[PDFPageInfo]
    words: list[PDFWord]


class Snippet(BaseModel):
    """A text snippet retrieved from the PDF."""

    text: str
    page: int
    start_word_idx: int
    end_word_idx: int
    score: float = Field(description="Relevance score")
    context_before: str = ""
    context_after: str = ""


class LLMExtractionRequest(BaseModel):
    """Request for LLM extraction."""

    hints: list[ExtractionHint]
    snippets: list[Snippet]
    max_tokens: int = 4096


class LLMFieldExtraction(BaseModel):
    """Single field extraction from LLM."""

    path: str
    value: str
    evidence_quote: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str | None = None


class LLMExtractionResponse(BaseModel):
    """Response from LLM extraction."""

    extractions: list[LLMFieldExtraction]
    tokens_used: int = 0
    model: str
