"""
Identity and certificate management for dataspace connectivity.

Provides tools for managing certificates, keys, and identity:

- CertManager: Certificate lifecycle management
- VaultClient: HashiCorp Vault integration for secrets
"""

from app.services.dataspace.identity.cert_manager import CertManager
from app.services.dataspace.identity.vault_client import VaultClient

__all__ = [
    "CertManager",
    "VaultClient",
]
