"""
Tests for the AuditService.

Tests audit log creation, retrieval, filtering, and persistence.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.services.dataspace.audit_service import AuditService
from app.services.dataspace.models import AuditEventType, AuditLogEntry


class TestAuditServiceLogEvent:
    """Tests for AuditService.log_event()."""

    def test_log_event_creates_entry(self, mock_audit_service):
        """Test that log_event creates an audit entry."""
        entry = mock_audit_service.log_event(
            event_type=AuditEventType.CONNECTION_CREATED,
            action="Created sandbox connection",
            connection_id="test-conn-001",
        )

        assert entry is not None
        assert entry.entry_id is not None
        assert entry.event_type == AuditEventType.CONNECTION_CREATED
        assert entry.action == "Created sandbox connection"
        assert entry.connection_id == "test-conn-001"
        assert entry.success is True

    def test_log_event_with_all_fields(self, mock_audit_service):
        """Test log_event with all optional fields."""
        entry = mock_audit_service.log_event(
            event_type=AuditEventType.PUBLICATION_COMPLETED,
            action="Published Nameplate submodel",
            connection_id="test-conn-001",
            resource_id="pub-001",
            resource_type="publication",
            actor="user@example.com",
            details={"template": "Nameplate", "version": "1.0"},
            success=True,
        )

        assert entry.resource_id == "pub-001"
        assert entry.resource_type == "publication"
        assert entry.actor == "user@example.com"
        assert entry.details == {"template": "Nameplate", "version": "1.0"}

    def test_log_event_failure(self, mock_audit_service):
        """Test logging a failed event."""
        entry = mock_audit_service.log_event(
            event_type=AuditEventType.TRANSFER_FAILED,
            action="Transfer failed",
            connection_id="test-conn-001",
            resource_id="transfer-001",
            success=False,
            error_message="Provider timeout",
        )

        assert entry.success is False
        assert entry.error_message == "Provider timeout"

    def test_log_event_persists_to_file(self, mock_audit_service, temp_dataspace_dir):
        """Test that log_event persists entry to file."""
        entry = mock_audit_service.log_event(
            event_type=AuditEventType.CONNECTION_CONNECTED,
            action="Connected to dataspace",
            connection_id="test-conn-001",
        )

        # Check file was created (service uses cache_dir.parent / "dataspace" / "audit")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_file = temp_dataspace_dir / "dataspace" / "audit" / f"{today}.jsonl"
        assert log_file.exists()

        # Check entry was written
        with open(log_file, "r") as f:
            lines = f.readlines()
            assert len(lines) >= 1
            last_entry = json.loads(lines[-1])
            assert last_entry["entry_id"] == entry.entry_id

    def test_log_event_generates_unique_ids(self, mock_audit_service):
        """Test that each log entry gets a unique ID."""
        entries = [
            mock_audit_service.log_event(
                event_type=AuditEventType.CONNECTION_CREATED,
                action=f"Action {i}",
            )
            for i in range(5)
        ]

        entry_ids = [e.entry_id for e in entries]
        assert len(set(entry_ids)) == 5  # All unique


class TestAuditServiceGetEntry:
    """Tests for AuditService.get_entry()."""

    def test_get_entry_returns_entry(self, mock_audit_service):
        """Test retrieving a specific entry by ID."""
        created = mock_audit_service.log_event(
            event_type=AuditEventType.CONNECTION_CREATED,
            action="Test action",
            connection_id="test-conn-001",
        )

        retrieved = mock_audit_service.get_entry(created.entry_id)

        assert retrieved is not None
        assert retrieved.entry_id == created.entry_id
        assert retrieved.action == "Test action"

    def test_get_entry_not_found(self, mock_audit_service):
        """Test that get_entry returns None for non-existent ID."""
        result = mock_audit_service.get_entry("non-existent-id")
        assert result is None

    def test_get_entry_searches_multiple_files(self, mock_audit_service, temp_dataspace_dir):
        """Test that get_entry searches across date-partitioned files."""
        # Create an entry for "yesterday" by writing directly
        # Service uses cache_dir.parent / "dataspace" / "audit"
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        yesterday_file = temp_dataspace_dir / "dataspace" / "audit" / f"{yesterday}.jsonl"
        yesterday_file.parent.mkdir(parents=True, exist_ok=True)

        old_entry = AuditLogEntry(
            entry_id="old-entry-001",
            event_type=AuditEventType.CONNECTION_CREATED,
            action="Old action",
            timestamp=datetime.now(timezone.utc) - timedelta(days=1),
        )

        with open(yesterday_file, "w") as f:
            f.write(json.dumps(old_entry.to_dict()) + "\n")

        # Should find the old entry
        retrieved = mock_audit_service.get_entry("old-entry-001")
        assert retrieved is not None
        assert retrieved.entry_id == "old-entry-001"


class TestAuditServiceListEntries:
    """Tests for AuditService.list_entries()."""

    def test_list_entries_returns_all(self, mock_audit_service):
        """Test listing all entries."""
        # Create some entries
        for i in range(5):
            mock_audit_service.log_event(
                event_type=AuditEventType.CONNECTION_CREATED,
                action=f"Action {i}",
                connection_id="test-conn-001",
            )

        entries, total = mock_audit_service.list_entries()

        assert len(entries) == 5
        assert total == 5

    def test_list_entries_filter_by_connection(self, mock_audit_service):
        """Test filtering by connection_id."""
        mock_audit_service.log_event(
            event_type=AuditEventType.CONNECTION_CREATED,
            action="Action 1",
            connection_id="conn-001",
        )
        mock_audit_service.log_event(
            event_type=AuditEventType.CONNECTION_CREATED,
            action="Action 2",
            connection_id="conn-002",
        )
        mock_audit_service.log_event(
            event_type=AuditEventType.CONNECTION_CONNECTED,
            action="Action 3",
            connection_id="conn-001",
        )

        entries, total = mock_audit_service.list_entries(connection_id="conn-001")

        assert len(entries) == 2
        assert total == 2
        assert all(e.connection_id == "conn-001" for e in entries)

    def test_list_entries_filter_by_event_type(self, mock_audit_service):
        """Test filtering by event_type."""
        mock_audit_service.log_event(
            event_type=AuditEventType.CONNECTION_CREATED,
            action="Created",
        )
        mock_audit_service.log_event(
            event_type=AuditEventType.CONNECTION_CONNECTED,
            action="Connected",
        )
        mock_audit_service.log_event(
            event_type=AuditEventType.CONNECTION_CONNECTED,
            action="Connected again",
        )

        entries, total = mock_audit_service.list_entries(
            event_type=AuditEventType.CONNECTION_CONNECTED
        )

        assert len(entries) == 2
        assert all(e.event_type == AuditEventType.CONNECTION_CONNECTED for e in entries)

    def test_list_entries_filter_by_success(self, mock_audit_service):
        """Test filtering by success status."""
        mock_audit_service.log_event(
            event_type=AuditEventType.TRANSFER_COMPLETED,
            action="Success",
            success=True,
        )
        mock_audit_service.log_event(
            event_type=AuditEventType.TRANSFER_FAILED,
            action="Failed",
            success=False,
        )
        mock_audit_service.log_event(
            event_type=AuditEventType.TRANSFER_FAILED,
            action="Failed again",
            success=False,
        )

        entries, total = mock_audit_service.list_entries(success=False)

        assert len(entries) == 2
        assert all(e.success is False for e in entries)

    def test_list_entries_pagination(self, mock_audit_service):
        """Test pagination with limit and offset."""
        for i in range(10):
            mock_audit_service.log_event(
                event_type=AuditEventType.CONNECTION_CREATED,
                action=f"Action {i}",
            )

        # Get first page
        entries, total = mock_audit_service.list_entries(limit=3, offset=0)
        assert len(entries) == 3
        assert total == 10

        # Get second page
        entries2, total2 = mock_audit_service.list_entries(limit=3, offset=3)
        assert len(entries2) == 3
        assert total2 == 10

        # Entries should be different
        entry_ids_1 = {e.entry_id for e in entries}
        entry_ids_2 = {e.entry_id for e in entries2}
        assert entry_ids_1.isdisjoint(entry_ids_2)

    def test_list_entries_sorted_by_timestamp_desc(self, mock_audit_service):
        """Test that entries are sorted by timestamp descending."""
        for i in range(5):
            mock_audit_service.log_event(
                event_type=AuditEventType.CONNECTION_CREATED,
                action=f"Action {i}",
            )

        entries, _ = mock_audit_service.list_entries()

        # Most recent first
        timestamps = [e.timestamp for e in entries]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_list_entries_filter_by_date_range(self, mock_audit_service, temp_dataspace_dir):
        """Test filtering by date range."""
        today = datetime.now(timezone.utc)
        yesterday = today - timedelta(days=1)

        # Create yesterday's entry directly
        # Service uses cache_dir.parent / "dataspace" / "audit"
        yesterday_file = temp_dataspace_dir / "dataspace" / "audit" / f"{yesterday.strftime('%Y-%m-%d')}.jsonl"
        yesterday_file.parent.mkdir(parents=True, exist_ok=True)

        old_entry = AuditLogEntry(
            entry_id="old-entry",
            event_type=AuditEventType.CONNECTION_CREATED,
            action="Old action",
            timestamp=yesterday,
        )
        with open(yesterday_file, "w") as f:
            f.write(json.dumps(old_entry.to_dict()) + "\n")

        # Create today's entry
        mock_audit_service.log_event(
            event_type=AuditEventType.CONNECTION_CONNECTED,
            action="Today action",
        )

        # Filter to today only
        entries, total = mock_audit_service.list_entries(
            start_date=today.replace(hour=0, minute=0, second=0),
            end_date=today.replace(hour=23, minute=59, second=59),
        )

        assert all(e.timestamp.date() == today.date() for e in entries)


class TestAuditServicePersistence:
    """Tests for audit log persistence."""

    def test_entries_survive_service_restart(self, temp_dataspace_dir):
        """Test that entries persist across service instances."""
        from unittest.mock import MagicMock, patch

        mock_settings = MagicMock()
        mock_settings.cache_dir = temp_dataspace_dir / "cache"
        mock_settings.cache_dir.mkdir(parents=True, exist_ok=True)

        with patch("app.services.dataspace.audit_service.get_settings", return_value=mock_settings):
            # Create first service and log entry
            service1 = AuditService()
            entry = service1.log_event(
                event_type=AuditEventType.CONNECTION_CREATED,
                action="Persistent action",
            )

            # Create second service instance
            service2 = AuditService()

            # Should find the entry
            retrieved = service2.get_entry(entry.entry_id)
            assert retrieved is not None
            assert retrieved.action == "Persistent action"

    def test_multiple_entries_same_day(self, mock_audit_service, temp_dataspace_dir):
        """Test multiple entries are appended to same day file."""
        for i in range(10):
            mock_audit_service.log_event(
                event_type=AuditEventType.CONNECTION_CREATED,
                action=f"Action {i}",
            )

        # Service uses cache_dir.parent / "dataspace" / "audit"
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_file = temp_dataspace_dir / "dataspace" / "audit" / f"{today}.jsonl"

        with open(log_file, "r") as f:
            lines = f.readlines()
            assert len(lines) == 10


class TestAuditLogEntry:
    """Tests for AuditLogEntry model."""

    def test_to_dict_and_from_dict(self, sample_audit_entry):
        """Test serialization round-trip."""
        entry_dict = sample_audit_entry.to_dict()
        restored = AuditLogEntry.from_dict(entry_dict)

        assert restored.entry_id == sample_audit_entry.entry_id
        assert restored.event_type == sample_audit_entry.event_type
        assert restored.action == sample_audit_entry.action
        assert restored.connection_id == sample_audit_entry.connection_id
        assert restored.success == sample_audit_entry.success

    def test_to_dict_contains_all_fields(self, sample_audit_entry):
        """Test that to_dict contains all expected fields."""
        entry_dict = sample_audit_entry.to_dict()

        expected_keys = {
            "entry_id",
            "event_type",
            "timestamp",
            "connection_id",
            "resource_id",
            "resource_type",
            "actor",
            "action",
            "details",
            "success",
            "error_message",
        }
        assert set(entry_dict.keys()) == expected_keys
