"""
Audit Report Generator for Magic Import extractions.

Generates auditable reports showing AI extraction provenance:
- Field values with source quotes
- Page and bounding box locations
- Confidence breakdown (LLM/Localizer/OCR/Rules)
- Review status (approved/edited/needs_review)
- Processing metadata
- Compliance summary for auditors
- Visual confidence breakdown charts
- Evidence appendix with cropped PDF regions
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timezone
from enum import Enum
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

from app.config import get_settings
from app.schemas.magic_import import (
    ConfidenceBreakdown,
    ExtractionStatus,
    FieldExtraction,
    MagicImportJob,
    MagicImportResult,
)
from app.services.magic_import.pymupdf_guard import assert_pymupdf_allowed

if TYPE_CHECKING:
    pass

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


class ComplianceSummary(BaseModel):
    """Compliance metrics for auditors - summarizes extraction quality."""

    # Overall quality score (0-100)
    quality_score: float = Field(
        ge=0.0, le=100.0, description="Overall extraction quality score (0-100)"
    )
    quality_grade: Literal["A", "B", "C", "D", "F"] = Field(
        description="Letter grade for extraction quality"
    )

    # Compliance rates
    required_fields_compliance: float = Field(
        ge=0.0,
        le=1.0,
        description="Ratio of required fields successfully extracted (or fill rate if required info unavailable)",
    )
    confidence_threshold_compliance: float = Field(
        ge=0.0, le=1.0, description="Ratio of fields meeting minimum confidence threshold"
    )
    human_verification_rate: float = Field(
        ge=0.0, le=1.0, description="Ratio of fields verified by human (approved/edited)"
    )

    # Risk indicators
    high_confidence_fields: int = Field(
        description="Fields with confidence >= 0.85"
    )
    medium_confidence_fields: int = Field(
        description="Fields with confidence 0.60-0.84"
    )
    low_confidence_fields: int = Field(
        description="Fields with confidence < 0.60"
    )

    # Audit flags
    flags: list[str] = Field(
        default_factory=list, description="Audit flags/warnings for reviewers"
    )


class EvidenceAppendixEntry(BaseModel):
    """Entry in evidence appendix showing cropped PDF region."""

    field_path: str = Field(description="Field this evidence supports")
    page_number: int = Field(description="1-indexed page number")
    quote: str = Field(description="Text extracted from region")
    confidence: float = Field(ge=0.0, le=1.0, description="Extraction confidence")
    # Image data encoded as base64 (for JSON) or raw bytes (for PDF)
    image_base64: str | None = Field(
        default=None, description="Base64-encoded cropped region image (PNG)"
    )
    bbox: dict | None = Field(
        default=None,
        description="Bounding box in PDF points (72 points/inch) with padding applied",
    )
    bbox_units: Literal["points"] = Field(
        default="points",
        description="Units for bbox coordinates (always 'points' = 72 per inch)",
    )
    padding_applied: int = Field(
        default=10,
        description="Padding in points added around the original evidence region",
    )


class ConfidenceDistribution(BaseModel):
    """Confidence score distribution for charting."""

    bucket_0_20: int = Field(default=0, description="Fields with 0-20% confidence")
    bucket_20_40: int = Field(default=0, description="Fields with 20-40% confidence")
    bucket_40_60: int = Field(default=0, description="Fields with 40-60% confidence")
    bucket_60_80: int = Field(default=0, description="Fields with 60-80% confidence")
    bucket_80_100: int = Field(default=0, description="Fields with 80-100% confidence")


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

    report_version: str = Field(default="2.0.0", description="Report format version")
    metadata: AuditReportMetadata = Field(description="Report metadata")
    summary: AuditReportSummary = Field(description="Summary statistics")
    compliance: ComplianceSummary = Field(description="Compliance summary for auditors")
    confidence_distribution: ConfidenceDistribution = Field(
        description="Confidence score distribution"
    )
    fields: list[AuditFieldEntry] = Field(description="Per-field audit entries")
    evidence_appendix: list[EvidenceAppendixEntry] = Field(
        default_factory=list, description="Evidence appendix with PDF region crops"
    )


class AuditReportGenerator:
    """Generates audit reports for Magic Import extractions."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def generate(
        self,
        job: MagicImportJob,
        result: MagicImportResult,
        format: Literal["json", "pdf"] = "json",
        *,
        pdf_path: Path | None = None,
        include_evidence_appendix: bool = True,
        confidence_threshold: float = 0.6,
        required_paths: set[str] | None = None,
        include_evidence_images: bool | None = None,
    ) -> bytes:
        """
        Generate audit report in the specified format.

        Args:
            job: The Magic Import job
            result: The extraction result
            format: Output format (json or pdf)
            pdf_path: Optional path to source PDF for evidence region extraction
            include_evidence_appendix: Whether to include cropped evidence regions
            confidence_threshold: Minimum confidence for compliance calculation
            required_paths: Set of field paths that are required (for accurate compliance)
            include_evidence_images: Whether to embed base64 images in evidence appendix.
                                    None (default) = auto: images for PDF, no images for JSON

        Returns:
            Report content as bytes
        """
        report = self._build_report(
            job,
            result,
            format=format,
            pdf_path=pdf_path,
            include_evidence_appendix=include_evidence_appendix,
            confidence_threshold=confidence_threshold,
            required_paths=required_paths,
            include_evidence_images=include_evidence_images,
        )

        if format == "json":
            return self._generate_json(report)
        elif format == "pdf":
            return self._generate_pdf(report, job, result, pdf_path=pdf_path)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _build_report(
        self,
        job: MagicImportJob,
        result: MagicImportResult,
        *,
        format: Literal["json", "pdf"] = "json",
        pdf_path: Path | None = None,
        include_evidence_appendix: bool = True,
        confidence_threshold: float = 0.6,
        required_paths: set[str] | None = None,
        include_evidence_images: bool | None = None,
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

        # Build compliance summary
        compliance = self._build_compliance_summary(
            result.extractions,
            confidence_threshold=confidence_threshold,
            required_paths=required_paths,
        )

        # Build confidence distribution
        confidence_dist = self._build_confidence_distribution(result.extractions)

        # Build evidence appendix (if PDF available)
        evidence_appendix: list[EvidenceAppendixEntry] = []
        if include_evidence_appendix and pdf_path and pdf_path.exists():
            # For JSON, default to no images; for PDF, include images
            embed_images = (
                include_evidence_images
                if include_evidence_images is not None
                else (format == "pdf")
            )
            evidence_appendix = self._build_evidence_appendix(
                result.extractions, pdf_path, include_images=embed_images
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
            compliance=compliance,
            confidence_distribution=confidence_dist,
            fields=fields,
            evidence_appendix=evidence_appendix,
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

    def _build_compliance_summary(
        self,
        extractions: list[FieldExtraction],
        confidence_threshold: float = 0.6,
        required_paths: set[str] | None = None,
    ) -> ComplianceSummary:
        """Build compliance summary metrics for auditors."""
        if not extractions:
            return ComplianceSummary(
                quality_score=0.0,
                quality_grade="F",
                required_fields_compliance=0.0,
                confidence_threshold_compliance=0.0,
                human_verification_rate=0.0,
                high_confidence_fields=0,
                medium_confidence_fields=0,
                low_confidence_fields=0,
                flags=["No extractions available"],
            )

        total = len(extractions)

        # Count confidence tiers
        high_conf = sum(1 for e in extractions if e.confidence >= 0.85)
        medium_conf = sum(1 for e in extractions if 0.60 <= e.confidence < 0.85)
        low_conf = sum(1 for e in extractions if e.confidence < 0.60)

        # Required fields compliance
        # If required_paths provided, use accurate calculation; otherwise report fill rate
        if required_paths:
            required_extractions = [e for e in extractions if e.path in required_paths]
            filled_required = sum(
                1 for e in required_extractions if e.status == ExtractionStatus.FILLED
            )
            required_compliance = (
                filled_required / len(required_extractions) if required_extractions else 1.0
            )
        else:
            # Fallback: report as "fill rate" if no required info available
            filled_count = sum(1 for e in extractions if e.status == ExtractionStatus.FILLED)
            required_compliance = filled_count / total

        # Confidence threshold compliance
        above_threshold = sum(1 for e in extractions if e.confidence >= confidence_threshold)
        threshold_compliance = above_threshold / total

        # Human verification rate
        verified = sum(1 for e in extractions if e.user_approved or e.user_edited)
        verification_rate = verified / total

        # Calculate quality score (weighted average)
        # 40% confidence, 30% evidence coverage, 20% threshold compliance, 10% verification
        avg_confidence = sum(e.confidence for e in extractions) / total
        evidence_coverage = sum(1 for e in extractions if e.evidence is not None) / total

        quality_score = (
            avg_confidence * 40 +
            evidence_coverage * 30 +
            threshold_compliance * 20 +
            verification_rate * 10
        )

        # Determine grade
        if quality_score >= 90:
            grade = "A"
        elif quality_score >= 80:
            grade = "B"
        elif quality_score >= 70:
            grade = "C"
        elif quality_score >= 60:
            grade = "D"
        else:
            grade = "F"

        # Generate audit flags
        flags: list[str] = []
        if low_conf > total * 0.2:
            flags.append(f"HIGH_LOW_CONFIDENCE: {low_conf}/{total} fields have <60% confidence")
        if verification_rate < 0.5:
            flags.append(f"LOW_VERIFICATION: Only {verification_rate*100:.0f}% of fields human-verified")
        if evidence_coverage < 0.7:
            flags.append(f"LOW_EVIDENCE: Only {evidence_coverage*100:.0f}% of fields have supporting evidence")
        # Only emit MISSING_REQUIRED flag if we have actual required paths info
        if required_paths and required_compliance < 0.9:
            flags.append(f"MISSING_REQUIRED: {(1-required_compliance)*100:.0f}% of required fields unfilled")

        needs_review = sum(
            1 for e in extractions
            if e.status in (ExtractionStatus.NEEDS_REVIEW, ExtractionStatus.CONFLICT)
        )
        if needs_review > 0:
            flags.append(f"PENDING_REVIEW: {needs_review} fields require human review")

        return ComplianceSummary(
            quality_score=round(quality_score, 1),
            quality_grade=grade,
            required_fields_compliance=round(required_compliance, 3),
            confidence_threshold_compliance=round(threshold_compliance, 3),
            human_verification_rate=round(verification_rate, 3),
            high_confidence_fields=high_conf,
            medium_confidence_fields=medium_conf,
            low_confidence_fields=low_conf,
            flags=flags,
        )

    def _build_confidence_distribution(
        self,
        extractions: list[FieldExtraction],
    ) -> ConfidenceDistribution:
        """Build confidence distribution for charting."""
        buckets = {
            "bucket_0_20": 0,
            "bucket_20_40": 0,
            "bucket_40_60": 0,
            "bucket_60_80": 0,
            "bucket_80_100": 0,
        }

        for e in extractions:
            conf = e.confidence
            if conf < 0.2:
                buckets["bucket_0_20"] += 1
            elif conf < 0.4:
                buckets["bucket_20_40"] += 1
            elif conf < 0.6:
                buckets["bucket_40_60"] += 1
            elif conf < 0.8:
                buckets["bucket_60_80"] += 1
            else:
                buckets["bucket_80_100"] += 1

        return ConfidenceDistribution(**buckets)

    def _build_evidence_appendix(
        self,
        extractions: list[FieldExtraction],
        pdf_path: Path,
        max_entries: int = 50,
        include_images: bool = True,
    ) -> list[EvidenceAppendixEntry]:
        """
        Build evidence appendix with cropped PDF regions.

        Uses PyMuPDF (fitz) to extract image regions from the source PDF
        corresponding to evidence bounding boxes.

        Args:
            extractions: List of field extractions
            pdf_path: Path to source PDF
            max_entries: Maximum number of entries to include
            include_images: Whether to embed base64 images (can be disabled for smaller JSON)
        """
        import base64

        padding = 10  # points (PDF uses 72 points per inch)

        assert_pymupdf_allowed()

        try:
            import fitz
        except ImportError:
            logger.warning("PyMuPDF not available, skipping evidence appendix images")
            # Still include entries without images
            entries = []
            for ext in extractions:
                if ext.evidence and ext.evidence.boxes:
                    entries.append(EvidenceAppendixEntry(
                        field_path=ext.path,
                        page_number=(ext.evidence.page or 0) + 1,
                        quote=ext.evidence.quote or "",
                        confidence=ext.confidence,
                        image_base64=None,
                        bbox=None,
                        padding_applied=padding,
                    ))
                    if len(entries) >= max_entries:
                        break
            return entries

        entries: list[EvidenceAppendixEntry] = []

        try:
            doc = fitz.open(str(pdf_path))
        except Exception as e:
            logger.warning(f"Could not open PDF for evidence appendix: {e}")
            return entries

        try:
            # Sort by confidence (highest first) and limit entries
            sorted_extractions = sorted(
                [e for e in extractions if e.evidence and e.evidence.boxes],
                key=lambda x: x.confidence,
                reverse=True,
            )[:max_entries]

            for ext in sorted_extractions:
                if not ext.evidence or not ext.evidence.boxes:
                    continue

                evidence = ext.evidence
                page_num = evidence.page or 0

                if page_num >= len(doc):
                    continue

                page = doc[page_num]
                page_rect = page.rect

                # Combine all bounding boxes into a single region
                boxes = evidence.boxes
                if not boxes:
                    continue

                # Convert normalized coordinates to page coordinates (in points)
                # Add padding around the region
                x0 = min(b.x0 for b in boxes) * page_rect.width - padding
                y0 = min(b.y0 for b in boxes) * page_rect.height - padding
                x1 = max(b.x1 for b in boxes) * page_rect.width + padding
                y1 = max(b.y1 for b in boxes) * page_rect.height + padding

                # Clamp to page bounds
                x0 = max(0, x0)
                y0 = max(0, y0)
                x1 = min(page_rect.width, x1)
                y1 = min(page_rect.height, y1)

                clip_rect = fitz.Rect(x0, y0, x1, y1)

                # Render the clipped region as an image (only if requested)
                image_base64 = None
                if include_images:
                    try:
                        # Use 2x zoom for better quality
                        mat = fitz.Matrix(2.0, 2.0)
                        pix = page.get_pixmap(matrix=mat, clip=clip_rect)
                        image_bytes = pix.tobytes("png")
                        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
                    except Exception as e:
                        logger.debug(f"Could not render evidence region: {e}")

                entries.append(EvidenceAppendixEntry(
                    field_path=ext.path,
                    page_number=page_num + 1,  # 1-indexed for display
                    quote=evidence.quote or "",
                    confidence=ext.confidence,
                    image_base64=image_base64,
                    bbox={
                        "x0": round(x0, 2),
                        "y0": round(y0, 2),
                        "x1": round(x1, 2),
                        "y1": round(y1, 2),
                    },
                    padding_applied=padding,
                ))

        finally:
            doc.close()

        return entries

    def _generate_json(self, report: AuditReport) -> bytes:
        """Generate JSON format audit report."""
        return report.model_dump_json(indent=2).encode("utf-8")

    def _generate_pdf(
        self,
        report: AuditReport,
        job: MagicImportJob,
        result: MagicImportResult,
        *,
        pdf_path: Path | None = None,
    ) -> bytes:
        """
        Generate PDF format audit report with charts and evidence appendix.

        Raises:
            ValueError: If reportlab is not installed.
        """
        import base64

        try:
            from reportlab.graphics.charts.barcharts import VerticalBarChart
            from reportlab.graphics.charts.piecharts import Pie
            from reportlab.graphics.shapes import Drawing, String
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.lib.units import cm, mm
            from reportlab.platypus import (
                Image,
                PageBreak,
                Paragraph,
                SimpleDocTemplate,
                Spacer,
                Table,
                TableStyle,
            )
        except ImportError:
            raise ValueError(
                "PDF generation requires reportlab. Install with: pip install reportlab"
            )

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

        # Reusable styles
        section_style = ParagraphStyle(
            "SectionHeader",
            parent=styles["Heading2"],
            fontSize=12,
            spaceBefore=4 * mm,
            spaceAfter=2 * mm,
        )
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

        # Metadata section
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

        # Compliance Summary section (for auditors)
        elements.append(Paragraph("Compliance Summary", section_style))

        # Quality score with grade badge
        grade_colors = {
            "A": colors.green,
            "B": colors.Color(0.5, 0.8, 0.2),  # Light green
            "C": colors.orange,
            "D": colors.Color(1, 0.5, 0),  # Dark orange
            "F": colors.red,
        }
        grade_color = grade_colors.get(report.compliance.quality_grade, colors.gray)

        # Create colored grade cell using Paragraph for inline color
        grade_para = Paragraph(
            f"{report.compliance.quality_score:.1f}/100 (Grade: "
            f"<font color='{grade_color.hexval()}'><b>{report.compliance.quality_grade}</b></font>)",
            styles["Normal"],
        )

        compliance_data = [
            ["Quality Score", grade_para],
            ["Required Fields", f"{report.compliance.required_fields_compliance * 100:.1f}% compliant"],
            ["Confidence Threshold", f"{report.compliance.confidence_threshold_compliance * 100:.1f}% above threshold"],
            ["Human Verification", f"{report.compliance.human_verification_rate * 100:.1f}% verified"],
            ["High Confidence (>=85%)", str(report.compliance.high_confidence_fields)],
            ["Medium Confidence (60-84%)", str(report.compliance.medium_confidence_fields)],
            ["Low Confidence (<60%)", str(report.compliance.low_confidence_fields)],
        ]

        compliance_table = Table(compliance_data, colWidths=[5 * cm, 9 * cm])
        compliance_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("TEXTCOLOR", (0, 0), (0, -1), colors.darkgray),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        elements.append(compliance_table)

        # Audit flags (if any)
        if report.compliance.flags:
            elements.append(Spacer(1, 3 * mm))
            flag_style = ParagraphStyle(
                "FlagStyle",
                parent=styles["Normal"],
                fontSize=8,
                textColor=colors.red,
                leftIndent=5,
            )
            elements.append(Paragraph("<b>Audit Flags:</b>", field_style))
            for flag in report.compliance.flags:
                elements.append(Paragraph(f"• {flag}", flag_style))

        elements.append(Spacer(1, 6 * mm))

        # Confidence Distribution Charts
        elements.append(Paragraph("Confidence Distribution", section_style))

        # Create pie chart for extraction status
        status_drawing = Drawing(200, 150)
        status_pie = Pie()
        status_pie.x = 50
        status_pie.y = 25
        status_pie.width = 100
        status_pie.height = 100

        # Status counts
        status_counts = Counter(f.extraction_status for f in report.fields)
        status_data = []
        status_labels = []
        status_colors_list = []

        status_color_map = {
            ExtractionStatus.FILLED: colors.green,
            ExtractionStatus.EMPTY: colors.gray,
            ExtractionStatus.NEEDS_REVIEW: colors.orange,
            ExtractionStatus.CONFLICT: colors.red,
        }

        for status in ExtractionStatus:
            count = status_counts.get(status, 0)
            if count > 0:
                status_data.append(count)
                status_labels.append(f"{status.value}: {count}")
                status_colors_list.append(status_color_map.get(status, colors.gray))

        if status_data:
            status_pie.data = status_data
            status_pie.labels = status_labels
            status_pie.slices.strokeWidth = 0.5
            for i, color in enumerate(status_colors_list):
                status_pie.slices[i].fillColor = color
            status_drawing.add(status_pie)

            # Add title
            status_title = String(100, 135, "Extraction Status", fontSize=10, textAnchor="middle")
            status_drawing.add(status_title)

        # Create bar chart for confidence distribution
        conf_drawing = Drawing(220, 150)
        conf_chart = VerticalBarChart()
        conf_chart.x = 30
        conf_chart.y = 30
        conf_chart.height = 90
        conf_chart.width = 170

        dist = report.confidence_distribution
        conf_chart.data = [[
            dist.bucket_0_20,
            dist.bucket_20_40,
            dist.bucket_40_60,
            dist.bucket_60_80,
            dist.bucket_80_100,
        ]]

        conf_chart.categoryAxis.categoryNames = ["0-20%", "20-40%", "40-60%", "60-80%", "80-100%"]
        conf_chart.categoryAxis.labels.angle = 0
        conf_chart.categoryAxis.labels.fontSize = 7
        conf_chart.valueAxis.valueMin = 0
        conf_chart.valueAxis.labels.fontSize = 7

        # Color gradient from red to green
        conf_chart.bars[0].fillColor = colors.Color(0.9, 0.2, 0.2)  # Red
        conf_chart.bars[(0, 1)].fillColor = colors.Color(1, 0.5, 0.2)  # Orange
        conf_chart.bars[(0, 2)].fillColor = colors.Color(1, 0.8, 0.2)  # Yellow
        conf_chart.bars[(0, 3)].fillColor = colors.Color(0.6, 0.8, 0.2)  # Light green
        conf_chart.bars[(0, 4)].fillColor = colors.Color(0.2, 0.8, 0.2)  # Green

        conf_drawing.add(conf_chart)

        # Add title
        conf_title = String(115, 135, "Confidence Buckets", fontSize=10, textAnchor="middle")
        conf_drawing.add(conf_title)

        # Add charts side by side in a table
        if status_data:
            charts_table = Table([[status_drawing, conf_drawing]], colWidths=[7 * cm, 8 * cm])
            elements.append(charts_table)
        else:
            elements.append(conf_drawing)

        elements.append(Spacer(1, 6 * mm))

        # Field extractions section
        elements.append(Paragraph("Field Extractions", section_style))
        elements.append(Spacer(1, 2 * mm))

        for field in report.fields:
            # Field header
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

        # Evidence Appendix (with cropped PDF regions)
        if report.evidence_appendix:
            elements.append(PageBreak())
            elements.append(Paragraph("Evidence Appendix", section_style))
            elements.append(Spacer(1, 2 * mm))

            appendix_intro = Paragraph(
                f"This appendix contains {len(report.evidence_appendix)} cropped regions "
                "from the source PDF showing the evidence for extracted values. "
                "Regions are sorted by confidence (highest first).",
                styles["Normal"],
            )
            elements.append(appendix_intro)
            elements.append(Spacer(1, 4 * mm))

            for idx, entry in enumerate(report.evidence_appendix, 1):
                # Entry header
                conf_percent = f"{entry.confidence * 100:.0f}%"
                entry_header = (
                    f"<b>#{idx}. {entry.field_path}</b> "
                    f"(Page {entry.page_number}, Confidence: {conf_percent})"
                )
                elements.append(Paragraph(entry_header, field_style))

                # Quote
                quote_display = entry.quote
                if len(quote_display) > 150:
                    quote_display = quote_display[:150] + "..."
                elements.append(Paragraph(f'"{quote_display}"', quote_style))

                # Image (if available)
                if entry.image_base64:
                    try:
                        image_data = base64.b64decode(entry.image_base64)
                        image_buffer = BytesIO(image_data)
                        img = Image(image_buffer)

                        # Scale image to fit page width (max 14cm)
                        max_width = 14 * cm
                        max_height = 6 * cm

                        # Maintain aspect ratio
                        aspect = img.imageWidth / img.imageHeight if img.imageHeight else 1
                        if img.imageWidth > max_width:
                            img.drawWidth = max_width
                            img.drawHeight = max_width / aspect
                        if img.drawHeight > max_height:
                            img.drawHeight = max_height
                            img.drawWidth = max_height * aspect

                        # Add border
                        elements.append(Spacer(1, 2 * mm))
                        elements.append(img)
                    except Exception as e:
                        logger.debug(f"Could not embed evidence image: {e}")
                        elements.append(
                            Paragraph(
                                f"[Image unavailable: {entry.bbox}]" if entry.bbox else "[Image unavailable]",
                                quote_style,
                            )
                        )

                elements.append(Spacer(1, 4 * mm))

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
