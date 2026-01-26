"""
Base class for dataspace providers.

All providers must implement this interface to support different
dataspace environments (sandbox, Catena-X, Manufacturing-X).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.services.dataspace.models import (
        AssetRegistration,
        ConnectionState,
        ContractNegotiation,
        HealthCheckResult,
    )


class DataspaceProvider(ABC):
    """
    Abstract base class for dataspace providers.

    Each provider implementation handles the specifics of connecting to
    and interacting with a particular dataspace environment.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'sandbox', 'catena-x')."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of the provider."""
        ...

    @abstractmethod
    async def connect(self, connection: "ConnectionState") -> "ConnectionState":
        """
        Establish connection to the dataspace.

        Args:
            connection: Connection configuration

        Returns:
            Updated connection state with status

        Raises:
            DataspaceConnectionError: If connection fails
        """
        ...

    @abstractmethod
    async def disconnect(self, connection: "ConnectionState") -> "ConnectionState":
        """
        Disconnect from the dataspace.

        Args:
            connection: Active connection to disconnect

        Returns:
            Updated connection state
        """
        ...

    @abstractmethod
    async def health_check(self, connection: "ConnectionState") -> list["HealthCheckResult"]:
        """
        Perform health check on connection.

        Args:
            connection: Connection to check

        Returns:
            List of health check results for each component
        """
        ...

    @abstractmethod
    async def register_asset(
        self,
        connection: "ConnectionState",
        registration: "AssetRegistration",
        aas_data: dict[str, Any],
    ) -> "AssetRegistration":
        """
        Register a Digital Twin asset in the dataspace.

        Args:
            connection: Active connection
            registration: Registration request
            aas_data: AAS data to register

        Returns:
            Updated registration with DTR/EDC asset IDs

        Raises:
            RegistrationError: If registration fails
        """
        ...

    @abstractmethod
    async def unregister_asset(
        self,
        connection: "ConnectionState",
        registration: "AssetRegistration",
    ) -> "AssetRegistration":
        """
        Unregister an asset from the dataspace.

        Args:
            connection: Active connection
            registration: Registration to remove

        Returns:
            Updated registration with pending status
        """
        ...

    @abstractmethod
    async def get_catalog(
        self,
        connection: "ConnectionState",
        provider_bpn: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve the data catalog from a provider.

        Args:
            connection: Active connection
            provider_bpn: Optional BPN to filter by provider

        Returns:
            List of available catalog entries
        """
        ...

    @abstractmethod
    async def negotiate_contract(
        self,
        connection: "ConnectionState",
        negotiation: "ContractNegotiation",
        policy: dict[str, Any],
    ) -> "ContractNegotiation":
        """
        Initiate contract negotiation with a provider.

        Args:
            connection: Active connection
            negotiation: Negotiation request
            policy: ODRL policy for the contract

        Returns:
            Updated negotiation state

        Raises:
            NegotiationError: If negotiation fails
        """
        ...

    @abstractmethod
    async def get_negotiation_state(
        self,
        connection: "ConnectionState",
        negotiation: "ContractNegotiation",
    ) -> "ContractNegotiation":
        """
        Get current state of a contract negotiation.

        Args:
            connection: Active connection
            negotiation: Negotiation to check

        Returns:
            Updated negotiation state
        """
        ...

    def is_available(self) -> bool:
        """
        Check if the provider is properly configured and available.

        Returns:
            True if provider can be used
        """
        return True

    def get_required_config(self) -> list[str]:
        """
        Get list of required configuration keys for this provider.

        Returns:
            List of required configuration key names
        """
        return []

    def validate_config(self, config: dict[str, Any]) -> tuple[bool, list[str]]:
        """
        Validate provider configuration.

        Args:
            config: Configuration dictionary to validate

        Returns:
            Tuple of (is_valid, list_of_missing_keys)
        """
        required = self.get_required_config()
        missing = [key for key in required if key not in config or not config[key]]
        return len(missing) == 0, missing


class DataspaceError(Exception):
    """Base exception for dataspace operations."""

    pass


class DataspaceConnectionError(DataspaceError):
    """Raised when connection to dataspace fails."""

    pass


class RegistrationError(DataspaceError):
    """Raised when asset registration fails."""

    pass


class NegotiationError(DataspaceError):
    """Raised when contract negotiation fails."""

    pass


class PolicyError(DataspaceError):
    """Raised when policy creation or validation fails."""

    pass
