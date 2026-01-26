"""
Catalog Service - Orchestrates catalog browsing and contract negotiation.

Provides a high-level API for searching provider catalogs and initiating
contract negotiations. Wraps TractusXClient methods with state management
and domain model transformations.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.services.dataspace.connection_manager import ConnectionManager
from app.services.dataspace.edc.tractus_x_client import TractusXClient
from app.services.dataspace.models import (
    ConnectionStatus,
    ContractNegotiation,
    ContractState,
)

logger = logging.getLogger(__name__)


class CatalogServiceError(Exception):
    """Base exception for catalog service errors."""

    def __init__(self, message: str, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.cause = cause


class CatalogOffer:
    """Domain model for a catalog offer."""

    def __init__(
        self,
        offer_id: str,
        asset_id: str,
        provider_bpn: str,
        policy: dict,
        properties: dict | None = None,
        content_type: str | None = None,
        name: str | None = None,
        description: str | None = None,
    ) -> None:
        self.offer_id = offer_id
        self.asset_id = asset_id
        self.provider_bpn = provider_bpn
        self.policy = policy
        self.properties = properties or {}
        self.content_type = content_type
        self.name = name
        self.description = description

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "offer_id": self.offer_id,
            "asset_id": self.asset_id,
            "provider_bpn": self.provider_bpn,
            "policy": self.policy,
            "properties": self.properties,
            "content_type": self.content_type,
            "name": self.name,
            "description": self.description,
        }

    @classmethod
    def from_dcat_dataset(
        cls, dataset: dict[str, Any], provider_bpn: str | None = None
    ) -> "CatalogOffer":
        """
        Transform a DCAT dataset from EDC catalog to CatalogOffer.

        Args:
            dataset: DCAT dataset from EDC catalog response
            provider_bpn: Provider BPN (may be extracted from dataset)

        Returns:
            CatalogOffer instance
        """
        # Extract offer/dataset ID
        offer_id = (
            dataset.get("@id")
            or dataset.get("dcat:dataset/@id")
            or dataset.get("id")
            or str(uuid.uuid4())
        )

        # Extract asset ID from properties or dataset
        asset_id = (
            dataset.get("https://w3id.org/edc/v0.0.1/ns/id")
            or dataset.get("edc:id")
            or dataset.get("assetId")
            or offer_id
        )

        # Extract BPN from participant ID or use provided
        extracted_bpn = (
            dataset.get("dcat:participantId")
            or dataset.get("edc:participantId")
            or provider_bpn
            or "unknown"
        )

        # Extract policy - could be hasPolicy or odrl:hasPolicy
        policy = (
            dataset.get("odrl:hasPolicy")
            or dataset.get("hasPolicy")
            or dataset.get("policy")
            or {}
        )
        if isinstance(policy, list):
            policy = policy[0] if policy else {}

        # Extract properties
        properties = {}
        for key in dataset:
            if key.startswith("https://") or key.startswith("edc:"):
                properties[key] = dataset[key]

        # Extract name and description
        name = (
            dataset.get("dct:title")
            or dataset.get("name")
            or dataset.get("https://w3id.org/edc/v0.0.1/ns/name")
        )
        description = (
            dataset.get("dct:description")
            or dataset.get("description")
            or dataset.get("https://w3id.org/edc/v0.0.1/ns/description")
        )
        content_type = (
            dataset.get("dct:format")
            or dataset.get("contentType")
            or dataset.get("https://w3id.org/edc/v0.0.1/ns/contenttype")
        )

        return cls(
            offer_id=offer_id,
            asset_id=asset_id,
            provider_bpn=extracted_bpn,
            policy=policy,
            properties=properties,
            content_type=content_type,
            name=name,
            description=description,
        )


class ProviderInfo:
    """Information about a known catalog provider."""

    def __init__(
        self,
        bpn: str,
        protocol_address: str,
        name: str | None = None,
        last_seen: datetime | None = None,
    ) -> None:
        self.bpn = bpn
        self.protocol_address = protocol_address
        self.name = name
        self.last_seen = last_seen

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "bpn": self.bpn,
            "protocol_address": self.protocol_address,
            "name": self.name,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProviderInfo":
        """Deserialize from dictionary."""
        return cls(
            bpn=data["bpn"],
            protocol_address=data["protocol_address"],
            name=data.get("name"),
            last_seen=(
                datetime.fromisoformat(data["last_seen"])
                if data.get("last_seen")
                else None
            ),
        )


class CatalogService:
    """
    Service for browsing dataspace catalogs and negotiating contracts.

    Provides high-level operations for:
    - Searching provider catalogs
    - Managing known providers
    - Initiating and tracking contract negotiations
    """

    def __init__(
        self,
        connection_manager: ConnectionManager | None = None,
    ) -> None:
        """
        Initialize the catalog service.

        Args:
            connection_manager: Connection manager instance
        """
        self.settings = get_settings()
        self.conn_manager = connection_manager or ConnectionManager()
        self.providers_dir = self.conn_manager.base_dir / "providers"
        self.providers_dir.mkdir(parents=True, exist_ok=True)

        # Client cache
        self._edc_clients: dict[str, TractusXClient] = {}

    async def _get_edc_client(self, connection_id: str) -> TractusXClient:
        """
        Get or create an EDC client for a connection.

        Args:
            connection_id: Connection ID

        Returns:
            TractusXClient instance

        Raises:
            CatalogServiceError: If connection not found or not connected
        """
        if connection_id in self._edc_clients:
            return self._edc_clients[connection_id]

        connection = self.conn_manager.get_connection(connection_id)
        if connection is None:
            raise CatalogServiceError(f"Connection not found: {connection_id}")

        if connection.status != ConnectionStatus.CONNECTED:
            raise CatalogServiceError(
                f"Connection not active: {connection.status.value}"
            )

        if not connection.edc_url:
            raise CatalogServiceError("Connection has no EDC URL configured")

        # Get API key from settings or metadata
        api_key = connection.metadata.get("edc_api_key") or self.settings.edc_api_key

        client = TractusXClient(
            control_plane_url=connection.edc_url,
            data_plane_url=connection.metadata.get("edc_data_url"),
            api_key=api_key,
        )

        self._edc_clients[connection_id] = client
        return client

    # -------------------------------------------------------------------------
    # Catalog Search
    # -------------------------------------------------------------------------

    async def search_catalog(
        self,
        connection_id: str,
        provider_address: str,
        provider_bpn: str | None = None,
        asset_id: str | None = None,
        semantic_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[CatalogOffer], int]:
        """
        Search a provider's catalog.

        Args:
            connection_id: Connection to use for the search
            provider_address: Provider's DSP protocol address
            provider_bpn: Optional provider BPN
            asset_id: Optional asset ID filter
            semantic_id: Optional semantic ID filter
            limit: Maximum results
            offset: Result offset

        Returns:
            Tuple of (offers, total_count)
        """
        logger.info(
            "Searching catalog at %s (connection=%s)",
            provider_address,
            connection_id,
        )

        client = await self._get_edc_client(connection_id)

        # Build query spec with filters
        query_spec = None
        filter_expressions = []

        if asset_id:
            filter_expressions.append({
                "operandLeft": "https://w3id.org/edc/v0.0.1/ns/id",
                "operator": "=",
                "operandRight": asset_id,
            })

        if semantic_id:
            filter_expressions.append({
                "operandLeft": "https://w3id.org/aas/3/0/semanticId",
                "operator": "=",
                "operandRight": semantic_id,
            })

        if filter_expressions:
            query_spec = {"filterExpression": filter_expressions}

        # Request catalog
        catalog = await client.request_catalog(
            counter_party_address=provider_address,
            counter_party_id=provider_bpn,
            query_spec=query_spec,
        )

        # Extract datasets
        datasets = catalog.get("dcat:dataset", catalog.get("dataset", []))
        if isinstance(datasets, dict):
            datasets = [datasets]

        # Transform to domain models
        offers = []
        for dataset in datasets:
            try:
                offer = CatalogOffer.from_dcat_dataset(dataset, provider_bpn)
                offers.append(offer)
            except Exception as e:
                logger.warning("Failed to parse catalog dataset: %s", e)
                continue

        total = len(offers)

        # Apply pagination
        paginated = offers[offset : offset + limit]

        # Update provider info
        if provider_bpn:
            await self._update_provider_info(
                connection_id, provider_bpn, provider_address
            )

        logger.info(
            "Found %d offers in catalog (returning %d)",
            total,
            len(paginated),
        )

        return paginated, total

    # -------------------------------------------------------------------------
    # Provider Management
    # -------------------------------------------------------------------------

    async def list_providers(self, connection_id: str) -> list[ProviderInfo]:
        """
        List known providers for a connection.

        Args:
            connection_id: Connection ID

        Returns:
            List of known providers
        """
        providers_file = self.providers_dir / f"{connection_id}.json"
        if not providers_file.exists():
            return []

        try:
            data = json.loads(providers_file.read_text())
            return [ProviderInfo.from_dict(p) for p in data.get("providers", [])]
        except Exception as e:
            logger.warning("Failed to load providers: %s", e)
            return []

    async def add_provider(
        self,
        connection_id: str,
        bpn: str,
        protocol_address: str,
        name: str | None = None,
    ) -> ProviderInfo:
        """
        Add a provider to the known providers list.

        Args:
            connection_id: Connection ID
            bpn: Provider BPN
            protocol_address: Provider's protocol address
            name: Optional provider name

        Returns:
            Created provider info
        """
        providers = await self.list_providers(connection_id)

        # Check if already exists
        existing = next((p for p in providers if p.bpn == bpn), None)
        if existing:
            existing.protocol_address = protocol_address
            existing.name = name or existing.name
            existing.last_seen = datetime.now(timezone.utc)
            provider = existing
        else:
            provider = ProviderInfo(
                bpn=bpn,
                protocol_address=protocol_address,
                name=name,
                last_seen=datetime.now(timezone.utc),
            )
            providers.append(provider)

        # Save
        providers_file = self.providers_dir / f"{connection_id}.json"
        providers_file.write_text(
            json.dumps(
                {"providers": [p.to_dict() for p in providers]},
                indent=2,
            )
        )

        return provider

    async def _update_provider_info(
        self,
        connection_id: str,
        bpn: str,
        protocol_address: str,
    ) -> None:
        """Update provider last_seen timestamp."""
        await self.add_provider(connection_id, bpn, protocol_address)

    # -------------------------------------------------------------------------
    # Contract Negotiation
    # -------------------------------------------------------------------------

    async def initiate_negotiation(
        self,
        connection_id: str,
        provider_address: str,
        offer_id: str,
        asset_id: str,
        policy: dict,
        provider_bpn: str | None = None,
    ) -> ContractNegotiation:
        """
        Initiate a contract negotiation with a provider.

        Args:
            connection_id: Connection to use
            provider_address: Provider's protocol address
            offer_id: Offer ID from catalog
            asset_id: Asset ID to negotiate
            policy: ODRL policy for the negotiation
            provider_bpn: Provider's BPN

        Returns:
            ContractNegotiation tracking object

        Raises:
            CatalogServiceError: If negotiation fails to start
        """
        logger.info(
            "Initiating negotiation for asset %s with %s",
            asset_id,
            provider_address,
        )

        client = await self._get_edc_client(connection_id)
        connection = self.conn_manager.get_connection(connection_id)

        # Build offer structure for EDC
        offer = {
            "offerId": offer_id,
            "assetId": asset_id,
            "policy": policy,
        }

        # Initiate negotiation via EDC
        try:
            result = await client.initiate_negotiation(
                counter_party_address=provider_address,
                protocol="dataspace-protocol-http",
                offer=offer,
                counter_party_id=provider_bpn,
            )
        except Exception as e:
            raise CatalogServiceError(f"Failed to initiate negotiation: {e}", cause=e)

        edc_negotiation_id = result.get("@id") or result.get("id")
        if not edc_negotiation_id:
            raise CatalogServiceError("EDC did not return negotiation ID")

        # Create tracking record
        negotiation = self.conn_manager.create_negotiation(
            connection_id=connection_id,
            asset_id=asset_id,
            provider_bpn=provider_bpn or "unknown",
            consumer_bpn=connection.bpn or "unknown",
            metadata={
                "edc_negotiation_id": edc_negotiation_id,
                "offer_id": offer_id,
                "provider_address": provider_address,
            },
        )

        logger.info(
            "Created negotiation %s (EDC: %s)",
            negotiation.negotiation_id,
            edc_negotiation_id,
        )

        return negotiation

    async def get_negotiation_status(
        self, negotiation_id: str
    ) -> ContractNegotiation | None:
        """
        Get the current status of a negotiation.

        Args:
            negotiation_id: Internal negotiation ID

        Returns:
            Updated negotiation state or None if not found
        """
        negotiation = self.conn_manager.get_negotiation(negotiation_id)
        if negotiation is None:
            return None

        edc_negotiation_id = negotiation.metadata.get("edc_negotiation_id")
        if not edc_negotiation_id:
            return negotiation

        # Fetch current state from EDC
        try:
            client = await self._get_edc_client(negotiation.connection_id)
            edc_state = await client.get_negotiation(edc_negotiation_id)

            if edc_state:
                # Map EDC state to our state
                state_str = edc_state.get("state", "").upper()
                state_map = {
                    "INITIAL": ContractState.INITIAL,
                    "REQUESTING": ContractState.REQUESTING,
                    "OFFERED": ContractState.OFFERED,
                    "AGREEING": ContractState.AGREEING,
                    "AGREED": ContractState.AGREED,
                    "VERIFYING": ContractState.VERIFYING,
                    "VERIFIED": ContractState.VERIFIED,
                    "FINALIZED": ContractState.FINALIZED,
                    "TERMINATED": ContractState.TERMINATED,
                    "ERROR": ContractState.ERROR,
                }
                new_state = state_map.get(state_str, negotiation.state)

                # Get agreement ID if finalized
                agreement_id = edc_state.get("contractAgreementId")

                # Update our record
                negotiation.state = new_state
                if agreement_id:
                    negotiation.agreement_id = agreement_id
                negotiation.updated_at = datetime.now(timezone.utc)

                self.conn_manager._save_negotiation(negotiation)

        except Exception as e:
            logger.warning("Failed to fetch EDC negotiation state: %s", e)

        return negotiation

    async def list_negotiations(
        self,
        connection_id: str | None = None,
        state: ContractState | None = None,
        limit: int = 50,
    ) -> list[ContractNegotiation]:
        """
        List negotiations with optional filters.

        Args:
            connection_id: Filter by connection
            state: Filter by state
            limit: Maximum results

        Returns:
            List of negotiations
        """
        negotiations: list[ContractNegotiation] = []

        for neg_path in self.conn_manager.negotiations_dir.glob("*.json"):
            try:
                data = json.loads(neg_path.read_text())
                negotiation = ContractNegotiation.from_dict(data)

                if connection_id and negotiation.connection_id != connection_id:
                    continue
                if state and negotiation.state != state:
                    continue

                negotiations.append(negotiation)
            except Exception as e:
                logger.warning("Failed to load negotiation: %s", e)

        negotiations.sort(key=lambda n: n.created_at, reverse=True)
        return negotiations[:limit]
