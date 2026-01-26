"""
Eclipse Dataspace Connector (EDC) clients.

Provides clients for interacting with EDC implementations:

- TractusXClient: Tractus-X EDC Management API client
- AASExtensionClient: AAS-specific EDC extension client
"""

from app.services.dataspace.edc.tractus_x_client import TractusXClient
from app.services.dataspace.edc.aas_extension_client import AASExtensionClient

__all__ = [
    "TractusXClient",
    "AASExtensionClient",
]
