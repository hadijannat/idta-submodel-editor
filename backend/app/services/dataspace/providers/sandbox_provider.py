"""
Sandbox dataspace provider for local testing.

Provides a mock implementation of the dataspace interface for
development and testing without requiring actual dataspace connectivity.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from app.services.dataspace.models import (
    ConnectionStatus,
    ContractState,
    HealthCheckResult,
    RegistrationStatus,
)
from app.services.dataspace.providers.provider_base import (
    DataspaceProvider,
    DataspaceConnectionError,
)

if TYPE_CHECKING:
    from app.services.dataspace.models import (
        AssetRegistration,
        ConnectionState,
        ContractNegotiation,
    )

logger = logging.getLogger(__name__)


class SandboxProvider(DataspaceProvider):
    """
    Sandbox provider for local testing and development.

    Simulates dataspace operations without actual network calls.
    Useful for development, testing, and demos.
    """

    @property
    def name(self) -> str:
        """Provider name."""
        return "sandbox"

    @property
    def description(self) -> str:
        """Provider description."""
        return "Local sandbox for testing dataspace connectivity without external dependencies"

    async def connect(
        self,
        connection: "ConnectionState",
        secrets: dict[str, Any] | None = None,
    ) -> "ConnectionState":
        """
        Simulate connection establishment.

        Args:
            connection: Connection configuration

        Returns:
            Updated connection state
        """
        logger.info("Sandbox: Establishing mock connection %s", connection.connection_id)

        # Simulate connection delay
        connection.status = ConnectionStatus.CONNECTED
        connection.updated_at = datetime.utcnow()
        connection.last_health_check = datetime.utcnow()

        # Set mock URLs if not provided
        if not connection.dtr_url:
            connection.dtr_url = "http://localhost:4175/aas-registry"
        if not connection.edc_url:
            connection.edc_url = "http://localhost:19193/management"
        if not connection.bpn:
            connection.bpn = f"BPNL00000000SANDBOX"

        logger.info("Sandbox: Connection %s established", connection.connection_id)
        return connection

    async def disconnect(self, connection: "ConnectionState") -> "ConnectionState":
        """
        Simulate disconnection.

        Args:
            connection: Active connection

        Returns:
            Updated connection state
        """
        logger.info("Sandbox: Disconnecting %s", connection.connection_id)

        connection.status = ConnectionStatus.DISCONNECTED
        connection.updated_at = datetime.utcnow()

        return connection

    async def health_check(self, connection: "ConnectionState") -> list[HealthCheckResult]:
        """
        Perform mock health check.

        Args:
            connection: Connection to check

        Returns:
            List of health check results
        """
        now = datetime.utcnow()

        return [
            HealthCheckResult(
                component="dtr",
                healthy=True,
                latency_ms=5.0,
                message="Sandbox DTR healthy",
                checked_at=now,
            ),
            HealthCheckResult(
                component="edc",
                healthy=True,
                latency_ms=3.0,
                message="Sandbox EDC healthy",
                checked_at=now,
            ),
            HealthCheckResult(
                component="identity",
                healthy=True,
                latency_ms=2.0,
                message="Sandbox identity healthy",
                checked_at=now,
            ),
        ]

    async def register_asset(
        self,
        connection: "ConnectionState",
        registration: "AssetRegistration",
        aas_data: dict[str, Any],
    ) -> "AssetRegistration":
        """
        Simulate asset registration.

        Args:
            connection: Active connection
            registration: Registration request
            aas_data: AAS data to register

        Returns:
            Updated registration
        """
        logger.info(
            "Sandbox: Registering asset %s for AAS %s",
            registration.registration_id,
            registration.aas_id,
        )

        # Generate mock IDs
        registration.dtr_asset_id = f"sandbox-dtr-{uuid.uuid4().hex[:8]}"
        registration.edc_asset_id = f"sandbox-edc-{uuid.uuid4().hex[:8]}"
        registration.status = RegistrationStatus.REGISTERED
        registration.updated_at = datetime.utcnow()

        logger.info(
            "Sandbox: Asset registered with DTR ID %s, EDC ID %s",
            registration.dtr_asset_id,
            registration.edc_asset_id,
        )

        return registration

    async def unregister_asset(
        self,
        connection: "ConnectionState",
        registration: "AssetRegistration",
    ) -> "AssetRegistration":
        """
        Simulate asset unregistration.

        Args:
            connection: Active connection
            registration: Registration to remove

        Returns:
            Updated registration
        """
        logger.info(
            "Sandbox: Unregistering asset %s",
            registration.registration_id,
        )

        registration.status = RegistrationStatus.UNPUBLISHED
        registration.dtr_asset_id = None
        registration.edc_asset_id = None
        registration.updated_at = datetime.utcnow()

        return registration

    async def get_catalog(
        self,
        connection: "ConnectionState",
        provider_bpn: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Return mock catalog entries.

        Args:
            connection: Active connection
            provider_bpn: Optional BPN filter

        Returns:
            List of mock catalog entries
        """
        # Return some sample catalog entries for testing
        return [
            {
                "id": "sandbox-catalog-1",
                "type": "Asset",
                "properties": {
                    "name": "Sample Digital Twin",
                    "description": "A sample digital twin for testing",
                    "contentType": "application/json",
                },
                "dataAddress": {
                    "type": "HttpData",
                    "baseUrl": "http://localhost:4175/aas/shells/sample-1",
                },
            },
            {
                "id": "sandbox-catalog-2",
                "type": "Asset",
                "properties": {
                    "name": "PCF Submodel",
                    "description": "Product Carbon Footprint data",
                    "contentType": "application/json",
                },
                "dataAddress": {
                    "type": "HttpData",
                    "baseUrl": "http://localhost:4175/aas/submodels/pcf-1",
                },
            },
        ]

    async def negotiate_contract(
        self,
        connection: "ConnectionState",
        negotiation: "ContractNegotiation",
        policy: dict[str, Any],
    ) -> "ContractNegotiation":
        """
        Simulate contract negotiation.

        Args:
            connection: Active connection
            negotiation: Negotiation request
            policy: ODRL policy

        Returns:
            Updated negotiation
        """
        logger.info(
            "Sandbox: Starting negotiation %s for asset %s",
            negotiation.negotiation_id,
            negotiation.asset_id,
        )

        # Simulate successful negotiation
        negotiation.state = ContractState.AGREED
        negotiation.offer_id = f"sandbox-offer-{uuid.uuid4().hex[:8]}"
        negotiation.agreement_id = f"sandbox-agreement-{uuid.uuid4().hex[:8]}"
        negotiation.policy_id = policy.get("@id", f"sandbox-policy-{uuid.uuid4().hex[:8]}")
        negotiation.updated_at = datetime.utcnow()

        logger.info(
            "Sandbox: Negotiation %s agreed with agreement ID %s",
            negotiation.negotiation_id,
            negotiation.agreement_id,
        )

        return negotiation

    async def get_negotiation_state(
        self,
        connection: "ConnectionState",
        negotiation: "ContractNegotiation",
    ) -> "ContractNegotiation":
        """
        Get mock negotiation state.

        Args:
            connection: Active connection
            negotiation: Negotiation to check

        Returns:
            Current negotiation state
        """
        # In sandbox, negotiations complete instantly
        return negotiation

    def is_available(self) -> bool:
        """Sandbox is always available."""
        return True

    def get_required_config(self) -> list[str]:
        """Sandbox requires no configuration."""
        return []
