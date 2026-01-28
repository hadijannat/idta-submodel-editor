"""
Audit Report Generator for Magic Import extractions.

Generates auditable reports showing AI extraction provenance:
- Field values with source quotes
- Page and bounding box locations
- Confidence breakdown (LLM/Localizer/OCR/Rules)
- Review status (approved/edited/needs_review)
- Processing metadata
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from enum import Enum
from io import BytesIO
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from app.config import get_settings
from app.schemas.magic_import import (
    ConfidenceBreakdown,
    EvidenceRef,
    ExtractionStatus,
    FieldExtraction,
    MagicImportJob,
    MagicImportResult,
)

logger = logging.getLogger(__name__)


class ReviewStatus(str, Enum):
    """User review status for audit reporting."""

    APPROVED = "approved"
    EDITED = "edited"
    NEEDS_REVIEW = "needs_review"
    NOT_REVIEWED = "not_reviewed"


class AuditFieldEntry(BaseModel):
    """Audit entry for a single extracted field."""

    path: str = Field(description="idShortPath of the field")
    value: str | None = Field(description="Extracted/final value")
    value_type: str | None = Field(default=None, description="Expected value type (XSD)")

    # Extraction status
    extraction_status: ExtractionStatus = Field(description="Status of extraction")
    review_status: ReviewStatus = Field(description="User review status")

    # Confidence
    confidence: float = Field(ge=0.0, le=1.0, description="Overall confidence score")
    confidence_breakdown: ConfidenceBreakdown | None = Field(
        default=None, description="Component confidence scores"
    )
    confidence_reasons: list[str] = Field(
        default_factory=list, description="Human-readable confidence explanations"
    )

    # Evidence
    has_evidence: bool = Field(description="Whether evidence was found")
    evidence_page: int | None = Field(default=None, description="0-indexed page number")
    evidence_quote: str | None = Field(default=None, description="Source quote from PDF")
    evidence_method: Literal["TEXT", "OCR"] | None = Field(
        default=None, description="Extraction method"
    )
    evidence_char_start: int | None = Field(
        default=None, description="Character offset start in page"
    )
    evidence_char_end: int | None = Field(
        default=None, description="Character offset end in page"
    )


class AuditReportSummary(BaseModel):
    """Summary statistics for audit report."""

    total_fields: int = Field(description="Total fields in template")
    fields_filled: int = Field(description="Fields with extracted values")
    fields_empty: int = Field(description="Fields without values")
    fields_needs_review: int = Field(description="Fields requiring review")
    fields_approved: int = Field(description="Fields approved by user")
    fields_edited: int = Field(description="Fields edited by user")
    average_confidence: float = Field(ge=0.0, le=1.0, description="Average confidence")
    evidence_coverage: float = Field(
        ge=0.0, le=1.0, description="Ratio of fields with evidence"
    )


class AuditReportMetadata(BaseModel):
    """Metadata for audit report."""

    job_id: str = Field(description="Magic Import job ID")
    generated_at: datetime = Field(description="Report generation timestamp")

    # Source document
    pdf_filename: str = Field(description="Original PDF filename")
    pdf_size_bytes: int = Field(description="PDF file size in bytes")

    # Template
    template_name: str = Field(description="Template used for extraction")
    template_status: Literal["published", "deprecated"] = Field(
        description="Template publication status"
    )
    template_version: str | None = Field(default=None, description="Template version")

    # Processing
    llm_provider: str = Field(description="LLM provider used")
    llm_model: str = Field(description="LLM model used")
    processing_time_seconds: float = Field(description="Total processing time")
    llm_tokens_used: int | None = Field(default=None, description="Tokens consumed")

    # Extraction job timestamps
    extraction_started_at: datetime = Field(description="When extraction started")
    extraction_completed_at: datetime = Field(description="When extraction completed")


class AuditReport(BaseModel):
    """Complete audit report for Magic Import extraction."""

    report_version: str = Field(default="1.0.0", description="Report format version")
    metadata: AuditReportMetadata = Field(description="Report metadata")
    summary: AuditReportSummary = Field(description="Summary statistics")
    fields: list[AuditFieldEntry] = Field(description="Per-field audit entries")


class AuditReportGenerator:
    """Generates audit reports for Magic Import extractions."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def generate(
        self,
        job: MagicImportJob,
        result: MagicImportResult,
        format: Literal["json", "pdf"] = "json",
    ) -> bytes:
        """
        Generate audit report in the specified format.

        Args:
            job: The Magic Import job
            result: The extraction result
            format: Output format (json or pdf)

        Returns:
            Report content as bytes
        """
        report = self._build_report(job, result)

        if format == "json":
            return self._generate_json(report)
        elif format == "pdf":
            return self._generate_pdf(report, job, result)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _build_report(
        self,
        job: MagicImportJob,
        result: MagicImportResult,
    ) -> AuditReport:
        """Build the audit report data structure."""
        now = datetime.now(timezone.utc)

        # Build field entries
        fields: list[AuditFieldEntry] = []
        for extraction in result.extractions:
            fields.append(self._build_field_entry(extraction))

        # Calculate summary statistics
        fields_filled = sum(1 for e in result.extractions if e.status == ExtractionStatus.FILLED)
        fields_empty = sum(1 for e in result.extractions if e.status == ExtractionStatus.EMPTY)
        fields_needs_review = sum(
            1
            for e in result.extractions
            if e.status in (ExtractionStatus.NEEDS_REVIEW, ExtractionStatus.CONFLICT)
        )
        fields_approved = sum(1 for e in result.extractions if e.user_approved)
        fields_edited = sum(1 for e in result.extractions if e.user_edited)
        fields_with_evidence = sum(1 for e in result.extractions if e.evidence is not None)

        summary = AuditReportSummary(
            total_fields=len(result.extractions),
            fields_filled=fields_filled,
            fields_empty=fields_empty,
            fields_needs_review=fields_needs_review,
            fields_approved=fields_approved,
            fields_edited=fields_edited,
            average_confidence=result.average_confidence,
            evidence_coverage=(
                fields_with_evidence / len(result.extractions)
                if result.extractions
                else 0.0
            ),
        )

        metadata = AuditReportMetadata(
            job_id=job.job_id,
            generated_at=now,
            pdf_filename=job.pdf_filename,
            pdf_size_bytes=job.pdf_size_bytes,
            template_name=job.template_name,
            template_status=job.template_status,
            template_version=job.template_version,
            llm_provider=result.llm_provider,
            llm_model=result.llm_model,
            processing_time_seconds=result.processing_time_seconds,
            llm_tokens_used=result.llm_tokens_used,
            extraction_started_at=job.created_at,
            extraction_completed_at=job.updated_at,
        )

        return AuditReport(
            metadata=metadata,
            summary=summary,
            fields=fields,
        )

    def _build_field_entry(self, extraction: FieldExtraction) -> AuditFieldEntry:
        """Build audit entry for a single field extraction."""
        # Determine review status
        if extraction.user_approved:
            review_status = ReviewStatus.APPROVED
        elif extraction.user_edited:
            review_status = ReviewStatus.EDITED
        elif extraction.needs_review:
            review_status = ReviewStatus.NEEDS_REVIEW
        else:
            review_status = ReviewStatus.NOT_REVIEWED

        # Extract confidence reasons as strings
        confidence_reasons = [
            reason.message for reason in extraction.confidence_reasons
        ]

        # Build entry
        entry = AuditFieldEntry(
            path=extraction.path,
            value=extraction.value_raw,
            value_type=extraction.value_type,
            extraction_status=extraction.status,
            review_status=review_status,
            confidence=extraction.confidence,
            confidence_breakdown=extraction.confidence_breakdown,
            confidence_reasons=confidence_reasons,
            has_evidence=extraction.evidence is not None,
        )

        # Add evidence details if present
        if extraction.evidence:
            entry.evidence_page = extraction.evidence.page
            entry.evidence_quote = extraction.evidence.quote
            entry.evidence_method = extraction.evidence.method
            entry.evidence_char_start = extraction.evidence.char_start
            entry.evidence_char_end = extraction.evidence.char_end

        return entry

    def _generate_json(self, report: AuditReport) -> bytes:
        """Generate JSON format audit report."""
        return report.model_dump_json(indent=2).encode("utf-8")

    def _generate_pdf(
        self,
        report: AuditReport,
        job: MagicImportJob,
        result: MagicImportResult,
    ) -> bytes:
        """Generate PDF format audit report."""
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.lib.units import cm, mm
            from reportlab.platypus import (
                Paragraph,
                SimpleDocTemplate,
                Spacer,
                Table,
                TableStyle,
            )
        except ImportError:
            logger.warning("reportlab not installed, falling back to JSON")
            return self._generate_json(report)

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        styles = getSampleStyleSheet()
        elements = []

        # Title
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=18,
            spaceAfter=6 * mm,
        )
        elements.append(Paragraph("EXTRACTION AUDIT REPORT", title_style))
        elements.append(Spacer(1, 4 * mm))

        # Metadata section
        section_style = ParagraphStyle(
            "SectionHeader",
            parent=styles["Heading2"],
            fontSize=12,
            spaceBefore=4 * mm,
            spaceAfter=2 * mm,
        )
        elements.append(Paragraph("Report Metadata", section_style))

        meta_data = [
            ["Job ID", report.metadata.job_id],
            ["Generated", report.metadata.generated_at.strftime("%Y-%m-%d %H:%M:%S UTC")],
            ["Source PDF", report.metadata.pdf_filename],
            ["PDF Size", f"{report.metadata.pdf_size_bytes:,} bytes"],
            ["Template", f"{report.metadata.template_name} ({report.metadata.template_status})"],
            ["LLM Provider", f"{report.metadata.llm_provider}/{report.metadata.llm_model}"],
            ["Processing Time", f"{report.metadata.processing_time_seconds:.1f}s"],
        ]
        if report.metadata.llm_tokens_used:
            meta_data.append(["Tokens Used", f"{report.metadata.llm_tokens_used:,}"])

        meta_table = Table(meta_data, colWidths=[4 * cm, 10 * cm])
        meta_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("TEXTCOLOR", (0, 0), (0, -1), colors.darkgray),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm),
                ]
            )
        )
        elements.append(meta_table)
        elements.append(Spacer(1, 4 * mm))

        # Summary section
        elements.append(Paragraph("Summary", section_style))

        summary_data = [
            ["Total Fields", str(report.summary.total_fields)],
            ["Fields Filled", str(report.summary.fields_filled)],
            ["Fields Empty", str(report.summary.fields_empty)],
            ["Needs Review", str(report.summary.fields_needs_review)],
            ["Approved", str(report.summary.fields_approved)],
            ["Edited", str(report.summary.fields_edited)],
            ["Avg Confidence", f"{report.summary.average_confidence * 100:.1f}%"],
            ["Evidence Coverage", f"{report.summary.evidence_coverage * 100:.1f}%"],
        ]

        summary_table = Table(summary_data, colWidths=[4 * cm, 10 * cm])
        summary_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("TEXTCOLOR", (0, 0), (0, -1), colors.darkgray),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm),
                ]
            )
        )
        elements.append(summary_table)
        elements.append(Spacer(1, 6 * mm))

        # Field extractions section
        elements.append(Paragraph("Field Extractions", section_style))
        elements.append(Spacer(1, 2 * mm))

        field_style = ParagraphStyle(
            "FieldEntry",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
        )
        quote_style = ParagraphStyle(
            "QuoteStyle",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            textColor=colors.darkgray,
            leftIndent=10,
        )

        for field in report.fields:
            # Field header
            status_color = self._get_status_color(field.extraction_status)
            review_badge = self._get_review_badge(field.review_status)

            field_header = f"<b>{field.path}</b> [{field.extraction_status.value}] {review_badge}"
            elements.append(Paragraph(field_header, field_style))

            # Value
            value_display = field.value if field.value else "<empty>"
            if len(value_display) > 100:
                value_display = value_display[:100] + "..."
            elements.append(Paragraph(f"Value: {value_display}", field_style))

            # Confidence
            conf_text = f"Confidence: {field.confidence * 100:.0f}%"
            if field.confidence_breakdown:
                conf_text += (
                    f" (LLM: {field.confidence_breakdown.llm * 100:.0f}% | "
                    f"Loc: {field.confidence_breakdown.localizer * 100:.0f}% | "
                    f"OCR: {field.confidence_breakdown.ocr * 100:.0f}%)"
                )
            elements.append(Paragraph(conf_text, field_style))

            # Evidence
            if field.has_evidence and field.evidence_quote:
                evidence_text = f"Source: Page {(field.evidence_page or 0) + 1}"
                if field.evidence_char_start is not None:
                    evidence_text += f", chars {field.evidence_char_start}-{field.evidence_char_end}"
                elements.append(Paragraph(evidence_text, field_style))

                quote_display = field.evidence_quote
                if len(quote_display) > 200:
                    quote_display = quote_display[:200] + "..."
                elements.append(Paragraph(f'"{quote_display}"', quote_style))
            else:
                elements.append(Paragraph("No evidence found", field_style))

            elements.append(Spacer(1, 3 * mm))

        # Build PDF
        doc.build(elements)
        return buffer.getvalue()

    def _get_status_color(self, status: ExtractionStatus) -> str:
        """Get color for extraction status."""
        colors_map = {
            ExtractionStatus.FILLED: "#28a745",
            ExtractionStatus.EMPTY: "#6c757d",
            ExtractionStatus.NEEDS_REVIEW: "#ffc107",
            ExtractionStatus.CONFLICT: "#dc3545",
        }
        return colors_map.get(status, "#6c757d")

    def _get_review_badge(self, status: ReviewStatus) -> str:
        """Get badge text for review status."""
        badges = {
            ReviewStatus.APPROVED: "✓ Approved",
            ReviewStatus.EDITED: "✎ Edited",
            ReviewStatus.NEEDS_REVIEW: "⚠ Needs Review",
            ReviewStatus.NOT_REVIEWED: "",
        }
        return badges.get(status, "")
