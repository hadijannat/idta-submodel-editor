"""
Tests for the ConnectionManager service.

Tests state persistence, connection lifecycle, and registration management.
"""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.dataspace.models import (
    AssetRegistration,
    ConnectionState,
    ConnectionStatus,
    ContractNegotiation,
    ContractState,
    DataspaceType,
    RegistrationStatus,
)


# ---------------------------------------------------------------------------
# ConnectionState Model Tests
# ---------------------------------------------------------------------------


class TestConnectionStateModel:
    """Tests for ConnectionState dataclass."""

    def test_connection_state_creation(self):
        """Test creating a ConnectionState with required fields."""
        conn = ConnectionState(
            connection_id="test-123",
            dataspace_type=DataspaceType.SANDBOX,
        )

        assert conn.connection_id == "test-123"
        assert conn.dataspace_type == DataspaceType.SANDBOX
        assert conn.status == ConnectionStatus.DISCONNECTED
        assert conn.metadata == {}

    def test_connection_state_full_creation(self):
        """Test creating a ConnectionState with all fields."""
        now = datetime.utcnow()
        conn = ConnectionState(
            connection_id="test-456",
            dataspace_type=DataspaceType.CATENA_X,
            status=ConnectionStatus.CONNECTED,
            provider_url="http://provider:8080",
            dtr_url="http://dtr:4003",
            edc_url="http://edc:8080",
            bpn="BPNL00000001TEST",
            created_at=now,
            updated_at=now,
            last_health_check=now,
            error_message=None,
            metadata={"key": "value"},
        )

        assert conn.status == ConnectionStatus.CONNECTED
        assert conn.bpn == "BPNL00000001TEST"
        assert conn.metadata["key"] == "value"

    def test_connection_state_to_dict(self):
        """Test serialization to dictionary."""
        now = datetime(2024, 1, 1, 12, 0, 0)
        conn = ConnectionState(
            connection_id="test-789",
            dataspace_type=DataspaceType.SANDBOX,
            status=ConnectionStatus.CONNECTED,
            created_at=now,
            updated_at=now,
            last_health_check=now,
            metadata={"env": "test"},
        )

        data = conn.to_dict()

        assert data["connection_id"] == "test-789"
        assert data["dataspace_type"] == "sandbox"
        assert data["status"] == "connected"
        assert data["created_at"] == now.isoformat()
        assert data["metadata"]["env"] == "test"

    def test_connection_state_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            "connection_id": "test-abc",
            "dataspace_type": "catena-x",
            "status": "connecting",
            "provider_url": "http://provider:8080",
            "dtr_url": "http://dtr:4003",
            "edc_url": "http://edc:8080",
            "bpn": "BPNL00000001TEST",
            "created_at": "2024-01-01T12:00:00",
            "updated_at": "2024-01-01T12:30:00",
            "last_health_check": None,
            "error_message": None,
            "metadata": {"test": True},
        }

        conn = ConnectionState.from_dict(data)

        assert conn.connection_id == "test-abc"
        assert conn.dataspace_type == DataspaceType.CATENA_X
        assert conn.status == ConnectionStatus.CONNECTING
        assert conn.bpn == "BPNL00000001TEST"
        assert conn.metadata["test"] is True

    def test_connection_state_roundtrip(self):
        """Test serialization and deserialization roundtrip."""
        original = ConnectionState(
            connection_id="roundtrip-test",
            dataspace_type=DataspaceType.MANUFACTURING_X,
            status=ConnectionStatus.ERROR,
            dtr_url="http://dtr:4003",
            error_message="Test error",
            metadata={"nested": {"key": "value"}},
        )

        data = original.to_dict()
        restored = ConnectionState.from_dict(data)

        assert restored.connection_id == original.connection_id
        assert restored.dataspace_type == original.dataspace_type
        assert restored.status == original.status
        assert restored.error_message == original.error_message
        assert restored.metadata == original.metadata


# ---------------------------------------------------------------------------
# AssetRegistration Model Tests
# ---------------------------------------------------------------------------


class TestAssetRegistrationModel:
    """Tests for AssetRegistration dataclass."""

    def test_registration_creation(self):
        """Test creating an AssetRegistration."""
        reg = AssetRegistration(
            registration_id="reg-123",
            connection_id="conn-456",
            aas_id="urn:aas:1",
            submodel_id="urn:submodel:1",
        )

        assert reg.registration_id == "reg-123"
        assert reg.status == RegistrationStatus.PENDING
        assert reg.dtr_asset_id is None

    def test_registration_to_dict(self):
        """Test serialization to dictionary."""
        now = datetime(2024, 1, 1, 12, 0, 0)
        reg = AssetRegistration(
            registration_id="reg-456",
            connection_id="conn-789",
            aas_id="urn:aas:2",
            submodel_id="urn:submodel:2",
            status=RegistrationStatus.REGISTERED,
            dtr_asset_id="dtr-001",
            edc_asset_id="edc-001",
            created_at=now,
            updated_at=now,
        )

        data = reg.to_dict()

        assert data["registration_id"] == "reg-456"
        assert data["status"] == "registered"
        assert data["dtr_asset_id"] == "dtr-001"

    def test_registration_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            "registration_id": "reg-abc",
            "connection_id": "conn-def",
            "aas_id": "urn:aas:3",
            "submodel_id": "urn:submodel:3",
            "status": "failed",
            "dtr_asset_id": None,
            "edc_asset_id": None,
            "created_at": "2024-01-01T12:00:00",
            "updated_at": "2024-01-01T12:05:00",
            "error_message": "Registration failed",
            "metadata": {},
        }

        reg = AssetRegistration.from_dict(data)

        assert reg.registration_id == "reg-abc"
        assert reg.status == RegistrationStatus.FAILED
        assert reg.error_message == "Registration failed"


# ---------------------------------------------------------------------------
# ContractNegotiation Model Tests
# ---------------------------------------------------------------------------


class TestContractNegotiationModel:
    """Tests for ContractNegotiation dataclass."""

    def test_negotiation_creation(self):
        """Test creating a ContractNegotiation."""
        neg = ContractNegotiation(
            negotiation_id="neg-123",
            connection_id="conn-456",
            asset_id="urn:asset:1",
            provider_bpn="BPNL00000001PROV",
            consumer_bpn="BPNL00000001CONS",
        )

        assert neg.negotiation_id == "neg-123"
        assert neg.state == ContractState.INITIAL
        assert neg.offer_id is None

    def test_negotiation_to_dict(self):
        """Test serialization to dictionary."""
        now = datetime(2024, 1, 1, 12, 0, 0)
        neg = ContractNegotiation(
            negotiation_id="neg-456",
            connection_id="conn-789",
            asset_id="urn:asset:2",
            provider_bpn="BPNL00000001PROV",
            consumer_bpn="BPNL00000001CONS",
            state=ContractState.AGREED,
            offer_id="offer-001",
            agreement_id="agreement-001",
            created_at=now,
            updated_at=now,
        )

        data = neg.to_dict()

        assert data["negotiation_id"] == "neg-456"
        assert data["state"] == "agreed"
        assert data["agreement_id"] == "agreement-001"

    def test_negotiation_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            "negotiation_id": "neg-abc",
            "connection_id": "conn-def",
            "asset_id": "urn:asset:3",
            "provider_bpn": "BPNL00000001PROV",
            "consumer_bpn": "BPNL00000001CONS",
            "state": "finalized",
            "offer_id": "offer-002",
            "agreement_id": "agreement-002",
            "policy_id": "policy-001",
            "created_at": "2024-01-01T12:00:00",
            "updated_at": "2024-01-01T12:10:00",
            "error_message": None,
            "metadata": {"custom": "data"},
        }

        neg = ContractNegotiation.from_dict(data)

        assert neg.negotiation_id == "neg-abc"
        assert neg.state == ContractState.FINALIZED
        assert neg.policy_id == "policy-001"


# ---------------------------------------------------------------------------
# ConnectionManager Tests
# ---------------------------------------------------------------------------


class TestConnectionManagerInit:
    """Tests for ConnectionManager initialization."""

    def test_init_creates_directories(self, mock_connection_manager, temp_dataspace_dir):
        """Test that directories are created on init."""
        manager = mock_connection_manager

        assert manager.connections_dir.exists()
        assert manager.registrations_dir.exists()
        assert manager.negotiations_dir.exists()


class TestConnectionManagerConnections:
    """Tests for ConnectionManager connection operations."""

    def test_create_connection(self, mock_connection_manager):
        """Test creating a new connection."""
        manager = mock_connection_manager

        connection = manager.create_connection(
            dataspace_type=DataspaceType.SANDBOX,
            dtr_url="http://dtr:4003",
            edc_url="http://edc:8080",
            bpn="BPNL00000001TEST",
        )

        assert connection.connection_id is not None
        assert len(connection.connection_id) == 32  # UUID hex
        assert connection.dataspace_type == DataspaceType.SANDBOX
        assert connection.status == ConnectionStatus.DISCONNECTED
        assert connection.bpn == "BPNL00000001TEST"

    def test_create_connection_persists_to_disk(self, mock_connection_manager):
        """Test that connection is saved to disk."""
        manager = mock_connection_manager

        connection = manager.create_connection(
            dataspace_type=DataspaceType.SANDBOX,
        )

        # Check file exists
        file_path = manager.connections_dir / f"{connection.connection_id}.json"
        assert file_path.exists()

        # Verify content
        data = json.loads(file_path.read_text())
        assert data["connection_id"] == connection.connection_id

    def test_get_connection_existing(self, mock_connection_manager):
        """Test getting an existing connection."""
        manager = mock_connection_manager

        # Create a connection
        created = manager.create_connection(
            dataspace_type=DataspaceType.SANDBOX,
            bpn="BPNL00000001TEST",
        )

        # Retrieve it
        retrieved = manager.get_connection(created.connection_id)

        assert retrieved is not None
        assert retrieved.connection_id == created.connection_id
        assert retrieved.bpn == "BPNL00000001TEST"

    def test_get_connection_not_found(self, mock_connection_manager):
        """Test getting a non-existent connection."""
        manager = mock_connection_manager

        result = manager.get_connection("nonexistent-id")

        assert result is None

    def test_update_connection_status(self, mock_connection_manager):
        """Test updating connection status."""
        manager = mock_connection_manager

        connection = manager.create_connection(
            dataspace_type=DataspaceType.SANDBOX,
        )

        updated = manager.update_connection(
            connection.connection_id,
            status=ConnectionStatus.CONNECTED,
        )

        assert updated is not None
        assert updated.status == ConnectionStatus.CONNECTED
        assert updated.updated_at > connection.created_at

    def test_update_connection_with_error(self, mock_connection_manager):
        """Test updating connection with error message."""
        manager = mock_connection_manager

        connection = manager.create_connection(
            dataspace_type=DataspaceType.SANDBOX,
        )

        updated = manager.update_connection(
            connection.connection_id,
            status=ConnectionStatus.ERROR,
            error_message="Connection timed out",
        )

        assert updated.status == ConnectionStatus.ERROR
        assert updated.error_message == "Connection timed out"

    def test_update_connection_not_found(self, mock_connection_manager):
        """Test updating a non-existent connection."""
        manager = mock_connection_manager

        result = manager.update_connection(
            "nonexistent-id",
            status=ConnectionStatus.CONNECTED,
        )

        assert result is None

    def test_update_connection_with_kwargs(self, mock_connection_manager):
        """Test updating connection with arbitrary kwargs."""
        manager = mock_connection_manager

        connection = manager.create_connection(
            dataspace_type=DataspaceType.SANDBOX,
        )

        # Update with kwargs
        updated = manager.update_connection(
            connection.connection_id,
            dtr_url="http://new-dtr:4003",
            edc_url="http://new-edc:8080",
        )

        assert updated.dtr_url == "http://new-dtr:4003"
        assert updated.edc_url == "http://new-edc:8080"

    def test_delete_connection(self, mock_connection_manager):
        """Test deleting a connection."""
        manager = mock_connection_manager

        connection = manager.create_connection(
            dataspace_type=DataspaceType.SANDBOX,
        )

        result = manager.delete_connection(connection.connection_id)

        assert result is True
        assert manager.get_connection(connection.connection_id) is None

    def test_delete_connection_not_found(self, mock_connection_manager):
        """Test deleting a non-existent connection."""
        manager = mock_connection_manager

        result = manager.delete_connection("nonexistent-id")

        assert result is False

    def test_delete_connection_removes_registrations(self, mock_connection_manager):
        """Test that deleting a connection also removes its registrations."""
        manager = mock_connection_manager

        # Create connection and registration
        connection = manager.create_connection(
            dataspace_type=DataspaceType.SANDBOX,
        )
        registration = manager.create_registration(
            connection_id=connection.connection_id,
            aas_id="urn:aas:1",
            submodel_id="urn:submodel:1",
        )

        # Delete connection
        manager.delete_connection(connection.connection_id)

        # Registration should also be gone
        assert manager.get_registration(registration.registration_id) is None

    def test_list_connections_empty(self, mock_connection_manager):
        """Test listing connections when none exist."""
        manager = mock_connection_manager

        connections = manager.list_connections()

        assert connections == []

    def test_list_connections(self, mock_connection_manager):
        """Test listing connections."""
        manager = mock_connection_manager

        # Create multiple connections
        manager.create_connection(dataspace_type=DataspaceType.SANDBOX)
        manager.create_connection(dataspace_type=DataspaceType.CATENA_X)
        manager.create_connection(dataspace_type=DataspaceType.SANDBOX)

        connections = manager.list_connections()

        assert len(connections) == 3

    def test_list_connections_filter_by_type(self, mock_connection_manager):
        """Test filtering connections by dataspace type."""
        manager = mock_connection_manager

        manager.create_connection(dataspace_type=DataspaceType.SANDBOX)
        manager.create_connection(dataspace_type=DataspaceType.CATENA_X)
        manager.create_connection(dataspace_type=DataspaceType.SANDBOX)

        sandbox_conns = manager.list_connections(dataspace_type=DataspaceType.SANDBOX)
        catena_conns = manager.list_connections(dataspace_type=DataspaceType.CATENA_X)

        assert len(sandbox_conns) == 2
        assert len(catena_conns) == 1

    def test_list_connections_filter_by_status(self, mock_connection_manager):
        """Test filtering connections by status."""
        manager = mock_connection_manager

        conn1 = manager.create_connection(dataspace_type=DataspaceType.SANDBOX)
        conn2 = manager.create_connection(dataspace_type=DataspaceType.SANDBOX)

        # Update status
        manager.update_connection(conn1.connection_id, status=ConnectionStatus.CONNECTED)

        connected = manager.list_connections(status=ConnectionStatus.CONNECTED)
        disconnected = manager.list_connections(status=ConnectionStatus.DISCONNECTED)

        assert len(connected) == 1
        assert len(disconnected) == 1

    def test_list_connections_limit(self, mock_connection_manager):
        """Test limiting number of returned connections."""
        manager = mock_connection_manager

        for _ in range(10):
            manager.create_connection(dataspace_type=DataspaceType.SANDBOX)

        limited = manager.list_connections(limit=5)

        assert len(limited) == 5

    def test_list_connections_sorted_by_created_at(self, mock_connection_manager):
        """Test that connections are sorted by created_at descending."""
        manager = mock_connection_manager

        conn1 = manager.create_connection(dataspace_type=DataspaceType.SANDBOX)
        conn2 = manager.create_connection(dataspace_type=DataspaceType.SANDBOX)
        conn3 = manager.create_connection(dataspace_type=DataspaceType.SANDBOX)

        connections = manager.list_connections()

        # Most recent first
        assert connections[0].connection_id == conn3.connection_id
        assert connections[1].connection_id == conn2.connection_id
        assert connections[2].connection_id == conn1.connection_id


class TestConnectionManagerRegistrations:
    """Tests for ConnectionManager registration operations."""

    def test_create_registration(self, mock_connection_manager):
        """Test creating a registration."""
        manager = mock_connection_manager

        registration = manager.create_registration(
            connection_id="test-conn",
            aas_id="urn:aas:1",
            submodel_id="urn:submodel:1",
            metadata={"template": "Nameplate"},
        )

        assert registration.registration_id is not None
        assert registration.connection_id == "test-conn"
        assert registration.aas_id == "urn:aas:1"
        assert registration.status == RegistrationStatus.PENDING
        assert registration.metadata["template"] == "Nameplate"

    def test_get_registration(self, mock_connection_manager):
        """Test getting a registration."""
        manager = mock_connection_manager

        created = manager.create_registration(
            connection_id="test-conn",
            aas_id="urn:aas:1",
            submodel_id="urn:submodel:1",
        )

        retrieved = manager.get_registration(created.registration_id)

        assert retrieved is not None
        assert retrieved.registration_id == created.registration_id

    def test_get_registration_not_found(self, mock_connection_manager):
        """Test getting a non-existent registration."""
        manager = mock_connection_manager

        result = manager.get_registration("nonexistent-id")

        assert result is None

    def test_update_registration(self, mock_connection_manager):
        """Test updating a registration."""
        manager = mock_connection_manager

        registration = manager.create_registration(
            connection_id="test-conn",
            aas_id="urn:aas:1",
            submodel_id="urn:submodel:1",
        )

        updated = manager.update_registration(
            registration.registration_id,
            status=RegistrationStatus.REGISTERED,
            dtr_asset_id="dtr-001",
            edc_asset_id="edc-001",
        )

        assert updated.status == RegistrationStatus.REGISTERED
        assert updated.dtr_asset_id == "dtr-001"
        assert updated.edc_asset_id == "edc-001"

    def test_update_registration_with_error(self, mock_connection_manager):
        """Test updating a registration with error."""
        manager = mock_connection_manager

        registration = manager.create_registration(
            connection_id="test-conn",
            aas_id="urn:aas:1",
            submodel_id="urn:submodel:1",
        )

        updated = manager.update_registration(
            registration.registration_id,
            status=RegistrationStatus.FAILED,
            error_message="DTR unavailable",
        )

        assert updated.status == RegistrationStatus.FAILED
        assert updated.error_message == "DTR unavailable"

    def test_list_registrations(self, mock_connection_manager):
        """Test listing registrations."""
        manager = mock_connection_manager

        manager.create_registration("conn-1", "aas-1", "sm-1")
        manager.create_registration("conn-1", "aas-2", "sm-2")
        manager.create_registration("conn-2", "aas-3", "sm-3")

        all_regs = manager.list_registrations()
        conn1_regs = manager.list_registrations(connection_id="conn-1")

        assert len(all_regs) == 3
        assert len(conn1_regs) == 2

    def test_list_registrations_by_status(self, mock_connection_manager):
        """Test filtering registrations by status."""
        manager = mock_connection_manager

        reg1 = manager.create_registration("conn-1", "aas-1", "sm-1")
        reg2 = manager.create_registration("conn-1", "aas-2", "sm-2")

        manager.update_registration(reg1.registration_id, status=RegistrationStatus.REGISTERED)

        registered = manager.list_registrations(status=RegistrationStatus.REGISTERED)
        pending = manager.list_registrations(status=RegistrationStatus.PENDING)

        assert len(registered) == 1
        assert len(pending) == 1


class TestConnectionManagerNegotiations:
    """Tests for ConnectionManager negotiation operations."""

    def test_create_negotiation(self, mock_connection_manager):
        """Test creating a negotiation."""
        manager = mock_connection_manager

        negotiation = manager.create_negotiation(
            connection_id="test-conn",
            asset_id="urn:asset:1",
            provider_bpn="BPNL00000001PROV",
            consumer_bpn="BPNL00000001CONS",
            metadata={"custom": "data"},
        )

        assert negotiation.negotiation_id is not None
        assert negotiation.connection_id == "test-conn"
        assert negotiation.asset_id == "urn:asset:1"
        assert negotiation.state == ContractState.INITIAL
        assert negotiation.metadata["custom"] == "data"

    def test_get_negotiation(self, mock_connection_manager):
        """Test getting a negotiation."""
        manager = mock_connection_manager

        created = manager.create_negotiation(
            connection_id="test-conn",
            asset_id="urn:asset:1",
            provider_bpn="BPNL00000001PROV",
            consumer_bpn="BPNL00000001CONS",
        )

        retrieved = manager.get_negotiation(created.negotiation_id)

        assert retrieved is not None
        assert retrieved.negotiation_id == created.negotiation_id

    def test_get_negotiation_not_found(self, mock_connection_manager):
        """Test getting a non-existent negotiation."""
        manager = mock_connection_manager

        result = manager.get_negotiation("nonexistent-id")

        assert result is None


# ---------------------------------------------------------------------------
# Persistence Tests
# ---------------------------------------------------------------------------


class TestConnectionManagerPersistence:
    """Tests for connection manager persistence across restarts."""

    def test_connection_survives_manager_recreation(
        self, temp_dataspace_dir, mock_settings
    ):
        """Test that connections persist across manager instances."""
        with patch("app.services.dataspace.connection_manager.get_settings") as mock_get:
            mock_get.return_value = mock_settings
            from app.services.dataspace.connection_manager import ConnectionManager

            # Create connection with first manager
            manager1 = ConnectionManager()
            connection = manager1.create_connection(
                dataspace_type=DataspaceType.SANDBOX,
                bpn="BPNL00000001PERS",
            )
            conn_id = connection.connection_id

            # Create new manager instance
            manager2 = ConnectionManager()

            # Retrieve connection
            retrieved = manager2.get_connection(conn_id)

            assert retrieved is not None
            assert retrieved.connection_id == conn_id
            assert retrieved.bpn == "BPNL00000001PERS"

    def test_registration_survives_manager_recreation(
        self, temp_dataspace_dir, mock_settings
    ):
        """Test that registrations persist across manager instances."""
        with patch("app.services.dataspace.connection_manager.get_settings") as mock_get:
            mock_get.return_value = mock_settings
            from app.services.dataspace.connection_manager import ConnectionManager

            # Create registration with first manager
            manager1 = ConnectionManager()
            registration = manager1.create_registration(
                connection_id="test-conn",
                aas_id="urn:aas:persist",
                submodel_id="urn:submodel:persist",
            )
            reg_id = registration.registration_id

            # Create new manager instance
            manager2 = ConnectionManager()

            # Retrieve registration
            retrieved = manager2.get_registration(reg_id)

            assert retrieved is not None
            assert retrieved.registration_id == reg_id
            assert retrieved.aas_id == "urn:aas:persist"
