"""
Tests for transfer-related dataspace router endpoints.

Tests transfer initiation, listing, retrieval, EDR access, and termination.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.services.dataspace.models import (
    ConnectionState,
    ConnectionStatus,
    DataspaceType,
    TransferProcess,
    TransferState,
)


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------


def create_test_app(mock_manager=None, mock_checker=None, mock_settings=None):
    """
    Create a FastAPI test application with mocked dependencies.

    Creates a minimal app with just the dataspace router for testing.
    """
    from app.errors import APIError, ErrorCode, ErrorResponse
    from app.middleware.correlation import get_correlation_id
    from app.routers.dataspace import (
        router,
        get_connection_manager,
        get_health_checker,
    )
    import app.routers.dataspace as dataspace_module

    # Mock get_settings to enable dataspace feature
    if mock_settings is None:
        mock_settings = MagicMock()
        mock_settings.dataspace_enabled = True
        mock_settings.dataspace_default_environment = "sandbox"
        mock_settings.dataspace_default_edc_mode = "tractus-x"

    original_get_settings = dataspace_module.get_settings
    dataspace_module.get_settings = lambda: mock_settings

    app = FastAPI()
    app.include_router(router)

    @app.exception_handler(APIError)
    async def api_error_handler(request: Request, exc: APIError):
        correlation_id = (
            getattr(request.state, "correlation_id", get_correlation_id()) or "unknown"
        )
        response = exc.to_response(correlation_id)
        return JSONResponse(
            status_code=exc.status_code,
            content=response.model_dump(mode="json"),
            headers={"X-Correlation-ID": correlation_id},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        correlation_id = (
            getattr(request.state, "correlation_id", get_correlation_id()) or "unknown"
        )
        response = ErrorResponse(
            code=ErrorCode.VALIDATION_FAILED,
            message="Request validation failed",
            detail={"errors": exc.errors()},
            correlation_id=correlation_id,
        )
        return JSONResponse(
            status_code=422,
            content=response.model_dump(mode="json"),
            headers={"X-Correlation-ID": correlation_id},
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        correlation_id = (
            getattr(request.state, "correlation_id", get_correlation_id()) or "unknown"
        )
        code_map = {
            400: ErrorCode.BAD_REQUEST,
            404: ErrorCode.RESOURCE_NOT_FOUND,
            409: ErrorCode.RESOURCE_CONFLICT,
            422: ErrorCode.VALIDATION_FAILED,
        }
        error_code = code_map.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
        response = ErrorResponse(
            code=error_code,
            message=exc.detail if isinstance(exc.detail, str) else str(exc.detail),
            detail=exc.detail if isinstance(exc.detail, dict) else None,
            correlation_id=correlation_id,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=response.model_dump(mode="json"),
            headers={"X-Correlation-ID": correlation_id},
        )

    # Override dependencies
    if mock_manager is not None:
        app.dependency_overrides[get_connection_manager] = lambda: mock_manager

    if mock_checker is not None:
        app.dependency_overrides[get_health_checker] = lambda: mock_checker

    return app


@pytest.fixture
def sample_connection():
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
def sample_transfer_started():
    """Create a sample transfer in STARTED state."""
    return TransferProcess(
        transfer_id="transfer-12345",
        connection_id="test-conn-12345",
        agreement_id="agreement-001",
        asset_id="urn:asset:test",
        provider_bpn="BPNL00000002PROV",
        consumer_bpn="BPNL00000001TEST",
        state=TransferState.STARTED,
        transfer_type="HttpData-PULL",
        created_at=datetime(2024, 1, 1, 16, 0),
        updated_at=datetime(2024, 1, 1, 16, 5),
    )


@pytest.fixture
def sample_transfer_completed():
    """Create a sample completed transfer with EDR."""
    return TransferProcess(
        transfer_id="transfer-12345",
        connection_id="test-conn-12345",
        agreement_id="agreement-001",
        asset_id="urn:asset:test",
        provider_bpn="BPNL00000002PROV",
        consumer_bpn="BPNL00000001TEST",
        state=TransferState.COMPLETED,
        transfer_type="HttpData-PULL",
        edr_endpoint="http://provider:8080/api/data",
        edr_token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        edr_expires_at=datetime(2024, 1, 2, 16, 0),
        created_at=datetime(2024, 1, 1, 16, 0),
        updated_at=datetime(2024, 1, 1, 16, 10),
        started_at=datetime(2024, 1, 1, 16, 1),
        completed_at=datetime(2024, 1, 1, 16, 10),
    )


@pytest.fixture
def sample_transfer_terminated():
    """Create a sample terminated transfer."""
    return TransferProcess(
        transfer_id="transfer-12345",
        connection_id="test-conn-12345",
        agreement_id="agreement-001",
        asset_id="urn:asset:test",
        provider_bpn="BPNL00000002PROV",
        consumer_bpn="BPNL00000001TEST",
        state=TransferState.TERMINATED,
        transfer_type="HttpData-PULL",
        created_at=datetime(2024, 1, 1, 16, 0),
        updated_at=datetime(2024, 1, 1, 16, 15),
    )


@pytest.fixture
def mock_connection_manager(sample_connection, sample_transfer_started):
    """Create mocked connection manager with transfer support."""
    manager = MagicMock()
    manager.get_connection.return_value = sample_connection
    manager.list_connections.return_value = [sample_connection]

    # Transfer methods - list_transfers returns just a list, not a tuple
    manager.create_transfer.return_value = sample_transfer_started
    manager.get_transfer.return_value = sample_transfer_started
    manager.list_transfers.return_value = [sample_transfer_started]
    manager.update_transfer.return_value = sample_transfer_started

    return manager


@pytest.fixture
def app_client(mock_connection_manager):
    """Create test client with mocked dependencies."""
    mock_health_checker = MagicMock()
    mock_health_checker.check_connection.return_value = []

    app = create_test_app(
        mock_manager=mock_connection_manager,
        mock_checker=mock_health_checker,
    )

    client = TestClient(app)
    yield client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestInitiateTransfer:
    """Tests for POST /api/dataspace/transfers."""

    def test_initiate_transfer_success(
        self,
        app_client,
        mock_connection_manager,
        sample_transfer_started,
    ):
        """Test successful transfer initiation."""
        request_data = {
            "connection_id": "test-conn-12345",
            "agreement_id": "agreement-001",
            "asset_id": "urn:asset:test",
            "provider_address": "http://provider:8080/api/v1/dsp",
            "provider_bpn": "BPNL00000002PROV",
        }

        response = app_client.post("/api/dataspace/transfers", json=request_data)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "transfer" in data
        assert "transfer_id" in data["transfer"]
        assert data["transfer"]["state"] in ["initial", "started", "provisioning"]

    def test_initiate_transfer_missing_connection(
        self,
        app_client,
        mock_connection_manager,
    ):
        """Test transfer initiation with non-existent connection."""
        mock_connection_manager.get_connection.return_value = None

        request_data = {
            "connection_id": "non-existent",
            "agreement_id": "agreement-001",
            "asset_id": "urn:asset:test",
            "provider_address": "http://provider:8080/api/v1/dsp",
            "provider_bpn": "BPNL00000002PROV",
        }

        response = app_client.post("/api/dataspace/transfers", json=request_data)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_initiate_transfer_invalid_request(self, app_client):
        """Test transfer initiation with invalid request."""
        request_data = {
            "connection_id": "test-conn-12345",
            # Missing required fields
        }

        response = app_client.post("/api/dataspace/transfers", json=request_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestListTransfers:
    """Tests for GET /api/dataspace/transfers."""

    def test_list_transfers_success(
        self,
        app_client,
        mock_connection_manager,
        sample_transfer_started,
    ):
        """Test listing transfers."""
        response = app_client.get("/api/dataspace/transfers")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "transfers" in data
        assert "total" in data

    def test_list_transfers_filter_by_connection(
        self,
        app_client,
        mock_connection_manager,
    ):
        """Test filtering transfers by connection_id."""
        response = app_client.get(
            "/api/dataspace/transfers",
            params={"connection_id": "test-conn-12345"},
        )

        assert response.status_code == status.HTTP_200_OK
        mock_connection_manager.list_transfers.assert_called()

    def test_list_transfers_filter_by_status(
        self,
        app_client,
        mock_connection_manager,
    ):
        """Test filtering transfers by status."""
        response = app_client.get(
            "/api/dataspace/transfers",
            params={"status": "completed"},
        )

        assert response.status_code == status.HTTP_200_OK


class TestGetTransfer:
    """Tests for GET /api/dataspace/transfers/{transfer_id}."""

    def test_get_transfer_success(
        self,
        app_client,
        mock_connection_manager,
        sample_transfer_started,
    ):
        """Test getting a specific transfer."""
        response = app_client.get(
            f"/api/dataspace/transfers/{sample_transfer_started.transfer_id}"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["transfer_id"] == sample_transfer_started.transfer_id

    def test_get_transfer_not_found(
        self,
        app_client,
        mock_connection_manager,
    ):
        """Test getting non-existent transfer."""
        mock_connection_manager.get_transfer.return_value = None

        response = app_client.get("/api/dataspace/transfers/non-existent")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestGetTransferEDR:
    """Tests for GET /api/dataspace/transfers/{transfer_id}/edr."""

    def test_get_edr_success(
        self,
        app_client,
        mock_connection_manager,
        sample_transfer_completed,
    ):
        """Test getting EDR for completed transfer."""
        mock_connection_manager.get_transfer.return_value = sample_transfer_completed

        response = app_client.get(
            f"/api/dataspace/transfers/{sample_transfer_completed.transfer_id}/edr"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Response has nested EDR structure
        assert "edr" in data
        assert "endpoint" in data["edr"]
        assert "auth_token" in data["edr"]

    def test_get_edr_transfer_not_completed(
        self,
        app_client,
        mock_connection_manager,
        sample_transfer_started,
    ):
        """Test that EDR is not available for non-completed transfers."""
        mock_connection_manager.get_transfer.return_value = sample_transfer_started

        response = app_client.get(
            f"/api/dataspace/transfers/{sample_transfer_started.transfer_id}/edr"
        )

        # Should return error or indicate EDR not available
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
        ]

    def test_get_edr_transfer_not_found(
        self,
        app_client,
        mock_connection_manager,
    ):
        """Test getting EDR for non-existent transfer."""
        mock_connection_manager.get_transfer.return_value = None

        response = app_client.get("/api/dataspace/transfers/non-existent/edr")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestTerminateTransfer:
    """Tests for POST /api/dataspace/transfers/{transfer_id}/terminate."""

    def test_terminate_transfer_success(
        self,
        app_client,
        mock_connection_manager,
        sample_transfer_started,
        sample_transfer_terminated,
    ):
        """Test terminating an active transfer."""
        mock_connection_manager.get_transfer.return_value = sample_transfer_started
        mock_connection_manager.update_transfer.return_value = sample_transfer_terminated

        response = app_client.post(
            f"/api/dataspace/transfers/{sample_transfer_started.transfer_id}/terminate"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["state"] == "terminated"

    def test_terminate_transfer_not_found(
        self,
        app_client,
        mock_connection_manager,
    ):
        """Test terminating non-existent transfer."""
        mock_connection_manager.get_transfer.return_value = None

        response = app_client.post("/api/dataspace/transfers/non-existent/terminate")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_terminate_already_completed_transfer(
        self,
        app_client,
        mock_connection_manager,
        sample_transfer_completed,
    ):
        """Test that completed transfers cannot be terminated."""
        mock_connection_manager.get_transfer.return_value = sample_transfer_completed

        response = app_client.post(
            f"/api/dataspace/transfers/{sample_transfer_completed.transfer_id}/terminate"
        )

        # Should return 409 Conflict for already terminal state
        assert response.status_code == status.HTTP_409_CONFLICT


# ---------------------------------------------------------------------------
# Model Tests
# ---------------------------------------------------------------------------


class TestTransferProcess:
    """Tests for TransferProcess model."""

    def test_transfer_is_terminal(
        self, sample_transfer_completed, sample_transfer_terminated
    ):
        """Test is_terminal property."""
        assert sample_transfer_completed.is_terminal is True
        assert sample_transfer_terminated.is_terminal is True

    def test_transfer_is_active(self, sample_transfer_started):
        """Test is_active property."""
        assert sample_transfer_started.is_active is True

    def test_transfer_to_dict_and_from_dict(self, sample_transfer_started):
        """Test serialization round-trip."""
        transfer_dict = sample_transfer_started.to_dict()
        restored = TransferProcess.from_dict(transfer_dict)

        assert restored.transfer_id == sample_transfer_started.transfer_id
        assert restored.connection_id == sample_transfer_started.connection_id
        assert restored.state == sample_transfer_started.state
        assert restored.asset_id == sample_transfer_started.asset_id

    def test_transfer_with_edr(self, sample_transfer_completed):
        """Test transfer with EDR fields."""
        assert sample_transfer_completed.edr_endpoint is not None
        assert sample_transfer_completed.edr_token is not None
        assert sample_transfer_completed.edr_expires_at is not None
