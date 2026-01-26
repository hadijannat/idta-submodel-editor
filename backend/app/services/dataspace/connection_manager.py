"""
Connection Manager - Manages dataspace connection state and persistence.

Handles connection lifecycle and persists state to cache directory for
recovery across application restarts.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from app.config import get_settings
from app.services.dataspace.models import (
    AssetRegistration,
    ConnectionState,
    ConnectionStatus,
    ContractNegotiation,
    DataspaceType,
    RegistrationStatus,
)

if TYPE_CHECKING:
    from app.services.dataspace.providers.provider_base import DataspaceProvider

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages dataspace connection state and file storage.

    Similar pattern to magic_import.job_manager but for dataspace connections.
    Persists connection state, registrations, and negotiations to disk.
    """

    def __init__(self) -> None:
        """Initialize connection manager with cache directories."""
        self.settings = get_settings()
        self.base_dir = self.settings.cache_dir.parent / "dataspace"
        self.connections_dir = self.base_dir / "connections"
        self.registrations_dir = self.base_dir / "registrations"
        self.negotiations_dir = self.base_dir / "negotiations"

        # Ensure directories exist
        for dir_path in [
            self.connections_dir,
            self.registrations_dir,
            self.negotiations_dir,
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)

        # Provider instances cache (lazy loaded)
        self._providers: dict[str, "DataspaceProvider"] = {}

    # -------------------------------------------------------------------------
    # Connection management
    # -------------------------------------------------------------------------

    def create_connection(
        self,
        dataspace_type: DataspaceType,
        provider_url: str | None = None,
        dtr_url: str | None = None,
        edc_url: str | None = None,
        bpn: str | None = None,
        owner_id: str | None = None,
        metadata: dict | None = None,
    ) -> ConnectionState:
        """
        Create a new dataspace connection.

        Args:
            dataspace_type: Type of dataspace (sandbox, catena-x, etc.)
            provider_url: Provider's base URL
            dtr_url: Digital Twin Registry URL
            edc_url: EDC Connector URL
            bpn: Business Partner Number
            metadata: Additional connection metadata

        Returns:
            Created connection state
        """
        connection_id = uuid.uuid4().hex
        now = datetime.utcnow()

        connection = ConnectionState(
            connection_id=connection_id,
            owner_id=owner_id,
            dataspace_type=dataspace_type,
            status=ConnectionStatus.DISCONNECTED,
            provider_url=provider_url,
            dtr_url=dtr_url,
            edc_url=edc_url,
            bpn=bpn,
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )

        self._save_connection(connection)
        logger.info(
            "Created connection %s for dataspace %s",
            connection_id,
            dataspace_type.value,
        )
        return connection

    def get_connection(self, connection_id: str) -> ConnectionState | None:
        """Get a connection by ID."""
        connection_path = self.connections_dir / f"{connection_id}.json"
        if not connection_path.exists():
            return None

        data = json.loads(connection_path.read_text())
        connection = ConnectionState.from_dict(data)
        if "credentials" in (connection.metadata or {}):
            # Scrub any persisted credentials
            connection.metadata.pop("credentials", None)
            self._save_connection(connection)
        return connection

    def update_connection(
        self,
        connection_id: str,
        status: ConnectionStatus | None = None,
        error_message: str | None = None,
        last_health_check: datetime | None = None,
        **kwargs,
    ) -> ConnectionState | None:
        """
        Update connection state.

        Args:
            connection_id: Connection to update
            status: New connection status
            error_message: Error message if status is ERROR
            last_health_check: Timestamp of last health check
            **kwargs: Additional fields to update

        Returns:
            Updated connection state or None if not found
        """
        connection = self.get_connection(connection_id)
        if connection is None:
            return None

        if status is not None:
            connection.status = status
        if error_message is not None:
            connection.error_message = error_message
        if last_health_check is not None:
            connection.last_health_check = last_health_check

        # Update any additional fields passed in kwargs
        for key, value in kwargs.items():
            if hasattr(connection, key):
                setattr(connection, key, value)

        connection.updated_at = datetime.utcnow()
        self._save_connection(connection)

        logger.info(
            "Updated connection %s: status=%s",
            connection_id,
            connection.status.value,
        )
        return connection

    def delete_connection(self, connection_id: str) -> bool:
        """
        Delete a connection and all associated registrations/negotiations.

        Args:
            connection_id: Connection to delete

        Returns:
            True if connection was deleted
        """
        deleted = False

        # Delete connection file
        connection_path = self.connections_dir / f"{connection_id}.json"
        if connection_path.exists():
            connection_path.unlink()
            deleted = True

        # Delete associated registrations
        for reg_path in self.registrations_dir.glob("*.json"):
            try:
                data = json.loads(reg_path.read_text())
                if data.get("connection_id") == connection_id:
                    reg_path.unlink()
            except Exception as e:
                logger.warning("Failed to check registration %s: %s", reg_path.stem, e)

        # Delete associated negotiations
        for neg_path in self.negotiations_dir.glob("*.json"):
            try:
                data = json.loads(neg_path.read_text())
                if data.get("connection_id") == connection_id:
                    neg_path.unlink()
            except Exception as e:
                logger.warning("Failed to check negotiation %s: %s", neg_path.stem, e)

        # Remove from provider cache
        if connection_id in self._providers:
            del self._providers[connection_id]

        if deleted:
            logger.info("Deleted connection %s", connection_id)

        return deleted

    def list_connections(
        self,
        dataspace_type: DataspaceType | None = None,
        status: ConnectionStatus | None = None,
        owner_id: str | None = None,
        limit: int = 50,
    ) -> list[ConnectionState]:
        """
        List connections with optional filters.

        Args:
            dataspace_type: Filter by dataspace type
            status: Filter by connection status
            limit: Maximum connections to return

        Returns:
            List of matching connections
        """
        connections: list[ConnectionState] = []

        for conn_path in self.connections_dir.glob("*.json"):
            try:
                data = json.loads(conn_path.read_text())
                connection = ConnectionState.from_dict(data)
                if "credentials" in (connection.metadata or {}):
                    connection.metadata.pop("credentials", None)
                    self._save_connection(connection)

                # Apply filters
                if dataspace_type is not None and connection.dataspace_type != dataspace_type:
                    continue
                if status is not None and connection.status != status:
                    continue
                if owner_id is not None and connection.owner_id != owner_id:
                    continue

                connections.append(connection)

            except Exception as e:
                logger.warning("Failed to load connection %s: %s", conn_path.stem, e)

        # Sort by created_at descending
        connections.sort(key=lambda c: c.created_at, reverse=True)
        return connections[:limit]

    def _save_connection(self, connection: ConnectionState) -> None:
        """Save connection state to disk."""
        connection_path = self.connections_dir / f"{connection.connection_id}.json"
        connection_path.write_text(json.dumps(connection.to_dict(), indent=2))

    # -------------------------------------------------------------------------
    # Asset registration management
    # -------------------------------------------------------------------------

    def create_registration(
        self,
        connection_id: str,
        aas_id: str,
        submodel_id: str,
        metadata: dict | None = None,
    ) -> AssetRegistration:
        """
        Create a new asset registration.

        Args:
            connection_id: Parent connection ID
            aas_id: AAS identifier
            submodel_id: Submodel identifier
            metadata: Additional registration metadata

        Returns:
            Created registration
        """
        registration_id = uuid.uuid4().hex
        now = datetime.utcnow()

        registration = AssetRegistration(
            registration_id=registration_id,
            connection_id=connection_id,
            aas_id=aas_id,
            submodel_id=submodel_id,
            status=RegistrationStatus.PENDING,
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )

        self._save_registration(registration)
        logger.info(
            "Created registration %s for AAS %s",
            registration_id,
            aas_id,
        )
        return registration

    def get_registration(self, registration_id: str) -> AssetRegistration | None:
        """Get a registration by ID."""
        reg_path = self.registrations_dir / f"{registration_id}.json"
        if not reg_path.exists():
            return None

        data = json.loads(reg_path.read_text())
        return AssetRegistration.from_dict(data)

    def update_registration(
        self,
        registration_id: str,
        status: RegistrationStatus | None = None,
        dtr_asset_id: str | None = None,
        edc_asset_id: str | None = None,
        error_message: str | None = None,
    ) -> AssetRegistration | None:
        """Update registration state."""
        registration = self.get_registration(registration_id)
        if registration is None:
            return None

        if status is not None:
            registration.status = status
        if dtr_asset_id is not None:
            registration.dtr_asset_id = dtr_asset_id
        if edc_asset_id is not None:
            registration.edc_asset_id = edc_asset_id
        if error_message is not None:
            registration.error_message = error_message

        registration.updated_at = datetime.utcnow()
        self._save_registration(registration)

        logger.info(
            "Updated registration %s: status=%s",
            registration_id,
            registration.status.value,
        )
        return registration

    def list_registrations(
        self,
        connection_id: str | None = None,
        status: RegistrationStatus | None = None,
        limit: int = 100,
    ) -> list[AssetRegistration]:
        """List registrations with optional filters."""
        registrations: list[AssetRegistration] = []

        for reg_path in self.registrations_dir.glob("*.json"):
            try:
                data = json.loads(reg_path.read_text())
                registration = AssetRegistration.from_dict(data)

                if connection_id is not None and registration.connection_id != connection_id:
                    continue
                if status is not None and registration.status != status:
                    continue

                registrations.append(registration)

            except Exception as e:
                logger.warning("Failed to load registration %s: %s", reg_path.stem, e)

        registrations.sort(key=lambda r: r.created_at, reverse=True)
        return registrations[:limit]

    def _save_registration(self, registration: AssetRegistration) -> None:
        """Save registration to disk."""
        reg_path = self.registrations_dir / f"{registration.registration_id}.json"
        reg_path.write_text(json.dumps(registration.to_dict(), indent=2))

    # -------------------------------------------------------------------------
    # Contract negotiation management
    # -------------------------------------------------------------------------

    def create_negotiation(
        self,
        connection_id: str,
        asset_id: str,
        provider_bpn: str,
        consumer_bpn: str,
        metadata: dict | None = None,
    ) -> ContractNegotiation:
        """
        Create a new contract negotiation.

        Args:
            connection_id: Parent connection ID
            asset_id: Asset to negotiate access to
            provider_bpn: Provider's Business Partner Number
            consumer_bpn: Consumer's Business Partner Number
            metadata: Additional negotiation metadata

        Returns:
            Created negotiation
        """
        negotiation_id = uuid.uuid4().hex
        now = datetime.utcnow()

        negotiation = ContractNegotiation(
            negotiation_id=negotiation_id,
            connection_id=connection_id,
            asset_id=asset_id,
            provider_bpn=provider_bpn,
            consumer_bpn=consumer_bpn,
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )

        self._save_negotiation(negotiation)
        logger.info(
            "Created negotiation %s for asset %s",
            negotiation_id,
            asset_id,
        )
        return negotiation

    def get_negotiation(self, negotiation_id: str) -> ContractNegotiation | None:
        """Get a negotiation by ID."""
        neg_path = self.negotiations_dir / f"{negotiation_id}.json"
        if not neg_path.exists():
            return None

        data = json.loads(neg_path.read_text())
        return ContractNegotiation.from_dict(data)

    def _save_negotiation(self, negotiation: ContractNegotiation) -> None:
        """Save negotiation to disk."""
        neg_path = self.negotiations_dir / f"{negotiation.negotiation_id}.json"
        neg_path.write_text(json.dumps(negotiation.to_dict(), indent=2))
