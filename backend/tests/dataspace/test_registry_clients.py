"""
Tests for the BaSyx and DTR registry clients.

Uses pytest with respx for mocking httpx requests.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.services.dataspace.registry.basyx_client import (
    BaSyxClient,
    BaSyxClientError,
    BaSyxConflictError,
)
from app.services.dataspace.registry.dtr_client import (
    DTRClient,
    DTRClientError,
    DTRConflictError,
    DTRAuthenticationError,
)


# ---------------------------------------------------------------------------
# BaSyxClient Tests
# ---------------------------------------------------------------------------


class TestBaSyxClientInit:
    """Tests for BaSyxClient initialization."""

    def test_init_basic(self):
        """Test basic client initialization."""
        client = BaSyxClient(base_url="http://basyx:4001")
        assert client.base_url == "http://basyx:4001"
        assert client.timeout == 30.0

    def test_init_strips_trailing_slash(self):
        """Test that trailing slash is stripped from base URL."""
        client = BaSyxClient(base_url="http://basyx:4001/")
        assert client.base_url == "http://basyx:4001"

    def test_init_custom_timeout(self):
        """Test client with custom timeout."""
        client = BaSyxClient(base_url="http://basyx:4001", timeout=60.0)
        assert client.timeout == 60.0


class TestBaSyxClientEncoding:
    """Tests for BaSyxClient ID encoding/decoding."""

    def test_encode_id(self):
        """Test encoding an identifier."""
        identifier = "urn:example:aas:123"
        encoded = BaSyxClient.encode_id(identifier)
        # Should be base64url encoded without padding
        assert "=" not in encoded
        assert "+" not in encoded
        assert "/" not in encoded

    def test_decode_id(self):
        """Test decoding an identifier."""
        identifier = "urn:example:aas:123"
        encoded = BaSyxClient.encode_id(identifier)
        decoded = BaSyxClient.decode_id(encoded)
        assert decoded == identifier

    def test_encode_decode_roundtrip(self):
        """Test encoding and decoding roundtrip."""
        identifiers = [
            "urn:example:aas:123",
            "https://example.com/aas/1",
            "urn:uuid:12345678-1234-1234-1234-123456789012",
            "simple-id",
        ]
        for identifier in identifiers:
            encoded = BaSyxClient.encode_id(identifier)
            decoded = BaSyxClient.decode_id(encoded)
            assert decoded == identifier


class TestBaSyxClientAASOperations:
    """Tests for BaSyxClient AAS Shell operations."""

    @pytest.fixture
    def mock_client(self):
        """Create a BaSyxClient with mocked HTTP client."""
        client = BaSyxClient(base_url="http://basyx:4001")
        client._client = AsyncMock(spec=httpx.AsyncClient)
        return client

    @pytest.mark.asyncio
    async def test_register_aas_success(self, mock_client):
        """Test successful AAS registration."""
        shell_descriptor = {
            "id": "urn:example:aas:1",
            "idShort": "TestAAS",
        }

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.content = json.dumps(shell_descriptor).encode()
        mock_response.json.return_value = shell_descriptor
        mock_client._client.post = AsyncMock(return_value=mock_response)

        result = await mock_client.register_aas(shell_descriptor)

        assert result["id"] == "urn:example:aas:1"
        mock_client._client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_aas_conflict(self, mock_client):
        """Test AAS registration when already exists."""
        shell_descriptor = {"id": "urn:example:aas:1"}

        mock_response = MagicMock()
        mock_response.status_code = 409
        mock_response.text = "Already exists"
        mock_client._client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(BaSyxConflictError):
            await mock_client.register_aas(shell_descriptor)

    @pytest.mark.asyncio
    async def test_get_aas_success(self, mock_client):
        """Test getting an existing AAS."""
        shell_descriptor = {
            "id": "urn:example:aas:1",
            "idShort": "TestAAS",
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = json.dumps(shell_descriptor).encode()
        mock_response.json.return_value = shell_descriptor
        mock_client._client.get = AsyncMock(return_value=mock_response)

        result = await mock_client.get_aas("urn:example:aas:1")

        assert result is not None
        assert result["id"] == "urn:example:aas:1"

    @pytest.mark.asyncio
    async def test_get_aas_not_found(self, mock_client):
        """Test getting a non-existent AAS."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not found"
        mock_client._client.get = AsyncMock(return_value=mock_response)

        result = await mock_client.get_aas("urn:example:aas:nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_update_aas_success(self, mock_client):
        """Test updating an AAS."""
        shell_descriptor = {
            "id": "urn:example:aas:1",
            "idShort": "UpdatedAAS",
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = json.dumps(shell_descriptor).encode()
        mock_response.json.return_value = shell_descriptor
        mock_client._client.put = AsyncMock(return_value=mock_response)

        result = await mock_client.update_aas("urn:example:aas:1", shell_descriptor)

        assert result["idShort"] == "UpdatedAAS"

    @pytest.mark.asyncio
    async def test_delete_aas_success(self, mock_client):
        """Test deleting an AAS."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.content = b""
        mock_client._client.delete = AsyncMock(return_value=mock_response)

        result = await mock_client.delete_aas("urn:example:aas:1")

        assert result is True

    @pytest.mark.asyncio
    async def test_get_all_aas_with_pagination(self, mock_client):
        """Test getting all AAS with pagination."""
        response_data = {
            "result": [
                {"id": "urn:example:aas:1"},
                {"id": "urn:example:aas:2"},
            ],
            "paging_metadata": {"cursor": "next-cursor-123"},
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = json.dumps(response_data).encode()
        mock_response.json.return_value = response_data
        mock_client._client.get = AsyncMock(return_value=mock_response)

        descriptors, next_cursor = await mock_client.get_all_aas(limit=10)

        assert len(descriptors) == 2
        assert next_cursor == "next-cursor-123"


class TestBaSyxClientSubmodelOperations:
    """Tests for BaSyxClient Submodel operations."""

    @pytest.fixture
    def mock_client(self):
        """Create a BaSyxClient with mocked HTTP client."""
        client = BaSyxClient(base_url="http://basyx:4001")
        client._client = AsyncMock(spec=httpx.AsyncClient)
        return client

    @pytest.mark.asyncio
    async def test_register_submodel_success(self, mock_client):
        """Test successful submodel registration."""
        submodel_descriptor = {
            "id": "urn:example:submodel:1",
            "idShort": "TestSubmodel",
        }

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.content = json.dumps(submodel_descriptor).encode()
        mock_response.json.return_value = submodel_descriptor
        mock_client._client.post = AsyncMock(return_value=mock_response)

        result = await mock_client.register_submodel(
            "urn:example:aas:1",
            submodel_descriptor,
        )

        assert result["id"] == "urn:example:submodel:1"

    @pytest.mark.asyncio
    async def test_get_submodel_success(self, mock_client):
        """Test getting an existing submodel."""
        submodel_descriptor = {
            "id": "urn:example:submodel:1",
            "idShort": "TestSubmodel",
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = json.dumps(submodel_descriptor).encode()
        mock_response.json.return_value = submodel_descriptor
        mock_client._client.get = AsyncMock(return_value=mock_response)

        result = await mock_client.get_submodel(
            "urn:example:aas:1",
            "urn:example:submodel:1",
        )

        assert result is not None
        assert result["id"] == "urn:example:submodel:1"

    @pytest.mark.asyncio
    async def test_delete_submodel_success(self, mock_client):
        """Test deleting a submodel."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.content = b""
        mock_client._client.delete = AsyncMock(return_value=mock_response)

        result = await mock_client.delete_submodel(
            "urn:example:aas:1",
            "urn:example:submodel:1",
        )

        assert result is True


class TestBaSyxClientLookup:
    """Tests for BaSyxClient lookup operations."""

    @pytest.fixture
    def mock_client(self):
        """Create a BaSyxClient with mocked HTTP client."""
        client = BaSyxClient(base_url="http://basyx:4001")
        client._client = AsyncMock(spec=httpx.AsyncClient)
        return client

    @pytest.mark.asyncio
    async def test_lookup_by_asset_id(self, mock_client):
        """Test looking up AAS by asset ID."""
        response_data = {"result": ["urn:example:aas:1", "urn:example:aas:2"]}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = json.dumps(response_data).encode()
        mock_response.json.return_value = response_data
        mock_client._client.get = AsyncMock(return_value=mock_response)

        result = await mock_client.lookup_by_asset_id(
            "manufacturerPartId",
            "ABC-123",
        )

        assert len(result) == 2
        assert "urn:example:aas:1" in result

    @pytest.mark.asyncio
    async def test_health_check_success(self, mock_client):
        """Test health check when server is healthy."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client._client.get = AsyncMock(return_value=mock_response)

        result = await mock_client.health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, mock_client):
        """Test health check when server is unhealthy."""
        mock_client._client.get = AsyncMock(side_effect=httpx.HTTPError("Connection failed"))

        result = await mock_client.health_check()

        assert result is False


# ---------------------------------------------------------------------------
# DTRClient Tests
# ---------------------------------------------------------------------------


class TestDTRClientInit:
    """Tests for DTRClient initialization."""

    def test_init_basic(self):
        """Test basic client initialization."""
        client = DTRClient(base_url="http://dtr:4003")
        assert client.base_url == "http://dtr:4003"
        assert client.auth_token is None
        assert client.timeout == 30.0

    def test_init_with_auth(self):
        """Test client initialization with auth token."""
        client = DTRClient(
            base_url="http://dtr:4003",
            auth_token="test-token-123",
        )
        assert client.auth_token == "test-token-123"

    def test_update_auth_token(self):
        """Test updating auth token."""
        client = DTRClient(base_url="http://dtr:4003")
        client.update_auth_token("new-token")
        assert client.auth_token == "new-token"


class TestDTRClientShellOperations:
    """Tests for DTRClient Shell Descriptor operations."""

    @pytest.fixture
    def mock_client(self):
        """Create a DTRClient with mocked HTTP client."""
        client = DTRClient(base_url="http://dtr:4003", auth_token="test-token")
        client._client = AsyncMock(spec=httpx.AsyncClient)
        return client

    @pytest.mark.asyncio
    async def test_create_shell_descriptor_success(self, mock_client):
        """Test successful shell descriptor creation."""
        descriptor = {
            "id": "urn:example:shell:1",
            "idShort": "TestShell",
        }

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.content = json.dumps(descriptor).encode()
        mock_response.json.return_value = descriptor
        mock_client._client.post = AsyncMock(return_value=mock_response)

        result = await mock_client.create_shell_descriptor(descriptor)

        assert result["id"] == "urn:example:shell:1"

    @pytest.mark.asyncio
    async def test_create_shell_descriptor_conflict(self, mock_client):
        """Test shell descriptor creation when already exists."""
        descriptor = {"id": "urn:example:shell:1"}

        mock_response = MagicMock()
        mock_response.status_code = 409
        mock_response.text = "Already exists"
        mock_client._client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(DTRConflictError):
            await mock_client.create_shell_descriptor(descriptor)

    @pytest.mark.asyncio
    async def test_create_shell_descriptor_unauthorized(self, mock_client):
        """Test shell descriptor creation when unauthorized."""
        descriptor = {"id": "urn:example:shell:1"}

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_client._client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(DTRAuthenticationError):
            await mock_client.create_shell_descriptor(descriptor)

    @pytest.mark.asyncio
    async def test_create_shell_descriptor_forbidden(self, mock_client):
        """Test shell descriptor creation when forbidden."""
        descriptor = {"id": "urn:example:shell:1"}

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"
        mock_client._client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(DTRAuthenticationError):
            await mock_client.create_shell_descriptor(descriptor)

    @pytest.mark.asyncio
    async def test_get_shell_descriptor_success(self, mock_client):
        """Test getting an existing shell descriptor."""
        descriptor = {
            "id": "urn:example:shell:1",
            "idShort": "TestShell",
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = json.dumps(descriptor).encode()
        mock_response.json.return_value = descriptor
        mock_client._client.get = AsyncMock(return_value=mock_response)

        result = await mock_client.get_shell_descriptor("urn:example:shell:1")

        assert result is not None
        assert result["id"] == "urn:example:shell:1"

    @pytest.mark.asyncio
    async def test_get_shell_descriptor_not_found(self, mock_client):
        """Test getting a non-existent shell descriptor."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not found"
        mock_client._client.get = AsyncMock(return_value=mock_response)

        result = await mock_client.get_shell_descriptor("urn:example:shell:nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_shell_descriptor_success(self, mock_client):
        """Test deleting a shell descriptor."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.content = b""
        mock_client._client.delete = AsyncMock(return_value=mock_response)

        result = await mock_client.delete_shell_descriptor("urn:example:shell:1")

        assert result is True


class TestDTRClientSubmodelOperations:
    """Tests for DTRClient Submodel Descriptor operations."""

    @pytest.fixture
    def mock_client(self):
        """Create a DTRClient with mocked HTTP client."""
        client = DTRClient(base_url="http://dtr:4003", auth_token="test-token")
        client._client = AsyncMock(spec=httpx.AsyncClient)
        return client

    @pytest.mark.asyncio
    async def test_create_submodel_descriptor_success(self, mock_client):
        """Test successful submodel descriptor creation."""
        descriptor = {
            "id": "urn:example:submodel:1",
            "idShort": "TestSubmodel",
        }

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.content = json.dumps(descriptor).encode()
        mock_response.json.return_value = descriptor
        mock_client._client.post = AsyncMock(return_value=mock_response)

        result = await mock_client.create_submodel_descriptor(
            "urn:example:shell:1",
            descriptor,
        )

        assert result["id"] == "urn:example:submodel:1"

    @pytest.mark.asyncio
    async def test_get_submodel_descriptor_success(self, mock_client):
        """Test getting an existing submodel descriptor."""
        descriptor = {
            "id": "urn:example:submodel:1",
            "idShort": "TestSubmodel",
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = json.dumps(descriptor).encode()
        mock_response.json.return_value = descriptor
        mock_client._client.get = AsyncMock(return_value=mock_response)

        result = await mock_client.get_submodel_descriptor(
            "urn:example:shell:1",
            "urn:example:submodel:1",
        )

        assert result is not None
        assert result["id"] == "urn:example:submodel:1"


class TestDTRClientLookup:
    """Tests for DTRClient lookup operations."""

    @pytest.fixture
    def mock_client(self):
        """Create a DTRClient with mocked HTTP client."""
        client = DTRClient(base_url="http://dtr:4003", auth_token="test-token")
        client._client = AsyncMock(spec=httpx.AsyncClient)
        return client

    @pytest.mark.asyncio
    async def test_lookup_shells_by_asset_ids(self, mock_client):
        """Test looking up shells by asset IDs."""
        response_data = {"result": ["urn:example:shell:1", "urn:example:shell:2"]}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = json.dumps(response_data).encode()
        mock_response.json.return_value = response_data
        mock_client._client.get = AsyncMock(return_value=mock_response)

        result = await mock_client.lookup_shells_by_asset_ids([
            {"name": "manufacturerPartId", "value": "ABC-123"},
        ])

        assert len(result) == 2
        assert "urn:example:shell:1" in result

    @pytest.mark.asyncio
    async def test_lookup_submodels_by_semantic_id(self, mock_client):
        """Test looking up submodels by semantic ID."""
        submodels_response = {
            "result": [
                {
                    "id": "urn:example:submodel:1",
                    "semanticId": {
                        "type": "ExternalReference",
                        "keys": [{"type": "GlobalReference", "value": "https://admin-shell.io/idta/Nameplate/3/0"}],
                    },
                },
                {
                    "id": "urn:example:submodel:2",
                    "semanticId": {
                        "type": "ExternalReference",
                        "keys": [{"type": "GlobalReference", "value": "https://admin-shell.io/idta/PCF/1/0"}],
                    },
                },
            ],
            "paging_metadata": {},
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = json.dumps(submodels_response).encode()
        mock_response.json.return_value = submodels_response
        mock_client._client.get = AsyncMock(return_value=mock_response)

        result = await mock_client.lookup_submodels_by_semantic_id(
            "urn:example:shell:1",
            "https://admin-shell.io/idta/Nameplate/3/0",
        )

        assert len(result) == 1
        assert result[0]["id"] == "urn:example:submodel:1"

    @pytest.mark.asyncio
    async def test_health_check_success(self, mock_client):
        """Test health check when server is healthy."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client._client.get = AsyncMock(return_value=mock_response)

        result = await mock_client.health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, mock_client):
        """Test health check when server is unhealthy."""
        mock_client._client.get = AsyncMock(side_effect=httpx.HTTPError("Connection failed"))

        result = await mock_client.health_check()

        assert result is False


# ---------------------------------------------------------------------------
# Context Manager Tests
# ---------------------------------------------------------------------------


class TestContextManagers:
    """Tests for client context managers."""

    @pytest.mark.asyncio
    async def test_basyx_context_manager(self):
        """Test BaSyxClient as async context manager."""
        async with BaSyxClient(base_url="http://basyx:4001") as client:
            assert client is not None
            assert client.base_url == "http://basyx:4001"

    @pytest.mark.asyncio
    async def test_dtr_context_manager(self):
        """Test DTRClient as async context manager."""
        async with DTRClient(base_url="http://dtr:4003") as client:
            assert client is not None
            assert client.base_url == "http://dtr:4003"


# ---------------------------------------------------------------------------
# Error Handling Tests
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Tests for error handling in clients."""

    @pytest.fixture
    def mock_basyx_client(self):
        """Create a BaSyxClient with mocked HTTP client."""
        client = BaSyxClient(base_url="http://basyx:4001")
        client._client = AsyncMock(spec=httpx.AsyncClient)
        return client

    @pytest.fixture
    def mock_dtr_client(self):
        """Create a DTRClient with mocked HTTP client."""
        client = DTRClient(base_url="http://dtr:4003")
        client._client = AsyncMock(spec=httpx.AsyncClient)
        return client

    @pytest.mark.asyncio
    async def test_basyx_server_error(self, mock_basyx_client):
        """Test handling of 500 server error."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_basyx_client._client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(BaSyxClientError) as exc_info:
            await mock_basyx_client.register_aas({"id": "test"})

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_dtr_server_error(self, mock_dtr_client):
        """Test handling of 500 server error."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_dtr_client._client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(DTRClientError) as exc_info:
            await mock_dtr_client.create_shell_descriptor({"id": "test"})

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_basyx_bad_request(self, mock_basyx_client):
        """Test handling of 400 bad request."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request: Invalid JSON"
        mock_basyx_client._client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(BaSyxClientError) as exc_info:
            await mock_basyx_client.register_aas({"invalid": "data"})

        assert exc_info.value.status_code == 400
        assert "Bad Request" in exc_info.value.response_body
