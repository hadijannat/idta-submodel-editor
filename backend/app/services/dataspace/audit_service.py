"""
Audit Service - Logs and retrieves dataspace audit events.

Provides comprehensive audit trail of all dataspace operations including
connections, publications, negotiations, transfers, and policy changes.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.services.dataspace.models import AuditEventType, AuditLogEntry

logger = logging.getLogger(__name__)


class AuditService:
    """
    Manages audit log entries for dataspace events.

    Uses file-based storage with date partitioning for efficient querying.
    Logs are stored in cache/dataspace/audit/YYYY-MM-DD.jsonl format.
    """

    def __init__(self) -> None:
        """Initialize audit service with cache directory."""
        self.settings = get_settings()
        self.base_dir = self.settings.cache_dir.parent / "dataspace"
        self.audit_dir = self.base_dir / "audit"
        self.audit_dir.mkdir(parents=True, exist_ok=True)

    def log_event(
        self,
        event_type: AuditEventType,
        action: str,
        connection_id: str | None = None,
        resource_id: str | None = None,
        resource_type: str | None = None,
        actor: str | None = None,
        details: dict[str, Any] | None = None,
        success: bool = True,
        error_message: str | None = None,
    ) -> AuditLogEntry:
        """
        Log an audit event.

        Args:
            event_type: Type of event
            action: Human-readable action description
            connection_id: Related connection ID
            resource_id: Related resource ID (publication, transfer, etc.)
            resource_type: Type of resource (connection, publication, transfer, etc.)
            actor: User or system ID that performed the action
            details: Additional event details
            success: Whether the action succeeded
            error_message: Error message if action failed

        Returns:
            Created audit log entry
        """
        entry_id = uuid.uuid4().hex
        now = datetime.utcnow()

        entry = AuditLogEntry(
            entry_id=entry_id,
            event_type=event_type,
            timestamp=now,
            connection_id=connection_id,
            resource_id=resource_id,
            resource_type=resource_type,
            actor=actor,
            action=action,
            details=details or {},
            success=success,
            error_message=error_message,
        )

        self._save_entry(entry)
        logger.debug(
            "Logged audit event %s: %s (success=%s)",
            event_type.value,
            action,
            success,
        )
        return entry

    def get_entry(self, entry_id: str) -> AuditLogEntry | None:
        """
        Get a specific audit entry by ID.

        Searches all date-partitioned files for the entry.
        """
        # Search through all log files
        for log_file in sorted(self.audit_dir.glob("*.jsonl"), reverse=True):
            with open(log_file, "r") as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        if data.get("entry_id") == entry_id:
                            return AuditLogEntry.from_dict(data)
                    except json.JSONDecodeError:
                        continue
        return None

    def list_entries(
        self,
        connection_id: str | None = None,
        event_type: AuditEventType | None = None,
        resource_type: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        success: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[AuditLogEntry], int]:
        """
        List audit entries with optional filters.

        Args:
            connection_id: Filter by connection ID
            event_type: Filter by event type
            resource_type: Filter by resource type
            start_date: Filter entries after this date
            end_date: Filter entries before this date
            success: Filter by success status
            limit: Maximum entries to return
            offset: Number of entries to skip

        Returns:
            Tuple of (entries, total_count)
        """
        entries: list[AuditLogEntry] = []

        # Determine which files to search
        if start_date and end_date:
            # Only search files within date range
            log_files = self._get_files_in_range(start_date, end_date)
        else:
            # Search all files (most recent first)
            log_files = sorted(self.audit_dir.glob("*.jsonl"), reverse=True)

        # Read and filter entries
        for log_file in log_files:
            file_entries = self._read_file_entries(
                log_file,
                connection_id=connection_id,
                event_type=event_type,
                resource_type=resource_type,
                start_date=start_date,
                end_date=end_date,
                success=success,
            )
            entries.extend(file_entries)

        # Sort by timestamp descending
        entries.sort(key=lambda e: e.timestamp, reverse=True)

        # Get total count before pagination
        total = len(entries)

        # Apply pagination
        entries = entries[offset : offset + limit]

        return entries, total

    def _save_entry(self, entry: AuditLogEntry) -> None:
        """Save entry to date-partitioned file."""
        date_str = entry.timestamp.strftime("%Y-%m-%d")
        log_file = self.audit_dir / f"{date_str}.jsonl"

        with open(log_file, "a") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")

    def _get_files_in_range(
        self, start_date: datetime, end_date: datetime
    ) -> list[Path]:
        """Get log files within a date range."""
        files = []
        current = start_date.date()
        end = end_date.date()

        while current <= end:
            date_str = current.strftime("%Y-%m-%d")
            log_file = self.audit_dir / f"{date_str}.jsonl"
            if log_file.exists():
                files.append(log_file)
            current += timedelta(days=1)

        # Return in reverse chronological order
        return sorted(files, reverse=True)

    def _read_file_entries(
        self,
        log_file: Path,
        connection_id: str | None = None,
        event_type: AuditEventType | None = None,
        resource_type: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        success: bool | None = None,
    ) -> list[AuditLogEntry]:
        """Read and filter entries from a log file."""
        entries = []

        try:
            with open(log_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        data = json.loads(line)
                        entry = AuditLogEntry.from_dict(data)

                        # Apply filters
                        if connection_id and entry.connection_id != connection_id:
                            continue
                        if event_type and entry.event_type != event_type:
                            continue
                        if resource_type and entry.resource_type != resource_type:
                            continue
                        if start_date and entry.timestamp < start_date:
                            continue
                        if end_date and entry.timestamp > end_date:
                            continue
                        if success is not None and entry.success != success:
                            continue

                        entries.append(entry)

                    except (json.JSONDecodeError, KeyError, ValueError) as e:
                        logger.warning("Failed to parse audit entry: %s", e)
                        continue

        except Exception as e:
            logger.warning("Failed to read audit file %s: %s", log_file, e)

        return entries


# Convenience functions for logging specific event types


def log_connection_created(
    audit: AuditService,
    connection_id: str,
    environment: str,
    actor: str | None = None,
) -> AuditLogEntry:
    """Log a connection creation event."""
    return audit.log_event(
        event_type=AuditEventType.CONNECTION_CREATED,
        action=f"Created connection to {environment} environment",
        connection_id=connection_id,
        resource_id=connection_id,
        resource_type="connection",
        actor=actor,
        details={"environment": environment},
    )


def log_connection_connected(
    audit: AuditService,
    connection_id: str,
    actor: str | None = None,
) -> AuditLogEntry:
    """Log a successful connection event."""
    return audit.log_event(
        event_type=AuditEventType.CONNECTION_CONNECTED,
        action="Successfully connected to dataspace",
        connection_id=connection_id,
        resource_id=connection_id,
        resource_type="connection",
        actor=actor,
    )


def log_connection_failed(
    audit: AuditService,
    connection_id: str,
    error_message: str,
    actor: str | None = None,
) -> AuditLogEntry:
    """Log a failed connection event."""
    return audit.log_event(
        event_type=AuditEventType.CONNECTION_FAILED,
        action="Connection to dataspace failed",
        connection_id=connection_id,
        resource_id=connection_id,
        resource_type="connection",
        actor=actor,
        success=False,
        error_message=error_message,
    )


def log_publication_started(
    audit: AuditService,
    connection_id: str,
    publication_id: str,
    template_name: str,
    actor: str | None = None,
) -> AuditLogEntry:
    """Log publication start event."""
    return audit.log_event(
        event_type=AuditEventType.PUBLICATION_STARTED,
        action=f"Started publishing {template_name} submodel",
        connection_id=connection_id,
        resource_id=publication_id,
        resource_type="publication",
        actor=actor,
        details={"template_name": template_name},
    )


def log_publication_completed(
    audit: AuditService,
    connection_id: str,
    publication_id: str,
    template_name: str,
    actor: str | None = None,
) -> AuditLogEntry:
    """Log publication completion event."""
    return audit.log_event(
        event_type=AuditEventType.PUBLICATION_COMPLETED,
        action=f"Successfully published {template_name} submodel",
        connection_id=connection_id,
        resource_id=publication_id,
        resource_type="publication",
        actor=actor,
        details={"template_name": template_name},
    )


def log_publication_failed(
    audit: AuditService,
    connection_id: str,
    publication_id: str,
    error_message: str,
    actor: str | None = None,
) -> AuditLogEntry:
    """Log publication failure event."""
    return audit.log_event(
        event_type=AuditEventType.PUBLICATION_FAILED,
        action="Publication failed",
        connection_id=connection_id,
        resource_id=publication_id,
        resource_type="publication",
        actor=actor,
        success=False,
        error_message=error_message,
    )


def log_transfer_initiated(
    audit: AuditService,
    connection_id: str,
    transfer_id: str,
    asset_id: str,
    provider_bpn: str,
    actor: str | None = None,
) -> AuditLogEntry:
    """Log transfer initiation event."""
    return audit.log_event(
        event_type=AuditEventType.TRANSFER_INITIATED,
        action=f"Initiated transfer for asset from {provider_bpn}",
        connection_id=connection_id,
        resource_id=transfer_id,
        resource_type="transfer",
        actor=actor,
        details={"asset_id": asset_id, "provider_bpn": provider_bpn},
    )


def log_transfer_completed(
    audit: AuditService,
    connection_id: str,
    transfer_id: str,
    actor: str | None = None,
) -> AuditLogEntry:
    """Log transfer completion event."""
    return audit.log_event(
        event_type=AuditEventType.TRANSFER_COMPLETED,
        action="Data transfer completed successfully",
        connection_id=connection_id,
        resource_id=transfer_id,
        resource_type="transfer",
        actor=actor,
    )


def log_transfer_failed(
    audit: AuditService,
    connection_id: str,
    transfer_id: str,
    error_message: str,
    actor: str | None = None,
) -> AuditLogEntry:
    """Log transfer failure event."""
    return audit.log_event(
        event_type=AuditEventType.TRANSFER_FAILED,
        action="Data transfer failed",
        connection_id=connection_id,
        resource_id=transfer_id,
        resource_type="transfer",
        actor=actor,
        success=False,
        error_message=error_message,
    )


def log_negotiation_initiated(
    audit: AuditService,
    connection_id: str,
    negotiation_id: str,
    asset_id: str,
    provider_bpn: str,
    actor: str | None = None,
) -> AuditLogEntry:
    """Log negotiation initiation event."""
    return audit.log_event(
        event_type=AuditEventType.NEGOTIATION_INITIATED,
        action=f"Initiated contract negotiation with {provider_bpn}",
        connection_id=connection_id,
        resource_id=negotiation_id,
        resource_type="negotiation",
        actor=actor,
        details={"asset_id": asset_id, "provider_bpn": provider_bpn},
    )


def log_negotiation_completed(
    audit: AuditService,
    connection_id: str,
    negotiation_id: str,
    agreement_id: str,
    actor: str | None = None,
) -> AuditLogEntry:
    """Log negotiation completion event."""
    return audit.log_event(
        event_type=AuditEventType.NEGOTIATION_COMPLETED,
        action="Contract negotiation finalized",
        connection_id=connection_id,
        resource_id=negotiation_id,
        resource_type="negotiation",
        actor=actor,
        details={"agreement_id": agreement_id},
    )


def log_catalog_searched(
    audit: AuditService,
    connection_id: str,
    provider_bpn: str,
    results_count: int,
    actor: str | None = None,
) -> AuditLogEntry:
    """Log catalog search event."""
    return audit.log_event(
        event_type=AuditEventType.CATALOG_SEARCHED,
        action=f"Searched catalog from {provider_bpn}",
        connection_id=connection_id,
        resource_type="catalog",
        actor=actor,
        details={"provider_bpn": provider_bpn, "results_count": results_count},
    )
