"""
Digital Twin Registry clients.

Provides clients for interacting with AAS registries:

- DTRClient: Digital Twin Registry (IDTA standard) client
- BaSyxClient: Eclipse BaSyx registry client
"""

from app.services.dataspace.registry.dtr_client import DTRClient
from app.services.dataspace.registry.basyx_client import BaSyxClient

__all__ = [
    "DTRClient",
    "BaSyxClient",
]
