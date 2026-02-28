"""
Tests for the CatalogService.

Tests catalog search, provider listing, and negotiation initiation.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.dataspace.catalog_service import (
    CatalogOffer,
    CatalogService,
    CatalogServiceError,
    ProviderInfo,
)
from app.services.dataspace.models import (
    ConnectionStatus,
    ContractNegotiation,
    ContractState,
)


class TestCatalogServiceSearch:
    """Tests for CatalogService.search_catalog()."""

    @pytest.fixture
    def mock_edc_client(self):
        """Create a mocked TractusXClient for catalog operations."""
        client = MagicMock()
        client.request_catalog = AsyncMock(
            return_value={
                "@type": "dcat:Catalog",
                "dcat:dataset": [
                    {
                        "@id": "urn:asset:test-1",
                        "odrl:hasPolicy": {
                            "@id": "offer-001",
                            "@type": "odrl:Offer",
                        },
                        "https://w3id.org/edc/v0.0.1/ns/properties": {
                            "name": "Test Asset 1",
                            "contenttype": "application/json",
                        },
                    },
                    {
                        "@id": "urn:asset:test-2",
                        "odrl:hasPolicy": {
                            "@id": "offer-002",
                            "@type": "odrl:Offer",
                        },
                        "https://w3id.org/edc/v0.0.1/ns/properties": {
                            "name": "Test Asset 2",
                        },
                    },
                ],
                "dcat:service": {
                    "dcat:endpointUrl": "http://provider:8080/api/v1/dsp",
                },
            }
        )
        return client

    @pytest.fixture
    def mock_connection_manager(self, sample_connection_state):
        """Create mocked connection manager for catalog service."""
        manager = MagicMock()
        # Return a connected connection
        sample_connection_state.status = ConnectionStatus.CONNECTED
        sample_connection_state.edc_url = "http://edc:8080"
        manager.get_connection.return_value = sample_connection_state
        manager.base_dir = MagicMock()
        manager.base_dir.__truediv__ = MagicMock(return_value=MagicMock())
        return manager

    @pytest.fixture
    def catalog_service(self, mock_connection_manager, temp_dataspace_dir):
        """Create CatalogService with mocked dependencies."""
        # Set up providers directory
        providers_dir = temp_dataspace_dir / "providers"
        providers_dir.mkdir(parents=True, exist_ok=True)
        mock_connection_manager.base_dir = temp_dataspace_dir

        mock_settings = MagicMock()
        mock_settings.edc_api_key = "test-api-key"

        with patch(
            "app.services.dataspace.catalog_service.get_settings",
            return_value=mock_settings,
        ):
            service = CatalogService(connection_manager=mock_connection_manager)
            yield service

    @pytest.mark.asyncio
    async def test_search_catalog_returns_offers(
        self, catalog_service, mock_edc_client
    ):
        """Test that search_catalog returns catalog offers."""
        # Patch the _get_edc_client method
        with patch.object(
            catalog_service,
            "_get_edc_client",
            AsyncMock(return_value=mock_edc_client),
        ):
            offers, total = await catalog_service.search_catalog(
                connection_id="test-conn-001",
                provider_address="http://provider:8080/api/v1/dsp",
            )

        assert len(offers) == 2
        assert total == 2
        assert all(isinstance(o, CatalogOffer) for o in offers)
        mock_edc_client.request_catalog.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_catalog_with_filter(self, catalog_service, mock_edc_client):
        """Test catalog search with asset type filter."""
        with patch.object(
            catalog_service,
            "_get_edc_client",
            AsyncMock(return_value=mock_edc_client),
        ):
            offers, total = await catalog_service.search_catalog(
                connection_id="test-conn-001",
                provider_address="http://provider:8080/api/v1/dsp",
                asset_id="urn:asset:test-1",
            )

        # Filter should be passed to the client
        call_kwargs = mock_edc_client.request_catalog.call_args
        assert call_kwargs is not None

    @pytest.mark.asyncio
    async def test_search_catalog_handles_empty_result(
        self, catalog_service, mock_edc_client
    ):
        """Test handling of empty catalog response."""
        mock_edc_client.request_catalog.return_value = {
            "@type": "dcat:Catalog",
            "dcat:dataset": [],
        }

        with patch.object(
            catalog_service,
            "_get_edc_client",
            AsyncMock(return_value=mock_edc_client),
        ):
            offers, total = await catalog_service.search_catalog(
                connection_id="test-conn-001",
                provider_address="http://provider:8080/api/v1/dsp",
            )

        assert offers == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_search_catalog_connection_not_found(self, catalog_service):
        """Test that search raises error when connection not found."""
        catalog_service.conn_manager.get_connection.return_value = None

        with pytest.raises(CatalogServiceError) as exc_info:
            await catalog_service.search_catalog(
                connection_id="non-existent",
                provider_address="http://provider:8080/api/v1/dsp",
            )

        assert "Connection not found" in str(exc_info.value)


class TestCatalogServiceProviders:
    """Tests for CatalogService.list_providers()."""

    @pytest.fixture
    def catalog_service_with_providers(self, temp_dataspace_dir):
        """Create CatalogService with known providers."""
        mock_settings = MagicMock()
        mock_settings.edc_api_key = "test-api-key"

        mock_conn_manager = MagicMock()
        mock_conn_manager.base_dir = temp_dataspace_dir

        with patch(
            "app.services.dataspace.catalog_service.get_settings",
            return_value=mock_settings,
        ):
            service = CatalogService(connection_manager=mock_conn_manager)
            yield service

    @pytest.mark.asyncio
    async def test_list_providers_returns_empty_for_new_connection(
        self, catalog_service_with_providers
    ):
        """Test listing providers for connection with no providers."""
        providers = await catalog_service_with_providers.list_providers(
            connection_id="test-conn-001"
        )

        assert providers == []

    @pytest.mark.asyncio
    async def test_add_and_list_providers(self, catalog_service_with_providers):
        """Test adding and listing providers."""
        # Add a provider
        provider = await catalog_service_with_providers.add_provider(
            connection_id="test-conn-001",
            bpn="BPNL00000003TEST",
            protocol_address="http://provider:8080/api/v1/dsp",
            name="Test Provider",
        )

        assert provider.bpn == "BPNL00000003TEST"
        assert provider.protocol_address == "http://provider:8080/api/v1/dsp"
        assert provider.name == "Test Provider"

        # List providers
        providers = await catalog_service_with_providers.list_providers(
            connection_id="test-conn-001"
        )

        assert len(providers) == 1
        assert providers[0].bpn == "BPNL00000003TEST"


class TestCatalogServiceNegotiation:
    """Tests for CatalogService.initiate_negotiation()."""

    @pytest.fixture
    def mock_edc_client_negotiation(self):
        """Create mocked client for negotiation."""
        client = MagicMock()
        client.initiate_negotiation = AsyncMock(
            return_value={
                "@type": "IdResponse",
                "@id": "neg-12345",
                "edc:createdAt": datetime.now(timezone.utc).isoformat(),
            }
        )
        client.get_negotiation = AsyncMock(
            return_value={
                "@type": "ContractNegotiation",
                "@id": "neg-12345",
                "state": "REQUESTED",
            }
        )
        return client

    @pytest.fixture
    def catalog_service_for_negotiation(
        self, sample_connection_state, temp_dataspace_dir
    ):
        """Create CatalogService for negotiation tests."""
        mock_settings = MagicMock()
        mock_settings.edc_api_key = "test-api-key"

        mock_conn_manager = MagicMock()
        mock_conn_manager.base_dir = temp_dataspace_dir

        # Configure connection
        sample_connection_state.status = ConnectionStatus.CONNECTED
        sample_connection_state.edc_url = "http://edc:8080"
        mock_conn_manager.get_connection.return_value = sample_connection_state

        # Configure negotiation creation
        mock_negotiation = ContractNegotiation(
            negotiation_id="neg-internal-001",
            connection_id=sample_connection_state.connection_id,
            asset_id="urn:asset:test",
            provider_bpn="BPNL00000003TEST",
            consumer_bpn=sample_connection_state.bpn or "unknown",
            state=ContractState.INITIAL,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            metadata={"edc_negotiation_id": "neg-12345"},
        )
        mock_conn_manager.create_negotiation.return_value = mock_negotiation

        with patch(
            "app.services.dataspace.catalog_service.get_settings",
            return_value=mock_settings,
        ):
            service = CatalogService(connection_manager=mock_conn_manager)
            yield service

    @pytest.mark.asyncio
    async def test_initiate_negotiation_returns_negotiation(
        self, catalog_service_for_negotiation, mock_edc_client_negotiation
    ):
        """Test that negotiation initiation returns negotiation object."""
        with patch.object(
            catalog_service_for_negotiation,
            "_get_edc_client",
            AsyncMock(return_value=mock_edc_client_negotiation),
        ):
            result = await catalog_service_for_negotiation.initiate_negotiation(
                connection_id="test-conn-001",
                provider_address="http://provider:8080/api/v1/dsp",
                offer_id="offer-001",
                asset_id="urn:asset:test",
                policy={"@type": "odrl:Offer"},
                provider_bpn="BPNL00000003TEST",
            )

        assert result is not None
        assert result.negotiation_id == "neg-internal-001"
        assert result.asset_id == "urn:asset:test"

    @pytest.mark.asyncio
    async def test_initiate_negotiation_validates_connection(
        self, catalog_service_for_negotiation
    ):
        """Test that negotiation validates connection exists."""
        catalog_service_for_negotiation.conn_manager.get_connection.return_value = None

        with pytest.raises(CatalogServiceError) as exc_info:
            await catalog_service_for_negotiation.initiate_negotiation(
                connection_id="non-existent",
                provider_address="http://provider:8080/api/v1/dsp",
                offer_id="offer-001",
                asset_id="urn:asset:test",
                policy={},
            )

        assert "Connection not found" in str(exc_info.value)


class TestCatalogServiceError:
    """Tests for CatalogServiceError."""

    def test_error_message(self):
        """Test error message formatting."""
        error = CatalogServiceError("Catalog search failed")
        assert str(error) == "Catalog search failed"

    def test_error_with_cause(self):
        """Test error with underlying cause."""
        cause = ValueError("Invalid provider address")
        error = CatalogServiceError("Catalog operation failed", cause=cause)
        # CatalogServiceError stores cause in .cause attribute, not __cause__
        assert error.cause == cause


class TestCatalogOffer:
    """Tests for CatalogOffer model."""

    def test_from_dcat_dataset_basic(self):
        """Test parsing basic DCAT dataset."""
        dataset = {
            "@id": "urn:asset:test",
            "odrl:hasPolicy": {
                "@id": "offer-001",
                "@type": "odrl:Offer",
                "odrl:permission": [],
            },
            "https://w3id.org/edc/v0.0.1/ns/properties": {
                "name": "Test Asset",
                "contenttype": "application/json",
            },
        }

        offer = CatalogOffer.from_dcat_dataset(dataset, provider_bpn="BPNL00000003TEST")

        assert offer.offer_id == "urn:asset:test"
        assert offer.asset_id == "urn:asset:test"
        assert offer.provider_bpn == "BPNL00000003TEST"
        assert offer.policy["@id"] == "offer-001"

    def test_from_dcat_dataset_multiple_policies(self):
        """Test dataset with multiple policy options - takes first."""
        dataset = {
            "@id": "urn:asset:test",
            "odrl:hasPolicy": [
                {"@id": "offer-001", "@type": "odrl:Offer"},
                {"@id": "offer-002", "@type": "odrl:Offer"},
            ],
        }

        offer = CatalogOffer.from_dcat_dataset(dataset)

        # Should take first policy
        assert offer.policy["@id"] == "offer-001"

    def test_to_dict(self):
        """Test serialization to dict."""
        offer = CatalogOffer(
            offer_id="offer-001",
            asset_id="urn:asset:test",
            provider_bpn="BPNL00000003TEST",
            policy={"@type": "odrl:Offer"},
            name="Test Offer",
        )

        result = offer.to_dict()

        assert result["offer_id"] == "offer-001"
        assert result["asset_id"] == "urn:asset:test"
        assert result["provider_bpn"] == "BPNL00000003TEST"
        assert result["name"] == "Test Offer"


class TestProviderInfo:
    """Tests for ProviderInfo model."""

    def test_to_dict_and_from_dict(self):
        """Test serialization round-trip."""
        provider = ProviderInfo(
            bpn="BPNL00000003TEST",
            protocol_address="http://provider:8080/api/v1/dsp",
            name="Test Provider",
            last_seen=datetime(2024, 1, 15, 10, 30, 0),
        )

        as_dict = provider.to_dict()
        restored = ProviderInfo.from_dict(as_dict)

        assert restored.bpn == provider.bpn
        assert restored.protocol_address == provider.protocol_address
        assert restored.name == provider.name
        assert restored.last_seen == provider.last_seen

    def test_from_dict_without_optional_fields(self):
        """Test deserialization without optional fields."""
        data = {
            "bpn": "BPNL00000003TEST",
            "protocol_address": "http://provider:8080/api/v1/dsp",
        }

        provider = ProviderInfo.from_dict(data)

        assert provider.bpn == "BPNL00000003TEST"
        assert provider.name is None
        assert provider.last_seen is None
