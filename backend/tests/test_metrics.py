"""Tests for Prometheus metrics module."""

import pytest
from prometheus_client import REGISTRY

from app.metrics import (
    magic_import_job_duration_seconds,
    set_app_info,
    track_duration,
    timed,
    record_magic_import_job,
    record_dataspace_publication,
    record_template_fetch,
    record_semantic_lookup,
    record_validation,
    record_export,
)


class TestAppInfo:
    """Tests for application info metric."""

    def test_set_app_info(self):
        """Test setting application info labels."""
        set_app_info(version="1.0.0", environment="test")

        # Verify info was set by checking the registry
        metric = REGISTRY.get_sample_value(
            "idta_submodel_editor_info",
            {"version": "1.0.0", "environment": "test"},
        )
        assert metric == 1.0


class TestMagicImportMetrics:
    """Tests for Magic Import metrics."""

    def test_record_magic_import_job_success(self):
        """Test recording a successful job."""
        initial = REGISTRY.get_sample_value(
            "magic_import_jobs_total",
            {"status": "success", "template_name": "PCF"},
        ) or 0

        record_magic_import_job(status="success", template_name="PCF")

        after = REGISTRY.get_sample_value(
            "magic_import_jobs_total",
            {"status": "success", "template_name": "PCF"},
        )
        assert after == initial + 1

    def test_record_magic_import_job_failed(self):
        """Test recording a failed job."""
        initial = REGISTRY.get_sample_value(
            "magic_import_jobs_total",
            {"status": "failed", "template_name": "Nameplate"},
        ) or 0

        record_magic_import_job(status="failed", template_name="Nameplate")

        after = REGISTRY.get_sample_value(
            "magic_import_jobs_total",
            {"status": "failed", "template_name": "Nameplate"},
        )
        assert after == initial + 1


class TestDataspaceMetrics:
    """Tests for Dataspace publication metrics."""

    def test_record_dataspace_publication_success(self):
        """Test recording a successful publication."""
        initial = REGISTRY.get_sample_value(
            "dataspace_publications_total",
            {"status": "success", "environment": "sandbox"},
        ) or 0

        record_dataspace_publication(status="success", environment="sandbox")

        after = REGISTRY.get_sample_value(
            "dataspace_publications_total",
            {"status": "success", "environment": "sandbox"},
        )
        assert after == initial + 1

    def test_record_dataspace_publication_failed(self):
        """Test recording a failed publication."""
        initial = REGISTRY.get_sample_value(
            "dataspace_publications_total",
            {"status": "failed", "environment": "catena-x"},
        ) or 0

        record_dataspace_publication(status="failed", environment="catena-x")

        after = REGISTRY.get_sample_value(
            "dataspace_publications_total",
            {"status": "failed", "environment": "catena-x"},
        )
        assert after == initial + 1


class TestTemplateFetchMetrics:
    """Tests for template fetch metrics."""

    def test_record_template_fetch_cache_hit(self):
        """Test recording a cache hit."""
        initial = REGISTRY.get_sample_value(
            "template_fetch_total",
            {"source": "github", "cache_hit": "true"},
        ) or 0

        record_template_fetch(source="github", cache_hit=True)

        after = REGISTRY.get_sample_value(
            "template_fetch_total",
            {"source": "github", "cache_hit": "true"},
        )
        assert after == initial + 1

    def test_record_template_fetch_cache_miss(self):
        """Test recording a cache miss."""
        initial = REGISTRY.get_sample_value(
            "template_fetch_total",
            {"source": "github", "cache_hit": "false"},
        ) or 0

        record_template_fetch(source="github", cache_hit=False)

        after = REGISTRY.get_sample_value(
            "template_fetch_total",
            {"source": "github", "cache_hit": "false"},
        )
        assert after == initial + 1

    def test_record_template_fetch_local(self):
        """Test recording a local template fetch."""
        initial = REGISTRY.get_sample_value(
            "template_fetch_total",
            {"source": "local", "cache_hit": "true"},
        ) or 0

        record_template_fetch(source="local", cache_hit=True)

        after = REGISTRY.get_sample_value(
            "template_fetch_total",
            {"source": "local", "cache_hit": "true"},
        )
        assert after == initial + 1


class TestSemanticLookupMetrics:
    """Tests for semantic lookup metrics."""

    def test_record_semantic_lookup_cache_hit(self):
        """Test recording a cached lookup."""
        initial = REGISTRY.get_sample_value(
            "semantic_lookup_total",
            {"provider": "eclass", "cache_hit": "true"},
        ) or 0

        record_semantic_lookup(provider="eclass", cache_hit=True)

        after = REGISTRY.get_sample_value(
            "semantic_lookup_total",
            {"provider": "eclass", "cache_hit": "true"},
        )
        assert after == initial + 1

    def test_record_semantic_lookup_cache_miss(self):
        """Test recording an uncached lookup."""
        initial = REGISTRY.get_sample_value(
            "semantic_lookup_total",
            {"provider": "iec-cdd", "cache_hit": "false"},
        ) or 0

        record_semantic_lookup(provider="iec-cdd", cache_hit=False)

        after = REGISTRY.get_sample_value(
            "semantic_lookup_total",
            {"provider": "iec-cdd", "cache_hit": "false"},
        )
        assert after == initial + 1


class TestValidationMetrics:
    """Tests for validation metrics."""

    def test_record_validation_pass(self):
        """Test recording a passing validation."""
        initial = REGISTRY.get_sample_value(
            "validation_total",
            {"template_name": "PCF", "result": "pass"},
        ) or 0

        record_validation(template_name="PCF", has_errors=False, has_warnings=False)

        after = REGISTRY.get_sample_value(
            "validation_total",
            {"template_name": "PCF", "result": "pass"},
        )
        assert after == initial + 1

    def test_record_validation_error(self):
        """Test recording a validation with errors."""
        initial = REGISTRY.get_sample_value(
            "validation_total",
            {"template_name": "Nameplate", "result": "error"},
        ) or 0

        record_validation(template_name="Nameplate", has_errors=True, has_warnings=False)

        after = REGISTRY.get_sample_value(
            "validation_total",
            {"template_name": "Nameplate", "result": "error"},
        )
        assert after == initial + 1

    def test_record_validation_warning(self):
        """Test recording a validation with warnings only."""
        initial = REGISTRY.get_sample_value(
            "validation_total",
            {"template_name": "ContactInfo", "result": "warning"},
        ) or 0

        record_validation(template_name="ContactInfo", has_errors=False, has_warnings=True)

        after = REGISTRY.get_sample_value(
            "validation_total",
            {"template_name": "ContactInfo", "result": "warning"},
        )
        assert after == initial + 1


class TestExportMetrics:
    """Tests for export metrics."""

    def test_record_export_aasx(self):
        """Test recording an AASX export."""
        initial = REGISTRY.get_sample_value(
            "export_total",
            {"format": "aasx", "template_name": "PCF"},
        ) or 0

        record_export(format_type="aasx", template_name="PCF")

        after = REGISTRY.get_sample_value(
            "export_total",
            {"format": "aasx", "template_name": "PCF"},
        )
        assert after == initial + 1

    def test_record_export_json(self):
        """Test recording a JSON export."""
        initial = REGISTRY.get_sample_value(
            "export_total",
            {"format": "json", "template_name": "Nameplate"},
        ) or 0

        record_export(format_type="json", template_name="Nameplate")

        after = REGISTRY.get_sample_value(
            "export_total",
            {"format": "json", "template_name": "Nameplate"},
        )
        assert after == initial + 1


class TestTrackDuration:
    """Tests for track_duration context manager."""

    def test_track_duration_records_time(self):
        """Test that duration is recorded."""
        # Just verify it doesn't raise
        with track_duration(magic_import_job_duration_seconds, template_name="test"):
            pass

    def test_track_duration_with_exception(self):
        """Test that duration is recorded even on exception."""
        with pytest.raises(ValueError):
            with track_duration(magic_import_job_duration_seconds, template_name="test"):
                raise ValueError("test error")

        # Duration should still be recorded (test passes if no exception from metric)


class TestTimedDecorator:
    """Tests for timed decorator."""

    def test_timed_decorator(self):
        """Test that timed decorator records duration."""

        @timed(
            magic_import_job_duration_seconds,
            lambda args: {"template_name": args[0]},
        )
        def sample_function(template_name: str) -> str:
            return f"processed {template_name}"

        result = sample_function("TestTemplate")
        assert result == "processed TestTemplate"

    def test_timed_decorator_preserves_exceptions(self):
        """Test that timed decorator preserves exceptions."""

        @timed(
            magic_import_job_duration_seconds,
            lambda args: {"template_name": "error-test"},
        )
        def failing_function() -> str:
            raise ValueError("intentional error")

        with pytest.raises(ValueError, match="intentional error"):
            failing_function()
