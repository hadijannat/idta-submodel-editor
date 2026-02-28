"""
Tests for Celery tasks in the dataspace module.

Tests the background task orchestration for connection, publication,
and health check workflows.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.dataspace.models import (
    AssetRegistration,
    ConnectionState,
    ConnectionStatus,
    ContractNegotiation,
    ContractState,
    DataspaceType,
    HealthCheckResult,
    RegistrationStatus,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_connection():
    """Create a sample connected connection."""
    return ConnectionState(
        connection_id="test-conn-12345",
        dataspace_type=DataspaceType.SANDBOX,
        status=ConnectionStatus.CONNECTED,
        provider_url="http://provider:8080",
        dtr_url="http://dtr:4003",
        edc_url="http://edc:8080",
        bpn="BPNL00000001TEST",
        created_at=datetime(2024, 1, 1, 12, 0, 0),
        updated_at=datetime(2024, 1, 1, 12, 30, 0),
        metadata={"environment": "sandbox"},
    )


@pytest.fixture
def sample_disconnected_connection():
    """Create a disconnected connection."""
    return ConnectionState(
        connection_id="test-conn-disconn",
        dataspace_type=DataspaceType.CATENA_X,
        status=ConnectionStatus.DISCONNECTED,
        dtr_url="http://dtr:4003",
        edc_url="http://edc:8080",
        bpn="BPNL00000001DISC",
    )


@pytest.fixture
def sample_registration():
    """Create a sample registration."""
    return AssetRegistration(
        registration_id="reg-12345",
        connection_id="test-conn-12345",
        aas_id="urn:example:aas:1",
        submodel_id="urn:example:submodel:1",
        status=RegistrationStatus.REGISTERED,
        dtr_asset_id="dtr-asset-001",
        edc_asset_id="edc-asset-001",
        created_at=datetime(2024, 1, 1, 13, 0, 0),
        updated_at=datetime(2024, 1, 1, 13, 5, 0),
        metadata={"template_name": "Nameplate"},
    )


@pytest.fixture
def sample_pending_registration():
    """Create a pending registration."""
    return AssetRegistration(
        registration_id="reg-pending-001",
        connection_id="test-conn-12345",
        aas_id="urn:example:aas:2",
        submodel_id="urn:example:submodel:2",
        status=RegistrationStatus.PENDING,
    )


@pytest.fixture
def sample_negotiation():
    """Create a sample negotiation."""
    return ContractNegotiation(
        negotiation_id="neg-12345",
        connection_id="test-conn-12345",
        asset_id="urn:asset:test",
        provider_bpn="BPNL00000001PROV",
        consumer_bpn="BPNL00000001CONS",
        state=ContractState.INITIAL,
    )


@pytest.fixture
def sample_health_results():
    """Create healthy health check results."""
    return [
        HealthCheckResult(
            component="dtr",
            healthy=True,
            latency_ms=25.5,
            message="DTR is healthy",
        ),
        HealthCheckResult(
            component="edc",
            healthy=True,
            latency_ms=35.2,
            message="EDC is healthy",
        ),
    ]


@pytest.fixture
def sample_unhealthy_health_results():
    """Create unhealthy health check results."""
    return [
        HealthCheckResult(
            component="dtr",
            healthy=True,
            latency_ms=25.5,
            message="DTR is healthy",
        ),
        HealthCheckResult(
            component="edc",
            healthy=False,
            latency_ms=5000.0,
            message="Connection timed out",
        ),
    ]


@pytest.fixture
def mock_sandbox_provider():
    """Create a mock sandbox provider."""
    provider = MagicMock()
    provider.name = "sandbox"

    async def mock_connect(connection, secrets=None):
        connection.status = ConnectionStatus.CONNECTED
        connection.dtr_url = "http://dtr:4003"
        connection.edc_url = "http://edc:8080"
        return connection

    async def mock_disconnect(connection):
        connection.status = ConnectionStatus.DISCONNECTED
        return connection

    async def mock_register_asset(connection, registration, aas_data):
        registration.status = RegistrationStatus.REGISTERED
        registration.dtr_asset_id = "dtr-asset-generated"
        registration.edc_asset_id = "edc-asset-generated"
        return registration

    async def mock_negotiate_contract(connection, negotiation, policy):
        negotiation.state = ContractState.AGREED
        negotiation.offer_id = "offer-generated"
        negotiation.agreement_id = "agreement-generated"
        return negotiation

    provider.connect = AsyncMock(side_effect=mock_connect)
    provider.disconnect = AsyncMock(side_effect=mock_disconnect)
    provider.register_asset = AsyncMock(side_effect=mock_register_asset)
    provider.negotiate_contract = AsyncMock(side_effect=mock_negotiate_contract)

    return provider


# ---------------------------------------------------------------------------
# Helper Function Tests
# ---------------------------------------------------------------------------


class TestRunAsync:
    """Tests for the run_async helper."""

    def test_run_async_with_coroutine(self):
        """Test run_async with a simple coroutine."""
        from app.services.dataspace.tasks import run_async

        async def sample_coro():
            return "result"

        result = run_async(sample_coro())
        assert result == "result"

    def test_run_async_with_value(self):
        """Test run_async with a coroutine that returns a value."""
        from app.services.dataspace.tasks import run_async

        async def add_numbers():
            return 1 + 2

        result = run_async(add_numbers())
        assert result == 3


class TestGetProviderForConnection:
    """Tests for get_provider_for_connection."""

    def test_get_sandbox_provider(self):
        """Test getting provider for sandbox connection."""
        from app.services.dataspace.tasks import get_provider_for_connection
        from app.services.dataspace.providers import SandboxProvider

        connection = ConnectionState(
            connection_id="test-1",
            dataspace_type=DataspaceType.SANDBOX,
        )

        provider = get_provider_for_connection(connection)

        assert isinstance(provider, SandboxProvider)

    def test_get_catena_x_provider(self):
        """Test getting provider for Catena-X connection."""
        from app.services.dataspace.tasks import get_provider_for_connection
        from app.services.dataspace.providers import CatenaXProvider

        connection = ConnectionState(
            connection_id="test-2",
            dataspace_type=DataspaceType.CATENA_X,
        )

        provider = get_provider_for_connection(connection)

        assert isinstance(provider, CatenaXProvider)


# ---------------------------------------------------------------------------
# Onboard Task Tests
# ---------------------------------------------------------------------------


class TestOnboardToDataspace:
    """Tests for onboard_to_dataspace task."""

    def test_onboard_connection_not_found(self):
        """Test onboarding with non-existent connection."""
        # Patch at the source module, not where it's imported
        with (
            patch(
                "app.services.dataspace.connection_manager.ConnectionManager"
            ) as MockManager,
            patch("app.config.get_settings") as mock_settings,
        ):
            mock_manager_instance = MagicMock()
            mock_manager_instance.get_connection.return_value = None
            MockManager.return_value = mock_manager_instance

            mock_settings.return_value = MagicMock(vault_url=None, vault_token=None)

            from app.services.dataspace.tasks import onboard_to_dataspace

            result = onboard_to_dataspace("nonexistent-id")

            assert "error" in result
            assert result["connection_id"] == "nonexistent-id"

    def test_onboard_success(
        self, sample_connection, sample_health_results, mock_sandbox_provider
    ):
        """Test successful onboarding."""
        with (
            patch(
                "app.services.dataspace.connection_manager.ConnectionManager"
            ) as MockManager,
            patch("app.services.dataspace.health.DataspaceHealthChecker") as MockChecker,
            patch(
                "app.services.dataspace.identity.vault_client.VaultClient"
            ) as MockVault,
            patch(
                "app.services.dataspace.tasks.get_provider_for_connection"
            ) as mock_get_provider,
            patch("app.config.get_settings") as mock_settings,
        ):
            # Setup mocks
            mock_manager_instance = MagicMock()
            mock_manager_instance.get_connection.return_value = sample_connection
            mock_manager_instance.update_connection.return_value = sample_connection
            MockManager.return_value = mock_manager_instance

            mock_checker_instance = MagicMock()
            mock_checker_instance.check_connection.return_value = sample_health_results
            MockChecker.return_value = mock_checker_instance

            mock_vault_instance = MagicMock()
            mock_vault_instance.is_configured = False
            MockVault.return_value = mock_vault_instance

            mock_get_provider.return_value = mock_sandbox_provider

            mock_settings.return_value = MagicMock(vault_url=None, vault_token=None)

            from app.services.dataspace.tasks import onboard_to_dataspace

            result = onboard_to_dataspace(sample_connection.connection_id)

            assert "error" not in result
            assert result["connection_id"] == sample_connection.connection_id
            assert result["status"] == "connected"
            assert "processing_time_seconds" in result

    def test_onboard_with_health_check_failure(
        self, sample_connection, sample_unhealthy_health_results, mock_sandbox_provider
    ):
        """Test onboarding when health check fails."""
        with (
            patch(
                "app.services.dataspace.connection_manager.ConnectionManager"
            ) as MockManager,
            patch("app.services.dataspace.health.DataspaceHealthChecker") as MockChecker,
            patch(
                "app.services.dataspace.identity.vault_client.VaultClient"
            ) as MockVault,
            patch(
                "app.services.dataspace.tasks.get_provider_for_connection"
            ) as mock_get_provider,
            patch("app.config.get_settings") as mock_settings,
        ):
            mock_manager_instance = MagicMock()
            mock_manager_instance.get_connection.return_value = sample_connection
            mock_manager_instance.update_connection.return_value = sample_connection
            MockManager.return_value = mock_manager_instance

            mock_checker_instance = MagicMock()
            mock_checker_instance.check_connection.return_value = (
                sample_unhealthy_health_results
            )
            MockChecker.return_value = mock_checker_instance

            mock_vault_instance = MagicMock()
            mock_vault_instance.is_configured = False
            MockVault.return_value = mock_vault_instance

            mock_get_provider.return_value = mock_sandbox_provider

            mock_settings.return_value = MagicMock(vault_url=None, vault_token=None)

            from app.services.dataspace.tasks import onboard_to_dataspace

            result = onboard_to_dataspace(sample_connection.connection_id)

            assert result["status"] == "degraded"


# ---------------------------------------------------------------------------
# Publish Submodel Task Tests
# ---------------------------------------------------------------------------


class TestPublishSubmodel:
    """Tests for publish_submodel task."""

    def test_publish_connection_not_found(self):
        """Test publishing with non-existent connection."""
        with patch(
            "app.services.dataspace.connection_manager.ConnectionManager"
        ) as MockManager:
            mock_manager_instance = MagicMock()
            mock_manager_instance.get_connection.return_value = None
            MockManager.return_value = mock_manager_instance

            from app.services.dataspace.tasks import publish_submodel

            result = publish_submodel("nonexistent-id", {})

            assert "error" in result
            assert result["connection_id"] == "nonexistent-id"

    def test_publish_connection_not_connected(self, sample_disconnected_connection):
        """Test publishing when connection is not connected."""
        with patch(
            "app.services.dataspace.connection_manager.ConnectionManager"
        ) as MockManager:
            mock_manager_instance = MagicMock()
            mock_manager_instance.get_connection.return_value = (
                sample_disconnected_connection
            )
            MockManager.return_value = mock_manager_instance

            from app.services.dataspace.tasks import publish_submodel

            result = publish_submodel(
                sample_disconnected_connection.connection_id,
                {"template_name": "Nameplate"},
            )

            assert "error" in result
            assert "not connected" in result["error"]

    def test_publish_missing_required_fields(self, sample_connection):
        """Test publishing with missing required fields."""
        with patch(
            "app.services.dataspace.connection_manager.ConnectionManager"
        ) as MockManager:
            mock_manager_instance = MagicMock()
            mock_manager_instance.get_connection.return_value = sample_connection
            MockManager.return_value = mock_manager_instance

            from app.services.dataspace.tasks import publish_submodel

            # Missing template_name, aas_id, submodel_id
            result = publish_submodel(
                sample_connection.connection_id,
                {"form_data": {}},
            )

            assert "error" in result
            assert "Missing required fields" in result["error"]


# ---------------------------------------------------------------------------
# Health Check Task Tests
# ---------------------------------------------------------------------------


class TestHealthCheckAll:
    """Tests for health_check_all task."""

    def test_health_check_all_no_connections(self):
        """Test health check when no connections exist."""
        with patch(
            "app.services.dataspace.connection_manager.ConnectionManager"
        ) as MockManager:
            mock_manager_instance = MagicMock()
            mock_manager_instance.list_connections.return_value = []
            MockManager.return_value = mock_manager_instance

            from app.services.dataspace.tasks import health_check_all

            result = health_check_all()

            assert result["connections_checked"] == 0
            assert result["results"] == []

    def test_health_check_all_multiple_connections(
        self, sample_connection, sample_health_results
    ):
        """Test health check for multiple connections."""
        conn2 = ConnectionState(
            connection_id="test-conn-2",
            dataspace_type=DataspaceType.CATENA_X,
            status=ConnectionStatus.CONNECTED,
            dtr_url="http://dtr:4003",
        )

        with (
            patch(
                "app.services.dataspace.connection_manager.ConnectionManager"
            ) as MockManager,
            patch("app.services.dataspace.health.DataspaceHealthChecker") as MockChecker,
        ):
            mock_manager_instance = MagicMock()
            mock_manager_instance.list_connections.return_value = [
                sample_connection,
                conn2,
            ]
            mock_manager_instance.update_connection.return_value = None
            MockManager.return_value = mock_manager_instance

            mock_checker_instance = MagicMock()
            mock_checker_instance.check_connection.return_value = sample_health_results
            MockChecker.return_value = mock_checker_instance

            from app.services.dataspace.tasks import health_check_all

            result = health_check_all()

            assert result["connections_checked"] == 2
            assert result["healthy_count"] == 2
            assert result["unhealthy_count"] == 0


class TestHealthCheckTask:
    """Tests for health_check_task."""

    def test_health_check_specific_connection(
        self, sample_connection, sample_health_results
    ):
        """Test health check for a specific connection."""
        with (
            patch(
                "app.services.dataspace.connection_manager.ConnectionManager"
            ) as MockManager,
            patch("app.services.dataspace.health.DataspaceHealthChecker") as MockChecker,
        ):
            mock_manager_instance = MagicMock()
            mock_manager_instance.get_connection.return_value = sample_connection
            mock_manager_instance.update_connection.return_value = None
            MockManager.return_value = mock_manager_instance

            mock_checker_instance = MagicMock()
            mock_checker_instance.check_connection.return_value = sample_health_results
            MockChecker.return_value = mock_checker_instance

            from app.services.dataspace.tasks import health_check_task

            result = health_check_task(sample_connection.connection_id)

            assert result["connection_id"] == sample_connection.connection_id
            assert result["healthy"] is True

    def test_health_check_connection_not_found(self):
        """Test health check for non-existent connection."""
        with patch(
            "app.services.dataspace.connection_manager.ConnectionManager"
        ) as MockManager:
            mock_manager_instance = MagicMock()
            mock_manager_instance.get_connection.return_value = None
            MockManager.return_value = mock_manager_instance

            from app.services.dataspace.tasks import health_check_task

            result = health_check_task("nonexistent-id")

            assert "error" in result

    def test_health_check_all_when_no_id(self):
        """Test that health_check_task calls health_check_all when no ID."""
        with patch("app.services.dataspace.tasks.health_check_all") as mock_check_all:
            mock_check_all.return_value = {"connections_checked": 0}

            from app.services.dataspace.tasks import health_check_task

            health_check_task(None)

            mock_check_all.assert_called_once()


# ---------------------------------------------------------------------------
# Connect Task Tests
# ---------------------------------------------------------------------------


class TestConnectDataspaceTask:
    """Tests for connect_dataspace_task."""

    def test_connect_success(self, sample_connection, mock_sandbox_provider):
        """Test successful connection."""
        with (
            patch(
                "app.services.dataspace.connection_manager.ConnectionManager"
            ) as MockManager,
            patch(
                "app.services.dataspace.tasks.get_provider_for_connection"
            ) as mock_get_provider,
        ):
            mock_manager_instance = MagicMock()
            mock_manager_instance.get_connection.return_value = sample_connection
            mock_manager_instance.update_connection.return_value = sample_connection
            MockManager.return_value = mock_manager_instance

            mock_get_provider.return_value = mock_sandbox_provider

            from app.services.dataspace.tasks import connect_dataspace_task

            result = connect_dataspace_task(sample_connection.connection_id)

            assert "error" not in result
            assert result["connection_id"] == sample_connection.connection_id
            assert result["provider"] == "sandbox"

    def test_connect_not_found(self):
        """Test connecting non-existent connection."""
        with patch(
            "app.services.dataspace.connection_manager.ConnectionManager"
        ) as MockManager:
            mock_manager_instance = MagicMock()
            mock_manager_instance.get_connection.return_value = None
            MockManager.return_value = mock_manager_instance

            from app.services.dataspace.tasks import connect_dataspace_task

            result = connect_dataspace_task("nonexistent-id")

            assert "error" in result


# ---------------------------------------------------------------------------
# Register Asset Task Tests
# ---------------------------------------------------------------------------


class TestRegisterAssetTask:
    """Tests for register_asset_task."""

    def test_register_asset_success(
        self, sample_connection, sample_pending_registration, mock_sandbox_provider
    ):
        """Test successful asset registration."""
        with (
            patch(
                "app.services.dataspace.connection_manager.ConnectionManager"
            ) as MockManager,
            patch(
                "app.services.dataspace.tasks.get_provider_for_connection"
            ) as mock_get_provider,
        ):
            mock_manager_instance = MagicMock()
            mock_manager_instance.get_registration.return_value = (
                sample_pending_registration
            )
            mock_manager_instance.get_connection.return_value = sample_connection
            mock_manager_instance.update_registration.return_value = (
                sample_pending_registration
            )
            MockManager.return_value = mock_manager_instance

            mock_get_provider.return_value = mock_sandbox_provider

            from app.services.dataspace.tasks import register_asset_task

            result = register_asset_task(sample_pending_registration.registration_id)

            assert "error" not in result
            assert result["status"] == "registered"

    def test_register_asset_not_found(self):
        """Test registering non-existent asset."""
        with patch(
            "app.services.dataspace.connection_manager.ConnectionManager"
        ) as MockManager:
            mock_manager_instance = MagicMock()
            mock_manager_instance.get_registration.return_value = None
            MockManager.return_value = mock_manager_instance

            from app.services.dataspace.tasks import register_asset_task

            result = register_asset_task("nonexistent-id")

            assert "error" in result

    def test_register_asset_connection_not_found(self, sample_pending_registration):
        """Test registering when parent connection not found."""
        with patch(
            "app.services.dataspace.connection_manager.ConnectionManager"
        ) as MockManager:
            mock_manager_instance = MagicMock()
            mock_manager_instance.get_registration.return_value = (
                sample_pending_registration
            )
            mock_manager_instance.get_connection.return_value = None
            MockManager.return_value = mock_manager_instance

            from app.services.dataspace.tasks import register_asset_task

            result = register_asset_task(sample_pending_registration.registration_id)

            assert "error" in result
            assert "Parent connection not found" in result["error"]


# ---------------------------------------------------------------------------
# Negotiate Contract Task Tests
# ---------------------------------------------------------------------------


class TestNegotiateContractTask:
    """Tests for negotiate_contract_task."""

    def test_negotiate_success(
        self, sample_connection, sample_negotiation, mock_sandbox_provider
    ):
        """Test successful contract negotiation."""
        with (
            patch(
                "app.services.dataspace.connection_manager.ConnectionManager"
            ) as MockManager,
            patch(
                "app.services.dataspace.tasks.get_provider_for_connection"
            ) as mock_get_provider,
        ):
            mock_manager_instance = MagicMock()
            mock_manager_instance.get_negotiation.return_value = sample_negotiation
            mock_manager_instance.get_connection.return_value = sample_connection
            MockManager.return_value = mock_manager_instance

            mock_get_provider.return_value = mock_sandbox_provider

            from app.services.dataspace.tasks import negotiate_contract_task

            result = negotiate_contract_task(sample_negotiation.negotiation_id)

            assert "error" not in result
            assert result["status"] == "agreed"

    def test_negotiate_not_found(self):
        """Test negotiating non-existent contract."""
        with patch(
            "app.services.dataspace.connection_manager.ConnectionManager"
        ) as MockManager:
            mock_manager_instance = MagicMock()
            mock_manager_instance.get_negotiation.return_value = None
            MockManager.return_value = mock_manager_instance

            from app.services.dataspace.tasks import negotiate_contract_task

            result = negotiate_contract_task("nonexistent-id")

            assert "error" in result


# ---------------------------------------------------------------------------
# Sync Registrations Task Tests
# ---------------------------------------------------------------------------


class TestSyncRegistrationsTask:
    """Tests for sync_registrations_task."""

    def test_sync_no_registrations(self, sample_connection):
        """Test sync when no registrations exist."""
        with patch(
            "app.services.dataspace.connection_manager.ConnectionManager"
        ) as MockManager:
            mock_manager_instance = MagicMock()
            mock_manager_instance.get_connection.return_value = sample_connection
            mock_manager_instance.list_registrations.return_value = []
            MockManager.return_value = mock_manager_instance

            from app.services.dataspace.tasks import sync_registrations_task

            result = sync_registrations_task(sample_connection.connection_id)

            assert result["registrations_synced"] == 0
            assert "No registrations to sync" in result["message"]

    def test_sync_with_registrations(self, sample_connection, sample_registration):
        """Test sync with existing registrations."""
        with (
            patch(
                "app.services.dataspace.connection_manager.ConnectionManager"
            ) as MockManager,
            patch(
                "app.services.dataspace.tasks.get_provider_for_connection"
            ) as mock_get_provider,
        ):
            mock_manager_instance = MagicMock()
            mock_manager_instance.get_connection.return_value = sample_connection
            mock_manager_instance.list_registrations.return_value = [sample_registration]
            MockManager.return_value = mock_manager_instance

            mock_provider = MagicMock()
            mock_get_provider.return_value = mock_provider

            from app.services.dataspace.tasks import sync_registrations_task

            result = sync_registrations_task(sample_connection.connection_id)

            assert result["total_registrations"] == 1
            assert result["registrations_synced"] == 1

    def test_sync_connection_not_found(self):
        """Test sync for non-existent connection."""
        with patch(
            "app.services.dataspace.connection_manager.ConnectionManager"
        ) as MockManager:
            mock_manager_instance = MagicMock()
            mock_manager_instance.get_connection.return_value = None
            MockManager.return_value = mock_manager_instance

            from app.services.dataspace.tasks import sync_registrations_task

            result = sync_registrations_task("nonexistent-id")

            assert "error" in result


# ---------------------------------------------------------------------------
# Disconnect Task Tests
# ---------------------------------------------------------------------------


class TestDisconnectDataspaceTask:
    """Tests for disconnect_dataspace_task."""

    def test_disconnect_success(self, sample_connection, mock_sandbox_provider):
        """Test successful disconnection."""
        with (
            patch(
                "app.services.dataspace.connection_manager.ConnectionManager"
            ) as MockManager,
            patch(
                "app.services.dataspace.tasks.get_provider_for_connection"
            ) as mock_get_provider,
        ):
            mock_manager_instance = MagicMock()
            mock_manager_instance.get_connection.return_value = sample_connection
            mock_manager_instance.update_connection.return_value = sample_connection
            MockManager.return_value = mock_manager_instance

            mock_get_provider.return_value = mock_sandbox_provider

            from app.services.dataspace.tasks import disconnect_dataspace_task

            result = disconnect_dataspace_task(sample_connection.connection_id)

            assert result["status"] == "disconnected"
            assert result["connection_id"] == sample_connection.connection_id

    def test_disconnect_not_found(self):
        """Test disconnecting non-existent connection."""
        with patch(
            "app.services.dataspace.connection_manager.ConnectionManager"
        ) as MockManager:
            mock_manager_instance = MagicMock()
            mock_manager_instance.get_connection.return_value = None
            MockManager.return_value = mock_manager_instance

            from app.services.dataspace.tasks import disconnect_dataspace_task

            result = disconnect_dataspace_task("nonexistent-id")

            assert "error" in result
