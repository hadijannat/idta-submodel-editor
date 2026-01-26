"""
Eclipse BaSyx registry client.

Provides HTTP client for interacting with Eclipse BaSyx AAS Registry
for local/on-premise deployments.

Supports BaSyx AAS Server REST API v2 with:
- Shell Descriptor management
- Submodel Descriptor management
- Lookup operations
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class BaSyxClientError(Exception):
    """Base exception for BaSyx client errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class BaSyxNotFoundError(BaSyxClientError):
    """Resource not found in BaSyx registry."""

    pass


class BaSyxConflictError(BaSyxClientError):
    """Resource already exists in BaSyx registry."""

    pass


class BaSyxClient:
    """
    Client for Eclipse BaSyx AAS Registry.

    BaSyx provides an open-source implementation of the AAS infrastructure.
    This client supports both the standalone registry and the integrated
    AAS Server registry endpoints.

    API Reference: https://app.swaggerhub.com/apis/Plattform_i40/AssetAdministrationShell-Registry
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
    ) -> None:
        """
        Initialize the BaSyx client.

        Args:
            base_url: BaSyx registry base URL
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=self.timeout,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @staticmethod
    def encode_id(identifier: str) -> str:
        """
        Encode an identifier for URL path.

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
            BaSyxNotFoundError: If resource not found (404)
            BaSyxConflictError: If resource already exists (409)
            BaSyxClientError: For other HTTP errors
        """
        if response.status_code == 404:
            raise BaSyxNotFoundError(
                f"{operation}: Resource not found",
                status_code=404,
                response_body=response.text,
            )

        if response.status_code == 409:
            raise BaSyxConflictError(
                f"{operation}: Resource already exists",
                status_code=409,
                response_body=response.text,
            )

        if response.status_code >= 400:
            raise BaSyxClientError(
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
    # AAS Shell Operations
    # -------------------------------------------------------------------------

    async def register_aas(self, shell_descriptor: dict[str, Any]) -> dict[str, Any]:
        """
        Register an AAS Shell in the BaSyx registry.

        Args:
            shell_descriptor: Shell Descriptor following AAS API spec

        Returns:
            Registered Shell Descriptor

        Raises:
            BaSyxConflictError: If shell already exists
            BaSyxClientError: For other errors
        """
        aas_id = shell_descriptor.get("id", "unknown")
        logger.info("Registering AAS Shell %s in BaSyx", aas_id)

        client = await self._get_client()
        response = await client.post(
            "/shell-descriptors",
            json=shell_descriptor,
        )

        result = await self._handle_response(response, "Register AAS")
        return result or shell_descriptor

    async def get_aas(self, aas_id: str) -> dict[str, Any] | None:
        """
        Get an AAS Shell Descriptor from BaSyx.

        Args:
            aas_id: AAS identifier

        Returns:
            Shell Descriptor or None if not found
        """
        encoded_id = self.encode_id(aas_id)
        logger.debug("Getting AAS %s from BaSyx", aas_id)

        client = await self._get_client()
        try:
            response = await client.get(f"/shell-descriptors/{encoded_id}")
            return await self._handle_response(response, "Get AAS")
        except BaSyxNotFoundError:
            return None

    async def update_aas(
        self,
        aas_id: str,
        shell_descriptor: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Update an AAS Shell Descriptor in BaSyx.

        Args:
            aas_id: AAS identifier
            shell_descriptor: Updated Shell Descriptor

        Returns:
            Updated Shell Descriptor

        Raises:
            BaSyxNotFoundError: If shell doesn't exist
            BaSyxClientError: For other errors
        """
        encoded_id = self.encode_id(aas_id)
        logger.info("Updating AAS %s in BaSyx", aas_id)

        client = await self._get_client()
        response = await client.put(
            f"/shell-descriptors/{encoded_id}",
            json=shell_descriptor,
        )

        result = await self._handle_response(response, "Update AAS")
        return result or shell_descriptor

    async def delete_aas(self, aas_id: str) -> bool:
        """
        Delete an AAS from BaSyx registry.

        Args:
            aas_id: AAS identifier

        Returns:
            True if deleted

        Raises:
            BaSyxNotFoundError: If shell doesn't exist
            BaSyxClientError: For other errors
        """
        encoded_id = self.encode_id(aas_id)
        logger.info("Deleting AAS %s from BaSyx", aas_id)

        client = await self._get_client()
        response = await client.delete(f"/shell-descriptors/{encoded_id}")
        await self._handle_response(response, "Delete AAS")
        return True

    async def get_all_aas(
        self,
        limit: int = 100,
        cursor: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        Get all AAS Shell Descriptors from BaSyx.

        Args:
            limit: Maximum results
            cursor: Pagination cursor

        Returns:
            Tuple of (descriptors, next_cursor)
        """
        logger.debug("Getting all AAS from BaSyx")

        client = await self._get_client()
        params: dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor

        response = await client.get("/shell-descriptors", params=params)
        result = await self._handle_response(response, "Get all AAS")

        if result is None:
            return [], None

        # BaSyx returns paginated results in a standard format
        descriptors = result.get("result", [])
        paging_metadata = result.get("paging_metadata", {})
        next_cursor = paging_metadata.get("cursor")

        return descriptors, next_cursor

    # -------------------------------------------------------------------------
    # Submodel Operations
    # -------------------------------------------------------------------------

    async def register_submodel(
        self,
        aas_id: str,
        submodel_descriptor: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Register a Submodel in BaSyx.

        Args:
            aas_id: Parent AAS identifier
            submodel_descriptor: Submodel Descriptor

        Returns:
            Registered Submodel Descriptor

        Raises:
            BaSyxNotFoundError: If parent AAS doesn't exist
            BaSyxConflictError: If submodel already exists
            BaSyxClientError: For other errors
        """
        encoded_id = self.encode_id(aas_id)
        submodel_id = submodel_descriptor.get("id", "unknown")
        logger.info(
            "Registering Submodel %s for AAS %s in BaSyx",
            submodel_id,
            aas_id,
        )

        client = await self._get_client()
        response = await client.post(
            f"/shell-descriptors/{encoded_id}/submodel-descriptors",
            json=submodel_descriptor,
        )

        result = await self._handle_response(response, "Register Submodel")
        return result or submodel_descriptor

    async def get_submodel(
        self,
        aas_id: str,
        submodel_id: str,
    ) -> dict[str, Any] | None:
        """
        Get a Submodel Descriptor from BaSyx.

        Args:
            aas_id: Parent AAS identifier
            submodel_id: Submodel identifier

        Returns:
            Submodel Descriptor or None if not found
        """
        encoded_aas = self.encode_id(aas_id)
        encoded_submodel = self.encode_id(submodel_id)
        logger.debug("Getting Submodel %s from BaSyx", submodel_id)

        client = await self._get_client()
        try:
            response = await client.get(
                f"/shell-descriptors/{encoded_aas}/submodel-descriptors/{encoded_submodel}"
            )
            return await self._handle_response(response, "Get Submodel")
        except BaSyxNotFoundError:
            return None

    async def update_submodel(
        self,
        aas_id: str,
        submodel_id: str,
        submodel_descriptor: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Update a Submodel Descriptor in BaSyx.

        Args:
            aas_id: Parent AAS identifier
            submodel_id: Submodel identifier
            submodel_descriptor: Updated Submodel Descriptor

        Returns:
            Updated Submodel Descriptor

        Raises:
            BaSyxNotFoundError: If submodel doesn't exist
            BaSyxClientError: For other errors
        """
        encoded_aas = self.encode_id(aas_id)
        encoded_submodel = self.encode_id(submodel_id)
        logger.info("Updating Submodel %s in BaSyx", submodel_id)

        client = await self._get_client()
        response = await client.put(
            f"/shell-descriptors/{encoded_aas}/submodel-descriptors/{encoded_submodel}",
            json=submodel_descriptor,
        )

        result = await self._handle_response(response, "Update Submodel")
        return result or submodel_descriptor

    async def delete_submodel(
        self,
        aas_id: str,
        submodel_id: str,
    ) -> bool:
        """
        Delete a Submodel from BaSyx.

        Args:
            aas_id: Parent AAS identifier
            submodel_id: Submodel identifier

        Returns:
            True if deleted

        Raises:
            BaSyxNotFoundError: If submodel doesn't exist
            BaSyxClientError: For other errors
        """
        encoded_aas = self.encode_id(aas_id)
        encoded_submodel = self.encode_id(submodel_id)
        logger.info("Deleting Submodel %s from BaSyx", submodel_id)

        client = await self._get_client()
        response = await client.delete(
            f"/shell-descriptors/{encoded_aas}/submodel-descriptors/{encoded_submodel}"
        )
        await self._handle_response(response, "Delete Submodel")
        return True

    async def get_all_submodels(
        self,
        aas_id: str,
        limit: int = 100,
        cursor: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        Get all Submodel Descriptors for an AAS.

        Args:
            aas_id: Parent AAS identifier
            limit: Maximum results
            cursor: Pagination cursor

        Returns:
            Tuple of (descriptors, next_cursor)
        """
        encoded_id = self.encode_id(aas_id)
        logger.debug("Getting all Submodels for AAS %s from BaSyx", aas_id)

        client = await self._get_client()
        params: dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor

        try:
            response = await client.get(
                f"/shell-descriptors/{encoded_id}/submodel-descriptors",
                params=params,
            )
            result = await self._handle_response(response, "Get all Submodels")

            if result is None:
                return [], None

            descriptors = result.get("result", [])
            paging_metadata = result.get("paging_metadata", {})
            next_cursor = paging_metadata.get("cursor")

            return descriptors, next_cursor
        except BaSyxNotFoundError:
            return [], None

    # -------------------------------------------------------------------------
    # Lookup Operations
    # -------------------------------------------------------------------------

    async def lookup_by_asset_id(
        self,
        asset_id_name: str,
        asset_id_value: str,
    ) -> list[str]:
        """
        Lookup AAS IDs by specific asset ID.

        Args:
            asset_id_name: Asset ID key name
            asset_id_value: Asset ID value

        Returns:
            List of matching AAS IDs
        """
        logger.debug(
            "Looking up AAS by asset ID %s=%s",
            asset_id_name,
            asset_id_value,
        )

        client = await self._get_client()

        # BaSyx uses base64-encoded asset IDs in query params
        asset_id_obj = [{"name": asset_id_name, "value": asset_id_value}]
        asset_ids_encoded = base64.urlsafe_b64encode(
            json.dumps(asset_id_obj).encode()
        ).decode()

        response = await client.get(
            "/lookup/shells",
            params={"assetIds": asset_ids_encoded},
        )

        result = await self._handle_response(response, "Lookup by asset ID")

        if result is None:
            return []

        # Result contains list of AAS IDs
        return result.get("result", [])

    async def lookup_by_semantic_id(
        self,
        semantic_id: str,
    ) -> list[str]:
        """
        Lookup Submodel IDs by semantic ID.

        Args:
            semantic_id: Semantic ID to search for

        Returns:
            List of matching Submodel IDs
        """
        logger.debug("Looking up submodels by semantic ID %s", semantic_id)

        client = await self._get_client()

        # Semantic ID needs to be base64-encoded
        semantic_ref = {
            "type": "ExternalReference",
            "keys": [{"type": "GlobalReference", "value": semantic_id}],
        }
        semantic_id_encoded = base64.urlsafe_b64encode(
            json.dumps(semantic_ref).encode()
        ).decode()

        response = await client.get(
            "/lookup/submodels",
            params={"semanticId": semantic_id_encoded},
        )

        result = await self._handle_response(response, "Lookup by semantic ID")

        if result is None:
            return []

        return result.get("result", [])

    # -------------------------------------------------------------------------
    # BaSyx-specific Operations
    # -------------------------------------------------------------------------

    async def get_server_info(self) -> dict[str, Any]:
        """
        Get BaSyx server information.

        Returns:
            Server info including version and configuration
        """
        client = await self._get_client()

        try:
            # BaSyx servers typically expose a description endpoint
            response = await client.get("/description")
            result = await self._handle_response(response, "Get server info")
            return result or {"server": "BaSyx", "version": "unknown"}
        except (BaSyxClientError, httpx.HTTPError):
            return {
                "server": "BaSyx",
                "version": "unknown",
                "error": "Could not retrieve server info",
            }

    async def health_check(self) -> bool:
        """
        Check BaSyx registry health.

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

    # -------------------------------------------------------------------------
    # Context Manager Support
    # -------------------------------------------------------------------------

    async def __aenter__(self) -> "BaSyxClient":
        """Enter async context."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context and close client."""
        await self.close()
