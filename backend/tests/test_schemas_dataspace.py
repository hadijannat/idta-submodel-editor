"""
Tests for dataspace Pydantic schemas.
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.dataspace import (
    AccessType,
    ConstraintOperator,
    CreateConnectionRequest,
    DataspaceConnection,
    DataspaceConnectionEndpoints,
    DataspaceConnectionStatus,
    DisconnectRequest,
    HealthCheckResult,
    ListConnectionsResponse,
    PolicyConfig,
    PolicyConstraint,
    PublicationStatus,
    PublishSubmodelRequest,
    SubmodelPublication,
    SubmodelPublicationEndpoints,
)


# ---------------------------------------------------------------------------
# Enum Tests
# ---------------------------------------------------------------------------


class TestDataspaceConnectionStatus:
    """Tests for DataspaceConnectionStatus enum."""

    def test_all_statuses_exist(self):
        """Verify all expected statuses are defined."""
        expected = [
            "NOT_CONNECTED",
            "PROVISIONING_SECRETS",
            "CONFIGURING_EDC",
            "REGISTERING_CONNECTOR",
            "PUBLISHING_SELF_DESCRIPTION",
            "CONNECTED",
            "DEGRADED",
            "DISCONNECTED",
            "FAILED",
        ]
        for status in expected:
            assert hasattr(DataspaceConnectionStatus, status)

    def test_status_values(self):
        """Verify status string values."""
        assert DataspaceConnectionStatus.CONNECTED.value == "connected"
        assert DataspaceConnectionStatus.NOT_CONNECTED.value == "not_connected"
        assert DataspaceConnectionStatus.FAILED.value == "failed"


class TestPublicationStatus:
    """Tests for PublicationStatus enum."""

    def test_all_statuses_exist(self):
        """Verify all expected statuses are defined."""
        expected = [
            "PENDING",
            "REGISTERING",
            "PUBLISHING",
            "PUBLISHED",
            "UPDATING",
            "UNPUBLISHING",
            "UNPUBLISHED",
            "FAILED",
        ]
        for status in expected:
            assert hasattr(PublicationStatus, status)


# ---------------------------------------------------------------------------
# DataspaceConnection Tests
# ---------------------------------------------------------------------------


class TestDataspaceConnection:
    """Tests for DataspaceConnection model."""

    def test_minimal_connection(self):
        """Test creating a connection with minimal required fields."""
        now = datetime.now(timezone.utc)
        conn = DataspaceConnection(
            connection_id="conn-123",
            status=DataspaceConnectionStatus.NOT_CONNECTED,
            environment="sandbox",
            edc_mode="tractus-x",
            created_at=now,
            updated_at=now,
        )
        assert conn.connection_id == "conn-123"
        assert conn.status == DataspaceConnectionStatus.NOT_CONNECTED
        assert conn.environment == "sandbox"
        assert conn.edc_mode == "tractus-x"
        assert conn.progress == 0.0
        assert conn.bpn is None
        assert conn.endpoints.basyx_url is None

    def test_full_connection(self):
        """Test creating a connection with all fields."""
        now = datetime.now(timezone.utc)
        endpoints = DataspaceConnectionEndpoints(
            basyx_url="https://basyx.example.com",
            dtr_url="https://dtr.example.com",
            edc_control_url="https://edc-control.example.com",
            edc_data_url="https://edc-data.example.com",
        )
        conn = DataspaceConnection(
            connection_id="conn-456",
            status=DataspaceConnectionStatus.CONNECTED,
            environment="catena-x-test",
            edc_mode="aas-extension",
            bpn="BPNL000000001234",
            endpoints=endpoints,
            progress=1.0,
            progress_message="Fully connected",
            last_health_check=now,
            created_at=now,
            updated_at=now,
        )
        assert conn.bpn == "BPNL000000001234"
        assert conn.endpoints.basyx_url == "https://basyx.example.com"
        assert conn.progress == 1.0

    def test_invalid_bpn_format(self):
        """Test that invalid BPN format is rejected."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValidationError) as exc_info:
            DataspaceConnection(
                connection_id="conn-bad",
                status=DataspaceConnectionStatus.NOT_CONNECTED,
                environment="sandbox",
                edc_mode="tractus-x",
                bpn="INVALID_BPN",
                created_at=now,
                updated_at=now,
            )
        assert "BPN" in str(exc_info.value)

    def test_valid_bpn_format(self):
        """Test that valid BPN format is accepted."""
        now = datetime.now(timezone.utc)
        conn = DataspaceConnection(
            connection_id="conn-good",
            status=DataspaceConnectionStatus.NOT_CONNECTED,
            environment="sandbox",
            edc_mode="tractus-x",
            bpn="BPNL00000001TEST",
            created_at=now,
            updated_at=now,
        )
        assert conn.bpn == "BPNL00000001TEST"

    def test_progress_bounds(self):
        """Test that progress is bounded between 0 and 1."""
        now = datetime.now(timezone.utc)

        # Valid progress
        conn = DataspaceConnection(
            connection_id="conn-prog",
            status=DataspaceConnectionStatus.PROVISIONING_SECRETS,
            environment="sandbox",
            edc_mode="tractus-x",
            progress=0.5,
            created_at=now,
            updated_at=now,
        )
        assert conn.progress == 0.5

        # Invalid progress > 1
        with pytest.raises(ValidationError):
            DataspaceConnection(
                connection_id="conn-bad",
                status=DataspaceConnectionStatus.PROVISIONING_SECRETS,
                environment="sandbox",
                edc_mode="tractus-x",
                progress=1.5,
                created_at=now,
                updated_at=now,
            )

        # Invalid progress < 0
        with pytest.raises(ValidationError):
            DataspaceConnection(
                connection_id="conn-bad",
                status=DataspaceConnectionStatus.PROVISIONING_SECRETS,
                environment="sandbox",
                edc_mode="tractus-x",
                progress=-0.1,
                created_at=now,
                updated_at=now,
            )

    def test_invalid_environment(self):
        """Test that invalid environment is rejected."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValidationError):
            DataspaceConnection(
                connection_id="conn-bad",
                status=DataspaceConnectionStatus.NOT_CONNECTED,
                environment="invalid-env",  # type: ignore
                edc_mode="tractus-x",
                created_at=now,
                updated_at=now,
            )


# ---------------------------------------------------------------------------
# CreateConnectionRequest Tests
# ---------------------------------------------------------------------------


class TestCreateConnectionRequest:
    """Tests for CreateConnectionRequest model."""

    def test_sandbox_without_bpn(self):
        """Test that sandbox environment works without BPN."""
        req = CreateConnectionRequest(
            environment="sandbox",
            edc_mode="tractus-x",
        )
        assert req.environment == "sandbox"
        assert req.bpn is None

    def test_catenax_requires_bpn(self):
        """Test that Catena-X environments require BPN."""
        with pytest.raises(ValidationError) as exc_info:
            CreateConnectionRequest(
                environment="catena-x-test",
                edc_mode="tractus-x",
            )
        assert "BPN is required" in str(exc_info.value)

    def test_catenax_with_valid_bpn(self):
        """Test Catena-X environment with valid BPN."""
        req = CreateConnectionRequest(
            environment="catena-x-prod",
            edc_mode="aas-extension",
            bpn="BPNL00000001PROD",
        )
        assert req.bpn == "BPNL00000001PROD"

    def test_catenax_with_invalid_bpn(self):
        """Test Catena-X environment with invalid BPN format."""
        with pytest.raises(ValidationError) as exc_info:
            CreateConnectionRequest(
                environment="catena-x-test",
                edc_mode="tractus-x",
                bpn="INVALID",
            )
        assert "BPN" in str(exc_info.value)

    def test_with_credentials(self):
        """Test request with credentials."""
        req = CreateConnectionRequest(
            environment="sandbox",
            edc_mode="tractus-x",
            credentials={"api_key": "secret123", "client_secret": "secret456"},
        )
        assert req.credentials["api_key"] == "secret123"


# ---------------------------------------------------------------------------
# PolicyConfig Tests
# ---------------------------------------------------------------------------


class TestPolicyConfig:
    """Tests for PolicyConfig model."""

    def test_default_policy(self):
        """Test creating a policy with defaults."""
        policy = PolicyConfig()
        assert policy.access_type == AccessType.RESTRICTED
        assert policy.target_paths == []
        assert policy.allowed_partners == []
        assert policy.constraints == []

    def test_public_policy(self):
        """Test creating a public access policy."""
        policy = PolicyConfig(access_type=AccessType.PUBLIC)
        assert policy.access_type == AccessType.PUBLIC

    def test_restricted_policy_with_partners(self):
        """Test creating a restricted policy with allowed partners."""
        policy = PolicyConfig(
            access_type=AccessType.RESTRICTED,
            allowed_partners=["BPNL00000001AAAA", "BPNL00000001BBBB"],
        )
        assert len(policy.allowed_partners) == 2

    def test_invalid_partner_bpn(self):
        """Test that invalid partner BPN is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            PolicyConfig(
                access_type=AccessType.RESTRICTED,
                allowed_partners=["INVALID_BPN"],
            )
        assert "Invalid BPN format" in str(exc_info.value)

    def test_policy_with_constraints(self):
        """Test creating a policy with ODRL constraints."""
        policy = PolicyConfig(
            access_type=AccessType.MEMBERSHIP,
            constraints=[
                PolicyConstraint(
                    left_operand="Membership",
                    operator=ConstraintOperator.EQ,
                    right_operand="active",
                ),
                PolicyConstraint(
                    left_operand="BusinessPartnerNumber",
                    operator=ConstraintOperator.IS_ANY_OF,
                    right_operand=["BPNL00000001AAAA", "BPNL00000001BBBB"],
                ),
            ],
        )
        assert len(policy.constraints) == 2
        assert policy.constraints[0].operator == ConstraintOperator.EQ

    def test_policy_with_validity_period(self):
        """Test creating a policy with validity period."""
        now = datetime.now(timezone.utc)
        policy = PolicyConfig(
            valid_from=now,
            valid_until=datetime(2025, 12, 31, tzinfo=timezone.utc),
        )
        assert policy.valid_from == now


# ---------------------------------------------------------------------------
# SubmodelPublication Tests
# ---------------------------------------------------------------------------


class TestSubmodelPublication:
    """Tests for SubmodelPublication model."""

    def test_minimal_publication(self):
        """Test creating a publication with minimal fields."""
        now = datetime.now(timezone.utc)
        pub = SubmodelPublication(
            publication_id="pub-123",
            connection_id="conn-456",
            template_name="DigitalNameplate",
            submodel_id="urn:example:submodel:1",
            status=PublicationStatus.PENDING,
            created_at=now,
            updated_at=now,
        )
        assert pub.publication_id == "pub-123"
        assert pub.status == PublicationStatus.PENDING
        assert pub.aas_id is None

    def test_full_publication(self):
        """Test creating a publication with all fields."""
        now = datetime.now(timezone.utc)
        endpoints = SubmodelPublicationEndpoints(
            aas_repository_url="https://basyx.example.com/aas",
            submodel_repository_url="https://basyx.example.com/submodel",
            dtr_asset_id="dtr-asset-123",
            edc_asset_id="edc-asset-456",
        )
        pub = SubmodelPublication(
            publication_id="pub-789",
            connection_id="conn-456",
            template_name="CarbonFootprint",
            submodel_id="urn:example:submodel:2",
            aas_id="urn:example:aas:1",
            status=PublicationStatus.PUBLISHED,
            endpoints=endpoints,
            policy_id="policy-abc",
            created_at=now,
            updated_at=now,
        )
        assert pub.endpoints.dtr_asset_id == "dtr-asset-123"
        assert pub.policy_id == "policy-abc"


# ---------------------------------------------------------------------------
# PublishSubmodelRequest Tests
# ---------------------------------------------------------------------------


class TestPublishSubmodelRequest:
    """Tests for PublishSubmodelRequest model."""

    def test_minimal_publish_request(self):
        """Test creating a minimal publish request."""
        req = PublishSubmodelRequest(
            connection_id="conn-123",
            template_name="DigitalNameplate",
            form_data={"elements": {}},
        )
        assert req.connection_id == "conn-123"
        assert req.template_status == "published"
        assert req.policy is None

    def test_full_publish_request(self):
        """Test creating a full publish request with all options."""
        req = PublishSubmodelRequest(
            connection_id="conn-123",
            template_name="CarbonFootprint",
            template_status="deprecated",
            template_version="1.0.0",
            form_data={"elements": {"ProductId": {"value": "ABC123"}}},
            aas_id="urn:example:aas:custom",
            submodel_id="urn:example:submodel:custom",
            policy=PolicyConfig(
                access_type=AccessType.RESTRICTED,
                allowed_partners=["BPNL00000001PART"],
            ),
        )
        assert req.template_version == "1.0.0"
        assert req.policy.allowed_partners == ["BPNL00000001PART"]


# ---------------------------------------------------------------------------
# Response Model Tests
# ---------------------------------------------------------------------------


class TestListConnectionsResponse:
    """Tests for ListConnectionsResponse model."""

    def test_empty_list(self):
        """Test empty connections list."""
        resp = ListConnectionsResponse(connections=[], total=0)
        assert resp.total == 0
        assert len(resp.connections) == 0

    def test_with_connections(self):
        """Test response with connections."""
        now = datetime.now(timezone.utc)
        conn = DataspaceConnection(
            connection_id="conn-1",
            status=DataspaceConnectionStatus.CONNECTED,
            environment="sandbox",
            edc_mode="tractus-x",
            created_at=now,
            updated_at=now,
        )
        resp = ListConnectionsResponse(connections=[conn], total=1)
        assert resp.total == 1
        assert resp.connections[0].connection_id == "conn-1"


class TestHealthCheckResult:
    """Tests for HealthCheckResult model."""

    def test_healthy_check(self):
        """Test a healthy component check."""
        now = datetime.now(timezone.utc)
        check = HealthCheckResult(
            component="basyx",
            healthy=True,
            latency_ms=45.2,
            message="OK",
            checked_at=now,
        )
        assert check.healthy is True
        assert check.latency_ms == 45.2

    def test_unhealthy_check(self):
        """Test an unhealthy component check."""
        now = datetime.now(timezone.utc)
        check = HealthCheckResult(
            component="edc",
            healthy=False,
            message="Connection refused",
            checked_at=now,
        )
        assert check.healthy is False
        assert check.latency_ms is None


class TestDisconnectRequest:
    """Tests for DisconnectRequest model."""

    def test_default_disconnect(self):
        """Test default disconnect request."""
        req = DisconnectRequest()
        assert req.force is False
        assert req.unpublish_all is False

    def test_force_disconnect(self):
        """Test force disconnect with unpublish."""
        req = DisconnectRequest(force=True, unpublish_all=True)
        assert req.force is True
        assert req.unpublish_all is True


# ---------------------------------------------------------------------------
# Serialization Tests
# ---------------------------------------------------------------------------


class TestSerialization:
    """Tests for model serialization."""

    def test_connection_to_dict(self):
        """Test serializing a connection to dict."""
        now = datetime.now(timezone.utc)
        conn = DataspaceConnection(
            connection_id="conn-ser",
            status=DataspaceConnectionStatus.CONNECTED,
            environment="sandbox",
            edc_mode="tractus-x",
            progress=0.75,
            created_at=now,
            updated_at=now,
        )
        data = conn.model_dump()
        assert data["connection_id"] == "conn-ser"
        assert data["status"] == "connected"
        assert data["progress"] == 0.75

    def test_connection_to_json(self):
        """Test serializing a connection to JSON."""
        now = datetime.now(timezone.utc)
        conn = DataspaceConnection(
            connection_id="conn-json",
            status=DataspaceConnectionStatus.FAILED,
            environment="catena-x-test",
            edc_mode="aas-extension",
            bpn="BPNL00000001JSON",
            error_message="Connection timed out",
            created_at=now,
            updated_at=now,
        )
        json_str = conn.model_dump_json()
        assert "conn-json" in json_str
        assert "failed" in json_str
        assert "BPNL00000001JSON" in json_str

    def test_policy_serialization(self):
        """Test serializing a policy with constraints."""
        policy = PolicyConfig(
            access_type=AccessType.RESTRICTED,
            allowed_partners=["BPNL00000001AAAA"],
            constraints=[
                PolicyConstraint(
                    left_operand="Membership",
                    operator=ConstraintOperator.EQ,
                    right_operand="active",
                )
            ],
        )
        data = policy.model_dump()
        assert data["access_type"] == "restricted"
        assert data["constraints"][0]["operator"] == "eq"
