"""
Tests for RulesEngine module.

Tests cross-field consistency validation including unit compatibility,
range plausibility, coupled fields, and cardinality checks.
"""

import pytest

from app.schemas.magic_import import (
    BBox,
    ConfidenceBreakdown,
    ConfidenceReason,
    ConfidenceReasonCode,
    EvidenceRef,
    ExtractionHint,
    ExtractionStatus,
    FieldExtraction,
)
from app.services.magic_import.rules_engine import (
    ConsistencyWarning,
    RulesEngine,
)


class TestRulesEngine:
    """Tests for RulesEngine class."""

    @pytest.fixture
    def engine(self):
        """Create a RulesEngine instance."""
        return RulesEngine()

    @pytest.fixture
    def sample_extraction(self):
        """Create a sample field extraction."""
        return FieldExtraction(
            path="Nameplate/RatedVoltage",
            value_type="xs:float",
            value_raw="400 V",
            value_normalized=400.0,
            status=ExtractionStatus.FILLED,
            confidence=0.9,
            confidence_breakdown=ConfidenceBreakdown(llm=0.9, localizer=0.9, ocr=1.0, rules=1.0),
            confidence_reasons=[],
            evidence=EvidenceRef(
                page=0,
                quote="Rated Voltage: 400 V",
                boxes=[BBox(x0=0.1, y0=0.1, x1=0.3, y1=0.15)],
            ),
            needs_review=False,
        )

    @pytest.fixture
    def sample_hint(self):
        """Create a sample extraction hint."""
        return ExtractionHint(
            path="Nameplate/RatedVoltage",
            label="Rated Voltage",
            element_type="Property",
            value_type="xs:float",
            semantic_id="0173-1#02-AAB123#001",
            semantic_label="Rated Voltage (V)",
            keywords=["voltage", "volt", "spannung"],
            required=True,
        )

    # =========================================================================
    # Unit Extraction Tests
    # =========================================================================

    def test_extract_unit_from_value_with_unit(self, engine):
        """Test extracting units from value strings."""
        assert engine._extract_unit_from_value("400 V") == "V"
        assert engine._extract_unit_from_value("5.5 kW") == "kW"
        assert engine._extract_unit_from_value("25 kg") == "kg"
        assert engine._extract_unit_from_value("100 %") == "%"

    def test_extract_unit_from_value_no_unit(self, engine):
        """Test extracting units when no unit is present."""
        assert engine._extract_unit_from_value("400") is None
        assert engine._extract_unit_from_value("hello") is None
        assert engine._extract_unit_from_value("") is None

    def test_extract_unit_from_value_complex_units(self, engine):
        """Test extracting complex units."""
        assert engine._extract_unit_from_value("10 m/s") == "m/s"
        assert engine._extract_unit_from_value("25 °C") == "°C"

    # =========================================================================
    # Numeric Parsing Tests
    # =========================================================================

    def test_parse_numeric_value(self, engine):
        """Test parsing numeric values from strings."""
        assert engine._parse_numeric_value("400") == 400.0
        assert engine._parse_numeric_value("5.5") == 5.5
        assert engine._parse_numeric_value("1,234.56") == 1234.56
        assert engine._parse_numeric_value("3,14") == 3.14  # European notation

    def test_parse_numeric_value_with_units(self, engine):
        """Test parsing numeric values with unit suffixes."""
        assert engine._parse_numeric_value("400 V") == 400.0
        assert engine._parse_numeric_value("5.5 kW") == 5.5
        assert engine._parse_numeric_value("25 kg") == 25.0

    def test_parse_numeric_value_invalid(self, engine):
        """Test parsing invalid numeric values."""
        assert engine._parse_numeric_value("") is None
        assert engine._parse_numeric_value("hello") is None
        assert engine._parse_numeric_value(None) is None

    # =========================================================================
    # Field Type Inference Tests
    # =========================================================================

    def test_infer_field_type_from_path(self, engine):
        """Test inferring field type from path."""
        assert engine._infer_field_type("RatedVoltage", None) == "voltage"
        assert engine._infer_field_type("RatedCurrent", None) == "current"
        assert engine._infer_field_type("RatedPower", None) == "power"
        assert engine._infer_field_type("Temperature", None) == "temperature"

    def test_infer_field_type_from_hint(self, engine):
        """Test inferring field type from hint keywords."""
        hint = ExtractionHint(
            path="SomeField",
            label="Custom Field",
            element_type="Property",
            keywords=["voltage", "spannung"],
        )
        assert engine._infer_field_type("SomeField", hint) == "voltage"

    def test_infer_field_type_unknown(self, engine):
        """Test that unknown fields return None."""
        assert engine._infer_field_type("UnknownField", None) is None

    # =========================================================================
    # Range Plausibility Tests
    # =========================================================================

    def test_check_range_plausibility_valid(self, engine):
        """Test that valid values produce no warnings."""
        extraction = FieldExtraction(
            path="RatedVoltage",
            value_raw="400 V",
            value_normalized=400.0,
            status=ExtractionStatus.FILLED,
            confidence=0.9,
        )

        warnings = engine._check_range_plausibility({extraction.path: extraction}, {})
        assert len(warnings) == 0

    def test_check_range_plausibility_out_of_range(self, engine):
        """Test that out-of-range values produce warnings."""
        extraction = FieldExtraction(
            path="RatedVoltage",
            value_raw="500000 V",  # 500kV is within range (100kV max)
            value_normalized=500000.0,
            status=ExtractionStatus.FILLED,
            confidence=0.9,
        )

        warnings = engine._check_range_plausibility({extraction.path: extraction}, {})
        assert len(warnings) == 1
        assert warnings[0].rule == "range_plausibility"
        assert "voltage" in warnings[0].message.lower()

    def test_check_range_plausibility_negative_power(self, engine):
        """Test that negative power produces error severity."""
        extraction = FieldExtraction(
            path="RatedPower",
            value_raw="-100 W",
            value_normalized=-100.0,
            status=ExtractionStatus.FILLED,
            confidence=0.9,
        )

        warnings = engine._check_range_plausibility({extraction.path: extraction}, {})
        assert len(warnings) == 1
        assert warnings[0].severity == "error"

    def test_check_range_plausibility_efficiency(self, engine):
        """Test that efficiency > 100% produces warning."""
        extraction = FieldExtraction(
            path="Efficiency",
            value_raw="120 %",
            value_normalized=120.0,
            status=ExtractionStatus.FILLED,
            confidence=0.9,
        )

        warnings = engine._check_range_plausibility({extraction.path: extraction}, {})
        assert len(warnings) == 1
        assert "efficiency" in warnings[0].message.lower()

    # =========================================================================
    # Coupled Fields Tests
    # =========================================================================

    def test_check_coupled_fields_consistent(self, engine):
        """Test that consistent P=U*I produces no warnings."""
        extractions = {
            "Nameplate/RatedPower": FieldExtraction(
                path="Nameplate/RatedPower",
                value_raw="2200 W",
                status=ExtractionStatus.FILLED,
                confidence=0.9,
            ),
            "Nameplate/RatedVoltage": FieldExtraction(
                path="Nameplate/RatedVoltage",
                value_raw="220 V",
                status=ExtractionStatus.FILLED,
                confidence=0.9,
            ),
            "Nameplate/RatedCurrent": FieldExtraction(
                path="Nameplate/RatedCurrent",
                value_raw="10 A",
                status=ExtractionStatus.FILLED,
                confidence=0.9,
            ),
        }

        warnings = engine._check_coupled_fields(extractions)
        assert len(warnings) == 0

    def test_check_coupled_fields_inconsistent(self, engine):
        """Test that inconsistent P≠U*I produces warning."""
        extractions = {
            "Nameplate/RatedPower": FieldExtraction(
                path="Nameplate/RatedPower",
                value_raw="5000 W",  # Should be ~2200W for 220V * 10A
                status=ExtractionStatus.FILLED,
                confidence=0.9,
            ),
            "Nameplate/RatedVoltage": FieldExtraction(
                path="Nameplate/RatedVoltage",
                value_raw="220 V",
                status=ExtractionStatus.FILLED,
                confidence=0.9,
            ),
            "Nameplate/RatedCurrent": FieldExtraction(
                path="Nameplate/RatedCurrent",
                value_raw="10 A",
                status=ExtractionStatus.FILLED,
                confidence=0.9,
            ),
        }

        warnings = engine._check_coupled_fields(extractions)
        # Note: Multiple rules can match (RatedPower and Power both match)
        assert len(warnings) >= 1
        assert all(w.rule == "coupled_fields" for w in warnings)
        assert all(len(w.paths) == 3 for w in warnings)

    def test_check_coupled_fields_missing_field(self, engine):
        """Test that missing fields don't trigger coupled check."""
        extractions = {
            "Nameplate/RatedPower": FieldExtraction(
                path="Nameplate/RatedPower",
                value_raw="5000 W",
                status=ExtractionStatus.FILLED,
                confidence=0.9,
            ),
            "Nameplate/RatedVoltage": FieldExtraction(
                path="Nameplate/RatedVoltage",
                value_raw="220 V",
                status=ExtractionStatus.FILLED,
                confidence=0.9,
            ),
            # Missing RatedCurrent
        }

        warnings = engine._check_coupled_fields(extractions)
        assert len(warnings) == 0

    # =========================================================================
    # Cardinality Tests
    # =========================================================================

    def test_check_cardinality_required_present(self, engine):
        """Test that required fields with values produce no warnings."""
        extraction = FieldExtraction(
            path="ManufacturerName",
            value_raw="Siemens",
            status=ExtractionStatus.FILLED,
            confidence=0.9,
        )
        hint = ExtractionHint(
            path="ManufacturerName",
            label="Manufacturer Name",
            element_type="Property",
            required=True,
        )

        warnings = engine._check_cardinality(
            {extraction.path: extraction},
            {hint.path: hint},
        )
        assert len(warnings) == 0

    def test_check_cardinality_required_missing(self, engine):
        """Test that required fields without values produce warnings."""
        hint = ExtractionHint(
            path="ManufacturerName",
            label="Manufacturer Name",
            element_type="Property",
            required=True,
        )

        warnings = engine._check_cardinality({}, {hint.path: hint})
        assert len(warnings) == 1
        assert warnings[0].rule == "cardinality_required"
        assert "Manufacturer Name" in warnings[0].message

    def test_check_cardinality_optional_missing(self, engine):
        """Test that optional fields without values produce no warnings."""
        hint = ExtractionHint(
            path="Description",
            label="Description",
            element_type="Property",
            required=False,
        )

        warnings = engine._check_cardinality({}, {hint.path: hint})
        assert len(warnings) == 0

    # =========================================================================
    # Unit Compatibility Tests
    # =========================================================================

    def test_check_unit_compatibility_matching(self, engine):
        """Test that matching units produce no warnings."""
        extraction = FieldExtraction(
            path="RatedPower",
            value_raw="5.5 kW",
            status=ExtractionStatus.FILLED,
            confidence=0.9,
        )
        hint = ExtractionHint(
            path="RatedPower",
            label="Rated Power",
            element_type="Property",
            semantic_label="Power (W)",
            keywords=["power", "watt"],
        )

        warnings = engine._check_unit_compatibility(
            {extraction.path: extraction},
            {hint.path: hint},
        )
        assert len(warnings) == 0

    def test_check_unit_compatibility_mismatch(self, engine):
        """Test that mismatched units produce warnings."""
        extraction = FieldExtraction(
            path="RatedPower",
            value_raw="5.5 kg",  # kg instead of power unit
            status=ExtractionStatus.FILLED,
            confidence=0.9,
        )
        hint = ExtractionHint(
            path="RatedPower",
            label="Rated Power",
            element_type="Property",
            semantic_label="Power (W)",
            keywords=["power", "watt"],
        )

        warnings = engine._check_unit_compatibility(
            {extraction.path: extraction},
            {hint.path: hint},
        )
        assert len(warnings) == 1
        assert warnings[0].rule == "unit_compatibility"
        assert "mismatch" in warnings[0].message.lower()

    # =========================================================================
    # Full Consistency Check Tests
    # =========================================================================

    def test_check_consistency_integration(self, engine, sample_extraction, sample_hint):
        """Test full consistency check integration."""
        extractions = [sample_extraction]
        hints = [sample_hint]

        warnings = engine.check_consistency(extractions, hints)
        # Should produce no warnings for valid data
        assert isinstance(warnings, list)

    def test_check_consistency_multiple_issues(self, engine):
        """Test that multiple issues are detected."""
        extractions = [
            FieldExtraction(
                path="RatedPower",
                value_raw="-100 W",  # Negative power
                status=ExtractionStatus.FILLED,
                confidence=0.9,
            ),
            FieldExtraction(
                path="Efficiency",
                value_raw="150 %",  # > 100%
                status=ExtractionStatus.FILLED,
                confidence=0.9,
            ),
        ]

        hints = [
            ExtractionHint(
                path="RequiredField",
                label="Required Field",
                element_type="Property",
                required=True,
            ),
        ]

        warnings = engine.check_consistency(extractions, hints)
        # Should have multiple warnings
        assert len(warnings) >= 2

    # =========================================================================
    # Apply Warnings Tests
    # =========================================================================

    def test_apply_warnings_to_extractions(self, engine, sample_extraction):
        """Test applying warnings to extractions."""
        warnings = [
            ConsistencyWarning(
                paths=[sample_extraction.path],
                rule="test_rule",
                message="Test warning message",
                severity="warning",
            ),
        ]

        updated = engine.apply_warnings_to_extractions([sample_extraction], warnings)

        assert len(updated) == 1
        assert len(updated[0].confidence_reasons) > len(sample_extraction.confidence_reasons)

        # Check that the warning was added as a reason
        codes = [r.code for r in updated[0].confidence_reasons]
        assert ConfidenceReasonCode.SEMANTIC_CONSTRAINT_VIOLATION in codes

    def test_apply_warnings_preserves_unaffected(self, engine, sample_extraction):
        """Test that unaffected extractions are preserved."""
        warnings = [
            ConsistencyWarning(
                paths=["OtherField"],
                rule="test_rule",
                message="Test warning",
                severity="warning",
            ),
        ]

        updated = engine.apply_warnings_to_extractions([sample_extraction], warnings)

        assert len(updated) == 1
        # Original extraction should be unchanged
        assert len(updated[0].confidence_reasons) == len(sample_extraction.confidence_reasons)

    def test_apply_warnings_multiple_paths(self, engine):
        """Test warnings affecting multiple fields."""
        extractions = [
            FieldExtraction(
                path="FieldA",
                value_raw="100",
                status=ExtractionStatus.FILLED,
                confidence=0.9,
            ),
            FieldExtraction(
                path="FieldB",
                value_raw="200",
                status=ExtractionStatus.FILLED,
                confidence=0.9,
            ),
        ]

        warnings = [
            ConsistencyWarning(
                paths=["FieldA", "FieldB"],
                rule="coupled_check",
                message="Fields are inconsistent",
                severity="warning",
            ),
        ]

        updated = engine.apply_warnings_to_extractions(extractions, warnings)

        # Both extractions should have the warning
        assert len(updated[0].confidence_reasons) == 1
        assert len(updated[1].confidence_reasons) == 1

    # =========================================================================
    # Custom Rules Tests
    # =========================================================================

    def test_register_custom_rule(self, engine):
        """Test registering and running custom rules."""
        custom_warning_triggered = []

        def custom_rule(extractions, hints):
            custom_warning_triggered.append(True)
            return [
                ConsistencyWarning(
                    paths=["test"],
                    rule="custom_rule",
                    message="Custom rule triggered",
                    severity="info",
                ),
            ]

        engine.register_rule(custom_rule)

        warnings = engine.check_consistency([], [])

        assert len(custom_warning_triggered) == 1
        assert len(warnings) == 1
        assert warnings[0].rule == "custom_rule"

    def test_custom_rule_exception_handled(self, engine):
        """Test that custom rule exceptions are handled gracefully."""

        def failing_rule(extractions, hints):
            raise ValueError("Custom rule failed")

        engine.register_rule(failing_rule)

        # Should not raise, just log warning
        warnings = engine.check_consistency([], [])
        # The failing rule shouldn't add any warnings
        assert isinstance(warnings, list)


class TestConsistencyWarning:
    """Tests for ConsistencyWarning model."""

    def test_warning_creation(self):
        """Test creating a ConsistencyWarning."""
        warning = ConsistencyWarning(
            paths=["Field1", "Field2"],
            rule="test_rule",
            message="Test message",
            severity="warning",
            expected="expected_value",
            actual="actual_value",
        )

        assert len(warning.paths) == 2
        assert warning.rule == "test_rule"
        assert warning.severity == "warning"

    def test_warning_defaults(self):
        """Test ConsistencyWarning defaults."""
        warning = ConsistencyWarning(
            paths=["Field1"],
            rule="test_rule",
            message="Test message",
        )

        assert warning.severity == "warning"
        assert warning.expected is None
        assert warning.actual is None

    def test_warning_severity_values(self):
        """Test valid severity values."""
        for severity in ["info", "warning", "error"]:
            warning = ConsistencyWarning(
                paths=["Field1"],
                rule="test_rule",
                message="Test message",
                severity=severity,
            )
            assert warning.severity == severity


class TestContactRulesExtraction:
    """Tests for rule-based contact information extraction."""

    @pytest.fixture
    def contact_index(self):
        """Create a PDF index with contact information in header/footer."""
        from app.schemas.magic_import import (
            BBox,
            PDFIndex,
            PDFIndexInfo,
            PDFPageInfo,
            PDFWord,
        )

        words = []
        # Simulates a header with contact info
        contact_text = [
            "info@lenntech.com",
            "Tel.",
            "+31-152-610-900",
            "www.lenntech.com",
            "Fax.",
            "+31-152-616-289",
        ]
        for i, text in enumerate(contact_text):
            words.append(
                PDFWord(
                    text=text,
                    page=0,
                    bbox=BBox(
                        x0=0.1 + i * 0.1,
                        y0=0.05,
                        x1=0.15 + i * 0.1,
                        y1=0.08,
                    ),
                    confidence=1.0,
                    method="TEXT",
                )
            )

        return PDFIndex(
            job_id="contact-rules-test",
            pdf_path="contact.pdf",
            info=PDFIndexInfo(
                total_pages=1,
                pages_with_text=1,
                pages_needing_ocr=0,
                total_words=len(words),
                language_detected=None,
            ),
            pages=[
                PDFPageInfo(
                    page_number=0,
                    width=612,
                    height=792,
                    has_text=True,
                    needs_ocr=False,
                    word_count=len(words),
                )
            ],
            words=words,
        )

    def test_extract_email_pattern(self, contact_index):
        """Test email extraction via regex pattern."""
        from app.services.magic_import.rules_engine import extract_contact_by_rules

        extractions = extract_contact_by_rules(contact_index)

        email_extractions = [e for e in extractions if e.pattern_name == "Email"]
        assert len(email_extractions) >= 1
        assert email_extractions[0].value == "info@lenntech.com"
        assert email_extractions[0].page == 0
        assert email_extractions[0].confidence == 0.92

    def test_extract_phone_pattern(self, contact_index):
        """Test phone extraction via regex pattern."""
        from app.services.magic_import.rules_engine import extract_contact_by_rules

        extractions = extract_contact_by_rules(contact_index)

        phone_extractions = [e for e in extractions if e.pattern_name == "Phone"]
        assert len(phone_extractions) >= 1
        assert "+31-152-610-900" in phone_extractions[0].value

    def test_extract_fax_pattern(self, contact_index):
        """Test fax extraction via regex pattern."""
        from app.services.magic_import.rules_engine import extract_contact_by_rules

        extractions = extract_contact_by_rules(contact_index)

        fax_extractions = [e for e in extractions if e.pattern_name == "Fax"]
        assert len(fax_extractions) >= 1
        assert "+31-152-616-289" in fax_extractions[0].value

    def test_extract_website_pattern(self, contact_index):
        """Test website extraction via regex pattern."""
        from app.services.magic_import.rules_engine import extract_contact_by_rules

        extractions = extract_contact_by_rules(contact_index)

        website_extractions = [e for e in extractions if e.pattern_name == "Website"]
        assert len(website_extractions) >= 1
        assert "www.lenntech.com" in website_extractions[0].value

    def test_extract_with_hints_filters_fields(self, contact_index):
        """Test that hints filter which fields to extract."""
        from app.services.magic_import.rules_engine import extract_contact_by_rules

        hints = [
            ExtractionHint(
                path="ContactInformation/EmailAddress",
                label="Email Address",
                element_type="Property",
                keywords=["email"],
            ),
        ]

        extractions = extract_contact_by_rules(contact_index, hints)

        # Should only extract email when hints filter to email
        assert len(extractions) >= 1
        assert all(e.pattern_name == "Email" for e in extractions)

    def test_extract_deduplicates_across_pages(self):
        """Test that duplicate values on multiple pages are deduplicated."""
        from app.schemas.magic_import import (
            BBox,
            PDFIndex,
            PDFIndexInfo,
            PDFPageInfo,
            PDFWord,
        )
        from app.services.magic_import.rules_engine import extract_contact_by_rules

        words = []
        # Same email on page 0 and page 1 (header/footer)
        for page in [0, 1]:
            words.append(
                PDFWord(
                    text="info@example.com",
                    page=page,
                    bbox=BBox(x0=0.1, y0=0.05, x1=0.3, y1=0.08),
                    confidence=1.0,
                    method="TEXT",
                )
            )

        index = PDFIndex(
            job_id="dedup-test",
            pdf_path="dedup.pdf",
            info=PDFIndexInfo(
                total_pages=2,
                pages_with_text=2,
                pages_needing_ocr=0,
                total_words=len(words),
            ),
            pages=[
                PDFPageInfo(
                    page_number=0,
                    width=612,
                    height=792,
                    has_text=True,
                    needs_ocr=False,
                    word_count=1,
                ),
                PDFPageInfo(
                    page_number=1,
                    width=612,
                    height=792,
                    has_text=True,
                    needs_ocr=False,
                    word_count=1,
                ),
            ],
            words=words,
        )

        extractions = extract_contact_by_rules(index)

        # Should only have 1 email extraction (deduplicated)
        email_extractions = [e for e in extractions if e.pattern_name == "Email"]
        assert len(email_extractions) == 1

    def test_merge_rule_extractions_with_llm(self):
        """Test merging rule extractions with LLM extractions."""
        from app.services.magic_import.rules_engine import (
            RuleExtraction,
            merge_rule_extractions_with_llm,
        )

        llm_extractions = [
            FieldExtraction(
                path="ContactInformation/EmailAddress",
                value_raw="",  # Empty - LLM failed to extract
                status=ExtractionStatus.EMPTY,
                confidence=0.0,
            ),
            FieldExtraction(
                path="ManufacturerName",
                value_raw="Siemens",
                status=ExtractionStatus.FILLED,
                confidence=0.9,
            ),
        ]

        rule_extractions = [
            RuleExtraction(
                path="ContactInformation/EmailAddress",
                value="info@example.com",
                evidence_quote="info@example.com",
                page=0,
                confidence=0.92,
                pattern_name="Email",
            ),
        ]

        merged = merge_rule_extractions_with_llm(llm_extractions, rule_extractions)

        # Should have 2 extractions
        assert len(merged) == 2

        # Email should now be filled from rule extraction
        email_ext = next(e for e in merged if "EmailAddress" in e.path)
        assert email_ext.value_raw == "info@example.com"
        assert email_ext.status == ExtractionStatus.FILLED
        assert email_ext.confidence == 0.92
        assert email_ext.evidence is not None
        assert email_ext.evidence.page == 0

        # ManufacturerName should be unchanged
        mfr_ext = next(e for e in merged if "ManufacturerName" in e.path)
        assert mfr_ext.value_raw == "Siemens"

    def test_merge_does_not_overwrite_filled_extractions(self):
        """Test that rule extractions don't overwrite LLM values."""
        from app.services.magic_import.rules_engine import (
            RuleExtraction,
            merge_rule_extractions_with_llm,
        )

        llm_extractions = [
            FieldExtraction(
                path="ContactInformation/EmailAddress",
                value_raw="support@company.com",  # LLM found a value
                status=ExtractionStatus.FILLED,
                confidence=0.85,
            ),
        ]

        rule_extractions = [
            RuleExtraction(
                path="ContactInformation/EmailAddress",
                value="info@example.com",  # Different value from rules
                evidence_quote="info@example.com",
                page=0,
                confidence=0.92,
                pattern_name="Email",
            ),
        ]

        merged = merge_rule_extractions_with_llm(llm_extractions, rule_extractions)

        # Should keep LLM value since it's filled
        assert len(merged) == 1
        assert merged[0].value_raw == "support@company.com"
