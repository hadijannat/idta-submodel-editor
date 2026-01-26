"""
Shared fixtures for dataspace module tests.

Provides mocked services, clients, and common test data
for dataspace-related tests.
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path
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
# Temporary Directory Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_dataspace_dir(tmp_path):
    """Create a temporary directory for dataspace cache."""
    dataspace_dir = tmp_path / "dataspace"
    dataspace_dir.mkdir()
    (dataspace_dir / "connections").mkdir()
    (dataspace_dir / "registrations").mkdir()
    (dataspace_dir / "negotiations").mkdir()
    return dataspace_dir


@pytest.fixture
def mock_settings(temp_dataspace_dir):
    """Mock settings with temporary cache directory."""
    settings = MagicMock()
    settings.cache_dir = temp_dataspace_dir / "cache"
    settings.dataspace_enabled = True
    settings.dataspace_default_environment = "sandbox"
    settings.dataspace_default_edc_mode = "tractus-x"
    settings.dtr_url = "http://dtr:4003"
    settings.edc_control_plane_url = "http://edc:8080"
    settings.edc_data_plane_url = "http://edc:8081"
    settings.basyx_aas_server_url = "http://basyx:4001"
    settings.vault_url = None
    settings.vault_token = None
    return settings


# ---------------------------------------------------------------------------
# Connection State Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_connection_state():
    """Create a sample connection state for testing."""
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
        last_health_check=datetime(2024, 1, 1, 12, 30, 0),
        metadata={"environment": "sandbox", "edc_mode": "tractus-x"},
    )


@pytest.fixture
def sample_connection_disconnected():
    """Create a disconnected connection state."""
    return ConnectionState(
        connection_id="test-conn-disconn",
        dataspace_type=DataspaceType.CATENA_X,
        status=ConnectionStatus.DISCONNECTED,
        dtr_url="http://dtr:4003",
        edc_url="http://edc:8080",
        bpn="BPNL00000001DISC",
        created_at=datetime(2024, 1, 1, 10, 0, 0),
        updated_at=datetime(2024, 1, 1, 10, 0, 0),
    )


@pytest.fixture
def sample_connection_error():
    """Create a connection in error state."""
    return ConnectionState(
        connection_id="test-conn-error",
        dataspace_type=DataspaceType.SANDBOX,
        status=ConnectionStatus.ERROR,
        dtr_url="http://dtr:4003",
        error_message="Connection timed out",
        created_at=datetime(2024, 1, 1, 11, 0, 0),
        updated_at=datetime(2024, 1, 1, 11, 5, 0),
    )


# ---------------------------------------------------------------------------
# Registration Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_registration():
    """Create a sample asset registration."""
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
def sample_registration_pending():
    """Create a pending registration."""
    return AssetRegistration(
        registration_id="reg-pending-001",
        connection_id="test-conn-12345",
        aas_id="urn:example:aas:2",
        submodel_id="urn:example:submodel:2",
        status=RegistrationStatus.PENDING,
        created_at=datetime(2024, 1, 1, 14, 0, 0),
        updated_at=datetime(2024, 1, 1, 14, 0, 0),
    )


# ---------------------------------------------------------------------------
# Negotiation Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_negotiation():
    """Create a sample contract negotiation."""
    return ContractNegotiation(
        negotiation_id="neg-12345",
        connection_id="test-conn-12345",
        asset_id="urn:asset:test",
        provider_bpn="BPNL00000001PROV",
        consumer_bpn="BPNL00000001CONS",
        state=ContractState.AGREED,
        offer_id="offer-001",
        agreement_id="agreement-001",
        created_at=datetime(2024, 1, 1, 15, 0, 0),
        updated_at=datetime(2024, 1, 1, 15, 10, 0),
    )


# ---------------------------------------------------------------------------
# Health Check Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_health_results():
    """Create sample health check results."""
    return [
        HealthCheckResult(
            component="dtr",
            healthy=True,
            latency_ms=25.5,
            message="DTR is healthy",
            checked_at=datetime(2024, 1, 1, 12, 30, 0),
        ),
        HealthCheckResult(
            component="edc",
            healthy=True,
            latency_ms=35.2,
            message="EDC is healthy",
            checked_at=datetime(2024, 1, 1, 12, 30, 0),
        ),
    ]


@pytest.fixture
def sample_health_results_unhealthy():
    """Create sample unhealthy health check results."""
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


# ---------------------------------------------------------------------------
# Mock Service Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_connection_manager(temp_dataspace_dir, mock_settings):
    """Create a ConnectionManager with mocked settings."""
    with patch("app.services.dataspace.connection_manager.get_settings") as mock_get:
        mock_get.return_value = mock_settings
        from app.services.dataspace.connection_manager import ConnectionManager

        manager = ConnectionManager()
        yield manager


@pytest.fixture
def mock_health_checker():
    """Create a mocked DataspaceHealthChecker."""
    checker = MagicMock()
    checker.check_connection.return_value = [
        HealthCheckResult(
            component="dtr",
            healthy=True,
            latency_ms=20.0,
            message="OK",
        ),
        HealthCheckResult(
            component="edc",
            healthy=True,
            latency_ms=30.0,
            message="OK",
        ),
    ]
    return checker


@pytest.fixture
def mock_policy_engine():
    """Create a mocked PolicyEngine."""
    engine = MagicMock()
    engine.validate_policy.return_value = (True, [])
    engine.translate.return_value = MagicMock(
        assets=[{"@id": "test-asset"}],
        access_policy={"@type": "Offer"},
        contract_policy={"@type": "Offer"},
        access_policy_id="urn:uuid:access-1",
        contract_policy_id="urn:uuid:contract-1",
        contract_definitions=[{"@id": "def-1"}],
        element_level=False,
        target_paths=[],
        to_dict=lambda: {},
    )
    return engine


@pytest.fixture
def mock_basyx_client():
    """Create a mocked BaSyxClient."""
    client = MagicMock()
    client.base_url = "http://basyx:4001"
    client.register_aas = AsyncMock(return_value={"id": "urn:aas:test"})
    client.update_aas = AsyncMock(return_value={"id": "urn:aas:test"})
    client.delete_aas = AsyncMock(return_value=True)
    client.get_aas = AsyncMock(return_value={"id": "urn:aas:test"})
    client.register_submodel = AsyncMock(return_value={"id": "urn:submodel:test"})
    client.update_submodel = AsyncMock(return_value={"id": "urn:submodel:test"})
    client.delete_submodel = AsyncMock(return_value=True)
    client.get_submodel = AsyncMock(return_value={"id": "urn:submodel:test"})
    client.get_all_submodels = AsyncMock(return_value=([], None))
    client.health_check = AsyncMock(return_value=True)
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_dtr_client():
    """Create a mocked DTRClient."""
    client = MagicMock()
    client.base_url = "http://dtr:4003"
    client.create_shell_descriptor = AsyncMock(return_value={"id": "urn:shell:test"})
    client.update_shell_descriptor = AsyncMock(return_value={"id": "urn:shell:test"})
    client.delete_shell_descriptor = AsyncMock(return_value=True)
    client.get_shell_descriptor = AsyncMock(return_value={"id": "urn:shell:test"})
    client.create_submodel_descriptor = AsyncMock(
        return_value={"id": "urn:submodel:test"}
    )
    client.update_submodel_descriptor = AsyncMock(
        return_value={"id": "urn:submodel:test"}
    )
    client.delete_submodel_descriptor = AsyncMock(return_value=True)
    client.get_submodel_descriptor = AsyncMock(return_value={"id": "urn:submodel:test"})
    client.health_check = AsyncMock(return_value=True)
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_edc_client():
    """Create a mocked TractusXClient."""
    client = MagicMock()
    client.base_url = "http://edc:8080"
    client.create_asset = AsyncMock(return_value={"@id": "test-asset"})
    client.get_asset = AsyncMock(return_value={"@id": "test-asset"})
    client.delete_asset = AsyncMock(return_value=True)
    client.create_policy = AsyncMock(return_value={"@id": "test-policy"})
    client.get_policy = AsyncMock(return_value={"@id": "test-policy"})
    client.delete_policy = AsyncMock(return_value=True)
    client.create_contract_definition = AsyncMock(return_value={"@id": "test-contract"})
    client.health_check = AsyncMock(return_value=True)
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_sandbox_provider():
    """Create a mocked SandboxProvider."""
    from app.services.dataspace.models import ConnectionStatus, RegistrationStatus

    provider = MagicMock()
    provider.name = "sandbox"

    async def mock_connect(connection):
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
        from app.services.dataspace.models import ContractState

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
# API Request/Response Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_create_connection_request():
    """Sample request for creating a connection."""
    return {
        "environment": "sandbox",
        "edc_mode": "tractus-x",
        "bpn": "BPNL00000001TEST",
        "credentials": None,
    }


@pytest.fixture
def sample_publish_request():
    """Sample request for publishing a submodel."""
    return {
        "connection_id": "test-conn-12345",
        "template_name": "Nameplate",
        "template_status": "published",
        "form_data": {"elements": {"SerialNumber": "SN-001"}},
        "aas_id": "urn:aas:new",
        "submodel_id": "urn:submodel:new",
        "policy": {
            "access_type": "membership",
            "allowed_partners": [],
            "constraints": [],
        },
    }


@pytest.fixture
def sample_policy_config():
    """Sample policy configuration."""
    return {
        "access_type": "membership",
        "allowed_partners": ["BPNL00000001AAAA"],
        "constraints": [
            {
                "left_operand": "Purpose",
                "operator": "eq",
                "right_operand": "cx.pcf:1",
            }
        ],
    }
