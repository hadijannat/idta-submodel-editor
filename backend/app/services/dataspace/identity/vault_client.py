"""
HashiCorp Vault client for secrets management.

Provides integration with HashiCorp Vault for secure storage of
credentials, certificates, and other secrets needed for dataspace connectivity.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class VaultClient:
    """
    Client for HashiCorp Vault.

    Provides secure access to secrets including:
    - API keys and tokens
    - Certificates and private keys
    - Database credentials
    - EDC connector credentials
    """

    def __init__(
        self,
        vault_url: str | None = None,
        token: str | None = None,
        mount_point: str = "secret",
        namespace: str | None = None,
    ) -> None:
        """
        Initialize the Vault client.

        Args:
            vault_url: Vault server URL
            token: Vault authentication token
            mount_point: KV secrets engine mount point
            namespace: Vault Enterprise namespace
        """
        self.vault_url = vault_url or "http://localhost:8200"
        self.token = token
        self.mount_point = mount_point
        self.namespace = namespace

        self._client = None
        self._authenticated = False

    @property
    def is_configured(self) -> bool:
        """Check if Vault is configured with credentials."""
        return bool(self.vault_url and self.token)

    def _headers(self) -> dict[str, str]:
        """Build Vault request headers."""
        headers = {"X-Vault-Token": self.token or ""}
        if self.namespace:
            headers["X-Vault-Namespace"] = self.namespace
        return headers

    async def authenticate(self) -> bool:
        """
        Authenticate with Vault.

        Returns:
            True if authentication successful
        """
        if not self.is_configured:
            logger.warning("Vault not configured")
            return False

        import httpx

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{self.vault_url.rstrip('/')}/v1/auth/token/lookup-self",
                    headers=self._headers(),
                )
                response.raise_for_status()

            self._authenticated = True
            logger.info("Authenticated with Vault at %s", self.vault_url)
            return True

        except Exception as e:
            logger.error("Vault authentication failed: %s", e)
            return False

    async def get_secret(self, path: str) -> dict[str, Any] | None:
        """
        Get a secret from Vault.

        Args:
            path: Secret path (relative to mount point)

        Returns:
            Secret data dictionary or None if not found
        """
        if not self.is_configured:
            logger.debug("Vault not configured, skipping secret retrieval")
            return None

        logger.debug("Getting secret from Vault: %s", path)

        import httpx

        url = f"{self.vault_url.rstrip('/')}/v1/{self.mount_point}/data/{path}"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url, headers=self._headers())
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                payload = response.json()
                return (payload.get("data") or {}).get("data")
        except httpx.HTTPError as e:
            logger.warning("Vault read failed for %s: %s", path, e)
            return None

    async def set_secret(
        self,
        path: str,
        data: dict[str, Any],
    ) -> bool:
        """
        Store a secret in Vault.

        Args:
            path: Secret path (relative to mount point)
            data: Secret data to store

        Returns:
            True if successful
        """
        if not self.is_configured:
            logger.warning("Vault not configured")
            return False

        logger.info("Storing secret in Vault: %s", path)

        import httpx

        url = f"{self.vault_url.rstrip('/')}/v1/{self.mount_point}/data/{path}"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    url,
                    headers=self._headers(),
                    json={"data": data},
                )
                response.raise_for_status()
            return True
        except httpx.HTTPError as e:
            logger.warning("Vault write failed for %s: %s", path, e)
            return False

    async def delete_secret(self, path: str) -> bool:
        """
        Delete a secret from Vault.

        Args:
            path: Secret path to delete

        Returns:
            True if deleted
        """
        if not self.is_configured:
            return False

        logger.info("Deleting secret from Vault: %s", path)

        import httpx

        url = f"{self.vault_url.rstrip('/')}/v1/{self.mount_point}/metadata/{path}"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.delete(url, headers=self._headers())
                response.raise_for_status()
            return True
        except httpx.HTTPError as e:
            logger.warning("Vault delete failed for %s: %s", path, e)
            return False

    async def get_edc_credentials(self, connection_id: str) -> dict[str, Any] | None:
        """
        Get EDC connector credentials for a connection.

        Args:
            connection_id: Connection identifier

        Returns:
            Credentials dictionary with api_key, etc.
        """
        path = f"dataspace/connections/{connection_id}/edc"
        return await self.get_secret(path)

    async def store_edc_credentials(
        self,
        connection_id: str,
        api_key: str,
        api_secret: str | None = None,
    ) -> bool:
        """
        Store EDC connector credentials.

        Args:
            connection_id: Connection identifier
            api_key: EDC API key
            api_secret: Optional API secret

        Returns:
            True if stored successfully
        """
        path = f"dataspace/connections/{connection_id}/edc"
        data = {
            "api_key": api_key,
        }
        if api_secret:
            data["api_secret"] = api_secret

        return await self.set_secret(path, data)

    async def get_dtr_credentials(self, connection_id: str) -> dict[str, Any] | None:
        """
        Get DTR credentials for a connection.

        Args:
            connection_id: Connection identifier

        Returns:
            Credentials dictionary with token, etc.
        """
        path = f"dataspace/connections/{connection_id}/dtr"
        return await self.get_secret(path)

    async def get_credentials(self, connection_id: str) -> dict[str, Any] | None:
        """
        Get generic credentials for a connection.

        Args:
            connection_id: Connection identifier

        Returns:
            Credentials dictionary or None
        """
        path = f"dataspace/connections/{connection_id}/credentials"
        return await self.get_secret(path)

    async def store_credentials(self, connection_id: str, data: dict[str, Any]) -> bool:
        """
        Store generic credentials for a connection.

        Args:
            connection_id: Connection identifier
            data: Credentials dictionary

        Returns:
            True if stored successfully
        """
        path = f"dataspace/connections/{connection_id}/credentials"
        return await self.set_secret(path, data)

    async def store_certificate(
        self,
        name: str,
        cert_pem: str,
        key_pem: str | None = None,
        chain_pem: str | None = None,
    ) -> bool:
        """
        Store a certificate in Vault.

        Args:
            name: Certificate identifier
            cert_pem: PEM-encoded certificate
            key_pem: Optional PEM-encoded private key
            chain_pem: Optional PEM-encoded certificate chain

        Returns:
            True if stored successfully
        """
        path = f"dataspace/certificates/{name}"
        data = {"cert": cert_pem}
        if key_pem:
            data["key"] = key_pem
        if chain_pem:
            data["chain"] = chain_pem

        return await self.set_secret(path, data)

    async def get_certificate(self, name: str) -> dict[str, str] | None:
        """
        Get a certificate from Vault.

        Args:
            name: Certificate identifier

        Returns:
            Dictionary with cert, key, chain PEM strings
        """
        path = f"dataspace/certificates/{name}"
        return await self.get_secret(path)

    async def health_check(self) -> bool:
        """
        Check Vault health.

        Returns:
            True if Vault is healthy and accessible
        """
        if not self.is_configured:
            return False

        # TODO: Implement actual health check

        return True

    async def close(self) -> None:
        """Close the Vault client."""
        self._client = None
        self._authenticated = False
