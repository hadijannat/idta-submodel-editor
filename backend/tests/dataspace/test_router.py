"""
Tests for the dataspace API router.

Tests all REST API endpoints using FastAPI TestClient with dependency overrides.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.services.dataspace.models import (
    AssetRegistration,
    ConnectionState,
    ConnectionStatus,
    DataspaceType,
    HealthCheckResult,
    RegistrationStatus,
)


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock()
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


@pytest.fixture
def mock_connection():
    """Create a sample connection for testing."""
    return ConnectionState(
        connection_id="test-conn-12345",
        dataspace_type=DataspaceType.SANDBOX,
        status=ConnectionStatus.CONNECTED,
        dtr_url="http://dtr:4003",
        edc_url="http://edc:8080",
        bpn="BPNL00000001TEST",
        created_at=datetime(2024, 1, 1, 12, 0, 0),
        updated_at=datetime(2024, 1, 1, 12, 30, 0),
        metadata={"environment": "sandbox", "edc_mode": "tractus-x"},
    )


@pytest.fixture
def mock_registration():
    """Create a sample registration for testing."""
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
def mock_health_results():
    """Create mock health check results."""
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


def create_test_app(
    mock_settings,
    mock_manager=None,
    mock_checker=None,
    mock_engine=None,
):
    """
    Create a FastAPI test application with mocked dependencies.

    Uses dependency_overrides for proper FastAPI dependency injection.
    """
    from app.routers.dataspace import (
        router,
        get_connection_manager,
        get_health_checker,
        get_policy_engine,
    )

    app = FastAPI()
    app.include_router(router)

    # Override dependencies
    if mock_manager is not None:
        app.dependency_overrides[get_connection_manager] = lambda: mock_manager

    if mock_checker is not None:
        app.dependency_overrides[get_health_checker] = lambda: mock_checker

    if mock_engine is not None:
        app.dependency_overrides[get_policy_engine] = lambda: mock_engine

    return app


# ---------------------------------------------------------------------------
# Dataspace Disabled Tests
# ---------------------------------------------------------------------------


class TestDataspaceDisabled:
    """Tests when dataspace feature is disabled."""

    def test_endpoints_return_503_when_disabled(self):
        """Test that endpoints return 503 when dataspace is disabled."""
        mock_settings = MagicMock()
        mock_settings.dataspace_enabled = False

        mock_manager = MagicMock()
        mock_manager.list_connections.return_value = []

        app = create_test_app(mock_settings, mock_manager=mock_manager)

        with patch("app.routers.dataspace.get_settings", return_value=mock_settings):
            client = TestClient(app, raise_server_exceptions=False)

            # Test various endpoints
            response = client.get("/api/dataspace/connections")
            assert response.status_code == 503
            assert "disabled" in response.json()["detail"].lower()

            response = client.get("/api/dataspace/publications")
            assert response.status_code == 503

            response = client.get("/api/dataspace/health")
            assert response.status_code == 503


# ---------------------------------------------------------------------------
# Connection Endpoints Tests
# ---------------------------------------------------------------------------


class TestConnectionEndpoints:
    """Tests for connection lifecycle endpoints."""

    def test_create_connection_success(self, mock_settings, mock_connection):
        """Test creating a new connection."""
        mock_manager = MagicMock()
        mock_manager.create_connection.return_value = mock_connection
        mock_manager.update_connection.return_value = mock_connection

        app = create_test_app(mock_settings, mock_manager=mock_manager)

        with patch("app.routers.dataspace.get_settings", return_value=mock_settings):
            client = TestClient(app)

            response = client.post(
                "/api/dataspace/connections",
                json={
                    "environment": "sandbox",
                    "edc_mode": "tractus-x",
                    "bpn": "BPNL00000001TEST",
                },
            )

            assert response.status_code == 201
            data = response.json()
            assert "connection" in data
            assert data["connection"]["connection_id"] == mock_connection.connection_id

    def test_list_connections(self, mock_settings, mock_connection):
        """Test listing connections."""
        mock_manager = MagicMock()
        mock_manager.list_connections.return_value = [mock_connection]

        app = create_test_app(mock_settings, mock_manager=mock_manager)

        with patch("app.routers.dataspace.get_settings", return_value=mock_settings):
            client = TestClient(app)

            response = client.get("/api/dataspace/connections")

            assert response.status_code == 200
            data = response.json()
            assert "connections" in data
            assert data["total"] == 1

    def test_get_connection_success(
        self, mock_settings, mock_connection, mock_health_results
    ):
        """Test getting a specific connection."""
        mock_manager = MagicMock()
        mock_manager.get_connection.return_value = mock_connection

        mock_checker = MagicMock()
        mock_checker.check_connection.return_value = mock_health_results

        app = create_test_app(
            mock_settings, mock_manager=mock_manager, mock_checker=mock_checker
        )

        with patch("app.routers.dataspace.get_settings", return_value=mock_settings):
            client = TestClient(app)

            response = client.get(
                f"/api/dataspace/connections/{mock_connection.connection_id}"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["connection"]["connection_id"] == mock_connection.connection_id
            assert len(data["health_checks"]) == 2

    def test_get_connection_not_found(self, mock_settings):
        """Test getting a non-existent connection."""
        mock_manager = MagicMock()
        mock_manager.get_connection.return_value = None

        mock_checker = MagicMock()

        app = create_test_app(
            mock_settings, mock_manager=mock_manager, mock_checker=mock_checker
        )

        with patch("app.routers.dataspace.get_settings", return_value=mock_settings):
            client = TestClient(app)

            response = client.get("/api/dataspace/connections/nonexistent-id")

            assert response.status_code == 404

    def test_disconnect_success(self, mock_settings, mock_connection):
        """Test disconnecting from a dataspace."""
        mock_manager = MagicMock()
        mock_manager.get_connection.return_value = mock_connection
        mock_manager.list_registrations.return_value = []
        mock_manager.delete_connection.return_value = True

        app = create_test_app(mock_settings, mock_manager=mock_manager)

        with patch("app.routers.dataspace.get_settings", return_value=mock_settings):
            client = TestClient(app)

            response = client.request(
                "DELETE",
                f"/api/dataspace/connections/{mock_connection.connection_id}",
                json={"force": False},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "disconnected"

    def test_disconnect_with_active_publications(
        self, mock_settings, mock_connection, mock_registration
    ):
        """Test disconnect fails when active publications exist."""
        mock_manager = MagicMock()
        mock_manager.get_connection.return_value = mock_connection
        mock_manager.list_registrations.return_value = [mock_registration]

        app = create_test_app(mock_settings, mock_manager=mock_manager)

        with patch("app.routers.dataspace.get_settings", return_value=mock_settings):
            client = TestClient(app)

            response = client.request(
                "DELETE",
                f"/api/dataspace/connections/{mock_connection.connection_id}",
                json={"force": False, "unpublish_all": False},
            )

            assert response.status_code == 409
            assert "active publications" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Publication Endpoints Tests
# ---------------------------------------------------------------------------


class TestPublicationEndpoints:
    """Tests for publication endpoints."""

    def test_publish_submodel_success(
        self, mock_settings, mock_connection, mock_registration
    ):
        """Test publishing a submodel."""
        mock_manager = MagicMock()
        mock_manager.get_connection.return_value = mock_connection
        mock_manager.create_registration.return_value = mock_registration

        app = create_test_app(mock_settings, mock_manager=mock_manager)

        with patch("app.routers.dataspace.get_settings", return_value=mock_settings):
            client = TestClient(app)

            response = client.post(
                "/api/dataspace/publications",
                json={
                    "connection_id": mock_connection.connection_id,
                    "template_name": "Nameplate",
                    "template_status": "published",
                    "form_data": {"elements": {}},
                    "aas_id": "urn:aas:new",
                    "submodel_id": "urn:submodel:new",
                },
            )

            assert response.status_code == 201
            data = response.json()
            assert "publication" in data

    def test_publish_submodel_connection_not_found(self, mock_settings):
        """Test publishing when connection doesn't exist."""
        mock_manager = MagicMock()
        mock_manager.get_connection.return_value = None

        app = create_test_app(mock_settings, mock_manager=mock_manager)

        with patch("app.routers.dataspace.get_settings", return_value=mock_settings):
            client = TestClient(app)

            response = client.post(
                "/api/dataspace/publications",
                json={
                    "connection_id": "nonexistent-id",
                    "template_name": "Nameplate",
                    "form_data": {},
                },
            )

            assert response.status_code == 404

    def test_list_publications(self, mock_settings, mock_registration):
        """Test listing publications."""
        mock_manager = MagicMock()
        mock_manager.list_registrations.return_value = [mock_registration]

        app = create_test_app(mock_settings, mock_manager=mock_manager)

        with patch("app.routers.dataspace.get_settings", return_value=mock_settings):
            client = TestClient(app)

            response = client.get("/api/dataspace/publications")

            assert response.status_code == 200
            data = response.json()
            assert "publications" in data

    def test_get_publication_success(self, mock_settings, mock_registration):
        """Test getting a specific publication."""
        mock_manager = MagicMock()
        mock_manager.get_registration.return_value = mock_registration

        app = create_test_app(mock_settings, mock_manager=mock_manager)

        with patch("app.routers.dataspace.get_settings", return_value=mock_settings):
            client = TestClient(app)

            response = client.get(
                f"/api/dataspace/publications/{mock_registration.registration_id}"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["publication_id"] == mock_registration.registration_id

    def test_unpublish_success(self, mock_settings, mock_registration):
        """Test unpublishing a submodel."""
        mock_manager = MagicMock()
        mock_manager.get_registration.return_value = mock_registration
        mock_manager.update_registration.return_value = mock_registration

        app = create_test_app(mock_settings, mock_manager=mock_manager)

        with patch("app.routers.dataspace.get_settings", return_value=mock_settings):
            client = TestClient(app)

            response = client.delete(
                f"/api/dataspace/publications/{mock_registration.registration_id}"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "unpublishing"


# ---------------------------------------------------------------------------
# Policy Endpoints Tests
# ---------------------------------------------------------------------------


class TestPolicyEndpoints:
    """Tests for policy endpoints."""

    def test_get_policy_templates(self, mock_settings):
        """Test getting policy templates."""
        app = create_test_app(mock_settings)

        with patch("app.routers.dataspace.get_settings", return_value=mock_settings):
            client = TestClient(app)

            response = client.get("/api/dataspace/policies/templates")

            assert response.status_code == 200
            data = response.json()
            assert len(data) > 0
            assert any(t["id"] == "unrestricted" for t in data)
            assert any(t["id"] == "membership_required" for t in data)

    def test_preview_policy(self, mock_settings):
        """Test previewing a policy configuration."""
        mock_engine = MagicMock()
        mock_engine.validate_policy.return_value = (True, [])

        app = create_test_app(mock_settings, mock_engine=mock_engine)

        with patch("app.routers.dataspace.get_settings", return_value=mock_settings):
            client = TestClient(app)

            response = client.post(
                "/api/dataspace/policies/preview",
                json={
                    "access_type": "membership",
                    "allowed_partners": [],
                    "constraints": [],
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert "odrl" in data
            assert data["valid"] is True

    def test_create_policy(self, mock_settings):
        """Test creating a policy."""
        mock_engine = MagicMock()
        mock_engine.validate_policy.return_value = (True, [])

        app = create_test_app(mock_settings, mock_engine=mock_engine)

        with patch("app.routers.dataspace.get_settings", return_value=mock_settings):
            client = TestClient(app)

            response = client.post(
                "/api/dataspace/policies",
                json={
                    "access_type": "public",
                    "allowed_partners": [],
                    "constraints": [],
                },
            )

            assert response.status_code == 201
            data = response.json()
            assert "policy_id" in data
            assert "odrl" in data


# ---------------------------------------------------------------------------
# Health Endpoints Tests
# ---------------------------------------------------------------------------


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_health_check_general(self, mock_settings):
        """Test general health check."""
        mock_manager = MagicMock()
        mock_checker = MagicMock()

        app = create_test_app(
            mock_settings, mock_manager=mock_manager, mock_checker=mock_checker
        )

        with patch("app.routers.dataspace.get_settings", return_value=mock_settings):
            client = TestClient(app)

            response = client.get("/api/dataspace/health")

            assert response.status_code == 200
            data = response.json()
            assert data["connection_id"] == "system"
            assert data["overall_healthy"] is True

    def test_health_check_specific_connection(
        self, mock_settings, mock_connection, mock_health_results
    ):
        """Test health check for specific connection."""
        mock_manager = MagicMock()
        mock_manager.get_connection.return_value = mock_connection
        mock_manager.update_connection.return_value = mock_connection

        mock_checker = MagicMock()
        mock_checker.check_connection.return_value = mock_health_results

        app = create_test_app(
            mock_settings, mock_manager=mock_manager, mock_checker=mock_checker
        )

        with patch("app.routers.dataspace.get_settings", return_value=mock_settings):
            client = TestClient(app)

            response = client.get(
                f"/api/dataspace/health?connection_id={mock_connection.connection_id}"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["connection_id"] == mock_connection.connection_id
            assert data["overall_healthy"] is True
            assert len(data["checks"]) == 2


# ---------------------------------------------------------------------------
# Environment and EDC Mode Endpoints Tests
# ---------------------------------------------------------------------------


class TestConfigurationEndpoints:
    """Tests for configuration endpoints."""

    def test_get_environments(self, mock_settings):
        """Test getting available environments."""
        app = create_test_app(mock_settings)

        with patch("app.routers.dataspace.get_settings", return_value=mock_settings):
            client = TestClient(app)

            response = client.get("/api/dataspace/environments")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 4
            assert any(env["id"] == "manufacturing-x" for env in data)
            assert any(e["id"] == "sandbox" for e in data)
            assert any(e["id"] == "catena-x-test" for e in data)
            assert any(e["id"] == "catena-x-prod" for e in data)

    def test_get_edc_modes(self, mock_settings):
        """Test getting available EDC modes."""
        app = create_test_app(mock_settings)

        with patch("app.routers.dataspace.get_settings", return_value=mock_settings):
            client = TestClient(app)

            response = client.get("/api/dataspace/edc-modes")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert any(m["id"] == "tractus-x" for m in data)
            assert any(m["id"] == "aas-extension" for m in data)


# ---------------------------------------------------------------------------
# Reconnect Endpoint Tests
# ---------------------------------------------------------------------------


class TestReconnectEndpoint:
    """Tests for reconnect endpoint."""

    def test_reconnect_success(self, mock_settings, mock_connection):
        """Test successful reconnection."""
        # Set connection to error state
        mock_connection.status = ConnectionStatus.ERROR

        mock_manager = MagicMock()
        mock_manager.get_connection.return_value = mock_connection
        mock_manager.update_connection.return_value = mock_connection

        app = create_test_app(mock_settings, mock_manager=mock_manager)

        with patch("app.routers.dataspace.get_settings", return_value=mock_settings):
            client = TestClient(app)

            response = client.post(
                f"/api/dataspace/connections/{mock_connection.connection_id}/reconnect"
            )

            assert response.status_code == 200
            data = response.json()
            assert "connection" in data

    def test_reconnect_not_found(self, mock_settings):
        """Test reconnecting non-existent connection."""
        mock_manager = MagicMock()
        mock_manager.get_connection.return_value = None

        app = create_test_app(mock_settings, mock_manager=mock_manager)

        with patch("app.routers.dataspace.get_settings", return_value=mock_settings):
            client = TestClient(app)

            response = client.post("/api/dataspace/connections/nonexistent-id/reconnect")

            assert response.status_code == 404
