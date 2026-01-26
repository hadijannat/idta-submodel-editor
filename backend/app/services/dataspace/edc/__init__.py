"""
Eclipse Dataspace Connector (EDC) clients.

Provides clients for interacting with EDC implementations:

- TractusXClient: Tractus-X EDC Management API client
- AASExtensionClient: AAS-specific EDC extension client

Exceptions:
- EDCClientError: Base exception for EDC client errors
- EDCAssetNotFoundError: Asset not found
- EDCAssetConflictError: Asset already exists
- EDCPolicyNotFoundError: Policy not found
- EDCContractNotFoundError: Contract not found
- EDCNegotiationError: Negotiation failed
- EDCAuthenticationError: Authentication failed
- EDCConnectionError: Connection failed
- AASExtensionError: AAS extension error
- AASShellNotFoundError: Shell not found
- AASSubmodelNotFoundError: Submodel not found
- AASRegistrationError: Registration failed
"""

from app.services.dataspace.edc.tractus_x_client import (
    TractusXClient,
    EDCClientError,
    EDCAssetNotFoundError,
    EDCAssetConflictError,
    EDCPolicyNotFoundError,
    EDCContractNotFoundError,
    EDCNegotiationError,
    EDCAuthenticationError,
    EDCConnectionError,
    EDC_CONTEXT,
)
from app.services.dataspace.edc.aas_extension_client import (
    AASExtensionClient,
    AASExtensionError,
    AASShellNotFoundError,
    AASSubmodelNotFoundError,
    AASRegistrationError,
)

__all__ = [
    # Clients
    "TractusXClient",
    "AASExtensionClient",
    # TractusX Exceptions
    "EDCClientError",
    "EDCAssetNotFoundError",
    "EDCAssetConflictError",
    "EDCPolicyNotFoundError",
    "EDCContractNotFoundError",
    "EDCNegotiationError",
    "EDCAuthenticationError",
    "EDCConnectionError",
    # AAS Extension Exceptions
    "AASExtensionError",
    "AASShellNotFoundError",
    "AASSubmodelNotFoundError",
    "AASRegistrationError",
    # Constants
    "EDC_CONTEXT",
]
