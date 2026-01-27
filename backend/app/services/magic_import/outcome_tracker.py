"""
OutcomeTracker service for tracking user corrections to extracted values.

Tracks what users do with extracted values - whether they accept, edit, delete,
or reject them. This enables answering Q2 about evidence thresholds by correlating
extraction confidence with user corrections.

Storage: JSONL files in {cache_dir}/outcomes/ organized by date (YYYY-MM-DD.jsonl).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from app.config import get_settings
from app.schemas.magic_import import (
    EvidenceQuality,
    ExtractionOutcome,
    FieldTypeCategory,
)


def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Compute the Levenshtein (edit) distance between two strings.

    The Levenshtein distance is the minimum number of single-character edits
    (insertions, deletions, or substitutions) required to change one string
    into the other.

    Args:
        s1: First string
        s2: Second string

    Returns:
        The edit distance between the two strings
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    # Use two rows instead of full matrix for space efficiency
    previous_row = list(range(len(s2) + 1))
    current_row = [0] * (len(s2) + 1)

    for i, c1 in enumerate(s1):
        current_row[0] = i + 1
        for j, c2 in enumerate(s2):
            # Cost is 0 if characters match, 1 otherwise
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row[j + 1] = min(insertions, deletions, substitutions)
        previous_row, current_row = current_row, previous_row

    return previous_row[len(s2)]


class OutcomeTracker:
    """
    Tracks user corrections to extracted values for quality feedback loop.

    Stores outcomes in JSONL format organized by date for efficient querying
    and analysis. Supports computing correction rates by confidence bucket
    to help determine optimal confidence thresholds.
    """

    # Confidence buckets for analysis (upper bound exclusive except for 1.0)
    CONFIDENCE_BUCKETS = [
        ("0.9-1.0", 0.9, 1.0),
        ("0.8-0.9", 0.8, 0.9),
        ("0.7-0.8", 0.7, 0.8),
        ("0.6-0.7", 0.6, 0.7),
        ("0.0-0.6", 0.0, 0.6),
    ]

    def __init__(self, cache_dir: Path | None = None):
        """
        Initialize the OutcomeTracker.

        Args:
            cache_dir: Base cache directory. If not provided, uses settings.
        """
        if cache_dir is None:
            settings = get_settings()
            cache_dir = settings.magic_import_cache_dir
        self.outcomes_dir = cache_dir / "outcomes"
        self.outcomes_dir.mkdir(parents=True, exist_ok=True)

    def _get_outcome_file(self, date: datetime) -> Path:
        """Get the JSONL file path for a given date."""
        date_str = date.strftime("%Y-%m-%d")
        return self.outcomes_dir / f"{date_str}.jsonl"

    def _bucket_for_confidence(self, confidence: float) -> str | None:
        """Get the bucket name for a confidence value."""
        for bucket_name, lower, upper in self.CONFIDENCE_BUCKETS:
            if bucket_name == "0.9-1.0":
                # Include 1.0 in this bucket
                if lower <= confidence <= upper:
                    return bucket_name
            else:
                if lower <= confidence < upper:
                    return bucket_name
        return None

    def record_correction(
        self,
        job_id: str,
        field_path: str,
        original_value: str | None,
        final_value: str | None,
        original_confidence: float,
        action: Literal["accepted", "edited", "deleted", "rejected"],
        had_evidence: bool,
        evidence_quality: EvidenceQuality,
        field_type: FieldTypeCategory,
        was_required: bool,
    ) -> ExtractionOutcome:
        """
        Record a user correction and return the outcome record.

        Args:
            job_id: ID of the Magic Import job
            field_path: idShortPath of the field
            original_value: Original extracted value (None if empty)
            final_value: Final value after user action (None if deleted)
            original_confidence: Confidence of original extraction
            action: Action taken by user on extraction
            had_evidence: Whether original extraction had evidence
            evidence_quality: Quality of evidence for original extraction
            field_type: Category of the field type
            was_required: Whether the field was required

        Returns:
            The recorded ExtractionOutcome
        """
        now = datetime.now(timezone.utc)

        # Calculate edit distance
        edit_distance = 0
        if action == "edited" and original_value is not None and final_value is not None:
            edit_distance = levenshtein_distance(original_value, final_value)
        elif action == "deleted" and original_value is not None:
            # Deletion is like editing to empty string
            edit_distance = len(original_value)
        elif action == "rejected" and original_value is not None:
            # Rejection with replacement
            if final_value is not None:
                edit_distance = levenshtein_distance(original_value, final_value)
            else:
                edit_distance = len(original_value)

        outcome = ExtractionOutcome(
            job_id=job_id,
            recorded_at=now,
            field_path=field_path,
            original_value=original_value,
            final_value=final_value,
            original_confidence=original_confidence,
            action=action,
            edit_distance=edit_distance,
            had_evidence=had_evidence,
            evidence_quality=evidence_quality,
            field_type=field_type,
            was_required=was_required,
        )

        # Append to JSONL file
        outcome_file = self._get_outcome_file(now)
        with open(outcome_file, "a", encoding="utf-8") as f:
            f.write(outcome.model_dump_json() + "\n")

        return outcome

    def get_outcomes_for_analysis(
        self,
        template_name: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        job_id: str | None = None,
    ) -> list[ExtractionOutcome]:
        """
        Retrieve outcomes for analysis with optional filters.

        Args:
            template_name: Filter by template name (not used in current storage,
                          but included for future extensibility)
            start_date: Filter outcomes recorded on or after this date
            end_date: Filter outcomes recorded on or before this date
            job_id: Filter by specific job ID

        Returns:
            List of ExtractionOutcome matching the filters
        """
        outcomes: list[ExtractionOutcome] = []

        # Get all JSONL files in the outcomes directory
        if not self.outcomes_dir.exists():
            return outcomes

        jsonl_files = sorted(self.outcomes_dir.glob("*.jsonl"))

        for file_path in jsonl_files:
            # Parse date from filename
            try:
                file_date_str = file_path.stem  # YYYY-MM-DD
                file_date = datetime.strptime(file_date_str, "%Y-%m-%d").replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                continue  # Skip files with invalid date format

            # Filter by date range at file level
            if start_date is not None:
                start_date_only = start_date.replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                if start_date.tzinfo is None:
                    start_date_only = start_date_only.replace(tzinfo=timezone.utc)
                if file_date < start_date_only:
                    continue

            if end_date is not None:
                end_date_only = end_date.replace(
                    hour=23, minute=59, second=59, microsecond=999999
                )
                if end_date.tzinfo is None:
                    end_date_only = end_date_only.replace(tzinfo=timezone.utc)
                if file_date > end_date_only:
                    continue

            # Read and filter outcomes from file
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        data = json.loads(line)
                        outcome = ExtractionOutcome.model_validate(data)

                        # Apply finer-grained date filter
                        if start_date is not None and outcome.recorded_at < start_date:
                            continue
                        if end_date is not None and outcome.recorded_at > end_date:
                            continue

                        # Apply job_id filter
                        if job_id is not None and outcome.job_id != job_id:
                            continue

                        outcomes.append(outcome)
                    except (json.JSONDecodeError, ValueError):
                        # Skip malformed lines
                        continue

        return outcomes

    def compute_correction_rates(
        self,
        outcomes: list[ExtractionOutcome] | None = None,
        template_name: str | None = None,
        days: int = 30,
    ) -> dict[str, dict]:
        """
        Compute correction rates by confidence bucket.

        Args:
            outcomes: Pre-fetched outcomes to analyze. If None, fetches from storage.
            template_name: Filter by template name (only used if outcomes is None)
            days: Number of days to look back (only used if outcomes is None)

        Returns:
            Dict with bucket names as keys, containing:
            {
                "0.9-1.0": {
                    "total": 100,
                    "accepted": 90,
                    "edited": 8,
                    "deleted": 1,
                    "rejected": 1,
                    "correction_rate": 0.10
                },
                ...
            }
        """
        if outcomes is None:
            # Fetch outcomes from the last N days
            end_date = datetime.now(timezone.utc)
            start_date = end_date.replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            # Go back 'days' days
            from datetime import timedelta

            start_date = start_date - timedelta(days=days)
            outcomes = self.get_outcomes_for_analysis(
                template_name=template_name,
                start_date=start_date,
                end_date=end_date,
            )

        # Initialize buckets
        results: dict[str, dict] = {}
        for bucket_name, _, _ in self.CONFIDENCE_BUCKETS:
            results[bucket_name] = {
                "total": 0,
                "accepted": 0,
                "edited": 0,
                "deleted": 0,
                "rejected": 0,
                "correction_rate": 0.0,
            }

        # Categorize outcomes into buckets
        for outcome in outcomes:
            bucket = self._bucket_for_confidence(outcome.original_confidence)
            if bucket is None:
                continue

            results[bucket]["total"] += 1
            results[bucket][outcome.action] += 1

        # Compute correction rates
        for bucket_name in results:
            bucket_data = results[bucket_name]
            total = bucket_data["total"]
            if total > 0:
                # Correction = anything that wasn't accepted
                corrections = total - bucket_data["accepted"]
                bucket_data["correction_rate"] = round(corrections / total, 4)

        return results
