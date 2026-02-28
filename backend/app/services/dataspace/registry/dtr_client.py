"""
Digital Twin Registry (DTR) client.

Provides HTTP client for interacting with IDTA-compliant Digital Twin Registries
following the AAS Registry API specification.

Supports:
- Shell Descriptor management
- Submodel Descriptor management
- Lookup operations by asset IDs and semantic IDs
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class DTRClientError(Exception):
    """Base exception for DTR client errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class DTRNotFoundError(DTRClientError):
    """Resource not found in DTR."""

    pass


class DTRConflictError(DTRClientError):
    """Resource already exists in DTR."""

    pass


class DTRAuthenticationError(DTRClientError):
    """Authentication failed with DTR."""

    pass


class DTRClient:
    """
    Client for IDTA-compliant Digital Twin Registry.

    Implements the AAS Registry API for:
    - Shell Descriptor management
    - Submodel Descriptor management
    - Lookup operations

    API Reference: https://app.swaggerhub.com/apis/Plattform_i40/AssetAdministrationShell-Registry
    """

    def __init__(
        self,
        base_url: str,
        auth_token: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        """
        Initialize the DTR client.

        Args:
            base_url: DTR API base URL
            auth_token: Optional OAuth2 bearer token
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self.timeout = timeout

        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None:
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"

            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=self.timeout,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def update_auth_token(self, token: str) -> None:
        """
        Update the authentication token.

        Args:
            token: New OAuth2 bearer token
        """
        self.auth_token = token
        # Force client recreation on next request
        if self._client is not None:
            # Don't close immediately, let it be recreated on next call
            self._client = None

    @staticmethod
    def encode_id(identifier: str) -> str:
        """
        Encode an identifier for URL path.

        AAS API requires base64url encoding of identifiers in paths.

        Args:
            identifier: Raw identifier string

        Returns:
            Base64url-encoded identifier
        """
        return base64.urlsafe_b64encode(identifier.encode()).decode().rstrip("=")

    @staticmethod
    def decode_id(encoded: str) -> str:
        """
        Decode a base64url-encoded identifier.

        Args:
            encoded: Base64url-encoded string

        Returns:
            Decoded identifier
        """
        # Add padding if needed
        padding = 4 - len(encoded) % 4
        if padding != 4:
            encoded += "=" * padding
        return base64.urlsafe_b64decode(encoded.encode()).decode()

    async def _handle_response(
        self,
        response: httpx.Response,
        operation: str,
    ) -> dict[str, Any] | None:
        """
        Handle HTTP response and raise appropriate exceptions.

        Args:
            response: HTTP response
            operation: Operation name for logging

        Returns:
            Parsed JSON response or None

        Raises:
            DTRNotFoundError: If resource not found (404)
            DTRConflictError: If resource already exists (409)
            DTRAuthenticationError: If authentication failed (401/403)
            DTRClientError: For other HTTP errors
        """
        if response.status_code == 401:
            raise DTRAuthenticationError(
                f"{operation}: Authentication required",
                status_code=401,
                response_body=response.text,
            )

        if response.status_code == 403:
            raise DTRAuthenticationError(
                f"{operation}: Access forbidden",
                status_code=403,
                response_body=response.text,
            )

        if response.status_code == 404:
            raise DTRNotFoundError(
                f"{operation}: Resource not found",
                status_code=404,
                response_body=response.text,
            )

        if response.status_code == 409:
            raise DTRConflictError(
                f"{operation}: Resource already exists",
                status_code=409,
                response_body=response.text,
            )

        if response.status_code >= 400:
            raise DTRClientError(
                f"{operation} failed: {response.status_code}",
                status_code=response.status_code,
                response_body=response.text,
            )

        # Handle empty responses (DELETE, etc.)
        if response.status_code == 204 or not response.content:
            return None

        try:
            return response.json()
        except json.JSONDecodeError:
            return None

    # -------------------------------------------------------------------------
    # Shell Descriptor Management
    # -------------------------------------------------------------------------

    async def create_shell_descriptor(
        self,
        descriptor: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Create a new Asset Administration Shell Descriptor.

        Args:
            descriptor: Shell Descriptor following AAS API spec

        Returns:
            Created Shell Descriptor

        Raises:
            DTRConflictError: If descriptor already exists
            DTRAuthenticationError: If authentication fails
            DTRClientError: For other errors
        """
        shell_id = descriptor.get("id", "unknown")
        logger.info("Creating Shell Descriptor %s", shell_id)

        client = await self._get_client()
        response = await client.post(
            "/shell-descriptors",
            json=descriptor,
        )

        result = await self._handle_response(response, "Create Shell Descriptor")
        return result or descriptor

    async def get_shell_descriptor(self, shell_id: str) -> dict[str, Any] | None:
        """
        Get a Shell Descriptor by ID.

        Args:
            shell_id: Shell identifier

        Returns:
            Shell Descriptor or None if not found
        """
        encoded_id = self.encode_id(shell_id)
        logger.debug("Getting Shell Descriptor %s", shell_id)

        client = await self._get_client()
        try:
            response = await client.get(f"/shell-descriptors/{encoded_id}")
            return await self._handle_response(response, "Get Shell Descriptor")
        except DTRNotFoundError:
            return None

    async def update_shell_descriptor(
        self,
        shell_id: str,
        descriptor: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Update a Shell Descriptor.

        Args:
            shell_id: Shell identifier
            descriptor: Updated Shell Descriptor

        Returns:
            Updated Shell Descriptor

        Raises:
            DTRNotFoundError: If descriptor doesn't exist
            DTRAuthenticationError: If authentication fails
            DTRClientError: For other errors
        """
        encoded_id = self.encode_id(shell_id)
        logger.info("Updating Shell Descriptor %s", shell_id)

        client = await self._get_client()
        response = await client.put(
            f"/shell-descriptors/{encoded_id}",
            json=descriptor,
        )

        result = await self._handle_response(response, "Update Shell Descriptor")
        return result or descriptor

    async def delete_shell_descriptor(self, shell_id: str) -> bool:
        """
        Delete a Shell Descriptor.

        Args:
            shell_id: Shell identifier

        Returns:
            True if deleted

        Raises:
            DTRNotFoundError: If descriptor doesn't exist
            DTRAuthenticationError: If authentication fails
            DTRClientError: For other errors
        """
        encoded_id = self.encode_id(shell_id)
        logger.info("Deleting Shell Descriptor %s", shell_id)

        client = await self._get_client()
        response = await client.delete(f"/shell-descriptors/{encoded_id}")
        await self._handle_response(response, "Delete Shell Descriptor")
        return True

    async def get_all_shell_descriptors(
        self,
        limit: int = 100,
        cursor: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        Get all Shell Descriptors with pagination.

        Args:
            limit: Maximum results per page
            cursor: Pagination cursor

        Returns:
            Tuple of (descriptors, next_cursor)
        """
        logger.debug("Getting all Shell Descriptors")

        client = await self._get_client()
        params: dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor

        response = await client.get("/shell-descriptors", params=params)
        result = await self._handle_response(response, "Get all Shell Descriptors")

        if result is None:
            return [], None

        # DTR returns paginated results in a standard format
        descriptors = result.get("result", [])
        paging_metadata = result.get("paging_metadata", {})
        next_cursor = paging_metadata.get("cursor")

        return descriptors, next_cursor

    # -------------------------------------------------------------------------
    # Submodel Descriptor Management
    # -------------------------------------------------------------------------

    async def create_submodel_descriptor(
        self,
        shell_id: str,
        descriptor: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Create a Submodel Descriptor for a Shell.

        Args:
            shell_id: Parent Shell identifier
            descriptor: Submodel Descriptor

        Returns:
            Created Submodel Descriptor

        Raises:
            DTRNotFoundError: If parent shell doesn't exist
            DTRConflictError: If submodel already exists
            DTRAuthenticationError: If authentication fails
            DTRClientError: For other errors
        """
        encoded_id = self.encode_id(shell_id)
        submodel_id = descriptor.get("id", "unknown")
        logger.info(
            "Creating Submodel Descriptor %s for Shell %s",
            submodel_id,
            shell_id,
        )

        client = await self._get_client()
        response = await client.post(
            f"/shell-descriptors/{encoded_id}/submodel-descriptors",
            json=descriptor,
        )

        result = await self._handle_response(response, "Create Submodel Descriptor")
        return result or descriptor

    async def get_submodel_descriptor(
        self,
        shell_id: str,
        submodel_id: str,
    ) -> dict[str, Any] | None:
        """
        Get a Submodel Descriptor.

        Args:
            shell_id: Parent Shell identifier
            submodel_id: Submodel identifier

        Returns:
            Submodel Descriptor or None if not found
        """
        encoded_shell = self.encode_id(shell_id)
        encoded_submodel = self.encode_id(submodel_id)
        logger.debug("Getting Submodel Descriptor %s", submodel_id)

        client = await self._get_client()
        try:
            response = await client.get(
                f"/shell-descriptors/{encoded_shell}/submodel-descriptors/{encoded_submodel}"
            )
            return await self._handle_response(response, "Get Submodel Descriptor")
        except DTRNotFoundError:
            return None

    async def update_submodel_descriptor(
        self,
        shell_id: str,
        submodel_id: str,
        descriptor: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Update a Submodel Descriptor.

        Args:
            shell_id: Parent Shell identifier
            submodel_id: Submodel identifier
            descriptor: Updated Submodel Descriptor

        Returns:
            Updated Submodel Descriptor

        Raises:
            DTRNotFoundError: If submodel doesn't exist
            DTRAuthenticationError: If authentication fails
            DTRClientError: For other errors
        """
        encoded_shell = self.encode_id(shell_id)
        encoded_submodel = self.encode_id(submodel_id)
        logger.info("Updating Submodel Descriptor %s", submodel_id)

        client = await self._get_client()
        response = await client.put(
            f"/shell-descriptors/{encoded_shell}/submodel-descriptors/{encoded_submodel}",
            json=descriptor,
        )

        result = await self._handle_response(response, "Update Submodel Descriptor")
        return result or descriptor

    async def delete_submodel_descriptor(
        self,
        shell_id: str,
        submodel_id: str,
    ) -> bool:
        """
        Delete a Submodel Descriptor.

        Args:
            shell_id: Parent Shell identifier
            submodel_id: Submodel identifier

        Returns:
            True if deleted

        Raises:
            DTRNotFoundError: If submodel doesn't exist
            DTRAuthenticationError: If authentication fails
            DTRClientError: For other errors
        """
        encoded_shell = self.encode_id(shell_id)
        encoded_submodel = self.encode_id(submodel_id)
        logger.info("Deleting Submodel Descriptor %s", submodel_id)

        client = await self._get_client()
        response = await client.delete(
            f"/shell-descriptors/{encoded_shell}/submodel-descriptors/{encoded_submodel}"
        )
        await self._handle_response(response, "Delete Submodel Descriptor")
        return True

    async def get_all_submodel_descriptors(
        self,
        shell_id: str,
        limit: int = 100,
        cursor: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        Get all Submodel Descriptors for a Shell.

        Args:
            shell_id: Parent Shell identifier
            limit: Maximum results per page
            cursor: Pagination cursor

        Returns:
            Tuple of (descriptors, next_cursor)
        """
        encoded_id = self.encode_id(shell_id)
        logger.debug("Getting all Submodel Descriptors for Shell %s", shell_id)

        client = await self._get_client()
        params: dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor

        try:
            response = await client.get(
                f"/shell-descriptors/{encoded_id}/submodel-descriptors",
                params=params,
            )
            result = await self._handle_response(response, "Get all Submodel Descriptors")

            if result is None:
                return [], None

            descriptors = result.get("result", [])
            paging_metadata = result.get("paging_metadata", {})
            next_cursor = paging_metadata.get("cursor")

            return descriptors, next_cursor
        except DTRNotFoundError:
            return [], None

    # -------------------------------------------------------------------------
    # Lookup Operations
    # -------------------------------------------------------------------------

    async def lookup_shells_by_asset_ids(
        self,
        asset_ids: list[dict[str, str]],
    ) -> list[str]:
        """
        Lookup Shell IDs by specific asset IDs.

        Args:
            asset_ids: List of specificAssetId key-value pairs
                       e.g., [{"name": "manufacturerPartId", "value": "123"}]

        Returns:
            List of matching Shell IDs
        """
        logger.debug("Looking up shells by asset IDs: %s", asset_ids)

        client = await self._get_client()

        # Encode asset IDs as base64
        asset_ids_encoded = base64.urlsafe_b64encode(
            json.dumps(asset_ids).encode()
        ).decode()

        response = await client.get(
            "/lookup/shells",
            params={"assetIds": asset_ids_encoded},
        )

        result = await self._handle_response(response, "Lookup shells by asset IDs")

        if result is None:
            return []

        return result.get("result", [])

    async def lookup_submodels_by_semantic_id(
        self,
        shell_id: str,
        semantic_id: str,
    ) -> list[dict[str, Any]]:
        """
        Lookup Submodel Descriptors by semantic ID.

        Args:
            shell_id: Parent Shell identifier
            semantic_id: Semantic ID to match

        Returns:
            List of matching Submodel Descriptors
        """
        logger.debug("Looking up submodels by semantic ID %s", semantic_id)

        # Get all submodels and filter by semantic ID
        submodels, _ = await self.get_all_submodel_descriptors(shell_id, limit=1000)

        matching = []
        for submodel in submodels:
            submodel_semantic_id = submodel.get("semanticId", {})
            if isinstance(submodel_semantic_id, dict):
                keys = submodel_semantic_id.get("keys", [])
                for key in keys:
                    if key.get("value") == semantic_id:
                        matching.append(submodel)
                        break

        return matching

    async def search_shells_by_semantic_id(
        self,
        semantic_id: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Search for Shell Descriptors containing submodels with a semantic ID.

        This is a convenience method that searches across all shells.

        Args:
            semantic_id: Semantic ID to search for
            limit: Maximum results

        Returns:
            List of matching Shell Descriptors
        """
        logger.debug("Searching shells by semantic ID %s", semantic_id)

        # Build search query
        # Note: Not all DTR implementations support this endpoint
        client = await self._get_client()

        # Encode semantic ID reference
        semantic_ref = {
            "type": "ExternalReference",
            "keys": [{"type": "GlobalReference", "value": semantic_id}],
        }
        semantic_id_encoded = base64.urlsafe_b64encode(
            json.dumps(semantic_ref).encode()
        ).decode()

        try:
            response = await client.get(
                "/search/shell-descriptors",
                params={"semanticId": semantic_id_encoded, "limit": limit},
            )
            result = await self._handle_response(response, "Search shells by semantic ID")

            if result is None:
                return []

            return result.get("result", [])
        except DTRClientError as e:
            # Fallback: search is not supported by all DTRs
            if e.status_code == 404:
                logger.warning("DTR does not support search endpoint, returning empty")
                return []
            raise

    # -------------------------------------------------------------------------
    # Health
    # -------------------------------------------------------------------------

    async def health_check(self) -> bool:
        """
        Check DTR health.

        Returns:
            True if healthy
        """
        client = await self._get_client()

        try:
            # Try to get shell descriptors with limit 1 as health check
            response = await client.get("/shell-descriptors", params={"limit": 1})
            return response.status_code < 500
        except httpx.HTTPError:
            return False

    async def get_description(self) -> dict[str, Any] | None:
        """
        Get DTR self-description.

        Returns:
            Description object or None if not available
        """
        client = await self._get_client()

        try:
            response = await client.get("/description")
            return await self._handle_response(response, "Get description")
        except DTRClientError:
            return None

    # -------------------------------------------------------------------------
    # Context Manager Support
    # -------------------------------------------------------------------------

    async def __aenter__(self) -> "DTRClient":
        """Enter async context."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context and close client."""
        await self.close()
