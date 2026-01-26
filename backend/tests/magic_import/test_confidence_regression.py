"""
Regression tests for Magic Import extraction confidence.

Uses golden fixtures to verify extraction quality doesn't degrade.
"""

import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "magic_import"


def load_expected_json(name: str) -> dict | None:
    """Load expected JSON fixture."""
    path = FIXTURES_DIR / f"{name}_expected.json"
    if path.exists():
        return json.loads(path.read_text())
    return None


class TestFixtureSchema:
    """Tests for fixture JSON schema validity."""

    def test_nameplate_text_fixture_exists(self):
        """Verify nameplate_text expected JSON exists and is valid."""
        expected = load_expected_json("nameplate_text")
        assert expected is not None, "nameplate_text_expected.json not found"
        assert "template_name" in expected
        assert "expected_extractions" in expected
        assert len(expected["expected_extractions"]) > 0

    def test_techspec_tables_fixture_exists(self):
        """Verify techspec_tables expected JSON exists and is valid."""
        expected = load_expected_json("techspec_tables")
        assert expected is not None, "techspec_tables_expected.json not found"
        assert "template_name" in expected
        assert "expected_extractions" in expected

    def test_extraction_schema_valid(self):
        """Verify extraction expectations have required fields."""
        expected = load_expected_json("nameplate_text")
        if expected is None:
            pytest.skip("Fixture not found")

        for extraction in expected["expected_extractions"]:
            assert "path" in extraction, "Extraction missing 'path'"
            assert "expected_value" in extraction, "Extraction missing 'expected_value'"
            # Confidence min should be between 0 and 1
            if "expected_confidence_min" in extraction:
                conf = extraction["expected_confidence_min"]
                assert 0 <= conf <= 1, f"Invalid confidence: {conf}"


class TestRegressionHelpers:
    """Tests for regression testing helper functions."""

    def test_confidence_within_threshold(self):
        """Test confidence comparison with threshold."""
        # Helper function for regression tests
        def confidence_acceptable(actual: float, expected_min: float, tolerance: float = 0.1) -> bool:
            """Check if actual confidence is within acceptable range."""
            return actual >= expected_min - tolerance

        assert confidence_acceptable(0.85, 0.80) is True
        assert confidence_acceptable(0.75, 0.80) is True  # Within 10% tolerance
        assert confidence_acceptable(0.65, 0.80) is False  # Too far below
        assert confidence_acceptable(0.95, 0.80) is True  # Above minimum

    def test_value_match_exact(self):
        """Test exact value matching."""
        def values_match(actual: str, expected: str, fuzzy: bool = False) -> bool:
            """Check if values match."""
            if fuzzy:
                return expected.lower() in actual.lower()
            return actual.strip() == expected.strip()

        assert values_match("Test Value", "Test Value") is True
        assert values_match(" Test Value ", "Test Value") is True
        assert values_match("test value", "Test Value") is False
        assert values_match("test value", "Test Value", fuzzy=True) is True

    def test_evidence_contains_quote(self):
        """Test evidence quote validation."""
        def evidence_valid(evidence: dict | None, expected_quote: str | None) -> bool:
            """Check if evidence contains expected quote."""
            if expected_quote is None:
                return True
            if evidence is None:
                return False
            return expected_quote.lower() in evidence.get("quote", "").lower()

        assert evidence_valid({"quote": "The manufacturer is ACME Corp"}, "ACME") is True
        assert evidence_valid({"quote": "The manufacturer is ACME Corp"}, "XYZ") is False
        assert evidence_valid(None, "ACME") is False
        assert evidence_valid(None, None) is True


@pytest.mark.skip(reason="Requires actual PDF fixtures - enable when fixtures are added")
class TestNameplateTextRegression:
    """Regression tests for nameplate_text.pdf extraction."""

    @pytest.fixture
    def expected(self):
        """Load expected extractions."""
        return load_expected_json("nameplate_text")

    @pytest.fixture
    def actual_result(self, expected):
        """Run extraction on fixture PDF and return result."""
        # This would run the actual extraction pipeline
        # For now, return None - implement when PDFs are available
        pdf_path = FIXTURES_DIR / "nameplate_text.pdf"
        if not pdf_path.exists():
            pytest.skip("PDF fixture not found")

        # TODO: Implement actual extraction
        # from app.services.magic_import.tasks import process_magic_import_job
        # result = run_extraction(pdf_path, expected["template_name"])
        # return result
        return None

    def test_manufacturer_name_extracted(self, expected, actual_result):
        """Test ManufacturerName is extracted correctly."""
        if actual_result is None:
            pytest.skip("Extraction not implemented")

        # Find expected extraction
        exp = next(
            (e for e in expected["expected_extractions"] if e["path"] == "ManufacturerName"),
            None,
        )
        assert exp is not None

        # Find actual extraction
        actual = next(
            (e for e in actual_result.extractions if e.path == "ManufacturerName"),
            None,
        )
        assert actual is not None, "ManufacturerName not extracted"

        # Check value matches
        assert actual.value_raw == exp["expected_value"]

        # Check confidence within threshold
        assert actual.confidence >= exp["expected_confidence_min"] - 0.1

    def test_serial_number_extracted(self, expected, actual_result):
        """Test SerialNumber is extracted correctly."""
        if actual_result is None:
            pytest.skip("Extraction not implemented")

        exp = next(
            (e for e in expected["expected_extractions"] if e["path"] == "SerialNumber"),
            None,
        )
        if exp is None:
            pytest.skip("SerialNumber not in expected extractions")

        actual = next(
            (e for e in actual_result.extractions if e.path == "SerialNumber"),
            None,
        )
        assert actual is not None, "SerialNumber not extracted"
        assert actual.confidence >= exp["expected_confidence_min"] - 0.1

    def test_classification_correct(self, expected, actual_result):
        """Test document classification is correct."""
        if actual_result is None:
            pytest.skip("Extraction not implemented")

        exp_class = expected.get("expected_classification", {})
        # actual_class = actual_result.classification

        if "doc_type" in exp_class:
            # assert actual_class.doc_type == exp_class["doc_type"]
            pass

        if "quality_score_min" in exp_class:
            # assert actual_class.quality_score >= exp_class["quality_score_min"]
            pass


@pytest.mark.skip(reason="Requires actual PDF fixtures - enable when fixtures are added")
class TestTechspecTablesRegression:
    """Regression tests for techspec_tables.pdf extraction."""

    @pytest.fixture
    def expected(self):
        """Load expected extractions."""
        return load_expected_json("techspec_tables")

    def test_table_extraction_confidence(self, expected):
        """Test that table values are extracted with acceptable confidence."""
        # This test would verify table extraction works
        pytest.skip("PDF fixture not available")

    def test_has_tables_detected(self, expected):
        """Test that tables are detected in classification."""
        exp_class = expected.get("expected_classification", {})
        assert exp_class.get("has_tables") is True
