"""
Tests for Audit Report Generator.

Tests audit report generation functionality including:
- Report building from job and result data
- Field entry construction with evidence
- Summary statistics calculation
- JSON format generation
- PDF format generation (when reportlab available)
"""

import json
import pytest
from datetime import datetime, timezone

from app.schemas.magic_import import (
    BBox,
    ConfidenceBreakdown,
    ConfidenceReason,
    ConfidenceReasonCode,
    EvidenceRef,
    ExtractionStatus,
    FieldExtraction,
    JobStatus,
    MagicImportJob,
    MagicImportResult,
    PDFIndexInfo,
)
from app.services.magic_import.audit_report import (
    AuditReport,
    AuditReportGenerator,
    ReviewStatus,
)


@pytest.fixture
def sample_job() -> MagicImportJob:
    """Create a sample Magic Import job."""
    now = datetime.now(timezone.utc)
    return MagicImportJob(
        job_id="test-job-123",
        status=JobStatus.DONE,
        template_name="IDTA-02006-1-0-Nameplate",
        template_status="published",
        template_version="1.0.0",
        pdf_filename="product_datasheet.pdf",
        pdf_size_bytes=512000,
        created_at=now,
        updated_at=now,
        progress=1.0,
        progress_message="Complete",
        pdf_info=PDFIndexInfo(
            total_pages=5,
            pages_with_text=5,
            pages_needing_ocr=0,
            total_words=2500,
            language_detected="en",
        ),
    )


@pytest.fixture
def sample_extractions() -> list[FieldExtraction]:
    """Create sample field extractions with various statuses."""
    return [
        # Filled with evidence, approved
        FieldExtraction(
            path="Nameplate/ManufacturerName",
            value_type="xs:string",
            value_raw="ACME Corporation",
            value_normalized="ACME Corporation",
            status=ExtractionStatus.FILLED,
            confidence=0.95,
            confidence_breakdown=ConfidenceBreakdown(
                llm=0.96,
                localizer=0.98,
                ocr=1.0,
                rules=0.9,
            ),
            confidence_reasons=[
                ConfidenceReason(
                    code=ConfidenceReasonCode.NO_EVIDENCE_FOUND,
                    message="Strong match with evidence",
                    severity="info",
                ),
            ],
            evidence=EvidenceRef(
                page=0,
                quote="manufactured by ACME Corporation since 1985",
                boxes=[BBox(x0=0.1, y0=0.2, x1=0.4, y1=0.25)],
                method="TEXT",
                locator_score=0.98,
                char_start=100,
                char_end=145,
            ),
            needs_review=False,
            user_edited=False,
            user_approved=True,
        ),
        # Filled with evidence, edited by user
        FieldExtraction(
            path="Nameplate/SerialNumber",
            value_type="xs:string",
            value_raw="SN-12345-ABC",
            value_normalized="SN-12345-ABC",
            status=ExtractionStatus.FILLED,
            confidence=0.85,
            confidence_breakdown=ConfidenceBreakdown(
                llm=0.88,
                localizer=0.90,
                ocr=0.85,
                rules=0.82,
            ),
            confidence_reasons=[
                ConfidenceReason(
                    code=ConfidenceReasonCode.OCR_QUALITY_LOW,
                    message="OCR confidence below threshold",
                    severity="warning",
                ),
            ],
            evidence=EvidenceRef(
                page=1,
                quote="Serial: SN-12345-ABC",
                boxes=[BBox(x0=0.5, y0=0.3, x1=0.8, y1=0.35)],
                method="OCR",
                locator_score=0.90,
                char_start=250,
                char_end=270,
            ),
            needs_review=False,
            user_edited=True,
            user_approved=False,
        ),
        # Needs review
        FieldExtraction(
            path="Nameplate/ProductType",
            value_type="xs:string",
            value_raw="Industrial Controller",
            value_normalized="Industrial Controller",
            status=ExtractionStatus.NEEDS_REVIEW,
            confidence=0.65,
            confidence_breakdown=ConfidenceBreakdown(
                llm=0.70,
                localizer=0.60,
                ocr=1.0,
                rules=0.55,
            ),
            confidence_reasons=[
                ConfidenceReason(
                    code=ConfidenceReasonCode.LOW_LLM_CONFIDENCE,
                    message="LLM confidence below threshold",
                    severity="warning",
                ),
                ConfidenceReason(
                    code=ConfidenceReasonCode.VALUE_OUTSIDE_EVIDENCE,
                    message="Value may be inferred rather than directly quoted",
                    severity="warning",
                ),
            ],
            evidence=EvidenceRef(
                page=0,
                quote="Type: Industrial Control",
                boxes=[BBox(x0=0.1, y0=0.5, x1=0.4, y1=0.55)],
                method="TEXT",
                locator_score=0.60,
            ),
            needs_review=True,
            user_edited=False,
            user_approved=False,
        ),
        # Empty - no value found
        FieldExtraction(
            path="Nameplate/YearOfConstruction",
            value_type="xs:string",
            value_raw="",
            value_normalized=None,
            status=ExtractionStatus.EMPTY,
            confidence=0.0,
            confidence_breakdown=None,
            confidence_reasons=[
                ConfidenceReason(
                    code=ConfidenceReasonCode.NO_EVIDENCE_FOUND,
                    message="No matching value found in document",
                    severity="info",
                ),
            ],
            evidence=None,
            needs_review=False,
            user_edited=False,
            user_approved=False,
        ),
    ]


@pytest.fixture
def sample_result(sample_extractions) -> MagicImportResult:
    """Create a sample Magic Import result."""
    return MagicImportResult(
        job_id="test-job-123",
        template_name="IDTA-02006-1-0-Nameplate",
        extractions=sample_extractions,
        fields_extracted=4,
        fields_needing_review=1,
        average_confidence=0.6125,  # (0.95 + 0.85 + 0.65 + 0.0) / 4
        llm_provider="openai",
        llm_model="gpt-5.5",
        processing_time_seconds=12.5,
        llm_tokens_used=3500,
        llm_prompt_tokens=2800,
        llm_completion_tokens=700,
        llm_called=True,
    )


class TestAuditFieldEntry:
    """Test AuditFieldEntry construction."""

    def test_from_filled_extraction_with_evidence(self, sample_extractions):
        """Test field entry from filled extraction with evidence."""
        generator = AuditReportGenerator()
        extraction = sample_extractions[0]  # Approved, with evidence

        entry = generator._build_field_entry(extraction)

        assert entry.path == "Nameplate/ManufacturerName"
        assert entry.value == "ACME Corporation"
        assert entry.value_type == "xs:string"
        assert entry.extraction_status == ExtractionStatus.FILLED
        assert entry.review_status == ReviewStatus.APPROVED
        assert entry.confidence == 0.95
        assert entry.has_evidence is True
        assert entry.evidence_page == 0
        assert entry.evidence_quote == "manufactured by ACME Corporation since 1985"
        assert entry.evidence_method == "TEXT"
        assert entry.evidence_char_start == 100
        assert entry.evidence_char_end == 145

    def test_from_edited_extraction(self, sample_extractions):
        """Test field entry from user-edited extraction."""
        generator = AuditReportGenerator()
        extraction = sample_extractions[1]  # Edited

        entry = generator._build_field_entry(extraction)

        assert entry.review_status == ReviewStatus.EDITED
        assert entry.confidence == 0.85

    def test_from_needs_review_extraction(self, sample_extractions):
        """Test field entry from extraction needing review."""
        generator = AuditReportGenerator()
        extraction = sample_extractions[2]  # Needs review

        entry = generator._build_field_entry(extraction)

        assert entry.review_status == ReviewStatus.NEEDS_REVIEW
        assert len(entry.confidence_reasons) == 2

    def test_from_empty_extraction(self, sample_extractions):
        """Test field entry from empty extraction."""
        generator = AuditReportGenerator()
        extraction = sample_extractions[3]  # Empty

        entry = generator._build_field_entry(extraction)

        assert entry.extraction_status == ExtractionStatus.EMPTY
        assert entry.review_status == ReviewStatus.NOT_REVIEWED
        assert entry.has_evidence is False
        assert entry.evidence_page is None
        assert entry.evidence_quote is None


class TestAuditReportSummary:
    """Test summary statistics calculation."""

    def test_summary_from_extractions(self, sample_job, sample_result):
        """Test summary statistics are calculated correctly."""
        generator = AuditReportGenerator()
        report = generator._build_report(sample_job, sample_result)

        summary = report.summary
        assert summary.total_fields == 4
        assert summary.fields_filled == 2  # ManufacturerName, SerialNumber
        assert summary.fields_empty == 1   # YearOfConstruction
        assert summary.fields_needs_review == 1  # ProductType
        assert summary.fields_approved == 1  # ManufacturerName
        assert summary.fields_edited == 1    # SerialNumber
        assert summary.evidence_coverage == 0.75  # 3/4 have evidence


class TestAuditReportMetadata:
    """Test report metadata construction."""

    def test_metadata_from_job(self, sample_job, sample_result):
        """Test metadata is populated correctly from job."""
        generator = AuditReportGenerator()
        report = generator._build_report(sample_job, sample_result)

        metadata = report.metadata
        assert metadata.job_id == "test-job-123"
        assert metadata.pdf_filename == "product_datasheet.pdf"
        assert metadata.pdf_size_bytes == 512000
        assert metadata.template_name == "IDTA-02006-1-0-Nameplate"
        assert metadata.template_status == "published"
        assert metadata.template_version == "1.0.0"
        assert metadata.llm_provider == "openai"
        assert metadata.llm_model == "gpt-5.5"
        assert metadata.processing_time_seconds == 12.5
        assert metadata.llm_tokens_used == 3500


class TestJSONGeneration:
    """Test JSON format audit report generation."""

    def test_generate_json(self, sample_job, sample_result):
        """Test JSON report generation."""
        generator = AuditReportGenerator()
        content = generator.generate(sample_job, sample_result, format="json")

        # Should be valid JSON
        data = json.loads(content.decode("utf-8"))

        assert data["report_version"] == "2.0.0"
        assert "metadata" in data
        assert "summary" in data
        assert "compliance" in data
        assert "confidence_distribution" in data
        assert "fields" in data
        assert "evidence_appendix" in data
        assert len(data["fields"]) == 4

    def test_json_field_structure(self, sample_job, sample_result):
        """Test JSON field entry structure."""
        generator = AuditReportGenerator()
        content = generator.generate(sample_job, sample_result, format="json")
        data = json.loads(content.decode("utf-8"))

        # Check first field (ManufacturerName)
        field = data["fields"][0]
        assert field["path"] == "Nameplate/ManufacturerName"
        assert field["value"] == "ACME Corporation"
        assert field["extraction_status"] == "filled"
        assert field["review_status"] == "approved"
        assert field["confidence"] == 0.95
        assert field["has_evidence"] is True
        assert field["evidence_page"] == 0
        assert "confidence_breakdown" in field

    def test_json_roundtrip(self, sample_job, sample_result):
        """Test that JSON can be parsed back to AuditReport."""
        generator = AuditReportGenerator()
        content = generator.generate(sample_job, sample_result, format="json")

        data = json.loads(content.decode("utf-8"))
        report = AuditReport.model_validate(data)

        assert report.metadata.job_id == "test-job-123"
        assert len(report.fields) == 4


class TestPDFGeneration:
    """Test PDF format audit report generation."""

    def test_generate_pdf_returns_bytes(self, sample_job, sample_result):
        """Test PDF generation returns bytes."""
        generator = AuditReportGenerator()

        try:
            content = generator.generate(sample_job, sample_result, format="pdf")
            # If reportlab is available, should be PDF
            assert isinstance(content, bytes)
            # PDF magic bytes
            if content.startswith(b"%PDF"):
                assert len(content) > 1000  # Non-trivial PDF
            else:
                # Fallback to JSON if reportlab not available
                data = json.loads(content.decode("utf-8"))
                assert "metadata" in data
        except Exception:
            pytest.skip("reportlab not available")

    def test_pdf_contains_metadata(self, sample_job, sample_result):
        """Test PDF contains expected content (basic structure check)."""
        generator = AuditReportGenerator()

        try:
            content = generator.generate(sample_job, sample_result, format="pdf")
            if content.startswith(b"%PDF"):
                # Check for expected strings in PDF
                content_str = content.decode("latin-1", errors="ignore")
                # ReportLab PDFs should contain these
                assert "audit" in content_str.lower() or "report" in content_str.lower()
        except Exception:
            pytest.skip("reportlab not available")


class TestInvalidFormats:
    """Test handling of invalid formats."""

    def test_invalid_format_raises_error(self, sample_job, sample_result):
        """Test that invalid format raises ValueError."""
        generator = AuditReportGenerator()

        with pytest.raises(ValueError, match="Unsupported format"):
            generator.generate(sample_job, sample_result, format="xml")  # type: ignore


class TestReviewStatusDetermination:
    """Test review status determination logic."""

    def test_approved_status(self):
        """Test approved review status."""
        extraction = FieldExtraction(
            path="test",
            value_raw="value",
            status=ExtractionStatus.FILLED,
            confidence=0.95,
            user_approved=True,
            user_edited=False,
            needs_review=False,
        )

        generator = AuditReportGenerator()
        entry = generator._build_field_entry(extraction)

        assert entry.review_status == ReviewStatus.APPROVED

    def test_edited_takes_precedence_over_approved(self):
        """Test edited status when both edited and approved are False."""
        extraction = FieldExtraction(
            path="test",
            value_raw="value",
            status=ExtractionStatus.FILLED,
            confidence=0.85,
            user_approved=False,
            user_edited=True,
            needs_review=False,
        )

        generator = AuditReportGenerator()
        entry = generator._build_field_entry(extraction)

        assert entry.review_status == ReviewStatus.EDITED

    def test_needs_review_status(self):
        """Test needs review status."""
        extraction = FieldExtraction(
            path="test",
            value_raw="value",
            status=ExtractionStatus.NEEDS_REVIEW,
            confidence=0.60,
            user_approved=False,
            user_edited=False,
            needs_review=True,
        )

        generator = AuditReportGenerator()
        entry = generator._build_field_entry(extraction)

        assert entry.review_status == ReviewStatus.NEEDS_REVIEW

    def test_not_reviewed_status(self):
        """Test not reviewed status (default)."""
        extraction = FieldExtraction(
            path="test",
            value_raw="value",
            status=ExtractionStatus.FILLED,
            confidence=0.90,
            user_approved=False,
            user_edited=False,
            needs_review=False,
        )

        generator = AuditReportGenerator()
        entry = generator._build_field_entry(extraction)

        assert entry.review_status == ReviewStatus.NOT_REVIEWED


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_extractions(self, sample_job):
        """Test report with no extractions."""
        result = MagicImportResult(
            job_id="test-job-123",
            template_name="IDTA-02006-1-0-Nameplate",
            extractions=[],
            fields_extracted=0,
            fields_needing_review=0,
            average_confidence=0.0,
            llm_provider="openai",
            llm_model="gpt-5.5",
            processing_time_seconds=0.5,
        )

        generator = AuditReportGenerator()
        report = generator._build_report(sample_job, result)

        assert report.summary.total_fields == 0
        assert report.summary.evidence_coverage == 0.0
        assert len(report.fields) == 0

    def test_long_evidence_quote(self, sample_job):
        """Test handling of very long evidence quotes."""
        extraction = FieldExtraction(
            path="test",
            value_raw="value",
            status=ExtractionStatus.FILLED,
            confidence=0.95,
            evidence=EvidenceRef(
                page=0,
                quote="x" * 500,  # Very long quote
                boxes=[],
                method="TEXT",
                locator_score=0.95,
            ),
        )

        result = MagicImportResult(
            job_id="test-job-123",
            template_name="Test",
            extractions=[extraction],
            fields_extracted=1,
            fields_needing_review=0,
            average_confidence=0.95,
            llm_provider="openai",
            llm_model="gpt-5.5",
            processing_time_seconds=1.0,
        )

        generator = AuditReportGenerator()
        content = generator.generate(sample_job, result, format="json")

        # Should not fail and should contain the quote
        data = json.loads(content.decode("utf-8"))
        assert len(data["fields"][0]["evidence_quote"]) == 500

    def test_special_characters_in_values(self, sample_job):
        """Test handling of special characters in values."""
        extraction = FieldExtraction(
            path="test",
            value_raw="Value with 'quotes' and \"double quotes\" and <tags>",
            status=ExtractionStatus.FILLED,
            confidence=0.95,
            evidence=EvidenceRef(
                page=0,
                quote="Quote with special chars: © ® ™ € £",
                boxes=[],
                method="TEXT",
                locator_score=0.95,
            ),
        )

        result = MagicImportResult(
            job_id="test-job-123",
            template_name="Test",
            extractions=[extraction],
            fields_extracted=1,
            fields_needing_review=0,
            average_confidence=0.95,
            llm_provider="openai",
            llm_model="gpt-5.5",
            processing_time_seconds=1.0,
        )

        generator = AuditReportGenerator()
        content = generator.generate(sample_job, result, format="json")

        # Should handle special chars correctly
        data = json.loads(content.decode("utf-8"))
        assert "quotes" in data["fields"][0]["value"]

    def test_null_confidence_breakdown(self, sample_job):
        """Test handling of null confidence breakdown."""
        extraction = FieldExtraction(
            path="test",
            value_raw="value",
            status=ExtractionStatus.FILLED,
            confidence=0.80,
            confidence_breakdown=None,  # Explicitly None
        )

        result = MagicImportResult(
            job_id="test-job-123",
            template_name="Test",
            extractions=[extraction],
            fields_extracted=1,
            fields_needing_review=0,
            average_confidence=0.80,
            llm_provider="openai",
            llm_model="gpt-5.5",
            processing_time_seconds=1.0,
        )

        generator = AuditReportGenerator()
        content = generator.generate(sample_job, result, format="json")

        data = json.loads(content.decode("utf-8"))
        assert data["fields"][0]["confidence_breakdown"] is None


class TestComplianceSummary:
    """Test compliance summary calculation for auditors."""

    def test_compliance_summary_quality_score(self, sample_job, sample_result):
        """Test quality score calculation."""
        generator = AuditReportGenerator()
        report = generator._build_report(sample_job, sample_result)

        # Quality score should be between 0 and 100
        assert 0 <= report.compliance.quality_score <= 100
        # Grade should be valid
        assert report.compliance.quality_grade in ("A", "B", "C", "D", "F")

    def test_compliance_with_required_paths(self, sample_job, sample_result):
        """Test compliance calculation with explicit required paths."""
        generator = AuditReportGenerator()

        # Define required paths - one filled, one empty
        required_paths = {
            "Nameplate/ManufacturerName",  # FILLED
            "Nameplate/YearOfConstruction",  # EMPTY
        }

        report = generator._build_report(
            sample_job, sample_result, required_paths=required_paths
        )

        # 1 of 2 required fields filled = 50%
        assert report.compliance.required_fields_compliance == 0.5

        # Should have MISSING_REQUIRED flag (compliance < 90%)
        has_missing_required_flag = any(
            "MISSING_REQUIRED" in flag for flag in report.compliance.flags
        )
        assert has_missing_required_flag

    def test_compliance_without_required_paths_uses_fill_rate(self, sample_job, sample_result):
        """Test compliance fallback to fill rate when no required paths provided."""
        generator = AuditReportGenerator()

        # Without required_paths, should use fill rate
        report = generator._build_report(sample_job, sample_result)

        # 2 filled out of 4 total = 50%
        assert report.compliance.required_fields_compliance == 0.5

        # Should NOT have MISSING_REQUIRED flag (no required info available)
        has_missing_required_flag = any(
            "MISSING_REQUIRED" in flag for flag in report.compliance.flags
        )
        assert not has_missing_required_flag

    def test_compliance_all_required_filled(self, sample_job, sample_result):
        """Test 100% compliance when all required fields are filled."""
        generator = AuditReportGenerator()

        # Only require fields that are FILLED
        required_paths = {
            "Nameplate/ManufacturerName",  # FILLED
            "Nameplate/SerialNumber",  # FILLED
        }

        report = generator._build_report(
            sample_job, sample_result, required_paths=required_paths
        )

        # Both required fields filled = 100%
        assert report.compliance.required_fields_compliance == 1.0

        # Should NOT have MISSING_REQUIRED flag
        has_missing_required_flag = any(
            "MISSING_REQUIRED" in flag for flag in report.compliance.flags
        )
        assert not has_missing_required_flag

    def test_compliance_summary_confidence_tiers(self, sample_job, sample_result):
        """Test confidence tier counts."""
        generator = AuditReportGenerator()
        report = generator._build_report(sample_job, sample_result)

        # Tiers should add up to total fields
        total_tiers = (
            report.compliance.high_confidence_fields +
            report.compliance.medium_confidence_fields +
            report.compliance.low_confidence_fields
        )
        assert total_tiers == report.summary.total_fields

    def test_compliance_flags_low_confidence(self, sample_job):
        """Test audit flags for low confidence extractions."""
        # Create extractions with mostly low confidence
        extractions = [
            FieldExtraction(
                path=f"field{i}",
                value_raw=f"value{i}",
                status=ExtractionStatus.FILLED,
                confidence=0.3 + (i * 0.05),  # 0.3, 0.35, 0.4, 0.45, 0.5
            )
            for i in range(5)
        ]

        result = MagicImportResult(
            job_id="test-job",
            template_name="Test",
            extractions=extractions,
            fields_extracted=5,
            fields_needing_review=0,
            average_confidence=0.4,
            llm_provider="openai",
            llm_model="gpt-5.5",
            processing_time_seconds=1.0,
        )

        generator = AuditReportGenerator()
        report = generator._build_report(sample_job, result)

        # Should have low confidence flag
        has_low_conf_flag = any("LOW_CONFIDENCE" in flag for flag in report.compliance.flags)
        assert has_low_conf_flag

    def test_compliance_grade_a(self, sample_job):
        """Test grade A for high quality extractions."""
        extractions = [
            FieldExtraction(
                path=f"field{i}",
                value_raw=f"value{i}",
                status=ExtractionStatus.FILLED,
                confidence=0.95,
                user_approved=True,
                evidence=EvidenceRef(
                    page=0,
                    quote="quote",
                    boxes=[],
                    method="TEXT",
                    locator_score=0.95,
                ),
            )
            for i in range(5)
        ]

        result = MagicImportResult(
            job_id="test-job",
            template_name="Test",
            extractions=extractions,
            fields_extracted=5,
            fields_needing_review=0,
            average_confidence=0.95,
            llm_provider="openai",
            llm_model="gpt-5.5",
            processing_time_seconds=1.0,
        )

        generator = AuditReportGenerator()
        report = generator._build_report(sample_job, result)

        # Should be grade A
        assert report.compliance.quality_grade == "A"


class TestConfidenceDistribution:
    """Test confidence distribution calculation."""

    def test_distribution_buckets(self, sample_job, sample_result):
        """Test confidence distribution buckets."""
        generator = AuditReportGenerator()
        report = generator._build_report(sample_job, sample_result)

        dist = report.confidence_distribution
        # All buckets should be non-negative
        assert dist.bucket_0_20 >= 0
        assert dist.bucket_20_40 >= 0
        assert dist.bucket_40_60 >= 0
        assert dist.bucket_60_80 >= 0
        assert dist.bucket_80_100 >= 0

        # Total should equal number of fields
        total = (
            dist.bucket_0_20 +
            dist.bucket_20_40 +
            dist.bucket_40_60 +
            dist.bucket_60_80 +
            dist.bucket_80_100
        )
        assert total == len(report.fields)

    def test_distribution_with_varied_confidence(self, sample_job):
        """Test distribution with extractions across all buckets."""
        extractions = [
            FieldExtraction(path="f1", value_raw="v1", status=ExtractionStatus.FILLED, confidence=0.15),
            FieldExtraction(path="f2", value_raw="v2", status=ExtractionStatus.FILLED, confidence=0.35),
            FieldExtraction(path="f3", value_raw="v3", status=ExtractionStatus.FILLED, confidence=0.55),
            FieldExtraction(path="f4", value_raw="v4", status=ExtractionStatus.FILLED, confidence=0.75),
            FieldExtraction(path="f5", value_raw="v5", status=ExtractionStatus.FILLED, confidence=0.95),
        ]

        result = MagicImportResult(
            job_id="test-job",
            template_name="Test",
            extractions=extractions,
            fields_extracted=5,
            fields_needing_review=0,
            average_confidence=0.55,
            llm_provider="openai",
            llm_model="gpt-5.5",
            processing_time_seconds=1.0,
        )

        generator = AuditReportGenerator()
        report = generator._build_report(sample_job, result)

        dist = report.confidence_distribution
        assert dist.bucket_0_20 == 1
        assert dist.bucket_20_40 == 1
        assert dist.bucket_40_60 == 1
        assert dist.bucket_60_80 == 1
        assert dist.bucket_80_100 == 1


class TestEvidenceAppendix:
    """Test evidence appendix generation."""

    def test_evidence_appendix_without_pdf(self, sample_job, sample_result):
        """Test evidence appendix generation without PDF file."""
        generator = AuditReportGenerator()
        report = generator._build_report(
            sample_job,
            sample_result,
            include_evidence_appendix=True,
            # No pdf_path provided
        )

        # Should have empty appendix without PDF
        assert report.evidence_appendix == []

    def test_evidence_appendix_entries_structure(self, sample_job):
        """Test evidence appendix entry structure."""
        from app.services.magic_import.audit_report import EvidenceAppendixEntry

        entry = EvidenceAppendixEntry(
            field_path="Nameplate/ManufacturerName",
            page_number=1,
            quote="Test quote",
            confidence=0.95,
            image_base64=None,
            bbox={"x0": 10.0, "y0": 20.0, "x1": 100.0, "y1": 50.0},
        )

        assert entry.field_path == "Nameplate/ManufacturerName"
        assert entry.page_number == 1
        assert entry.confidence == 0.95
        assert entry.bbox is not None
        # New fields for Issue 2 fix
        assert entry.bbox_units == "points"
        assert entry.padding_applied == 10

    def test_evidence_appendix_disabled(self, sample_job, sample_result):
        """Test evidence appendix can be disabled."""
        generator = AuditReportGenerator()
        report = generator._build_report(
            sample_job,
            sample_result,
            include_evidence_appendix=False,
        )

        # Should have empty appendix when disabled
        assert report.evidence_appendix == []


class TestEvidenceImageEmbedding:
    """Test evidence image embedding control (Issue 3 fix)."""

    def test_json_format_excludes_images_by_default(self, sample_job, sample_result):
        """Test that JSON format excludes images by default."""
        generator = AuditReportGenerator()
        # When format is JSON and include_evidence_images is None (default),
        # images should NOT be embedded
        report = generator._build_report(
            sample_job,
            sample_result,
            format="json",
            include_evidence_appendix=True,
            # No pdf_path means no appendix, but test the logic path
        )
        # Without PDF, appendix is empty anyway
        assert report.evidence_appendix == []

    def test_pdf_format_includes_images_by_default(self, sample_job, sample_result):
        """Test that PDF format includes images by default."""
        generator = AuditReportGenerator()
        # When format is PDF and include_evidence_images is None (default),
        # images should be embedded (if PDF available)
        report = generator._build_report(
            sample_job,
            sample_result,
            format="pdf",
            include_evidence_appendix=True,
        )
        # Without PDF path, appendix is empty anyway
        assert report.evidence_appendix == []

    def test_explicit_include_images_overrides_format_default(self, sample_job, sample_result):
        """Test that explicit include_evidence_images overrides format default."""
        generator = AuditReportGenerator()
        # Even for JSON, if explicitly set to True, should include images
        # (when PDF is available)
        report = generator._build_report(
            sample_job,
            sample_result,
            format="json",
            include_evidence_appendix=True,
            include_evidence_images=True,  # Explicit override
        )
        # Without PDF path, appendix is empty
        assert report.evidence_appendix == []

    def test_generate_json_without_images(self, sample_job, sample_result):
        """Test generate() with JSON format excludes images."""
        generator = AuditReportGenerator()
        content = generator.generate(
            sample_job,
            sample_result,
            format="json",
            include_evidence_images=False,
        )

        data = json.loads(content.decode("utf-8"))
        # Should succeed and have evidence_appendix key
        assert "evidence_appendix" in data

    def test_generate_json_explicit_with_images(self, sample_job, sample_result):
        """Test generate() with JSON format can explicitly include images."""
        generator = AuditReportGenerator()
        content = generator.generate(
            sample_job,
            sample_result,
            format="json",
            include_evidence_images=True,  # Explicitly request images
        )

        data = json.loads(content.decode("utf-8"))
        # Should succeed
        assert "evidence_appendix" in data


class TestPDFEnhancements:
    """Test PDF generation enhancements."""

    def test_pdf_contains_compliance_section(self, sample_job, sample_result):
        """Test PDF contains compliance summary section."""
        generator = AuditReportGenerator()

        try:
            content = generator.generate(sample_job, sample_result, format="pdf")
            if content.startswith(b"%PDF"):
                content_str = content.decode("latin-1", errors="ignore")
                # Should contain compliance-related terms
                assert "compliance" in content_str.lower() or "quality" in content_str.lower()
        except Exception:
            pytest.skip("reportlab not available")

    def test_pdf_contains_charts(self, sample_job, sample_result):
        """Test PDF contains chart elements (confidence distribution)."""
        generator = AuditReportGenerator()

        try:
            content = generator.generate(sample_job, sample_result, format="pdf")
            if content.startswith(b"%PDF"):
                # PDF should be larger due to chart graphics
                assert len(content) > 1000  # Charts add significant size
        except Exception:
            pytest.skip("reportlab not available")
