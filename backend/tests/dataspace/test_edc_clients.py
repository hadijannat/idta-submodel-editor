"""
Tests for the EDC clients (TractusXClient and AASExtensionClient).

Uses pytest with mocked httpx requests.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.services.dataspace.edc import (
    TractusXClient,
    AASExtensionClient,
    EDCClientError,
    EDCAssetNotFoundError,
    EDCAssetConflictError,
    EDCPolicyNotFoundError,
    EDCContractNotFoundError,
    EDCNegotiationError,
    EDCAuthenticationError,
    EDCConnectionError,
    AASExtensionError,
    AASShellNotFoundError,
    AASSubmodelNotFoundError,
)


# ---------------------------------------------------------------------------
# TractusXClient Tests
# ---------------------------------------------------------------------------


class TestTractusXClientInit:
    """Tests for TractusXClient initialization."""

    def test_init_basic(self):
        """Test basic client initialization."""
        client = TractusXClient(base_url="http://edc:8080")
        assert client.base_url == "http://edc:8080"
        assert client.api_key is None
        assert client.auth_token is None
        assert client.timeout == 30.0

    def test_init_strips_trailing_slash(self):
        """Test that trailing slash is stripped from base URL."""
        client = TractusXClient(base_url="http://edc:8080/")
        assert client.base_url == "http://edc:8080"

    def test_init_with_api_key(self):
        """Test client initialization with API key."""
        client = TractusXClient(
            base_url="http://edc:8080",
            api_key="test-api-key",
        )
        assert client.api_key == "test-api-key"

    def test_init_with_auth_token(self):
        """Test client initialization with auth token."""
        client = TractusXClient(
            base_url="http://edc:8080",
            auth_token="test-bearer-token",
        )
        assert client.auth_token == "test-bearer-token"

    def test_init_custom_timeout(self):
        """Test client with custom timeout."""
        client = TractusXClient(base_url="http://edc:8080", timeout=60.0)
        assert client.timeout == 60.0

    def test_update_auth_token(self):
        """Test updating auth token."""
        client = TractusXClient(base_url="http://edc:8080")
        client.update_auth_token("new-token")
        assert client.auth_token == "new-token"


class TestTractusXClientAssetOperations:
    """Tests for TractusXClient asset operations."""

    @pytest.fixture
    def mock_client(self):
        """Create a TractusXClient with mocked HTTP client."""
        client = TractusXClient(base_url="http://edc:8080")
        client._client = AsyncMock(spec=httpx.AsyncClient)
        return client

    @pytest.mark.asyncio
    async def test_create_asset_success(self, mock_client):
        """Test successful asset creation."""
        asset = {
            "@id": "test-asset-1",
            "properties": {"name": "Test Asset"},
            "dataAddress": {"type": "HttpData", "baseUrl": "http://example.com"},
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = json.dumps(asset).encode()
        mock_response.json.return_value = asset
        mock_client._client.post = AsyncMock(return_value=mock_response)

        result = await mock_client.create_asset(asset)

        assert result["@id"] == "test-asset-1"
        mock_client._client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_asset_conflict(self, mock_client):
        """Test asset creation when already exists."""
        asset = {"@id": "test-asset-1"}

        mock_response = MagicMock()
        mock_response.status_code = 409
        mock_response.text = "Asset already exists"
        mock_client._client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(EDCAssetConflictError):
            await mock_client.create_asset(asset)

    @pytest.mark.asyncio
    async def test_get_asset_success(self, mock_client):
        """Test getting an existing asset."""
        asset = {
            "@id": "test-asset-1",
            "properties": {"name": "Test Asset"},
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = json.dumps(asset).encode()
        mock_response.json.return_value = asset
        mock_client._client.get = AsyncMock(return_value=mock_response)

        result = await mock_client.get_asset("test-asset-1")

        assert result is not None
        assert result["@id"] == "test-asset-1"

    @pytest.mark.asyncio
    async def test_get_asset_not_found(self, mock_client):
        """Test getting a non-existent asset."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not found"
        mock_client._client.get = AsyncMock(return_value=mock_response)

        result = await mock_client.get_asset("nonexistent-asset")

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_asset_success(self, mock_client):
        """Test deleting an asset."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.content = b""
        mock_client._client.delete = AsyncMock(return_value=mock_response)

        result = await mock_client.delete_asset("test-asset-1")

        assert result is True

    @pytest.mark.asyncio
    async def test_query_assets_success(self, mock_client):
        """Test querying assets."""
        assets = [
            {"@id": "asset-1"},
            {"@id": "asset-2"},
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = json.dumps(assets).encode()
        mock_response.json.return_value = assets
        mock_client._client.post = AsyncMock(return_value=mock_response)

        result = await mock_client.query_assets(limit=10)

        assert len(result) == 2


class TestTractusXClientPolicyOperations:
    """Tests for TractusXClient policy operations."""

    @pytest.fixture
    def mock_client(self):
        """Create a TractusXClient with mocked HTTP client."""
        client = TractusXClient(base_url="http://edc:8080")
        client._client = AsyncMock(spec=httpx.AsyncClient)
        return client

    @pytest.mark.asyncio
    async def test_create_policy_success(self, mock_client):
        """Test successful policy creation."""
        policy = {
            "@id": "test-policy-1",
            "policy": {"@type": "odrl:Set"},
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = json.dumps(policy).encode()
        mock_response.json.return_value = policy
        mock_client._client.post = AsyncMock(return_value=mock_response)

        result = await mock_client.create_policy(policy)

        assert result["@id"] == "test-policy-1"

    @pytest.mark.asyncio
    async def test_get_policy_not_found(self, mock_client):
        """Test getting a non-existent policy."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not found"
        mock_client._client.get = AsyncMock(return_value=mock_response)

        result = await mock_client.get_policy("nonexistent-policy")

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_policy_success(self, mock_client):
        """Test deleting a policy."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.content = b""
        mock_client._client.delete = AsyncMock(return_value=mock_response)

        result = await mock_client.delete_policy("test-policy-1")

        assert result is True


class TestTractusXClientContractOperations:
    """Tests for TractusXClient contract operations."""

    @pytest.fixture
    def mock_client(self):
        """Create a TractusXClient with mocked HTTP client."""
        client = TractusXClient(base_url="http://edc:8080")
        client._client = AsyncMock(spec=httpx.AsyncClient)
        return client

    @pytest.mark.asyncio
    async def test_create_contract_definition_success(self, mock_client):
        """Test successful contract definition creation."""
        definition = {
            "@id": "test-contract-def-1",
            "accessPolicyId": "policy-1",
            "contractPolicyId": "policy-1",
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = json.dumps(definition).encode()
        mock_response.json.return_value = definition
        mock_client._client.post = AsyncMock(return_value=mock_response)

        result = await mock_client.create_contract_definition(definition)

        assert result["@id"] == "test-contract-def-1"

    @pytest.mark.asyncio
    async def test_delete_contract_definition_success(self, mock_client):
        """Test deleting a contract definition."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.content = b""
        mock_client._client.delete = AsyncMock(return_value=mock_response)

        result = await mock_client.delete_contract_definition("test-contract-def-1")

        assert result is True


class TestTractusXClientNegotiation:
    """Tests for TractusXClient negotiation operations."""

    @pytest.fixture
    def mock_client(self):
        """Create a TractusXClient with mocked HTTP client."""
        client = TractusXClient(base_url="http://edc:8080")
        client._client = AsyncMock(spec=httpx.AsyncClient)
        return client

    @pytest.mark.asyncio
    async def test_initiate_negotiation_success(self, mock_client):
        """Test successful negotiation initiation."""
        negotiation_result = {
            "@id": "negotiation-123",
            "state": "REQUESTING",
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = json.dumps(negotiation_result).encode()
        mock_response.json.return_value = negotiation_result
        mock_response.text = ""
        mock_client._client.post = AsyncMock(return_value=mock_response)

        offer = {
            "offerId": "offer-1",
            "assetId": "asset-1",
            "policy": {"@type": "odrl:Set"},
        }

        result = await mock_client.initiate_negotiation(
            counter_party_address="http://provider:8080/api/v1/dsp",
            protocol="dataspace-protocol-http",
            offer=offer,
        )

        assert result["@id"] == "negotiation-123"
        assert result["state"] == "REQUESTING"

    @pytest.mark.asyncio
    async def test_get_negotiation_success(self, mock_client):
        """Test getting negotiation state."""
        negotiation = {
            "@id": "negotiation-123",
            "state": "AGREED",
            "contractAgreementId": "agreement-456",
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = json.dumps(negotiation).encode()
        mock_response.json.return_value = negotiation
        mock_client._client.get = AsyncMock(return_value=mock_response)

        result = await mock_client.get_negotiation("negotiation-123")

        assert result is not None
        assert result["state"] == "AGREED"

    @pytest.mark.asyncio
    async def test_get_negotiation_state(self, mock_client):
        """Test getting just negotiation state string."""
        negotiation = {
            "@id": "negotiation-123",
            "state": "FINALIZED",
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = json.dumps(negotiation).encode()
        mock_response.json.return_value = negotiation
        mock_client._client.get = AsyncMock(return_value=mock_response)

        state = await mock_client.get_negotiation_state("negotiation-123")

        assert state == "FINALIZED"


class TestTractusXClientCatalog:
    """Tests for TractusXClient catalog operations."""

    @pytest.fixture
    def mock_client(self):
        """Create a TractusXClient with mocked HTTP client."""
        client = TractusXClient(base_url="http://edc:8080")
        client._client = AsyncMock(spec=httpx.AsyncClient)
        return client

    @pytest.mark.asyncio
    async def test_request_catalog_success(self, mock_client):
        """Test requesting catalog."""
        catalog = {
            "@type": "dcat:Catalog",
            "dcat:dataset": [
                {"@id": "offer-1"},
                {"@id": "offer-2"},
            ],
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = json.dumps(catalog).encode()
        mock_response.json.return_value = catalog
        mock_client._client.post = AsyncMock(return_value=mock_response)

        result = await mock_client.request_catalog(
            counter_party_address="http://provider:8080/api/v1/dsp",
        )

        assert result["@type"] == "dcat:Catalog"
        assert len(result["dcat:dataset"]) == 2

    @pytest.mark.asyncio
    async def test_get_catalog_offers_success(self, mock_client):
        """Test getting catalog offers."""
        catalog = {
            "@type": "dcat:Catalog",
            "dcat:dataset": [
                {"@id": "offer-1", "name": "Test Offer"},
            ],
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = json.dumps(catalog).encode()
        mock_response.json.return_value = catalog
        mock_client._client.post = AsyncMock(return_value=mock_response)

        offers = await mock_client.get_catalog_offers(
            counter_party_address="http://provider:8080/api/v1/dsp",
            asset_id="asset-1",
        )

        assert len(offers) == 1
        assert offers[0]["@id"] == "offer-1"


class TestTractusXClientTransfer:
    """Tests for TractusXClient transfer operations."""

    @pytest.fixture
    def mock_client(self):
        """Create a TractusXClient with mocked HTTP client."""
        client = TractusXClient(base_url="http://edc:8080")
        client._client = AsyncMock(spec=httpx.AsyncClient)
        return client

    @pytest.mark.asyncio
    async def test_initiate_transfer_success(self, mock_client):
        """Test initiating a transfer."""
        transfer_result = {
            "@id": "transfer-123",
            "state": "INITIAL",
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = json.dumps(transfer_result).encode()
        mock_response.json.return_value = transfer_result
        mock_response.text = ""
        mock_client._client.post = AsyncMock(return_value=mock_response)

        result = await mock_client.initiate_transfer(
            agreement_id="agreement-456",
            asset_id="asset-1",
            counter_party_address="http://provider:8080/api/v1/dsp",
            data_destination={"type": "HttpData"},
        )

        assert result["@id"] == "transfer-123"

    @pytest.mark.asyncio
    async def test_get_transfer_state(self, mock_client):
        """Test getting transfer state."""
        transfer = {
            "@id": "transfer-123",
            "state": "COMPLETED",
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = json.dumps(transfer).encode()
        mock_response.json.return_value = transfer
        mock_client._client.get = AsyncMock(return_value=mock_response)

        state = await mock_client.get_transfer_state("transfer-123")

        assert state == "COMPLETED"


class TestTractusXClientHelpers:
    """Tests for TractusXClient helper methods."""

    def test_build_asset(self):
        """Test building an asset definition."""
        client = TractusXClient(base_url="http://edc:8080")

        asset = client.build_asset(
            asset_id="test-asset",
            name="Test Asset",
            base_url="http://example.com/data",
            description="A test asset",
        )

        assert asset["@id"] == "test-asset"
        assert asset["properties"]["name"] == "Test Asset"
        assert asset["properties"]["description"] == "A test asset"
        assert asset["dataAddress"]["baseUrl"] == "http://example.com/data"

    def test_build_policy_definition(self):
        """Test building a policy definition."""
        client = TractusXClient(base_url="http://edc:8080")

        policy = client.build_policy_definition(
            policy_id="test-policy",
            permissions=[{"odrl:action": "USE"}],
        )

        assert policy["@id"] == "test-policy"
        assert policy["policy"]["@type"] == "odrl:Set"
        assert len(policy["policy"]["odrl:permission"]) == 1

    def test_build_contract_definition(self):
        """Test building a contract definition."""
        client = TractusXClient(base_url="http://edc:8080")

        contract_def = client.build_contract_definition(
            definition_id="test-contract",
            access_policy_id="access-policy",
            contract_policy_id="contract-policy",
            asset_id="test-asset",
        )

        assert contract_def["@id"] == "test-contract"
        assert contract_def["accessPolicyId"] == "access-policy"
        assert contract_def["contractPolicyId"] == "contract-policy"
        assert len(contract_def["assetsSelector"]) == 1


class TestTractusXClientAuth:
    """Tests for TractusXClient authentication handling."""

    @pytest.fixture
    def mock_client(self):
        """Create a TractusXClient with mocked HTTP client."""
        client = TractusXClient(base_url="http://edc:8080")
        client._client = AsyncMock(spec=httpx.AsyncClient)
        return client

    @pytest.mark.asyncio
    async def test_unauthorized_error(self, mock_client):
        """Test handling of 401 unauthorized."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_client._client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(EDCAuthenticationError) as exc_info:
            await mock_client.create_asset({"@id": "test"})

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_forbidden_error(self, mock_client):
        """Test handling of 403 forbidden."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"
        mock_client._client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(EDCAuthenticationError) as exc_info:
            await mock_client.create_asset({"@id": "test"})

        assert exc_info.value.status_code == 403


class TestTractusXClientHealth:
    """Tests for TractusXClient health check."""

    @pytest.fixture
    def mock_client(self):
        """Create a TractusXClient with mocked HTTP client."""
        client = TractusXClient(base_url="http://edc:8080")
        client._client = AsyncMock(spec=httpx.AsyncClient)
        return client

    @pytest.mark.asyncio
    async def test_health_check_success(self, mock_client):
        """Test health check when healthy."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client._client.post = AsyncMock(return_value=mock_response)

        result = await mock_client.health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, mock_client):
        """Test health check when unhealthy."""
        mock_client._client.post = AsyncMock(
            side_effect=httpx.HTTPError("Connection failed")
        )

        result = await mock_client.health_check()

        assert result is False


# ---------------------------------------------------------------------------
# AASExtensionClient Tests
# ---------------------------------------------------------------------------


class TestAASExtensionClientInit:
    """Tests for AASExtensionClient initialization."""

    def test_init_basic(self):
        """Test basic client initialization."""
        client = AASExtensionClient(base_url="http://edc:8080")
        assert client.base_url == "http://edc:8080"
        assert client.dtr_url is None

    def test_init_with_dtr(self):
        """Test client initialization with DTR URL."""
        client = AASExtensionClient(
            base_url="http://edc:8080",
            dtr_url="http://dtr:4001",
        )
        assert client.dtr_url == "http://dtr:4001"


class TestAASExtensionClientEncoding:
    """Tests for AASExtensionClient ID encoding."""

    def test_encode_id(self):
        """Test encoding an identifier."""
        identifier = "urn:example:aas:123"
        encoded = AASExtensionClient.encode_id(identifier)
        assert "=" not in encoded

    def test_decode_id(self):
        """Test decoding an identifier."""
        identifier = "urn:example:aas:123"
        encoded = AASExtensionClient.encode_id(identifier)
        decoded = AASExtensionClient.decode_id(encoded)
        assert decoded == identifier


class TestAASExtensionClientShellOperations:
    """Tests for AASExtensionClient shell operations."""

    @pytest.fixture
    def mock_client(self):
        """Create an AASExtensionClient with mocked HTTP client."""
        client = AASExtensionClient(base_url="http://edc:8080")
        client._client = AsyncMock(spec=httpx.AsyncClient)
        return client

    @pytest.mark.asyncio
    async def test_register_shell_via_extension(self, mock_client):
        """Test registering a shell via AAS extension endpoint."""
        shell_descriptor = {
            "id": "urn:example:shell:1",
            "idShort": "TestShell",
        }

        result = {
            "shellId": "urn:example:shell:1",
            "edcAssetId": "aas-shell-abc123",
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = json.dumps(result).encode()
        mock_response.json.return_value = result
        mock_client._client.post = AsyncMock(return_value=mock_response)

        registration = await mock_client.register_shell(shell_descriptor, policy_id="policy-1")

        assert registration["shellId"] == "urn:example:shell:1"

    @pytest.mark.asyncio
    async def test_register_shell_fallback_to_edc(self, mock_client):
        """Test registering a shell falling back to EDC API."""
        shell_descriptor = {
            "id": "urn:example:shell:1",
            "idShort": "TestShell",
        }

        # First call (AAS extension) fails
        extension_response = MagicMock()
        extension_response.status_code = 404

        # Second call (EDC API) succeeds
        edc_response = MagicMock()
        edc_response.status_code = 200
        edc_response.content = b"{}"
        edc_response.json.return_value = {}

        mock_client._client.post = AsyncMock(
            side_effect=[extension_response, edc_response]
        )

        registration = await mock_client.register_shell(shell_descriptor)

        assert "shellId" in registration
        assert "edcAssetId" in registration


class TestAASExtensionClientSubmodelOperations:
    """Tests for AASExtensionClient submodel operations."""

    @pytest.fixture
    def mock_client(self):
        """Create an AASExtensionClient with mocked HTTP client."""
        client = AASExtensionClient(base_url="http://edc:8080")
        client._client = AsyncMock(spec=httpx.AsyncClient)
        return client

    @pytest.mark.asyncio
    async def test_register_submodel_success(self, mock_client):
        """Test registering a submodel."""
        submodel_descriptor = {
            "id": "urn:example:submodel:1",
            "idShort": "TestSubmodel",
            "semanticId": {
                "type": "ExternalReference",
                "keys": [{"type": "GlobalReference", "value": "https://admin-shell.io/test"}],
            },
        }

        result = {
            "submodelId": "urn:example:submodel:1",
            "edcAssetId": "aas-submodel-xyz789",
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = json.dumps(result).encode()
        mock_response.json.return_value = result
        mock_client._client.post = AsyncMock(return_value=mock_response)

        registration = await mock_client.register_submodel(
            shell_id="urn:example:shell:1",
            submodel_descriptor=submodel_descriptor,
            policy_id="policy-1",
        )

        assert registration["submodelId"] == "urn:example:submodel:1"


class TestAASExtensionClientLookup:
    """Tests for AASExtensionClient lookup operations."""

    @pytest.fixture
    def mock_client(self):
        """Create an AASExtensionClient with mocked HTTP client."""
        client = AASExtensionClient(base_url="http://edc:8080")
        client._client = AsyncMock(spec=httpx.AsyncClient)
        return client

    @pytest.mark.asyncio
    async def test_lookup_shells_success(self, mock_client):
        """Test looking up shells."""
        result = {
            "result": ["urn:example:shell:1", "urn:example:shell:2"],
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = json.dumps(result).encode()
        mock_response.json.return_value = result
        mock_client._client.get = AsyncMock(return_value=mock_response)

        shells = await mock_client.lookup_shells([
            {"name": "manufacturerPartId", "value": "ABC-123"},
        ])

        assert len(shells) == 2

    @pytest.mark.asyncio
    async def test_lookup_submodel_descriptors_success(self, mock_client):
        """Test looking up submodel descriptors."""
        submodels = {
            "result": [
                {
                    "id": "urn:example:submodel:1",
                    "semanticId": {
                        "keys": [{"value": "https://admin-shell.io/test"}],
                    },
                },
            ],
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = json.dumps(submodels).encode()
        mock_response.json.return_value = submodels
        mock_client._client.get = AsyncMock(return_value=mock_response)

        result = await mock_client.lookup_submodel_descriptors(
            shell_id="urn:example:shell:1",
            semantic_id="https://admin-shell.io/test",
        )

        assert len(result) == 1


class TestAASExtensionClientContractGeneration:
    """Tests for AASExtensionClient contract generation."""

    @pytest.fixture
    def mock_client(self):
        """Create an AASExtensionClient with mocked HTTP client."""
        client = AASExtensionClient(base_url="http://edc:8080")
        client._client = AsyncMock(spec=httpx.AsyncClient)
        return client

    @pytest.mark.asyncio
    async def test_create_contracts_from_aas(self, mock_client):
        """Test creating contracts from AAS structure."""
        shell_descriptor = {
            "id": "urn:example:shell:1",
            "idShort": "TestShell",
            "submodelDescriptors": [
                {
                    "id": "urn:example:submodel:1",
                    "idShort": "Submodel1",
                },
                {
                    "id": "urn:example:submodel:2",
                    "idShort": "Submodel2",
                },
            ],
        }

        # Mock responses for shell and submodel registrations
        shell_result = {
            "shellId": "urn:example:shell:1",
            "edcAssetId": "aas-shell-abc",
            "contractDefinitionId": "contract-shell",
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = json.dumps(shell_result).encode()
        mock_response.json.return_value = shell_result

        # Return different results for shell and submodel registrations
        mock_client._client.post = AsyncMock(return_value=mock_response)

        result = await mock_client.create_contracts_from_aas(
            shell_descriptor=shell_descriptor,
            access_policy_id="access-policy",
            contract_policy_id="contract-policy",
        )

        assert result["shellAssetId"] is not None
        assert len(result["submodels"]) == 2


class TestAASExtensionClientHealth:
    """Tests for AASExtensionClient health check."""

    @pytest.fixture
    def mock_client(self):
        """Create an AASExtensionClient with mocked HTTP client."""
        client = AASExtensionClient(base_url="http://edc:8080")
        client._client = AsyncMock(spec=httpx.AsyncClient)
        return client

    @pytest.mark.asyncio
    async def test_health_check_success(self, mock_client):
        """Test health check when healthy."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client._client.get = AsyncMock(return_value=mock_response)

        result = await mock_client.health_check()

        assert result is True


# ---------------------------------------------------------------------------
# Context Manager Tests
# ---------------------------------------------------------------------------


class TestContextManagers:
    """Tests for client context managers."""

    @pytest.mark.asyncio
    async def test_tractus_x_context_manager(self):
        """Test TractusXClient as async context manager."""
        async with TractusXClient(base_url="http://edc:8080") as client:
            assert client is not None
            assert client.base_url == "http://edc:8080"

    @pytest.mark.asyncio
    async def test_aas_extension_context_manager(self):
        """Test AASExtensionClient as async context manager."""
        async with AASExtensionClient(base_url="http://edc:8080") as client:
            assert client is not None
            assert client.base_url == "http://edc:8080"


# ---------------------------------------------------------------------------
# Exception Tests
# ---------------------------------------------------------------------------


class TestExceptions:
    """Tests for custom exceptions."""

    def test_edc_client_error(self):
        """Test EDCClientError."""
        error = EDCClientError(
            "Test error",
            status_code=500,
            response_body="Internal Server Error",
        )
        assert str(error) == "Test error"
        assert error.status_code == 500
        assert error.response_body == "Internal Server Error"

    def test_exception_hierarchy(self):
        """Test exception inheritance."""
        assert issubclass(EDCAssetNotFoundError, EDCClientError)
        assert issubclass(EDCAssetConflictError, EDCClientError)
        assert issubclass(EDCPolicyNotFoundError, EDCClientError)
        assert issubclass(EDCContractNotFoundError, EDCClientError)
        assert issubclass(EDCNegotiationError, EDCClientError)
        assert issubclass(EDCAuthenticationError, EDCClientError)
        assert issubclass(EDCConnectionError, EDCClientError)
        assert issubclass(AASExtensionError, EDCClientError)
        assert issubclass(AASShellNotFoundError, AASExtensionError)
        assert issubclass(AASSubmodelNotFoundError, AASExtensionError)
