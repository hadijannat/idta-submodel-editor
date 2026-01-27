"""
Tests for OutcomeTracker service.

Tests outcome tracking functionality including:
- Recording user corrections with edit distance calculation
- Retrieving outcomes with filters
- Computing correction rates by confidence bucket
- JSONL storage organization by date
"""

import json

import pytest
from datetime import datetime, timedelta, timezone

from app.schemas.magic_import import (
    EvidenceQuality,
    ExtractionOutcome,
    FieldTypeCategory,
)
from app.services.magic_import.outcome_tracker import (
    OutcomeTracker,
    levenshtein_distance,
)


class TestLevenshteinDistance:
    """Test suite for Levenshtein distance calculation."""

    def test_identical_strings(self):
        """Test distance between identical strings is 0."""
        assert levenshtein_distance("hello", "hello") == 0
        assert levenshtein_distance("", "") == 0
        assert levenshtein_distance("a", "a") == 0

    def test_empty_string(self):
        """Test distance with empty string equals length of other."""
        assert levenshtein_distance("hello", "") == 5
        assert levenshtein_distance("", "world") == 5

    def test_single_insertion(self):
        """Test single character insertion."""
        assert levenshtein_distance("hello", "hellos") == 1
        assert levenshtein_distance("cat", "cats") == 1

    def test_single_deletion(self):
        """Test single character deletion."""
        assert levenshtein_distance("hello", "hell") == 1
        assert levenshtein_distance("cats", "cat") == 1

    def test_single_substitution(self):
        """Test single character substitution."""
        assert levenshtein_distance("hello", "hallo") == 1
        assert levenshtein_distance("cat", "bat") == 1

    def test_multiple_operations(self):
        """Test multiple edit operations."""
        # "kitten" -> "sitting": k->s, e->i, +g
        assert levenshtein_distance("kitten", "sitting") == 3

    def test_symmetric(self):
        """Test that distance is symmetric."""
        assert levenshtein_distance("abc", "xyz") == levenshtein_distance("xyz", "abc")
        assert levenshtein_distance("hello", "world") == levenshtein_distance(
            "world", "hello"
        )

    def test_case_sensitive(self):
        """Test that comparison is case-sensitive."""
        assert levenshtein_distance("Hello", "hello") == 1
        assert levenshtein_distance("ABC", "abc") == 3


class TestOutcomeTrackerInit:
    """Test OutcomeTracker initialization."""

    def test_init_with_custom_cache_dir(self, tmp_path):
        """Test initialization with custom cache directory."""
        tracker = OutcomeTracker(cache_dir=tmp_path)
        assert tracker.outcomes_dir == tmp_path / "outcomes"
        assert tracker.outcomes_dir.exists()

    def test_init_creates_outcomes_directory(self, tmp_path):
        """Test that init creates the outcomes directory."""
        cache_dir = tmp_path / "new_cache"
        tracker = OutcomeTracker(cache_dir=cache_dir)
        assert tracker.outcomes_dir.exists()


class TestRecordCorrection:
    """Test suite for record_correction method."""

    @pytest.fixture
    def tracker(self, tmp_path):
        """Create a tracker with temp directory."""
        return OutcomeTracker(cache_dir=tmp_path)

    def test_record_accepted(self, tracker):
        """Test recording an accepted extraction."""
        outcome = tracker.record_correction(
            job_id="job-123",
            field_path="Nameplate/SerialNumber",
            original_value="SN-12345",
            final_value="SN-12345",
            original_confidence=0.95,
            action="accepted",
            had_evidence=True,
            evidence_quality=EvidenceQuality.TEXT_GROUNDED,
            field_type=FieldTypeCategory.IDENTIFIER,
            was_required=True,
        )

        assert outcome.job_id == "job-123"
        assert outcome.field_path == "Nameplate/SerialNumber"
        assert outcome.original_value == "SN-12345"
        assert outcome.final_value == "SN-12345"
        assert outcome.action == "accepted"
        assert outcome.edit_distance == 0  # No edit for accepted
        assert outcome.had_evidence is True
        assert outcome.evidence_quality == EvidenceQuality.TEXT_GROUNDED
        assert outcome.field_type == FieldTypeCategory.IDENTIFIER
        assert outcome.was_required is True
        assert outcome.recorded_at is not None

    def test_record_edited_calculates_distance(self, tracker):
        """Test that edited corrections calculate edit distance."""
        outcome = tracker.record_correction(
            job_id="job-123",
            field_path="ProductName",
            original_value="Widget",
            final_value="Widgets",  # Added 's'
            original_confidence=0.80,
            action="edited",
            had_evidence=True,
            evidence_quality=EvidenceQuality.TEXT_INFERRED,
            field_type=FieldTypeCategory.TEXT_SHORT,
            was_required=False,
        )

        assert outcome.action == "edited"
        assert outcome.edit_distance == 1  # One insertion

    def test_record_deleted_sets_distance_to_original_length(self, tracker):
        """Test that deleted corrections set distance to original length."""
        outcome = tracker.record_correction(
            job_id="job-123",
            field_path="Description",
            original_value="Some text",
            final_value=None,
            original_confidence=0.40,
            action="deleted",
            had_evidence=False,
            evidence_quality=EvidenceQuality.NONE,
            field_type=FieldTypeCategory.TEXT_LONG,
            was_required=False,
        )

        assert outcome.action == "deleted"
        assert outcome.edit_distance == 9  # len("Some text")

    def test_record_rejected_with_replacement(self, tracker):
        """Test rejected correction with replacement value."""
        outcome = tracker.record_correction(
            job_id="job-123",
            field_path="Weight",
            original_value="5.5 kg",
            final_value="5.5 lb",
            original_confidence=0.70,
            action="rejected",
            had_evidence=True,
            evidence_quality=EvidenceQuality.OCR_LOW,
            field_type=FieldTypeCategory.NUMERIC_UNIT,
            was_required=True,
        )

        assert outcome.action == "rejected"
        assert outcome.edit_distance == 2  # "kg" -> "lb"

    def test_record_writes_to_jsonl_file(self, tracker, tmp_path):
        """Test that recording writes to JSONL file."""
        tracker.record_correction(
            job_id="job-123",
            field_path="Field1",
            original_value="value1",
            final_value="value1",
            original_confidence=0.90,
            action="accepted",
            had_evidence=True,
            evidence_quality=EvidenceQuality.TEXT_GROUNDED,
            field_type=FieldTypeCategory.TEXT_SHORT,
            was_required=False,
        )

        # Check that file was created
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        expected_file = tmp_path / "outcomes" / f"{today}.jsonl"
        assert expected_file.exists()

        # Check content
        with open(expected_file, "r") as f:
            lines = f.readlines()
            assert len(lines) == 1
            data = json.loads(lines[0])
            assert data["job_id"] == "job-123"

    def test_multiple_records_same_day(self, tracker, tmp_path):
        """Test multiple recordings on the same day append to same file."""
        for i in range(3):
            tracker.record_correction(
                job_id=f"job-{i}",
                field_path=f"Field{i}",
                original_value=f"value{i}",
                final_value=f"value{i}",
                original_confidence=0.90,
                action="accepted",
                had_evidence=True,
                evidence_quality=EvidenceQuality.TEXT_GROUNDED,
                field_type=FieldTypeCategory.TEXT_SHORT,
                was_required=False,
            )

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        expected_file = tmp_path / "outcomes" / f"{today}.jsonl"

        with open(expected_file, "r") as f:
            lines = f.readlines()
            assert len(lines) == 3


class TestGetOutcomesForAnalysis:
    """Test suite for get_outcomes_for_analysis method."""

    @pytest.fixture
    def tracker_with_data(self, tmp_path):
        """Create a tracker and populate with test data."""
        tracker = OutcomeTracker(cache_dir=tmp_path)

        # Record some outcomes
        for i in range(5):
            tracker.record_correction(
                job_id=f"job-{i}",
                field_path=f"Field{i}",
                original_value=f"value{i}",
                final_value=f"value{i}",
                original_confidence=0.80 + i * 0.04,
                action="accepted" if i % 2 == 0 else "edited",
                had_evidence=True,
                evidence_quality=EvidenceQuality.TEXT_GROUNDED,
                field_type=FieldTypeCategory.TEXT_SHORT,
                was_required=i < 2,
            )

        return tracker

    def test_get_all_outcomes(self, tracker_with_data):
        """Test retrieving all outcomes without filters."""
        outcomes = tracker_with_data.get_outcomes_for_analysis()
        assert len(outcomes) == 5

    def test_filter_by_job_id(self, tracker_with_data):
        """Test filtering by job ID."""
        outcomes = tracker_with_data.get_outcomes_for_analysis(job_id="job-2")
        assert len(outcomes) == 1
        assert outcomes[0].job_id == "job-2"

    def test_filter_nonexistent_job(self, tracker_with_data):
        """Test filtering by nonexistent job ID returns empty."""
        outcomes = tracker_with_data.get_outcomes_for_analysis(job_id="nonexistent")
        assert len(outcomes) == 0

    def test_empty_directory(self, tmp_path):
        """Test with empty outcomes directory."""
        tracker = OutcomeTracker(cache_dir=tmp_path)
        outcomes = tracker.get_outcomes_for_analysis()
        assert len(outcomes) == 0

    def test_filter_by_date_range(self, tmp_path):
        """Test filtering by date range."""
        tracker = OutcomeTracker(cache_dir=tmp_path)

        # Create files for different dates manually
        outcomes_dir = tmp_path / "outcomes"

        # Create outcome for yesterday
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        yesterday_file = outcomes_dir / f"{yesterday.strftime('%Y-%m-%d')}.jsonl"
        yesterday_outcome = ExtractionOutcome(
            job_id="old-job",
            recorded_at=yesterday,
            field_path="OldField",
            original_value="old",
            final_value="old",
            original_confidence=0.90,
            action="accepted",
            edit_distance=0,
            had_evidence=True,
            evidence_quality=EvidenceQuality.TEXT_GROUNDED,
            field_type=FieldTypeCategory.TEXT_SHORT,
            was_required=False,
        )
        with open(yesterday_file, "w") as f:
            f.write(yesterday_outcome.model_dump_json() + "\n")

        # Create outcome for today
        today = datetime.now(timezone.utc)
        today_file = outcomes_dir / f"{today.strftime('%Y-%m-%d')}.jsonl"
        today_outcome = ExtractionOutcome(
            job_id="new-job",
            recorded_at=today,
            field_path="NewField",
            original_value="new",
            final_value="new",
            original_confidence=0.95,
            action="accepted",
            edit_distance=0,
            had_evidence=True,
            evidence_quality=EvidenceQuality.TEXT_GROUNDED,
            field_type=FieldTypeCategory.TEXT_SHORT,
            was_required=False,
        )
        with open(today_file, "w") as f:
            f.write(today_outcome.model_dump_json() + "\n")

        # Get all
        all_outcomes = tracker.get_outcomes_for_analysis()
        assert len(all_outcomes) == 2

        # Get only today
        today_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
        today_outcomes = tracker.get_outcomes_for_analysis(start_date=today_start)
        assert len(today_outcomes) == 1
        assert today_outcomes[0].job_id == "new-job"

        # Get only yesterday
        yesterday_end = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
        yesterday_start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_outcomes = tracker.get_outcomes_for_analysis(
            start_date=yesterday_start, end_date=yesterday_end
        )
        assert len(yesterday_outcomes) == 1
        assert yesterday_outcomes[0].job_id == "old-job"


class TestComputeCorrectionRates:
    """Test suite for compute_correction_rates method."""

    @pytest.fixture
    def outcomes(self) -> list[ExtractionOutcome]:
        """Create sample outcomes for testing."""
        now = datetime.now(timezone.utc)

        return [
            # High confidence (0.9-1.0) - 3 accepted, 1 edited
            ExtractionOutcome(
                job_id="job-1",
                recorded_at=now,
                field_path="Field1",
                original_value="v1",
                final_value="v1",
                original_confidence=0.95,
                action="accepted",
                edit_distance=0,
                had_evidence=True,
                evidence_quality=EvidenceQuality.TEXT_GROUNDED,
                field_type=FieldTypeCategory.IDENTIFIER,
                was_required=True,
            ),
            ExtractionOutcome(
                job_id="job-2",
                recorded_at=now,
                field_path="Field2",
                original_value="v2",
                final_value="v2",
                original_confidence=0.92,
                action="accepted",
                edit_distance=0,
                had_evidence=True,
                evidence_quality=EvidenceQuality.TEXT_GROUNDED,
                field_type=FieldTypeCategory.IDENTIFIER,
                was_required=True,
            ),
            ExtractionOutcome(
                job_id="job-3",
                recorded_at=now,
                field_path="Field3",
                original_value="v3",
                final_value="v3",
                original_confidence=0.98,
                action="accepted",
                edit_distance=0,
                had_evidence=True,
                evidence_quality=EvidenceQuality.TEXT_GROUNDED,
                field_type=FieldTypeCategory.IDENTIFIER,
                was_required=True,
            ),
            ExtractionOutcome(
                job_id="job-4",
                recorded_at=now,
                field_path="Field4",
                original_value="v4",
                final_value="v4-fixed",
                original_confidence=0.91,
                action="edited",
                edit_distance=6,
                had_evidence=True,
                evidence_quality=EvidenceQuality.TEXT_GROUNDED,
                field_type=FieldTypeCategory.IDENTIFIER,
                was_required=True,
            ),
            # Medium confidence (0.8-0.9) - 1 accepted, 2 edited
            ExtractionOutcome(
                job_id="job-5",
                recorded_at=now,
                field_path="Field5",
                original_value="v5",
                final_value="v5",
                original_confidence=0.85,
                action="accepted",
                edit_distance=0,
                had_evidence=True,
                evidence_quality=EvidenceQuality.TEXT_GROUNDED,
                field_type=FieldTypeCategory.TEXT_SHORT,
                was_required=False,
            ),
            ExtractionOutcome(
                job_id="job-6",
                recorded_at=now,
                field_path="Field6",
                original_value="v6",
                final_value="v6-new",
                original_confidence=0.82,
                action="edited",
                edit_distance=4,
                had_evidence=True,
                evidence_quality=EvidenceQuality.TEXT_INFERRED,
                field_type=FieldTypeCategory.TEXT_SHORT,
                was_required=False,
            ),
            ExtractionOutcome(
                job_id="job-7",
                recorded_at=now,
                field_path="Field7",
                original_value="v7",
                final_value=None,
                original_confidence=0.80,
                action="deleted",
                edit_distance=2,
                had_evidence=False,
                evidence_quality=EvidenceQuality.NONE,
                field_type=FieldTypeCategory.TEXT_SHORT,
                was_required=False,
            ),
            # Low confidence (0.6-0.7) - 0 accepted, 1 rejected
            ExtractionOutcome(
                job_id="job-8",
                recorded_at=now,
                field_path="Field8",
                original_value="wrong",
                final_value="correct",
                original_confidence=0.65,
                action="rejected",
                edit_distance=7,
                had_evidence=False,
                evidence_quality=EvidenceQuality.NONE,
                field_type=FieldTypeCategory.TEXT_LONG,
                was_required=True,
            ),
            # Very low confidence (0.0-0.6) - 0 accepted, 2 rejected
            ExtractionOutcome(
                job_id="job-9",
                recorded_at=now,
                field_path="Field9",
                original_value="bad",
                final_value="good",
                original_confidence=0.40,
                action="rejected",
                edit_distance=4,
                had_evidence=False,
                evidence_quality=EvidenceQuality.NONE,
                field_type=FieldTypeCategory.TEXT_SHORT,
                was_required=False,
            ),
            ExtractionOutcome(
                job_id="job-10",
                recorded_at=now,
                field_path="Field10",
                original_value="terrible",
                final_value=None,
                original_confidence=0.20,
                action="deleted",
                edit_distance=8,
                had_evidence=False,
                evidence_quality=EvidenceQuality.NONE,
                field_type=FieldTypeCategory.TEXT_SHORT,
                was_required=False,
            ),
        ]

    def test_correction_rates_structure(self, tmp_path, outcomes):
        """Test that correction rates have correct structure."""
        tracker = OutcomeTracker(cache_dir=tmp_path)
        rates = tracker.compute_correction_rates(outcomes=outcomes)

        # Check all buckets exist
        assert "0.9-1.0" in rates
        assert "0.8-0.9" in rates
        assert "0.7-0.8" in rates
        assert "0.6-0.7" in rates
        assert "0.0-0.6" in rates

        # Check bucket structure
        for bucket in rates.values():
            assert "total" in bucket
            assert "accepted" in bucket
            assert "edited" in bucket
            assert "deleted" in bucket
            assert "rejected" in bucket
            assert "correction_rate" in bucket

    def test_high_confidence_bucket(self, tmp_path, outcomes):
        """Test correction rate for high confidence bucket."""
        tracker = OutcomeTracker(cache_dir=tmp_path)
        rates = tracker.compute_correction_rates(outcomes=outcomes)

        bucket = rates["0.9-1.0"]
        assert bucket["total"] == 4
        assert bucket["accepted"] == 3
        assert bucket["edited"] == 1
        assert bucket["correction_rate"] == 0.25  # 1/4

    def test_medium_confidence_bucket(self, tmp_path, outcomes):
        """Test correction rate for medium confidence bucket."""
        tracker = OutcomeTracker(cache_dir=tmp_path)
        rates = tracker.compute_correction_rates(outcomes=outcomes)

        bucket = rates["0.8-0.9"]
        assert bucket["total"] == 3
        assert bucket["accepted"] == 1
        assert bucket["edited"] == 1
        assert bucket["deleted"] == 1
        # 2 corrections out of 3
        assert bucket["correction_rate"] == pytest.approx(0.6667, rel=0.01)

    def test_low_confidence_bucket(self, tmp_path, outcomes):
        """Test correction rate for low confidence bucket."""
        tracker = OutcomeTracker(cache_dir=tmp_path)
        rates = tracker.compute_correction_rates(outcomes=outcomes)

        bucket = rates["0.6-0.7"]
        assert bucket["total"] == 1
        assert bucket["accepted"] == 0
        assert bucket["rejected"] == 1
        assert bucket["correction_rate"] == 1.0  # All corrected

    def test_very_low_confidence_bucket(self, tmp_path, outcomes):
        """Test correction rate for very low confidence bucket."""
        tracker = OutcomeTracker(cache_dir=tmp_path)
        rates = tracker.compute_correction_rates(outcomes=outcomes)

        bucket = rates["0.0-0.6"]
        assert bucket["total"] == 2
        assert bucket["accepted"] == 0
        assert bucket["rejected"] == 1
        assert bucket["deleted"] == 1
        assert bucket["correction_rate"] == 1.0  # All corrected

    def test_empty_bucket(self, tmp_path, outcomes):
        """Test that empty buckets have zero correction rate."""
        tracker = OutcomeTracker(cache_dir=tmp_path)
        rates = tracker.compute_correction_rates(outcomes=outcomes)

        bucket = rates["0.7-0.8"]
        assert bucket["total"] == 0
        assert bucket["correction_rate"] == 0.0

    def test_empty_outcomes(self, tmp_path):
        """Test with no outcomes."""
        tracker = OutcomeTracker(cache_dir=tmp_path)
        rates = tracker.compute_correction_rates(outcomes=[])

        for bucket in rates.values():
            assert bucket["total"] == 0
            assert bucket["correction_rate"] == 0.0

    def test_boundary_confidence_values(self, tmp_path):
        """Test confidence values at bucket boundaries."""
        tracker = OutcomeTracker(cache_dir=tmp_path)

        now = datetime.now(timezone.utc)
        boundary_outcomes = [
            # 1.0 should be in 0.9-1.0
            ExtractionOutcome(
                job_id="j1",
                recorded_at=now,
                field_path="F1",
                original_value="v",
                final_value="v",
                original_confidence=1.0,
                action="accepted",
                edit_distance=0,
                had_evidence=True,
                evidence_quality=EvidenceQuality.TEXT_GROUNDED,
                field_type=FieldTypeCategory.IDENTIFIER,
                was_required=True,
            ),
            # 0.9 should be in 0.9-1.0
            ExtractionOutcome(
                job_id="j2",
                recorded_at=now,
                field_path="F2",
                original_value="v",
                final_value="v",
                original_confidence=0.9,
                action="accepted",
                edit_distance=0,
                had_evidence=True,
                evidence_quality=EvidenceQuality.TEXT_GROUNDED,
                field_type=FieldTypeCategory.IDENTIFIER,
                was_required=True,
            ),
            # 0.8 should be in 0.8-0.9
            ExtractionOutcome(
                job_id="j3",
                recorded_at=now,
                field_path="F3",
                original_value="v",
                final_value="v",
                original_confidence=0.8,
                action="accepted",
                edit_distance=0,
                had_evidence=True,
                evidence_quality=EvidenceQuality.TEXT_GROUNDED,
                field_type=FieldTypeCategory.IDENTIFIER,
                was_required=True,
            ),
            # 0.0 should be in 0.0-0.6
            ExtractionOutcome(
                job_id="j4",
                recorded_at=now,
                field_path="F4",
                original_value="v",
                final_value="x",
                original_confidence=0.0,
                action="rejected",
                edit_distance=1,
                had_evidence=False,
                evidence_quality=EvidenceQuality.NONE,
                field_type=FieldTypeCategory.IDENTIFIER,
                was_required=True,
            ),
        ]

        rates = tracker.compute_correction_rates(outcomes=boundary_outcomes)

        assert rates["0.9-1.0"]["total"] == 2
        assert rates["0.8-0.9"]["total"] == 1
        assert rates["0.0-0.6"]["total"] == 1


class TestCorrectionRatesFromStorage:
    """Test compute_correction_rates when fetching from storage."""

    def test_fetch_from_storage(self, tmp_path):
        """Test that correction rates can fetch from storage."""
        tracker = OutcomeTracker(cache_dir=tmp_path)

        # Record some outcomes
        for i in range(3):
            tracker.record_correction(
                job_id=f"job-{i}",
                field_path=f"Field{i}",
                original_value=f"value{i}",
                final_value=f"value{i}",
                original_confidence=0.95,
                action="accepted",
                had_evidence=True,
                evidence_quality=EvidenceQuality.TEXT_GROUNDED,
                field_type=FieldTypeCategory.TEXT_SHORT,
                was_required=False,
            )

        # Compute without passing outcomes - should fetch from storage
        rates = tracker.compute_correction_rates(days=1)

        assert rates["0.9-1.0"]["total"] == 3
        assert rates["0.9-1.0"]["accepted"] == 3
        assert rates["0.9-1.0"]["correction_rate"] == 0.0


class TestIntegration:
    """Integration tests for OutcomeTracker."""

    def test_full_workflow(self, tmp_path):
        """Test complete workflow: record, retrieve, analyze."""
        tracker = OutcomeTracker(cache_dir=tmp_path)

        # Simulate user session
        # High confidence extractions - mostly accepted
        for i in range(10):
            tracker.record_correction(
                job_id=f"job-high-{i}",
                field_path=f"HighField{i}",
                original_value=f"high-{i}",
                final_value=f"high-{i}" if i < 9 else f"high-{i}-fixed",
                original_confidence=0.92 + i * 0.008,
                action="accepted" if i < 9 else "edited",
                had_evidence=True,
                evidence_quality=EvidenceQuality.TABLE_STRUCTURED,
                field_type=FieldTypeCategory.IDENTIFIER,
                was_required=True,
            )

        # Low confidence extractions - mostly edited/rejected
        for i in range(5):
            tracker.record_correction(
                job_id=f"job-low-{i}",
                field_path=f"LowField{i}",
                original_value=f"low-{i}",
                final_value=f"corrected-{i}",
                original_confidence=0.45 + i * 0.03,
                action="rejected" if i < 4 else "accepted",
                had_evidence=False,
                evidence_quality=EvidenceQuality.NONE,
                field_type=FieldTypeCategory.TEXT_LONG,
                was_required=False,
            )

        # Retrieve all
        all_outcomes = tracker.get_outcomes_for_analysis()
        assert len(all_outcomes) == 15

        # Analyze
        rates = tracker.compute_correction_rates(outcomes=all_outcomes)

        # High confidence bucket should have low correction rate
        assert rates["0.9-1.0"]["correction_rate"] < 0.2  # < 20% corrections

        # Low confidence bucket should have high correction rate
        assert rates["0.0-0.6"]["correction_rate"] > 0.5  # > 50% corrections

    def test_persistence_across_instances(self, tmp_path):
        """Test that data persists across tracker instances."""
        # First tracker writes data
        tracker1 = OutcomeTracker(cache_dir=tmp_path)
        tracker1.record_correction(
            job_id="persist-test",
            field_path="Field",
            original_value="v1",
            final_value="v1",
            original_confidence=0.90,
            action="accepted",
            had_evidence=True,
            evidence_quality=EvidenceQuality.TEXT_GROUNDED,
            field_type=FieldTypeCategory.TEXT_SHORT,
            was_required=False,
        )

        # Second tracker should read the same data
        tracker2 = OutcomeTracker(cache_dir=tmp_path)
        outcomes = tracker2.get_outcomes_for_analysis(job_id="persist-test")

        assert len(outcomes) == 1
        assert outcomes[0].job_id == "persist-test"
