"""
Dataspace Connectivity - Manufacturing-X / Catena-X Integration.

This module provides connectivity to dataspace ecosystems for SMEs to:
- Connect Digital Twins to Manufacturing-X / Catena-X networks
- Register assets in Digital Twin Registries (DTR)
- Negotiate and manage data contracts via Eclipse Dataspace Connector (EDC)
- Handle identity and certificate management

Main components:
- ConnectionManager: Manages connection state and persistence
- DataspaceProvider (abstract): Interface for dataspace implementations
- SandboxProvider: Local testing environment
- CatenaXProvider: Production Catena-X connectivity
- AASPublisher: Publishes submodels to BaSyx and DTR

Submodules:
- providers/: Dataspace provider implementations
- edc/: Eclipse Dataspace Connector clients
- registry/: Digital Twin Registry clients
- policy/: ODRL policy engine and templates
- identity/: Certificate and identity management
"""

from app.services.dataspace.connection_manager import ConnectionManager
from app.services.dataspace.health import DataspaceHealthChecker
from app.services.dataspace.publisher import (
    AASPublisher,
    AASPublisherError,
    PublicationResult,
)

__all__ = [
    "ConnectionManager",
    "DataspaceHealthChecker",
    "AASPublisher",
    "AASPublisherError",
    "PublicationResult",
]
