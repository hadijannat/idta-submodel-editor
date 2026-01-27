"""
Schemas for Magic Import (PDF-to-AAS extraction).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class ConfidenceReasonCode(str, Enum):
    """Codes explaining why confidence may be low."""

    MULTIPLE_CANDIDATES = "multiple_candidates"
    OCR_QUALITY_LOW = "ocr_quality_low"
    UNIT_AMBIGUITY = "unit_ambiguity"
    TYPE_MISMATCH = "type_mismatch"
    NO_EVIDENCE_FOUND = "no_evidence_found"
    LOW_LLM_CONFIDENCE = "low_llm_confidence"
    VALUE_OUTSIDE_EVIDENCE = "value_outside_evidence"
    SEMANTIC_CONSTRAINT_VIOLATION = "semantic_constraint_violation"


class ConfidenceReason(BaseModel):
    """Structured reason explaining a confidence factor."""

    code: ConfidenceReasonCode
    message: str = Field(description="Human-readable explanation")
    severity: Literal["info", "warning", "error"] = "warning"
    detail: dict | None = Field(default=None, description="Additional context data")


class JobStatus(str, Enum):
    """Job processing status."""

    UPLOADED = "uploaded"
    INDEXING = "indexing"
    OCR = "ocr"
    EXTRACTING = "extracting"
    LOCALIZING = "localizing"
    SCORING = "scoring"
    VALIDATING = "validating"
    DONE = "done"
    FAILED = "failed"


class ExtractionStatus(str, Enum):
    """Status of a field extraction."""

    FILLED = "filled"  # Value extracted with evidence
    EMPTY = "empty"  # Not found in document
    NEEDS_REVIEW = "needs_review"  # Low confidence or missing evidence
    CONFLICT = "conflict"  # Multiple conflicting values found


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
    # New fields for reproducibility and precise localization
    snippet_hash: str | None = Field(
        default=None, description="SHA256 hash of underlying text span for reproducibility"
    )
    char_start: int | None = Field(
        default=None, ge=0, description="Character offset start in page text"
    )
    char_end: int | None = Field(
        default=None, ge=0, description="Character offset end in page text"
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
    status: ExtractionStatus = Field(
        default=ExtractionStatus.NEEDS_REVIEW,
        description="Extraction status indicating document grounding",
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Overall confidence score")
    confidence_breakdown: ConfidenceBreakdown | None = None
    confidence_reasons: list[ConfidenceReason] = Field(
        default_factory=list, description="Actionable reasons for confidence score"
    )
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


class DocumentClassification(BaseModel):
    """Classification results for a PDF document."""

    doc_type: Literal["text", "scanned", "mixed"] = Field(
        description="Document type based on text extraction method"
    )
    language: str | None = Field(
        default=None, description="Detected primary language (ISO 639-1)"
    )
    has_tables: bool = Field(
        default=False, description="Whether tables were detected"
    )
    quality_score: float = Field(
        ge=0.0, le=1.0, description="Overall document quality score"
    )
    avg_ocr_confidence: float | None = Field(
        default=None, description="Average OCR confidence for scanned pages"
    )
    text_density: float = Field(
        default=0.0, description="Words per page average"
    )


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
    doc_classification: DocumentClassification | None = Field(
        default=None, description="Document classification results"
    )
    idempotency_key: str | None = Field(
        default=None,
        description="Hash of (pdf_bytes + template_id + extractor_version) for reproducibility",
    )


class ValidationError(BaseModel):
    """A validation error for a specific field."""

    path: str = Field(description="idShortPath of the field with error")
    message: str = Field(description="Human-readable error message")
    code: str = Field(description="Error code for programmatic handling")


class ValidationResult(BaseModel):
    """Result of validating extractions against template schema."""

    is_valid: bool = Field(description="True if no errors (warnings OK)")
    errors: list[ValidationError] = Field(default_factory=list)
    warnings: list[ValidationError] = Field(default_factory=list)


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
    llm_tokens_used: int | None = Field(
        default=None, description="Total tokens used by the LLM for this job"
    )
    llm_prompt_tokens: int | None = Field(
        default=None, description="Prompt tokens used by the LLM (if available)"
    )
    llm_completion_tokens: int | None = Field(
        default=None, description="Completion tokens used by the LLM (if available)"
    )
    llm_called: bool | None = Field(
        default=None, description="Whether the LLM was actually called"
    )
    mismatch_suspected: bool = Field(
        default=False,
        description="Heuristic flag indicating template/document mismatch",
    )
    mismatch_reasons: list[str] = Field(
        default_factory=list,
        description="Heuristic reasons for possible template/document mismatch",
    )
    validation_result: ValidationResult | None = Field(
        default=None, description="Template schema validation result"
    )
    template_version_used: str | None = Field(
        default=None, description="Version of template used for extraction"
    )
    unmapped_findings: list["UnmappedFinding"] = Field(
        default_factory=list,
        description="Values found in document that don't map to template fields",
    )
    quality_metrics: "QualityMetrics | None" = Field(
        default=None, description="Comprehensive quality metrics for extraction"
    )


class MagicImportApplyRequest(BaseModel):
    """Request to apply extractions to form."""

    job_id: str
    extractions: list[FieldExtraction]


class ReExtractRequest(BaseModel):
    """Request to re-extract specific fields."""

    paths: list[str] = Field(description="List of idShortPaths to re-extract")
    hint: str | None = Field(
        default=None, description="Optional hint to guide re-extraction"
    )


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
    user_hint: str | None = Field(
        default=None, description="Optional user-provided hint for re-extraction"
    )


class ExtractionSpec(BaseModel):
    """
    Template-derived extraction specification.

    Defines exactly what can be extracted - prevents inventing fields.
    Generated from template schema, never from document content.
    """

    path: str = Field(description="Stable internal path (idShortPath)")
    id_short: str = Field(description="Element idShort")
    semantic_id: str | None = Field(default=None, description="Semantic ID reference")
    element_type: Literal[
        "Property", "SMC", "SML", "MLP", "Range", "File", "Blob", "Entity"
    ] = Field(description="AAS submodel element type")
    value_type: str | None = Field(default=None, description="XSD value type for Property")
    cardinality: str = Field(
        default="[0..1]",
        description="Cardinality constraint (e.g., '[0..1]', '[1]', '[1..*]')",
    )
    known_labels: list[str] = Field(
        default_factory=list,
        description="Known labels from template and synonyms from semantic dictionary",
    )
    required: bool = Field(default=False, description="Whether this field is required")


class UnmappedFinding(BaseModel):
    """
    A value found in the document that doesn't map to any template field.

    Used to surface potentially important data that wasn't extracted
    because no matching template field exists.
    """

    value: str = Field(description="The extracted value")
    evidence: EvidenceRef = Field(description="Source evidence in PDF")
    suggested_paths: list[str] = Field(
        default_factory=list,
        description="Possible template fields this might belong to",
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence that this is a meaningful value"
    )
    source: Literal["table", "text", "key_value"] = Field(
        default="text", description="Where this finding came from"
    )
    context: str | None = Field(
        default=None, description="Surrounding context from document"
    )


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
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    model: str


class ExtractionCandidate(BaseModel):
    """A candidate extraction from the LLM (Pass A: high-recall generation)."""

    path: str = Field(description="idShortPath of target field")
    value: str = Field(description="Candidate value (or 'NOT_FOUND')")
    evidence_quote: str | None = Field(
        default=None, description="Exact quote from document supporting this value"
    )
    llm_confidence: float = Field(
        ge=0.0, le=1.0, description="LLM's self-reported confidence"
    )
    source: Literal["llm", "regex", "table"] = Field(
        default="llm", description="Source of this candidate"
    )
    reasoning: str | None = Field(
        default=None, description="LLM reasoning for this extraction"
    )


class CandidateSet(BaseModel):
    """Set of candidates for a single field (for verification phase)."""

    path: str = Field(description="idShortPath of target field")
    candidates: list[ExtractionCandidate] = Field(
        default_factory=list, description="Ranked candidates (1-3 per field)"
    )
    selected_index: int | None = Field(
        default=None, description="Index of verified candidate after Pass B"
    )
    verification_notes: str | None = Field(
        default=None, description="Notes from verification phase"
    )


class LLMCandidateResponse(BaseModel):
    """Response from LLM candidate generation (Pass A)."""

    candidate_sets: list[CandidateSet]
    tokens_used: int = 0
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    model: str


# ============================================================================
# Quality Metrics Schemas
# ============================================================================


class EvidenceQuality(str, Enum):
    """Quality classification of evidence supporting an extraction."""

    TABLE_STRUCTURED = "table_structured"  # Value from structured table cell
    TABLE_KEY_VALUE = "table_key_value"  # Value from key-value table row
    TEXT_GROUNDED = "text_grounded"  # Value with exact text match
    TEXT_INFERRED = "text_inferred"  # Value inferred from surrounding text
    OCR_HIGH = "ocr_high"  # OCR extraction with high confidence
    OCR_LOW = "ocr_low"  # OCR extraction with low confidence
    NONE = "none"  # No evidence found


class FieldTypeCategory(str, Enum):
    """Categorization of field types for metrics and analysis."""

    IDENTIFIER = "identifier"  # IDs, codes, serial numbers
    DATE_TIME = "date_time"  # Dates, times, timestamps
    NUMERIC_UNIT = "numeric_unit"  # Numbers with units (e.g., "5.2 kg")
    NUMERIC_PURE = "numeric_pure"  # Pure numbers without units
    ENUM_CHOICE = "enum_choice"  # Enumerated/choice values
    BOOLEAN = "boolean"  # True/false values
    TEXT_SHORT = "text_short"  # Short text (< 100 chars)
    TEXT_LONG = "text_long"  # Long text (>= 100 chars)
    CONTACT = "contact"  # Email, phone, address
    REFERENCE = "reference"  # References to other entities


class FieldMetrics(BaseModel):
    """Detailed metrics for a single extracted field."""

    path: str = Field(description="idShortPath of the field")
    field_type_category: FieldTypeCategory = Field(
        description="Category of the field type"
    )
    is_required: bool = Field(description="Whether the field is required by template")
    confidence: float = Field(ge=0.0, le=1.0, description="Extraction confidence score")
    evidence_ratio: float = Field(
        ge=0.0, le=1.0, description="Ratio of value supported by evidence"
    )
    evidence_quality: EvidenceQuality = Field(
        description="Quality classification of the evidence"
    )
    source_table: bool = Field(
        default=False, description="Whether value came from table extraction"
    )
    source_text: bool = Field(
        default=False, description="Whether value came from text extraction"
    )
    source_ocr: bool = Field(
        default=False, description="Whether value came from OCR extraction"
    )
    grounding_verified: bool = Field(
        default=False, description="Whether evidence quote was verified in document"
    )
    llm_provider: str | None = Field(
        default=None, description="LLM provider used for extraction"
    )
    llm_model: str | None = Field(
        default=None, description="LLM model used for extraction"
    )


class TemplateMismatchMetrics(BaseModel):
    """Metrics indicating potential template/document mismatch."""

    keyword_match_ratio: float = Field(
        ge=0.0, le=1.0, description="Ratio of template keywords found in document"
    )
    extraction_yield: float = Field(
        ge=0.0, le=1.0, description="Ratio of fields with extracted values"
    )
    evidence_localization_rate: float = Field(
        ge=0.0, le=1.0, description="Ratio of extractions with localized evidence"
    )
    mismatch_score: float = Field(
        ge=0.0, le=1.0, description="Overall mismatch score (0=match, 1=mismatch)"
    )
    mismatch_indicators: list[str] = Field(
        default_factory=list, description="Specific indicators of mismatch"
    )
    recommended_action: Literal["proceed", "warn", "abort"] = Field(
        description="Recommended action based on mismatch analysis"
    )


class AutoApplyThresholds(BaseModel):
    """Thresholds for automatic application of extractions."""

    min_confidence: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
        description="Minimum confidence for auto-apply eligibility",
    )
    min_evidence_ratio: float = Field(
        default=0.9,
        ge=0.0,
        le=1.0,
        description="Minimum evidence ratio for auto-apply eligibility",
    )
    require_grounding: bool = Field(
        default=True, description="Whether verified grounding is required"
    )
    allowed_evidence_qualities: list[EvidenceQuality] = Field(
        default_factory=lambda: [
            EvidenceQuality.TABLE_STRUCTURED,
            EvidenceQuality.TABLE_KEY_VALUE,
            EvidenceQuality.TEXT_GROUNDED,
            EvidenceQuality.OCR_HIGH,
        ],
        description="Evidence quality levels allowed for auto-apply",
    )
    blocked_field_types: list[FieldTypeCategory] = Field(
        default_factory=list,
        description="Field types blocked from auto-apply (require manual review)",
    )


class QualityMetrics(BaseModel):
    """Comprehensive quality metrics for a Magic Import extraction job."""

    job_id: str = Field(description="ID of the Magic Import job")
    template_name: str = Field(description="Name of the template used")
    computed_at: datetime = Field(description="When metrics were computed")

    # Overall confidence metrics
    overall_confidence: float = Field(
        ge=0.0, le=1.0, description="Simple average confidence across all extractions"
    )
    weighted_confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Weighted confidence (required fields weighted higher)",
    )

    # Evidence metrics
    evidence_ratio: float = Field(
        ge=0.0, le=1.0, description="Ratio of extractions with any evidence"
    )
    table_evidence_ratio: float = Field(
        ge=0.0, le=1.0, description="Ratio of extractions from table sources"
    )
    text_evidence_ratio: float = Field(
        ge=0.0, le=1.0, description="Ratio of extractions from text sources"
    )
    high_confidence_no_evidence_count: int = Field(
        ge=0, description="Count of high-confidence extractions lacking evidence"
    )
    grounding_rate: float = Field(
        ge=0.0, le=1.0, description="Ratio of extractions with verified grounding"
    )

    # Field coverage metrics
    required_field_total: int = Field(ge=0, description="Total required fields")
    required_field_extracted: int = Field(
        ge=0, description="Required fields with values"
    )
    required_field_coverage: float = Field(
        ge=0.0, le=1.0, description="Ratio of required fields extracted"
    )
    optional_field_coverage: float = Field(
        ge=0.0, le=1.0, description="Ratio of optional fields extracted"
    )

    # Per-field metrics
    field_metrics: list[FieldMetrics] = Field(
        default_factory=list, description="Detailed metrics for each field"
    )

    # Error analysis
    error_rates_by_type: dict[str, float] = Field(
        default_factory=dict,
        description="Error rates grouped by field type category",
    )

    # Mismatch detection
    mismatch_metrics: TemplateMismatchMetrics | None = Field(
        default=None, description="Template/document mismatch metrics"
    )

    # LLM usage
    llm_provider: str = Field(description="LLM provider used for extraction")
    llm_model: str = Field(description="LLM model used for extraction")
    llm_tokens_used: int | None = Field(
        default=None, description="Total tokens consumed by LLM"
    )

    # Auto-apply metrics
    auto_apply_eligible_count: int = Field(
        ge=0, default=0, description="Number of fields eligible for auto-apply"
    )
    auto_apply_thresholds_used: AutoApplyThresholds | None = Field(
        default=None, description="Thresholds used for auto-apply eligibility"
    )

    # Experiment tracking
    experiment_id: str | None = Field(
        default=None, description="A/B experiment identifier"
    )
    experiment_variant: str | None = Field(
        default=None, description="A/B experiment variant (control/treatment)"
    )


class ExtractionOutcome(BaseModel):
    """Tracks user corrections to extracted values for quality feedback loop."""

    job_id: str = Field(description="ID of the Magic Import job")
    template_name: str | None = Field(
        default=None, description="Template name used for the job"
    )
    template_status: Literal["published", "deprecated"] | None = Field(
        default=None, description="Template status used for the job"
    )
    template_version: str | None = Field(
        default=None, description="Template version used for the job"
    )
    recorded_at: datetime = Field(description="When the outcome was recorded")
    field_path: str = Field(description="idShortPath of the field")

    # Value tracking
    original_value: str | None = Field(
        description="Original extracted value (None if empty)"
    )
    final_value: str | None = Field(
        description="Final value after user action (None if deleted)"
    )
    original_confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence of original extraction"
    )

    # User action
    action: Literal["accepted", "edited", "deleted", "rejected"] = Field(
        description="Action taken by user on extraction"
    )
    edit_distance: int = Field(
        default=0, ge=0, description="Levenshtein distance between original and final"
    )

    # Evidence context
    had_evidence: bool = Field(
        description="Whether original extraction had evidence"
    )
    evidence_quality: EvidenceQuality = Field(
        description="Quality of evidence for original extraction"
    )

    # Field context
    field_type: FieldTypeCategory = Field(description="Category of the field type")
    was_required: bool = Field(description="Whether the field was required")


# Rebuild models with forward references
MagicImportResult.model_rebuild()
