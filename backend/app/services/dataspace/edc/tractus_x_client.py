"""
Tractus-X EDC Management API client.

Provides HTTP client for interacting with Tractus-X EDC Management APIs
for asset management, policy definitions, and contract negotiations.

API Reference: Tractus-X EDC Management API v3
https://github.com/eclipse-tractusx/tractusx-edc
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class EDCClientError(Exception):
    """Base exception for EDC client errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class EDCAssetNotFoundError(EDCClientError):
    """Asset not found in EDC."""

    pass


class EDCAssetConflictError(EDCClientError):
    """Asset already exists in EDC."""

    pass


class EDCPolicyNotFoundError(EDCClientError):
    """Policy definition not found in EDC."""

    pass


class EDCContractNotFoundError(EDCClientError):
    """Contract definition or agreement not found in EDC."""

    pass


class EDCNegotiationError(EDCClientError):
    """Contract negotiation failed."""

    pass


class EDCAuthenticationError(EDCClientError):
    """Authentication or authorization failed."""

    pass


class EDCConnectionError(EDCClientError):
    """Connection to EDC failed."""

    pass


# ---------------------------------------------------------------------------
# EDC JSON-LD Context
# ---------------------------------------------------------------------------

EDC_CONTEXT = {
    "@vocab": "https://w3id.org/edc/v0.0.1/ns/",
    "edc": "https://w3id.org/edc/v0.0.1/ns/",
    "odrl": "http://www.w3.org/ns/odrl/2/",
    "dcat": "http://www.w3.org/ns/dcat#",
    "dct": "http://purl.org/dc/terms/",
    "dspace": "https://w3id.org/dspace/v0.8/",
    "cx-policy": "https://w3id.org/catenax/policy/",
}


# ---------------------------------------------------------------------------
# Client Implementation
# ---------------------------------------------------------------------------


class TractusXClient:
    """
    Client for Tractus-X EDC Management API.

    Implements the EDC Management API v3 for:
    - Asset management
    - Policy definition management
    - Contract definition management
    - Contract negotiation
    - Transfer process management
    - Catalog queries

    The client uses lazy-loaded HTTP connections and supports both
    API key authentication and OAuth2 bearer tokens.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        auth_token: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        """
        Initialize the Tractus-X EDC client.

        Args:
            base_url: EDC Management API base URL
            api_key: Optional API key for X-Api-Key authentication
            auth_token: Optional OAuth2 bearer token
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.auth_token = auth_token
        self.timeout = timeout

        # Lazy-loaded HTTP client
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None:
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            if self.api_key:
                headers["X-Api-Key"] = self.api_key
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
        Update the OAuth2 bearer token.

        Args:
            token: New bearer token
        """
        self.auth_token = token
        # Reset client to use new token
        if self._client is not None:
            # Client will be recreated with new token on next request
            self._client = None

    async def _handle_response(
        self,
        response: httpx.Response,
        operation: str,
        resource_type: str = "resource",
    ) -> dict[str, Any] | None:
        """
        Handle HTTP response and raise appropriate exceptions.

        Args:
            response: HTTP response
            operation: Operation name for logging
            resource_type: Type of resource (asset, policy, contract, etc.)

        Returns:
            Parsed JSON response or None

        Raises:
            EDCAssetNotFoundError: If asset not found (404)
            EDCPolicyNotFoundError: If policy not found (404)
            EDCContractNotFoundError: If contract not found (404)
            EDCAssetConflictError: If resource already exists (409)
            EDCAuthenticationError: If authentication fails (401, 403)
            EDCClientError: For other HTTP errors
        """
        if response.status_code == 401 or response.status_code == 403:
            raise EDCAuthenticationError(
                f"{operation}: Authentication failed",
                status_code=response.status_code,
                response_body=response.text,
            )

        if response.status_code == 404:
            if resource_type == "asset":
                raise EDCAssetNotFoundError(
                    f"{operation}: Asset not found",
                    status_code=404,
                    response_body=response.text,
                )
            elif resource_type == "policy":
                raise EDCPolicyNotFoundError(
                    f"{operation}: Policy not found",
                    status_code=404,
                    response_body=response.text,
                )
            elif resource_type in ("contract", "agreement", "negotiation"):
                raise EDCContractNotFoundError(
                    f"{operation}: Contract not found",
                    status_code=404,
                    response_body=response.text,
                )
            else:
                raise EDCClientError(
                    f"{operation}: Resource not found",
                    status_code=404,
                    response_body=response.text,
                )

        if response.status_code == 409:
            raise EDCAssetConflictError(
                f"{operation}: Resource already exists",
                status_code=409,
                response_body=response.text,
            )

        if response.status_code >= 400:
            raise EDCClientError(
                f"{operation} failed: {response.status_code}",
                status_code=response.status_code,
                response_body=response.text,
            )

        # Handle empty responses (DELETE, etc.)
        if response.status_code == 204 or not response.content:
            return None

        try:
            return response.json()
        except ValueError:
            return None

    def _build_context(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Add JSON-LD context to request payload.

        Args:
            data: Request payload

        Returns:
            Payload with context
        """
        if "@context" not in data:
            data = {"@context": EDC_CONTEXT, **data}
        return data

    # -------------------------------------------------------------------------
    # Asset Management
    # -------------------------------------------------------------------------

    async def create_asset(self, asset: dict[str, Any]) -> dict[str, Any]:
        """
        Create a new asset in the EDC.

        Args:
            asset: Asset definition following EDC Asset schema
                Required fields:
                - @id: Unique asset identifier
                - properties: Asset properties (name, description, etc.)
                - dataAddress: Data address specification

        Returns:
            Created asset with ID

        Raises:
            EDCAssetConflictError: If asset already exists
            EDCClientError: For other errors
        """
        asset_id = asset.get("@id", asset.get("id", "unknown"))
        logger.info("Creating EDC asset: %s", asset_id)

        client = await self._get_client()
        payload = self._build_context(asset)

        try:
            response = await client.post(
                "/management/v3/assets",
                json=payload,
            )
            result = await self._handle_response(
                response, "Create asset", resource_type="asset"
            )
            logger.info("Successfully created EDC asset: %s", asset_id)
            return result or asset
        except httpx.HTTPError as e:
            logger.error("Failed to create EDC asset: %s", str(e))
            raise EDCConnectionError(
                f"Connection error creating asset: {e}",
                status_code=None,
                response_body=None,
            )

    async def get_asset(self, asset_id: str) -> dict[str, Any] | None:
        """
        Get an asset by ID.

        Args:
            asset_id: Asset identifier

        Returns:
            Asset definition or None if not found
        """
        logger.debug("Getting EDC asset: %s", asset_id)

        client = await self._get_client()
        try:
            response = await client.get(f"/management/v3/assets/{asset_id}")
            return await self._handle_response(
                response, "Get asset", resource_type="asset"
            )
        except EDCAssetNotFoundError:
            return None
        except httpx.HTTPError as e:
            logger.error("Failed to get EDC asset: %s", str(e))
            raise EDCConnectionError(
                f"Connection error getting asset: {e}",
                status_code=None,
                response_body=None,
            )

    async def delete_asset(self, asset_id: str) -> bool:
        """
        Delete an asset.

        Args:
            asset_id: Asset to delete

        Returns:
            True if deleted successfully

        Raises:
            EDCAssetNotFoundError: If asset doesn't exist
            EDCClientError: For other errors
        """
        logger.info("Deleting EDC asset: %s", asset_id)

        client = await self._get_client()
        try:
            response = await client.delete(f"/management/v3/assets/{asset_id}")
            await self._handle_response(
                response, "Delete asset", resource_type="asset"
            )
            logger.info("Successfully deleted EDC asset: %s", asset_id)
            return True
        except httpx.HTTPError as e:
            logger.error("Failed to delete EDC asset: %s", str(e))
            raise EDCConnectionError(
                f"Connection error deleting asset: {e}",
                status_code=None,
                response_body=None,
            )

    async def query_assets(
        self,
        filter_expression: dict[str, Any] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Query assets with optional filter.

        Args:
            filter_expression: EDC criterion filter expression
            limit: Maximum results
            offset: Results offset

        Returns:
            List of matching assets
        """
        logger.debug("Querying EDC assets with limit=%d, offset=%d", limit, offset)

        client = await self._get_client()

        # Build query specification
        query_spec: dict[str, Any] = {
            "@context": EDC_CONTEXT,
            "offset": offset,
            "limit": limit,
        }

        if filter_expression:
            query_spec["filterExpression"] = filter_expression

        try:
            response = await client.post(
                "/management/v3/assets/request",
                json=query_spec,
            )
            result = await self._handle_response(response, "Query assets")

            if result is None:
                return []

            # EDC returns assets in a list
            return result if isinstance(result, list) else []
        except httpx.HTTPError as e:
            logger.error("Failed to query EDC assets: %s", str(e))
            raise EDCConnectionError(
                f"Connection error querying assets: {e}",
                status_code=None,
                response_body=None,
            )

    async def update_asset(
        self, asset_id: str, asset: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Update an existing asset.

        Args:
            asset_id: Asset identifier
            asset: Updated asset definition

        Returns:
            Updated asset

        Raises:
            EDCAssetNotFoundError: If asset doesn't exist
            EDCClientError: For other errors
        """
        logger.info("Updating EDC asset: %s", asset_id)

        client = await self._get_client()
        payload = self._build_context(asset)

        try:
            response = await client.put(
                f"/management/v3/assets/{asset_id}",
                json=payload,
            )
            result = await self._handle_response(
                response, "Update asset", resource_type="asset"
            )
            logger.info("Successfully updated EDC asset: %s", asset_id)
            return result or asset
        except httpx.HTTPError as e:
            logger.error("Failed to update EDC asset: %s", str(e))
            raise EDCConnectionError(
                f"Connection error updating asset: {e}",
                status_code=None,
                response_body=None,
            )

    # -------------------------------------------------------------------------
    # Policy Definition Management
    # -------------------------------------------------------------------------

    async def create_policy(self, policy: dict[str, Any]) -> dict[str, Any]:
        """
        Create a policy definition.

        Args:
            policy: ODRL policy definition
                Required fields:
                - @id: Unique policy identifier
                - policy: ODRL policy object with permissions/prohibitions

        Returns:
            Created policy with ID

        Raises:
            EDCAssetConflictError: If policy already exists
            EDCClientError: For other errors
        """
        policy_id = policy.get("@id", policy.get("id", "unknown"))
        logger.info("Creating EDC policy definition: %s", policy_id)

        client = await self._get_client()
        payload = self._build_context(policy)

        try:
            response = await client.post(
                "/management/v3/policydefinitions",
                json=payload,
            )
            result = await self._handle_response(
                response, "Create policy", resource_type="policy"
            )
            logger.info("Successfully created EDC policy: %s", policy_id)
            return result or policy
        except httpx.HTTPError as e:
            logger.error("Failed to create EDC policy: %s", str(e))
            raise EDCConnectionError(
                f"Connection error creating policy: {e}",
                status_code=None,
                response_body=None,
            )

    async def get_policy(self, policy_id: str) -> dict[str, Any] | None:
        """
        Get a policy definition by ID.

        Args:
            policy_id: Policy identifier

        Returns:
            Policy definition or None if not found
        """
        logger.debug("Getting EDC policy definition: %s", policy_id)

        client = await self._get_client()
        try:
            response = await client.get(
                f"/management/v3/policydefinitions/{policy_id}"
            )
            return await self._handle_response(
                response, "Get policy", resource_type="policy"
            )
        except EDCPolicyNotFoundError:
            return None
        except httpx.HTTPError as e:
            logger.error("Failed to get EDC policy: %s", str(e))
            raise EDCConnectionError(
                f"Connection error getting policy: {e}",
                status_code=None,
                response_body=None,
            )

    async def delete_policy(self, policy_id: str) -> bool:
        """
        Delete a policy definition.

        Args:
            policy_id: Policy to delete

        Returns:
            True if deleted

        Raises:
            EDCPolicyNotFoundError: If policy doesn't exist
            EDCClientError: For other errors
        """
        logger.info("Deleting EDC policy definition: %s", policy_id)

        client = await self._get_client()
        try:
            response = await client.delete(
                f"/management/v3/policydefinitions/{policy_id}"
            )
            await self._handle_response(
                response, "Delete policy", resource_type="policy"
            )
            logger.info("Successfully deleted EDC policy: %s", policy_id)
            return True
        except httpx.HTTPError as e:
            logger.error("Failed to delete EDC policy: %s", str(e))
            raise EDCConnectionError(
                f"Connection error deleting policy: {e}",
                status_code=None,
                response_body=None,
            )

    async def query_policies(
        self,
        filter_expression: dict[str, Any] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Query policy definitions with optional filter.

        Args:
            filter_expression: EDC criterion filter expression
            limit: Maximum results
            offset: Results offset

        Returns:
            List of matching policy definitions
        """
        logger.debug("Querying EDC policies with limit=%d, offset=%d", limit, offset)

        client = await self._get_client()

        query_spec: dict[str, Any] = {
            "@context": EDC_CONTEXT,
            "offset": offset,
            "limit": limit,
        }

        if filter_expression:
            query_spec["filterExpression"] = filter_expression

        try:
            response = await client.post(
                "/management/v3/policydefinitions/request",
                json=query_spec,
            )
            result = await self._handle_response(response, "Query policies")

            if result is None:
                return []

            return result if isinstance(result, list) else []
        except httpx.HTTPError as e:
            logger.error("Failed to query EDC policies: %s", str(e))
            raise EDCConnectionError(
                f"Connection error querying policies: {e}",
                status_code=None,
                response_body=None,
            )

    # -------------------------------------------------------------------------
    # Contract Definition Management
    # -------------------------------------------------------------------------

    async def create_contract_definition(
        self,
        definition: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Create a contract definition.

        Contract definitions link assets to policies for catalog exposure.

        Args:
            definition: Contract definition
                Required fields:
                - @id: Unique contract definition ID
                - accessPolicyId: Policy for access control
                - contractPolicyId: Policy for contract terms
                - assetsSelector: Criterion to select assets

        Returns:
            Created contract definition with ID

        Raises:
            EDCAssetConflictError: If definition already exists
            EDCClientError: For other errors
        """
        definition_id = definition.get("@id", definition.get("id", "unknown"))
        logger.info("Creating EDC contract definition: %s", definition_id)

        client = await self._get_client()
        payload = self._build_context(definition)

        try:
            response = await client.post(
                "/management/v3/contractdefinitions",
                json=payload,
            )
            result = await self._handle_response(
                response, "Create contract definition", resource_type="contract"
            )
            logger.info("Successfully created EDC contract definition: %s", definition_id)
            return result or definition
        except httpx.HTTPError as e:
            logger.error("Failed to create EDC contract definition: %s", str(e))
            raise EDCConnectionError(
                f"Connection error creating contract definition: {e}",
                status_code=None,
                response_body=None,
            )

    async def get_contract_definition(
        self, definition_id: str
    ) -> dict[str, Any] | None:
        """
        Get a contract definition by ID.

        Args:
            definition_id: Contract definition identifier

        Returns:
            Contract definition or None if not found
        """
        logger.debug("Getting EDC contract definition: %s", definition_id)

        client = await self._get_client()
        try:
            response = await client.get(
                f"/management/v3/contractdefinitions/{definition_id}"
            )
            return await self._handle_response(
                response, "Get contract definition", resource_type="contract"
            )
        except EDCContractNotFoundError:
            return None
        except httpx.HTTPError as e:
            logger.error("Failed to get EDC contract definition: %s", str(e))
            raise EDCConnectionError(
                f"Connection error getting contract definition: {e}",
                status_code=None,
                response_body=None,
            )

    async def delete_contract_definition(self, definition_id: str) -> bool:
        """
        Delete a contract definition.

        Args:
            definition_id: Contract definition to delete

        Returns:
            True if deleted

        Raises:
            EDCContractNotFoundError: If definition doesn't exist
            EDCClientError: For other errors
        """
        logger.info("Deleting EDC contract definition: %s", definition_id)

        client = await self._get_client()
        try:
            response = await client.delete(
                f"/management/v3/contractdefinitions/{definition_id}"
            )
            await self._handle_response(
                response, "Delete contract definition", resource_type="contract"
            )
            logger.info("Successfully deleted EDC contract definition: %s", definition_id)
            return True
        except httpx.HTTPError as e:
            logger.error("Failed to delete EDC contract definition: %s", str(e))
            raise EDCConnectionError(
                f"Connection error deleting contract definition: {e}",
                status_code=None,
                response_body=None,
            )

    async def query_contract_definitions(
        self,
        filter_expression: dict[str, Any] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Query contract definitions with optional filter.

        Args:
            filter_expression: EDC criterion filter expression
            limit: Maximum results
            offset: Results offset

        Returns:
            List of matching contract definitions
        """
        logger.debug(
            "Querying EDC contract definitions with limit=%d, offset=%d",
            limit,
            offset,
        )

        client = await self._get_client()

        query_spec: dict[str, Any] = {
            "@context": EDC_CONTEXT,
            "offset": offset,
            "limit": limit,
        }

        if filter_expression:
            query_spec["filterExpression"] = filter_expression

        try:
            response = await client.post(
                "/management/v3/contractdefinitions/request",
                json=query_spec,
            )
            result = await self._handle_response(response, "Query contract definitions")

            if result is None:
                return []

            return result if isinstance(result, list) else []
        except httpx.HTTPError as e:
            logger.error("Failed to query EDC contract definitions: %s", str(e))
            raise EDCConnectionError(
                f"Connection error querying contract definitions: {e}",
                status_code=None,
                response_body=None,
            )

    # -------------------------------------------------------------------------
    # Contract Negotiation
    # -------------------------------------------------------------------------

    async def initiate_negotiation(
        self,
        counter_party_address: str,
        protocol: str,
        offer: dict[str, Any],
        counter_party_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Initiate a contract negotiation.

        Args:
            counter_party_address: Provider's protocol address
            protocol: Protocol type (e.g., "dataspace-protocol-http")
            offer: Contract offer to negotiate
                Required fields in offer:
                - offerId: Offer ID from catalog
                - assetId: Asset being negotiated
                - policy: Policy terms
            counter_party_id: Optional provider BPN

        Returns:
            Negotiation state including @id

        Raises:
            EDCNegotiationError: If negotiation initiation fails
            EDCClientError: For other errors
        """
        logger.info(
            "Initiating EDC contract negotiation with %s",
            counter_party_address,
        )

        client = await self._get_client()

        negotiation_request = {
            "@context": EDC_CONTEXT,
            "@type": "ContractRequest",
            "counterPartyAddress": counter_party_address,
            "protocol": protocol,
            "policy": offer.get("policy", offer),
        }

        if counter_party_id:
            negotiation_request["counterPartyId"] = counter_party_id

        # Add offer ID if provided
        if "offerId" in offer:
            negotiation_request["policy"]["@id"] = offer["offerId"]

        try:
            response = await client.post(
                "/management/v3/contractnegotiations",
                json=negotiation_request,
            )
            result = await self._handle_response(
                response, "Initiate negotiation", resource_type="negotiation"
            )

            if result is None:
                raise EDCNegotiationError(
                    "Negotiation initiation returned no result",
                    status_code=response.status_code,
                    response_body=response.text,
                )

            logger.info(
                "Successfully initiated EDC negotiation: %s",
                result.get("@id", "unknown"),
            )
            return result
        except httpx.HTTPError as e:
            logger.error("Failed to initiate EDC negotiation: %s", str(e))
            raise EDCConnectionError(
                f"Connection error initiating negotiation: {e}",
                status_code=None,
                response_body=None,
            )

    async def get_negotiation(self, negotiation_id: str) -> dict[str, Any] | None:
        """
        Get negotiation state.

        Args:
            negotiation_id: Negotiation identifier

        Returns:
            Current negotiation state including:
            - @id: Negotiation ID
            - state: Current state (INITIAL, REQUESTING, AGREED, etc.)
            - counterPartyAddress: Provider address
            - contractAgreementId: Agreement ID if finalized
        """
        logger.debug("Getting EDC negotiation state: %s", negotiation_id)

        client = await self._get_client()
        try:
            response = await client.get(
                f"/management/v3/contractnegotiations/{negotiation_id}"
            )
            return await self._handle_response(
                response, "Get negotiation", resource_type="negotiation"
            )
        except EDCContractNotFoundError:
            return None
        except httpx.HTTPError as e:
            logger.error("Failed to get EDC negotiation: %s", str(e))
            raise EDCConnectionError(
                f"Connection error getting negotiation: {e}",
                status_code=None,
                response_body=None,
            )

    async def get_negotiation_state(self, negotiation_id: str) -> str | None:
        """
        Get just the negotiation state string.

        Args:
            negotiation_id: Negotiation identifier

        Returns:
            State string (INITIAL, REQUESTING, AGREED, FINALIZED, etc.)
            or None if not found
        """
        negotiation = await self.get_negotiation(negotiation_id)
        if negotiation:
            return negotiation.get("state") or negotiation.get("edc:state")
        return None

    async def terminate_negotiation(
        self,
        negotiation_id: str,
        reason: str = "Terminated by user",
    ) -> bool:
        """
        Terminate an ongoing negotiation.

        Args:
            negotiation_id: Negotiation to terminate
            reason: Termination reason

        Returns:
            True if terminated
        """
        logger.info("Terminating EDC negotiation: %s", negotiation_id)

        client = await self._get_client()

        termination_request = {
            "@context": EDC_CONTEXT,
            "@type": "TerminateNegotiation",
            "reason": reason,
        }

        try:
            response = await client.post(
                f"/management/v3/contractnegotiations/{negotiation_id}/terminate",
                json=termination_request,
            )
            await self._handle_response(
                response, "Terminate negotiation", resource_type="negotiation"
            )
            logger.info("Successfully terminated EDC negotiation: %s", negotiation_id)
            return True
        except httpx.HTTPError as e:
            logger.error("Failed to terminate EDC negotiation: %s", str(e))
            raise EDCConnectionError(
                f"Connection error terminating negotiation: {e}",
                status_code=None,
                response_body=None,
            )

    async def query_negotiations(
        self,
        filter_expression: dict[str, Any] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Query contract negotiations.

        Args:
            filter_expression: EDC criterion filter expression
            limit: Maximum results
            offset: Results offset

        Returns:
            List of negotiations
        """
        logger.debug(
            "Querying EDC negotiations with limit=%d, offset=%d",
            limit,
            offset,
        )

        client = await self._get_client()

        query_spec: dict[str, Any] = {
            "@context": EDC_CONTEXT,
            "offset": offset,
            "limit": limit,
        }

        if filter_expression:
            query_spec["filterExpression"] = filter_expression

        try:
            response = await client.post(
                "/management/v3/contractnegotiations/request",
                json=query_spec,
            )
            result = await self._handle_response(response, "Query negotiations")

            if result is None:
                return []

            return result if isinstance(result, list) else []
        except httpx.HTTPError as e:
            logger.error("Failed to query EDC negotiations: %s", str(e))
            raise EDCConnectionError(
                f"Connection error querying negotiations: {e}",
                status_code=None,
                response_body=None,
            )

    # -------------------------------------------------------------------------
    # Contract Agreements
    # -------------------------------------------------------------------------

    async def get_agreement(self, agreement_id: str) -> dict[str, Any] | None:
        """
        Get a contract agreement by ID.

        Args:
            agreement_id: Agreement identifier

        Returns:
            Contract agreement or None if not found
        """
        logger.debug("Getting EDC contract agreement: %s", agreement_id)

        client = await self._get_client()
        try:
            response = await client.get(
                f"/management/v3/contractagreements/{agreement_id}"
            )
            return await self._handle_response(
                response, "Get agreement", resource_type="agreement"
            )
        except EDCContractNotFoundError:
            return None
        except httpx.HTTPError as e:
            logger.error("Failed to get EDC agreement: %s", str(e))
            raise EDCConnectionError(
                f"Connection error getting agreement: {e}",
                status_code=None,
                response_body=None,
            )

    async def query_agreements(
        self,
        filter_expression: dict[str, Any] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Query contract agreements.

        Args:
            filter_expression: EDC criterion filter expression
            limit: Maximum results
            offset: Results offset

        Returns:
            List of contract agreements
        """
        logger.debug(
            "Querying EDC agreements with limit=%d, offset=%d",
            limit,
            offset,
        )

        client = await self._get_client()

        query_spec: dict[str, Any] = {
            "@context": EDC_CONTEXT,
            "offset": offset,
            "limit": limit,
        }

        if filter_expression:
            query_spec["filterExpression"] = filter_expression

        try:
            response = await client.post(
                "/management/v3/contractagreements/request",
                json=query_spec,
            )
            result = await self._handle_response(response, "Query agreements")

            if result is None:
                return []

            return result if isinstance(result, list) else []
        except httpx.HTTPError as e:
            logger.error("Failed to query EDC agreements: %s", str(e))
            raise EDCConnectionError(
                f"Connection error querying agreements: {e}",
                status_code=None,
                response_body=None,
            )

    # -------------------------------------------------------------------------
    # Catalog
    # -------------------------------------------------------------------------

    async def request_catalog(
        self,
        counter_party_address: str,
        protocol: str = "dataspace-protocol-http",
        query_spec: dict[str, Any] | None = None,
        counter_party_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Request catalog from a provider.

        Args:
            counter_party_address: Provider's protocol address
            protocol: Protocol type
            query_spec: Optional query specification with filters
            counter_party_id: Optional provider BPN

        Returns:
            Catalog response containing DCAT datasets
        """
        logger.info("Requesting EDC catalog from %s", counter_party_address)

        client = await self._get_client()

        catalog_request = {
            "@context": EDC_CONTEXT,
            "@type": "CatalogRequest",
            "counterPartyAddress": counter_party_address,
            "protocol": protocol,
        }

        if counter_party_id:
            catalog_request["counterPartyId"] = counter_party_id

        if query_spec:
            catalog_request["querySpec"] = query_spec

        try:
            response = await client.post(
                "/management/v3/catalog/request",
                json=catalog_request,
            )
            result = await self._handle_response(response, "Request catalog")

            if result is None:
                return {
                    "@type": "dcat:Catalog",
                    "dcat:dataset": [],
                }

            logger.info(
                "Received EDC catalog with %d datasets",
                len(result.get("dcat:dataset", result.get("dataset", []))),
            )
            return result
        except httpx.HTTPError as e:
            logger.error("Failed to request EDC catalog: %s", str(e))
            raise EDCConnectionError(
                f"Connection error requesting catalog: {e}",
                status_code=None,
                response_body=None,
            )

    async def get_catalog_offers(
        self,
        counter_party_address: str,
        asset_id: str | None = None,
        protocol: str = "dataspace-protocol-http",
    ) -> list[dict[str, Any]]:
        """
        Get catalog offers, optionally filtered by asset ID.

        Args:
            counter_party_address: Provider's protocol address
            asset_id: Optional asset ID to filter offers
            protocol: Protocol type

        Returns:
            List of offers (DCAT datasets)
        """
        query_spec = None
        if asset_id:
            query_spec = {
                "filterExpression": [
                    {
                        "operandLeft": "https://w3id.org/edc/v0.0.1/ns/id",
                        "operator": "=",
                        "operandRight": asset_id,
                    }
                ]
            }

        catalog = await self.request_catalog(
            counter_party_address=counter_party_address,
            protocol=protocol,
            query_spec=query_spec,
        )

        # Extract datasets from catalog
        datasets = catalog.get("dcat:dataset", catalog.get("dataset", []))

        # Ensure it's a list
        if isinstance(datasets, dict):
            datasets = [datasets]

        return datasets

    # -------------------------------------------------------------------------
    # Transfer Process
    # -------------------------------------------------------------------------

    async def initiate_transfer(
        self,
        agreement_id: str,
        asset_id: str,
        counter_party_address: str,
        data_destination: dict[str, Any],
        protocol: str = "dataspace-protocol-http",
        transfer_type: str = "HttpData-PULL",
        private_properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Initiate a data transfer.

        Args:
            agreement_id: Contract agreement ID
            asset_id: Asset to transfer
            counter_party_address: Provider address
            data_destination: Destination data address
            protocol: Protocol type
            transfer_type: Transfer type (HttpData-PULL, HttpData-PUSH, etc.)
            private_properties: Optional private properties

        Returns:
            Transfer process state
        """
        logger.info(
            "Initiating EDC transfer for agreement %s, asset %s",
            agreement_id,
            asset_id,
        )

        client = await self._get_client()

        transfer_request = {
            "@context": EDC_CONTEXT,
            "@type": "TransferRequestDto",
            "connectorId": counter_party_address,
            "counterPartyAddress": counter_party_address,
            "contractId": agreement_id,
            "assetId": asset_id,
            "protocol": protocol,
            "transferType": transfer_type,
            "dataDestination": data_destination,
        }

        if private_properties:
            transfer_request["privateProperties"] = private_properties

        try:
            response = await client.post(
                "/management/v3/transferprocesses",
                json=transfer_request,
            )
            result = await self._handle_response(
                response, "Initiate transfer", resource_type="transfer"
            )

            if result is None:
                raise EDCClientError(
                    "Transfer initiation returned no result",
                    status_code=response.status_code,
                    response_body=response.text,
                )

            logger.info(
                "Successfully initiated EDC transfer: %s",
                result.get("@id", "unknown"),
            )
            return result
        except httpx.HTTPError as e:
            logger.error("Failed to initiate EDC transfer: %s", str(e))
            raise EDCConnectionError(
                f"Connection error initiating transfer: {e}",
                status_code=None,
                response_body=None,
            )

    async def get_transfer(self, transfer_id: str) -> dict[str, Any] | None:
        """
        Get transfer process state.

        Args:
            transfer_id: Transfer process identifier

        Returns:
            Current transfer state
        """
        logger.debug("Getting EDC transfer state: %s", transfer_id)

        client = await self._get_client()
        try:
            response = await client.get(
                f"/management/v3/transferprocesses/{transfer_id}"
            )
            return await self._handle_response(
                response, "Get transfer", resource_type="transfer"
            )
        except EDCClientError:
            return None
        except httpx.HTTPError as e:
            logger.error("Failed to get EDC transfer: %s", str(e))
            raise EDCConnectionError(
                f"Connection error getting transfer: {e}",
                status_code=None,
                response_body=None,
            )

    async def get_transfer_state(self, transfer_id: str) -> str | None:
        """
        Get just the transfer state string.

        Args:
            transfer_id: Transfer process identifier

        Returns:
            State string (INITIAL, PROVISIONING, STARTED, COMPLETED, etc.)
            or None if not found
        """
        transfer = await self.get_transfer(transfer_id)
        if transfer:
            return transfer.get("state") or transfer.get("edc:state")
        return None

    async def terminate_transfer(
        self,
        transfer_id: str,
        reason: str = "Terminated by user",
    ) -> bool:
        """
        Terminate an ongoing transfer.

        Args:
            transfer_id: Transfer to terminate
            reason: Termination reason

        Returns:
            True if terminated
        """
        logger.info("Terminating EDC transfer: %s", transfer_id)

        client = await self._get_client()

        termination_request = {
            "@context": EDC_CONTEXT,
            "@type": "TerminateTransfer",
            "reason": reason,
        }

        try:
            response = await client.post(
                f"/management/v3/transferprocesses/{transfer_id}/terminate",
                json=termination_request,
            )
            await self._handle_response(
                response, "Terminate transfer", resource_type="transfer"
            )
            logger.info("Successfully terminated EDC transfer: %s", transfer_id)
            return True
        except httpx.HTTPError as e:
            logger.error("Failed to terminate EDC transfer: %s", str(e))
            raise EDCConnectionError(
                f"Connection error terminating transfer: {e}",
                status_code=None,
                response_body=None,
            )

    async def query_transfers(
        self,
        filter_expression: dict[str, Any] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Query transfer processes.

        Args:
            filter_expression: EDC criterion filter expression
            limit: Maximum results
            offset: Results offset

        Returns:
            List of transfer processes
        """
        logger.debug(
            "Querying EDC transfers with limit=%d, offset=%d",
            limit,
            offset,
        )

        client = await self._get_client()

        query_spec: dict[str, Any] = {
            "@context": EDC_CONTEXT,
            "offset": offset,
            "limit": limit,
        }

        if filter_expression:
            query_spec["filterExpression"] = filter_expression

        try:
            response = await client.post(
                "/management/v3/transferprocesses/request",
                json=query_spec,
            )
            result = await self._handle_response(response, "Query transfers")

            if result is None:
                return []

            return result if isinstance(result, list) else []
        except httpx.HTTPError as e:
            logger.error("Failed to query EDC transfers: %s", str(e))
            raise EDCConnectionError(
                f"Connection error querying transfers: {e}",
                status_code=None,
                response_body=None,
            )

    # -------------------------------------------------------------------------
    # EDR (Endpoint Data Reference)
    # -------------------------------------------------------------------------

    async def get_edr(self, transfer_id: str) -> dict[str, Any] | None:
        """
        Get Endpoint Data Reference for a transfer.

        The EDR contains the endpoint URL and authorization token
        for accessing transferred data.

        Args:
            transfer_id: Transfer process identifier

        Returns:
            EDR with endpoint and authorization or None
        """
        logger.debug("Getting EDR for transfer: %s", transfer_id)

        client = await self._get_client()
        try:
            response = await client.get(
                f"/management/v3/edrs/{transfer_id}/dataaddress"
            )
            return await self._handle_response(response, "Get EDR")
        except EDCClientError:
            return None
        except httpx.HTTPError as e:
            logger.error("Failed to get EDR: %s", str(e))
            raise EDCConnectionError(
                f"Connection error getting EDR: {e}",
                status_code=None,
                response_body=None,
            )

    # -------------------------------------------------------------------------
    # Health
    # -------------------------------------------------------------------------

    async def health_check(self) -> bool:
        """
        Check EDC connector health.

        Returns:
            True if healthy
        """
        client = await self._get_client()

        try:
            # Try to query assets with limit 1 as health check
            response = await client.post(
                "/management/v3/assets/request",
                json={"@context": EDC_CONTEXT, "limit": 1},
            )
            return response.status_code < 500
        except httpx.HTTPError:
            return False

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def build_asset(
        self,
        asset_id: str,
        name: str,
        base_url: str,
        proxy_path: bool = True,
        proxy_method: bool = True,
        content_type: str = "application/json",
        description: str | None = None,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Build an EDC asset definition.

        Helper method to construct a properly formatted asset.

        Args:
            asset_id: Unique asset identifier
            name: Human-readable name
            base_url: Data endpoint base URL
            proxy_path: Allow path proxying
            proxy_method: Allow method proxying
            content_type: Content type for data
            description: Optional description
            properties: Additional properties

        Returns:
            Asset definition ready for create_asset()
        """
        asset = {
            "@context": EDC_CONTEXT,
            "@id": asset_id,
            "properties": {
                "name": name,
                "contenttype": content_type,
            },
            "dataAddress": {
                "@type": "DataAddress",
                "type": "HttpData",
                "baseUrl": base_url,
                "proxyPath": str(proxy_path).lower(),
                "proxyMethod": str(proxy_method).lower(),
            },
        }

        if description:
            asset["properties"]["description"] = description

        if properties:
            asset["properties"].update(properties)

        return asset

    def build_policy_definition(
        self,
        policy_id: str,
        permissions: list[dict[str, Any]] | None = None,
        prohibitions: list[dict[str, Any]] | None = None,
        obligations: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        Build an EDC policy definition.

        Helper method to construct a properly formatted policy.

        Args:
            policy_id: Unique policy identifier
            permissions: List of ODRL permissions
            prohibitions: List of ODRL prohibitions
            obligations: List of ODRL obligations

        Returns:
            Policy definition ready for create_policy()
        """
        policy = {
            "@context": EDC_CONTEXT,
            "@id": policy_id,
            "policy": {
                "@type": "odrl:Set",
            },
        }

        if permissions:
            policy["policy"]["odrl:permission"] = permissions
        if prohibitions:
            policy["policy"]["odrl:prohibition"] = prohibitions
        if obligations:
            policy["policy"]["odrl:obligation"] = obligations

        # Default to unrestricted use if no rules specified
        if not any([permissions, prohibitions, obligations]):
            policy["policy"]["odrl:permission"] = [
                {
                    "odrl:action": "USE",
                }
            ]

        return policy

    def build_contract_definition(
        self,
        definition_id: str,
        access_policy_id: str,
        contract_policy_id: str,
        asset_selector: list[dict[str, Any]] | None = None,
        asset_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Build an EDC contract definition.

        Helper method to construct a properly formatted contract definition.

        Args:
            definition_id: Unique definition identifier
            access_policy_id: Policy ID for access control
            contract_policy_id: Policy ID for contract terms
            asset_selector: Criterion to select assets
            asset_id: Simple asset ID selector (alternative to asset_selector)

        Returns:
            Contract definition ready for create_contract_definition()
        """
        definition = {
            "@context": EDC_CONTEXT,
            "@id": definition_id,
            "accessPolicyId": access_policy_id,
            "contractPolicyId": contract_policy_id,
        }

        if asset_selector:
            definition["assetsSelector"] = asset_selector
        elif asset_id:
            definition["assetsSelector"] = [
                {
                    "operandLeft": "https://w3id.org/edc/v0.0.1/ns/id",
                    "operator": "=",
                    "operandRight": asset_id,
                }
            ]

        return definition

    # -------------------------------------------------------------------------
    # Context Manager Support
    # -------------------------------------------------------------------------

    async def __aenter__(self) -> "TractusXClient":
        """Enter async context."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context and close client."""
        await self.close()
