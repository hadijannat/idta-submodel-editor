"""
Tests for the AAS Publisher service.

Tests the orchestration of hydration and publication to BaSyx and DTR.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.dataspace.publisher import (
    AASPublisher,
    AASPublisherError,
    PublicationResult,
)
from app.services.dataspace.registry.basyx_client import (
    BaSyxClient,
    BaSyxConflictError,
)
from app.services.dataspace.registry.dtr_client import (
    DTRClient,
    DTRConflictError,
)
from app.services.hydrator import HydratorService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_basyx_client():
    """Create a mocked BaSyx client."""
    client = MagicMock(spec=BaSyxClient)
    client.base_url = "http://basyx:4001"
    client.register_aas = AsyncMock()
    client.update_aas = AsyncMock()
    client.delete_aas = AsyncMock()
    client.get_aas = AsyncMock()
    client.register_submodel = AsyncMock()
    client.update_submodel = AsyncMock()
    client.delete_submodel = AsyncMock()
    client.get_submodel = AsyncMock()
    client.get_all_submodels = AsyncMock(return_value=([], None))
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_dtr_client():
    """Create a mocked DTR client."""
    client = MagicMock(spec=DTRClient)
    client.base_url = "http://dtr:4003"
    client.create_shell_descriptor = AsyncMock()
    client.update_shell_descriptor = AsyncMock()
    client.delete_shell_descriptor = AsyncMock()
    client.create_submodel_descriptor = AsyncMock()
    client.update_submodel_descriptor = AsyncMock()
    client.delete_submodel_descriptor = AsyncMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_hydrator():
    """Create a mocked HydratorService."""
    hydrator = MagicMock(spec=HydratorService)
    # Return a valid JSON structure
    hydrator.hydrate_to_json.return_value = json.dumps({
        "assetAdministrationShells": [
            {
                "id": "urn:example:aas:1",
                "idShort": "TestAAS",
                "assetInformation": {
                    "assetKind": "Instance",
                    "globalAssetId": "urn:example:asset:1",
                },
            }
        ],
        "submodels": [
            {
                "id": "urn:example:submodel:1",
                "idShort": "TestSubmodel",
                "semanticId": {
                    "type": "ExternalReference",
                    "keys": [{"type": "GlobalReference", "value": "https://example.com/semantic"}],
                },
            }
        ],
    })
    return hydrator


# ---------------------------------------------------------------------------
# PublicationResult Tests
# ---------------------------------------------------------------------------


class TestPublicationResult:
    """Tests for PublicationResult."""

    def test_success_result(self):
        """Test creating a successful result."""
        result = PublicationResult(
            success=True,
            aas_id="urn:example:aas:1",
            submodel_id="urn:example:submodel:1",
            aas_endpoint="http://basyx:4001/shells/abc",
            dtr_registered=True,
        )

        assert result.success is True
        assert result.aas_id == "urn:example:aas:1"
        assert result.submodel_id == "urn:example:submodel:1"
        assert result.aas_endpoint is not None
        assert result.dtr_registered is True
        assert result.published_at is not None
        assert result.error_message is None

    def test_failure_result(self):
        """Test creating a failure result."""
        result = PublicationResult(
            success=False,
            aas_id="urn:example:aas:1",
            submodel_id="urn:example:submodel:1",
            error_message="Publication failed",
        )

        assert result.success is False
        assert result.published_at is None
        assert result.error_message == "Publication failed"

    def test_to_dict(self):
        """Test serialization to dictionary."""
        result = PublicationResult(
            success=True,
            aas_id="urn:example:aas:1",
            submodel_id="urn:example:submodel:1",
            aas_endpoint="http://basyx:4001/shells/abc",
            dtr_registered=True,
        )

        data = result.to_dict()

        assert "success" in data
        assert "aas_id" in data
        assert "submodel_id" in data
        assert "aas_endpoint" in data
        assert "dtr_registered" in data
        assert "published_at" in data


# ---------------------------------------------------------------------------
# AASPublisher Tests
# ---------------------------------------------------------------------------


class TestAASPublisherInit:
    """Tests for AASPublisher initialization."""

    def test_init_with_basyx_only(self, mock_basyx_client):
        """Test initialization with BaSyx client only."""
        publisher = AASPublisher(basyx_client=mock_basyx_client)

        assert publisher.basyx is mock_basyx_client
        assert publisher.dtr is None
        assert publisher.hydrator is not None

    def test_init_with_both_clients(self, mock_basyx_client, mock_dtr_client):
        """Test initialization with both clients."""
        publisher = AASPublisher(
            basyx_client=mock_basyx_client,
            dtr_client=mock_dtr_client,
        )

        assert publisher.basyx is mock_basyx_client
        assert publisher.dtr is mock_dtr_client

    def test_init_with_custom_hydrator(self, mock_basyx_client, mock_hydrator):
        """Test initialization with custom hydrator."""
        publisher = AASPublisher(
            basyx_client=mock_basyx_client,
            hydrator=mock_hydrator,
        )

        assert publisher.hydrator is mock_hydrator


class TestAASPublisherPublish:
    """Tests for AASPublisher.publish_submodel()."""

    @pytest.mark.asyncio
    async def test_publish_success_basyx_only(
        self,
        mock_basyx_client,
        mock_hydrator,
    ):
        """Test successful publication to BaSyx only."""
        publisher = AASPublisher(
            basyx_client=mock_basyx_client,
            hydrator=mock_hydrator,
        )

        result = await publisher.publish_submodel(
            template_aasx_bytes=b"fake-aasx",
            form_data={"elements": {}},
            aas_id="urn:example:aas:1",
            submodel_id="urn:example:submodel:1",
            register_in_dtr=False,
        )

        assert result.success is True
        assert result.aas_id == "urn:example:aas:1"
        assert result.submodel_id == "urn:example:submodel:1"
        assert result.dtr_registered is False

        # Verify BaSyx was called
        mock_basyx_client.register_aas.assert_called_once()
        mock_basyx_client.register_submodel.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_success_with_dtr(
        self,
        mock_basyx_client,
        mock_dtr_client,
        mock_hydrator,
    ):
        """Test successful publication to both BaSyx and DTR."""
        publisher = AASPublisher(
            basyx_client=mock_basyx_client,
            dtr_client=mock_dtr_client,
            hydrator=mock_hydrator,
        )

        result = await publisher.publish_submodel(
            template_aasx_bytes=b"fake-aasx",
            form_data={"elements": {}},
            aas_id="urn:example:aas:1",
            submodel_id="urn:example:submodel:1",
        )

        assert result.success is True
        assert result.dtr_registered is True

        # Verify both clients were called
        mock_basyx_client.register_aas.assert_called_once()
        mock_basyx_client.register_submodel.assert_called_once()
        mock_dtr_client.create_shell_descriptor.assert_called_once()
        mock_dtr_client.create_submodel_descriptor.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_auto_generates_ids(
        self,
        mock_basyx_client,
        mock_hydrator,
    ):
        """Test that IDs are auto-generated when not provided."""
        publisher = AASPublisher(
            basyx_client=mock_basyx_client,
            hydrator=mock_hydrator,
        )

        result = await publisher.publish_submodel(
            template_aasx_bytes=b"fake-aasx",
            form_data={"elements": {}},
            register_in_dtr=False,
        )

        assert result.success is True
        assert result.aas_id.startswith("urn:aas:")
        assert result.submodel_id.startswith("urn:submodel:")

    @pytest.mark.asyncio
    async def test_publish_handles_aas_conflict(
        self,
        mock_basyx_client,
        mock_hydrator,
    ):
        """Test that existing AAS is updated on conflict."""
        mock_basyx_client.register_aas.side_effect = BaSyxConflictError(
            "Already exists",
            status_code=409,
        )

        publisher = AASPublisher(
            basyx_client=mock_basyx_client,
            hydrator=mock_hydrator,
        )

        result = await publisher.publish_submodel(
            template_aasx_bytes=b"fake-aasx",
            form_data={"elements": {}},
            aas_id="urn:example:aas:1",
            submodel_id="urn:example:submodel:1",
            register_in_dtr=False,
        )

        assert result.success is True
        mock_basyx_client.update_aas.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_handles_submodel_conflict(
        self,
        mock_basyx_client,
        mock_hydrator,
    ):
        """Test that existing submodel is updated on conflict."""
        mock_basyx_client.register_submodel.side_effect = BaSyxConflictError(
            "Already exists",
            status_code=409,
        )

        publisher = AASPublisher(
            basyx_client=mock_basyx_client,
            hydrator=mock_hydrator,
        )

        result = await publisher.publish_submodel(
            template_aasx_bytes=b"fake-aasx",
            form_data={"elements": {}},
            aas_id="urn:example:aas:1",
            submodel_id="urn:example:submodel:1",
            register_in_dtr=False,
        )

        assert result.success is True
        mock_basyx_client.update_submodel.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_handles_dtr_conflict(
        self,
        mock_basyx_client,
        mock_dtr_client,
        mock_hydrator,
    ):
        """Test that existing DTR entries are updated on conflict."""
        mock_dtr_client.create_shell_descriptor.side_effect = DTRConflictError(
            "Already exists",
            status_code=409,
        )
        mock_dtr_client.create_submodel_descriptor.side_effect = DTRConflictError(
            "Already exists",
            status_code=409,
        )

        publisher = AASPublisher(
            basyx_client=mock_basyx_client,
            dtr_client=mock_dtr_client,
            hydrator=mock_hydrator,
        )

        result = await publisher.publish_submodel(
            template_aasx_bytes=b"fake-aasx",
            form_data={"elements": {}},
            aas_id="urn:example:aas:1",
            submodel_id="urn:example:submodel:1",
        )

        assert result.success is True
        assert result.dtr_registered is True
        mock_dtr_client.update_shell_descriptor.assert_called_once()
        mock_dtr_client.update_submodel_descriptor.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_with_asset_ids(
        self,
        mock_basyx_client,
        mock_hydrator,
    ):
        """Test publication with specific asset IDs."""
        publisher = AASPublisher(
            basyx_client=mock_basyx_client,
            hydrator=mock_hydrator,
        )

        asset_ids = [
            {"name": "manufacturerPartId", "value": "ABC-123"},
            {"name": "serialNumber", "value": "SN-001"},
        ]

        result = await publisher.publish_submodel(
            template_aasx_bytes=b"fake-aasx",
            form_data={"elements": {}},
            aas_id="urn:example:aas:1",
            submodel_id="urn:example:submodel:1",
            asset_ids=asset_ids,
            register_in_dtr=False,
        )

        assert result.success is True

        # Check that asset IDs were included in the shell descriptor
        call_args = mock_basyx_client.register_aas.call_args
        shell_descriptor = call_args[0][0]
        assert shell_descriptor["specificAssetIds"] == asset_ids


class TestAASPublisherUpdate:
    """Tests for AASPublisher.update_submodel()."""

    @pytest.mark.asyncio
    async def test_update_success(
        self,
        mock_basyx_client,
        mock_dtr_client,
        mock_hydrator,
    ):
        """Test successful submodel update."""
        publisher = AASPublisher(
            basyx_client=mock_basyx_client,
            dtr_client=mock_dtr_client,
            hydrator=mock_hydrator,
        )

        result = await publisher.update_submodel(
            aas_id="urn:example:aas:1",
            submodel_id="urn:example:submodel:1",
            template_aasx_bytes=b"fake-aasx",
            form_data={"elements": {}},
        )

        assert result.success is True
        mock_basyx_client.update_submodel.assert_called_once()
        mock_dtr_client.update_submodel_descriptor.assert_called_once()


class TestAASPublisherUnpublish:
    """Tests for AASPublisher.unpublish_submodel()."""

    @pytest.mark.asyncio
    async def test_unpublish_success(
        self,
        mock_basyx_client,
        mock_dtr_client,
    ):
        """Test successful unpublish."""
        publisher = AASPublisher(
            basyx_client=mock_basyx_client,
            dtr_client=mock_dtr_client,
        )

        result = await publisher.unpublish_submodel(
            aas_id="urn:example:aas:1",
            submodel_id="urn:example:submodel:1",
        )

        assert result is True
        mock_dtr_client.delete_submodel_descriptor.assert_called_once()
        mock_basyx_client.delete_submodel.assert_called_once()

    @pytest.mark.asyncio
    async def test_unpublish_deletes_empty_shell(
        self,
        mock_basyx_client,
        mock_dtr_client,
    ):
        """Test that empty shell is deleted after unpublish."""
        mock_basyx_client.get_all_submodels.return_value = ([], None)

        publisher = AASPublisher(
            basyx_client=mock_basyx_client,
            dtr_client=mock_dtr_client,
        )

        await publisher.unpublish_submodel(
            aas_id="urn:example:aas:1",
            submodel_id="urn:example:submodel:1",
        )

        mock_basyx_client.delete_aas.assert_called_once()
        mock_dtr_client.delete_shell_descriptor.assert_called_once()


class TestAASPublisherStatus:
    """Tests for AASPublisher.get_publication_status()."""

    @pytest.mark.asyncio
    async def test_get_status_published(
        self,
        mock_basyx_client,
        mock_dtr_client,
    ):
        """Test getting status of published submodel."""
        mock_basyx_client.get_submodel.return_value = {"id": "urn:example:submodel:1"}
        mock_dtr_client.get_submodel_descriptor.return_value = {"id": "urn:example:submodel:1"}

        publisher = AASPublisher(
            basyx_client=mock_basyx_client,
            dtr_client=mock_dtr_client,
        )

        status = await publisher.get_publication_status(
            aas_id="urn:example:aas:1",
            submodel_id="urn:example:submodel:1",
        )

        assert status["basyx"]["registered"] is True
        assert status["dtr"]["registered"] is True

    @pytest.mark.asyncio
    async def test_get_status_not_published(
        self,
        mock_basyx_client,
        mock_dtr_client,
    ):
        """Test getting status of non-published submodel."""
        mock_basyx_client.get_submodel.return_value = None
        mock_dtr_client.get_submodel_descriptor.return_value = None

        publisher = AASPublisher(
            basyx_client=mock_basyx_client,
            dtr_client=mock_dtr_client,
        )

        status = await publisher.get_publication_status(
            aas_id="urn:example:aas:1",
            submodel_id="urn:example:submodel:1",
        )

        assert status["basyx"]["registered"] is False
        assert status["dtr"]["registered"] is False


class TestAASPublisherContextManager:
    """Tests for AASPublisher context manager."""

    @pytest.mark.asyncio
    async def test_context_manager(
        self,
        mock_basyx_client,
        mock_dtr_client,
    ):
        """Test using publisher as context manager."""
        async with AASPublisher(
            basyx_client=mock_basyx_client,
            dtr_client=mock_dtr_client,
        ) as publisher:
            assert publisher is not None

        mock_basyx_client.close.assert_called_once()
        mock_dtr_client.close.assert_called_once()
