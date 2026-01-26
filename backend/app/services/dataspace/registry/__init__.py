"""
Digital Twin Registry clients.

Provides clients for interacting with AAS registries:

- DTRClient: Digital Twin Registry (IDTA standard) client
- BaSyxClient: Eclipse BaSyx registry client
"""

from app.services.dataspace.registry.dtr_client import (
    DTRClient,
    DTRClientError,
    DTRNotFoundError,
    DTRConflictError,
    DTRAuthenticationError,
)
from app.services.dataspace.registry.basyx_client import (
    BaSyxClient,
    BaSyxClientError,
    BaSyxNotFoundError,
    BaSyxConflictError,
)

__all__ = [
    # DTR Client
    "DTRClient",
    "DTRClientError",
    "DTRNotFoundError",
    "DTRConflictError",
    "DTRAuthenticationError",
    # BaSyx Client
    "BaSyxClient",
    "BaSyxClientError",
    "BaSyxNotFoundError",
    "BaSyxConflictError",
]
