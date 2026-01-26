"""
AAS Extension client for EDC.

Provides client for interacting with the AAS-specific EDC extension
that simplifies Digital Twin registration and data exchange.

The AAS Extension typically builds on the standard EDC Management API
and adds AAS-specific endpoints for automated asset creation from
AAS structures, registry-based discovery, and streamlined contract
generation.
"""

from __future__ import annotations

import base64
import logging
import uuid
from typing import Any

import httpx

from app.services.dataspace.edc.tractus_x_client import (
    EDCClientError,
    EDCAssetNotFoundError,
    EDCAssetConflictError,
    EDCAuthenticationError,
    EDCConnectionError,
    EDC_CONTEXT,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# AAS-specific Exceptions
# ---------------------------------------------------------------------------


class AASExtensionError(EDCClientError):
    """Base exception for AAS Extension errors."""

    pass


class AASShellNotFoundError(AASExtensionError):
    """AAS Shell not found in registry."""

    pass


class AASSubmodelNotFoundError(AASExtensionError):
    """Submodel not found in registry."""

    pass


class AASRegistrationError(AASExtensionError):
    """Failed to register AAS/Submodel."""

    pass


# ---------------------------------------------------------------------------
# Client Implementation
# ---------------------------------------------------------------------------


class AASExtensionClient:
    """
    Client for AAS-specific EDC extension.

    The AAS Extension provides simplified APIs for:
    - Registering AAS Shells as EDC Assets
    - Linking to Digital Twin Registry entries
    - Managing submodel access policies
    - Handling AAS-specific data formats
    - Automated contract generation from AAS structure

    This client can work with various AAS-EDC integration patterns:
    - Direct AAS Extension endpoints (if available)
    - Standard EDC APIs with AAS-aware asset construction
    - DTR (Digital Twin Registry) integration
    """

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        auth_token: str | None = None,
        dtr_url: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        """
        Initialize the AAS Extension client.

        Args:
            base_url: AAS Extension API base URL (usually same as EDC Management API)
            api_key: Optional API key for authentication
            auth_token: Optional OAuth2 bearer token
            dtr_url: Optional Digital Twin Registry URL
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.auth_token = auth_token
        self.dtr_url = dtr_url.rstrip("/") if dtr_url else None
        self.timeout = timeout

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
        if self._client is not None:
            self._client = None

    @staticmethod
    def encode_id(identifier: str) -> str:
        """
        Encode an identifier for URL path (base64url).

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
        padding = 4 - len(encoded) % 4
        if padding != 4:
            encoded += "=" * padding
        return base64.urlsafe_b64decode(encoded.encode()).decode()

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
            resource_type: Type of resource (shell, submodel, etc.)

        Returns:
            Parsed JSON response or None

        Raises:
            AASShellNotFoundError: If shell not found (404)
            AASSubmodelNotFoundError: If submodel not found (404)
            AASRegistrationError: If registration fails
            AASExtensionError: For other errors
        """
        if response.status_code == 401 or response.status_code == 403:
            raise EDCAuthenticationError(
                f"{operation}: Authentication failed",
                status_code=response.status_code,
                response_body=response.text,
            )

        if response.status_code == 404:
            if resource_type == "shell":
                raise AASShellNotFoundError(
                    f"{operation}: Shell not found",
                    status_code=404,
                    response_body=response.text,
                )
            elif resource_type == "submodel":
                raise AASSubmodelNotFoundError(
                    f"{operation}: Submodel not found",
                    status_code=404,
                    response_body=response.text,
                )
            else:
                raise AASExtensionError(
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
            raise AASExtensionError(
                f"{operation} failed: {response.status_code}",
                status_code=response.status_code,
                response_body=response.text,
            )

        # Handle empty responses
        if response.status_code == 204 or not response.content:
            return None

        try:
            return response.json()
        except ValueError:
            return None

    # -------------------------------------------------------------------------
    # Shell Registration
    # -------------------------------------------------------------------------

    async def register_shell(
        self,
        shell_descriptor: dict[str, Any],
        policy_id: str | None = None,
        create_contract: bool = True,
    ) -> dict[str, Any]:
        """
        Register an AAS Shell with the EDC.

        This creates both the DTR entry and EDC asset in a coordinated operation.

        Args:
            shell_descriptor: AAS Shell Descriptor following AAS API spec
                Required fields:
                - id: Unique shell identifier (URN/IRI)
                - idShort: Human-readable short name
                Optional fields:
                - description: Shell description
                - specificAssetIds: Asset identifiers for lookup
                - submodelDescriptors: Submodel descriptors to include
            policy_id: Optional policy to apply to the asset
            create_contract: Whether to create contract definition

        Returns:
            Registration result with:
            - shellId: Shell identifier
            - dtrId: DTR registration ID (if DTR used)
            - edcAssetId: EDC asset ID
            - contractDefinitionId: Contract definition ID (if created)

        Raises:
            AASRegistrationError: If registration fails
            EDCAssetConflictError: If shell already registered
        """
        shell_id = shell_descriptor.get("id", "unknown")
        logger.info("Registering AAS Shell %s", shell_id)

        client = await self._get_client()

        # Generate EDC asset ID from shell ID
        edc_asset_id = f"aas-shell-{self.encode_id(shell_id)}"

        # Build AAS-aware EDC asset
        asset = self._build_shell_asset(shell_descriptor, edc_asset_id)

        # Try AAS Extension endpoint first (if available)
        try:
            response = await client.post(
                "/aas/shells",
                json={
                    "shellDescriptor": shell_descriptor,
                    "policyId": policy_id,
                    "createContract": create_contract,
                },
            )

            if response.status_code < 400:
                result = await self._handle_response(
                    response, "Register shell (extension)", resource_type="shell"
                )
                if result:
                    logger.info("Successfully registered AAS Shell via extension: %s", shell_id)
                    return result

        except httpx.HTTPError:
            # Extension endpoint not available, fall back to standard EDC
            logger.debug("AAS Extension endpoint not available, using standard EDC API")

        # Fall back to standard EDC asset creation
        try:
            response = await client.post(
                "/management/v3/assets",
                json=asset,
            )
            await self._handle_response(
                response, "Create shell asset", resource_type="shell"
            )

            result = {
                "shellId": shell_id,
                "edcAssetId": edc_asset_id,
            }

            # Create contract definition if requested
            if create_contract and policy_id:
                contract_def_id = f"contract-{edc_asset_id}"
                contract_def = self._build_contract_definition(
                    contract_def_id,
                    policy_id,
                    edc_asset_id,
                )
                await client.post(
                    "/management/v3/contractdefinitions",
                    json=contract_def,
                )
                result["contractDefinitionId"] = contract_def_id

            logger.info("Successfully registered AAS Shell: %s", shell_id)
            return result

        except httpx.HTTPError as e:
            logger.error("Failed to register AAS Shell: %s", str(e))
            raise EDCConnectionError(
                f"Connection error registering shell: {e}",
                status_code=None,
                response_body=None,
            )

    async def unregister_shell(
        self,
        shell_id: str,
        delete_submodels: bool = True,
    ) -> bool:
        """
        Unregister an AAS Shell from the EDC.

        Removes both DTR entry and EDC asset.

        Args:
            shell_id: Shell identifier to unregister
            delete_submodels: Also delete associated submodel assets

        Returns:
            True if unregistered successfully

        Raises:
            AASShellNotFoundError: If shell not found
            AASExtensionError: For other errors
        """
        logger.info("Unregistering AAS Shell %s", shell_id)

        client = await self._get_client()
        edc_asset_id = f"aas-shell-{self.encode_id(shell_id)}"

        # Try AAS Extension endpoint first
        try:
            response = await client.delete(
                f"/aas/shells/{self.encode_id(shell_id)}",
                params={"deleteSubmodels": str(delete_submodels).lower()},
            )

            if response.status_code < 400:
                logger.info("Successfully unregistered AAS Shell via extension: %s", shell_id)
                return True

        except httpx.HTTPError:
            logger.debug("AAS Extension endpoint not available, using standard EDC API")

        # Fall back to standard EDC asset deletion
        try:
            # Delete contract definition first
            contract_def_id = f"contract-{edc_asset_id}"
            await client.delete(f"/management/v3/contractdefinitions/{contract_def_id}")
        except httpx.HTTPError:
            pass  # Contract definition may not exist

        try:
            response = await client.delete(f"/management/v3/assets/{edc_asset_id}")

            if response.status_code == 404:
                raise AASShellNotFoundError(
                    f"Shell not found: {shell_id}",
                    status_code=404,
                    response_body=response.text,
                )

            await self._handle_response(
                response, "Delete shell asset", resource_type="shell"
            )

            logger.info("Successfully unregistered AAS Shell: %s", shell_id)
            return True

        except AASShellNotFoundError:
            raise
        except httpx.HTTPError as e:
            logger.error("Failed to unregister AAS Shell: %s", str(e))
            raise EDCConnectionError(
                f"Connection error unregistering shell: {e}",
                status_code=None,
                response_body=None,
            )

    # -------------------------------------------------------------------------
    # Submodel Registration
    # -------------------------------------------------------------------------

    async def register_submodel(
        self,
        shell_id: str,
        submodel_descriptor: dict[str, Any],
        policy_id: str | None = None,
        submodel_endpoint: str | None = None,
        create_contract: bool = True,
    ) -> dict[str, Any]:
        """
        Register a Submodel for an existing Shell.

        Creates an EDC asset for the submodel with proper linking
        to the parent shell.

        Args:
            shell_id: Parent shell identifier
            submodel_descriptor: Submodel Descriptor
                Required fields:
                - id: Unique submodel identifier
                - idShort: Human-readable name
                - semanticId: Semantic ID reference
            policy_id: Optional policy for the submodel
            submodel_endpoint: Optional submodel data endpoint URL
            create_contract: Whether to create contract definition

        Returns:
            Registration result with:
            - submodelId: Submodel identifier
            - edcAssetId: EDC asset ID
            - contractDefinitionId: Contract definition ID (if created)

        Raises:
            AASRegistrationError: If registration fails
        """
        submodel_id = submodel_descriptor.get("id", "unknown")
        logger.info(
            "Registering Submodel %s for Shell %s",
            submodel_id,
            shell_id,
        )

        client = await self._get_client()

        # Generate EDC asset ID from submodel ID
        edc_asset_id = f"aas-submodel-{self.encode_id(submodel_id)}"

        # Build AAS-aware EDC asset for submodel
        asset = self._build_submodel_asset(
            shell_id,
            submodel_descriptor,
            edc_asset_id,
            submodel_endpoint,
        )

        # Try AAS Extension endpoint first
        try:
            response = await client.post(
                f"/aas/shells/{self.encode_id(shell_id)}/submodels",
                json={
                    "submodelDescriptor": submodel_descriptor,
                    "policyId": policy_id,
                    "createContract": create_contract,
                },
            )

            if response.status_code < 400:
                result = await self._handle_response(
                    response, "Register submodel (extension)", resource_type="submodel"
                )
                if result:
                    logger.info("Successfully registered Submodel via extension: %s", submodel_id)
                    return result

        except httpx.HTTPError:
            logger.debug("AAS Extension endpoint not available, using standard EDC API")

        # Fall back to standard EDC asset creation
        try:
            response = await client.post(
                "/management/v3/assets",
                json=asset,
            )
            await self._handle_response(
                response, "Create submodel asset", resource_type="submodel"
            )

            result = {
                "submodelId": submodel_id,
                "shellId": shell_id,
                "edcAssetId": edc_asset_id,
            }

            # Create contract definition if requested
            if create_contract and policy_id:
                contract_def_id = f"contract-{edc_asset_id}"
                contract_def = self._build_contract_definition(
                    contract_def_id,
                    policy_id,
                    edc_asset_id,
                )
                await client.post(
                    "/management/v3/contractdefinitions",
                    json=contract_def,
                )
                result["contractDefinitionId"] = contract_def_id

            logger.info("Successfully registered Submodel: %s", submodel_id)
            return result

        except httpx.HTTPError as e:
            logger.error("Failed to register Submodel: %s", str(e))
            raise EDCConnectionError(
                f"Connection error registering submodel: {e}",
                status_code=None,
                response_body=None,
            )

    async def unregister_submodel(self, shell_id: str, submodel_id: str) -> bool:
        """
        Unregister a Submodel.

        Args:
            shell_id: Parent shell identifier
            submodel_id: Submodel to unregister

        Returns:
            True if unregistered

        Raises:
            AASSubmodelNotFoundError: If submodel not found
        """
        logger.info("Unregistering Submodel %s", submodel_id)

        client = await self._get_client()
        edc_asset_id = f"aas-submodel-{self.encode_id(submodel_id)}"

        # Try AAS Extension endpoint first
        try:
            response = await client.delete(
                f"/aas/shells/{self.encode_id(shell_id)}/submodels/{self.encode_id(submodel_id)}"
            )

            if response.status_code < 400:
                logger.info("Successfully unregistered Submodel via extension: %s", submodel_id)
                return True

        except httpx.HTTPError:
            logger.debug("AAS Extension endpoint not available, using standard EDC API")

        # Fall back to standard EDC
        try:
            # Delete contract definition first
            contract_def_id = f"contract-{edc_asset_id}"
            await client.delete(f"/management/v3/contractdefinitions/{contract_def_id}")
        except httpx.HTTPError:
            pass

        try:
            response = await client.delete(f"/management/v3/assets/{edc_asset_id}")

            if response.status_code == 404:
                raise AASSubmodelNotFoundError(
                    f"Submodel not found: {submodel_id}",
                    status_code=404,
                    response_body=response.text,
                )

            await self._handle_response(
                response, "Delete submodel asset", resource_type="submodel"
            )

            logger.info("Successfully unregistered Submodel: %s", submodel_id)
            return True

        except AASSubmodelNotFoundError:
            raise
        except httpx.HTTPError as e:
            logger.error("Failed to unregister Submodel: %s", str(e))
            raise EDCConnectionError(
                f"Connection error unregistering submodel: {e}",
                status_code=None,
                response_body=None,
            )

    # -------------------------------------------------------------------------
    # Shell Descriptor Operations
    # -------------------------------------------------------------------------

    async def get_shell_descriptor(
        self,
        shell_id: str,
        agreement_id: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Get an AAS Shell Descriptor through the EDC.

        If agreement_id is provided, retrieves from provider via data exchange.
        Otherwise, retrieves from local DTR if configured.

        Args:
            shell_id: Shell identifier
            agreement_id: Optional contract agreement for remote access

        Returns:
            Shell Descriptor or None if not found
        """
        logger.debug("Getting Shell Descriptor %s", shell_id)

        client = await self._get_client()

        # Try AAS Extension endpoint first
        try:
            params = {}
            if agreement_id:
                params["agreementId"] = agreement_id

            response = await client.get(
                f"/aas/shells/{self.encode_id(shell_id)}",
                params=params if params else None,
            )

            if response.status_code == 200:
                return await self._handle_response(
                    response, "Get shell descriptor", resource_type="shell"
                )
            elif response.status_code == 404:
                return None

        except httpx.HTTPError:
            logger.debug("AAS Extension endpoint not available")

        # Fall back to DTR if configured
        if self.dtr_url:
            try:
                dtr_client = httpx.AsyncClient(
                    base_url=self.dtr_url,
                    headers={"Accept": "application/json"},
                    timeout=self.timeout,
                )
                response = await dtr_client.get(
                    f"/shell-descriptors/{self.encode_id(shell_id)}"
                )
                await dtr_client.aclose()

                if response.status_code == 200:
                    return response.json()
            except httpx.HTTPError as e:
                logger.debug("DTR lookup failed: %s", str(e))

        return None

    async def get_submodel(
        self,
        shell_id: str,
        submodel_id: str,
        agreement_id: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Get a Submodel through the EDC.

        Args:
            shell_id: Parent shell identifier
            submodel_id: Submodel identifier
            agreement_id: Optional contract agreement for remote access

        Returns:
            Submodel data or None if not found
        """
        logger.debug("Getting Submodel %s", submodel_id)

        client = await self._get_client()

        # Try AAS Extension endpoint first
        try:
            params = {}
            if agreement_id:
                params["agreementId"] = agreement_id

            response = await client.get(
                f"/aas/shells/{self.encode_id(shell_id)}/submodels/{self.encode_id(submodel_id)}",
                params=params if params else None,
            )

            if response.status_code == 200:
                return await self._handle_response(
                    response, "Get submodel", resource_type="submodel"
                )
            elif response.status_code == 404:
                return None

        except httpx.HTTPError:
            logger.debug("AAS Extension endpoint not available")

        return None

    # -------------------------------------------------------------------------
    # Lookup Operations
    # -------------------------------------------------------------------------

    async def lookup_shells(
        self,
        specific_asset_ids: list[dict[str, Any]],
    ) -> list[str]:
        """
        Lookup Shell IDs by specific asset IDs.

        Args:
            specific_asset_ids: List of specificAssetId filters
                Each item should have:
                - name: Asset ID key name
                - value: Asset ID value

        Returns:
            List of matching Shell IDs
        """
        logger.debug("Looking up shells by specific asset IDs")

        client = await self._get_client()

        # Try AAS Extension endpoint first
        try:
            # Build query parameters
            asset_ids_encoded = base64.urlsafe_b64encode(
                str(specific_asset_ids).encode()
            ).decode()

            response = await client.get(
                "/aas/lookup/shells",
                params={"assetIds": asset_ids_encoded},
            )

            if response.status_code == 200:
                result = await self._handle_response(response, "Lookup shells")
                if result:
                    return result.get("result", result.get("paging_metadata", {}).get("result", []))

        except httpx.HTTPError:
            logger.debug("AAS Extension lookup not available")

        # Fall back to DTR if configured
        if self.dtr_url:
            try:
                dtr_client = httpx.AsyncClient(
                    base_url=self.dtr_url,
                    headers={"Accept": "application/json"},
                    timeout=self.timeout,
                )

                # Build query params for DTR
                import json
                asset_ids_param = base64.urlsafe_b64encode(
                    json.dumps(specific_asset_ids).encode()
                ).decode()

                response = await dtr_client.get(
                    "/lookup/shells",
                    params={"assetIds": asset_ids_param},
                )
                await dtr_client.aclose()

                if response.status_code == 200:
                    result = response.json()
                    return result.get("result", [])

            except httpx.HTTPError as e:
                logger.debug("DTR lookup failed: %s", str(e))

        return []

    async def lookup_submodel_descriptors(
        self,
        shell_id: str,
        semantic_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Lookup Submodel Descriptors for a Shell.

        Args:
            shell_id: Shell identifier
            semantic_id: Optional semantic ID filter

        Returns:
            List of matching Submodel Descriptors
        """
        logger.debug("Looking up submodels for Shell %s", shell_id)

        client = await self._get_client()

        # Try AAS Extension endpoint first
        try:
            params = {}
            if semantic_id:
                semantic_ref = {
                    "type": "ExternalReference",
                    "keys": [{"type": "GlobalReference", "value": semantic_id}],
                }
                params["semanticId"] = base64.urlsafe_b64encode(
                    str(semantic_ref).encode()
                ).decode()

            response = await client.get(
                f"/aas/shells/{self.encode_id(shell_id)}/submodel-descriptors",
                params=params if params else None,
            )

            if response.status_code == 200:
                result = await self._handle_response(response, "Lookup submodels")
                if result:
                    submodels = result.get("result", [])

                    # Filter by semantic ID if needed
                    if semantic_id and submodels:
                        submodels = [
                            sm for sm in submodels
                            if self._matches_semantic_id(sm, semantic_id)
                        ]

                    return submodels

        except httpx.HTTPError:
            logger.debug("AAS Extension lookup not available")

        # Fall back to getting shell descriptor and extracting submodels
        shell = await self.get_shell_descriptor(shell_id)
        if shell:
            submodels = shell.get("submodelDescriptors", [])
            if semantic_id:
                submodels = [
                    sm for sm in submodels
                    if self._matches_semantic_id(sm, semantic_id)
                ]
            return submodels

        return []

    def _matches_semantic_id(
        self,
        submodel: dict[str, Any],
        semantic_id: str,
    ) -> bool:
        """Check if submodel matches semantic ID."""
        sm_semantic = submodel.get("semanticId", {})
        keys = sm_semantic.get("keys", [])
        for key in keys:
            if key.get("value") == semantic_id:
                return True
        return False

    # -------------------------------------------------------------------------
    # Automated Contract Generation
    # -------------------------------------------------------------------------

    async def create_contracts_from_aas(
        self,
        shell_descriptor: dict[str, Any],
        access_policy_id: str,
        contract_policy_id: str,
        submodel_policies: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Create EDC contracts from an AAS structure.

        Automatically creates assets and contract definitions for a shell
        and all its submodels.

        Args:
            shell_descriptor: Complete shell descriptor with submodels
            access_policy_id: Default access policy ID
            contract_policy_id: Default contract policy ID
            submodel_policies: Optional per-submodel policy overrides
                Keys are submodel IDs, values are policy IDs

        Returns:
            Creation result with:
            - shellAssetId: Created shell asset ID
            - shellContractId: Created shell contract ID
            - submodels: List of created submodel assets/contracts
        """
        shell_id = shell_descriptor.get("id", "unknown")
        logger.info("Creating contracts from AAS structure for %s", shell_id)

        result = {
            "shellAssetId": None,
            "shellContractId": None,
            "submodels": [],
        }

        # Register shell
        shell_result = await self.register_shell(
            shell_descriptor,
            policy_id=access_policy_id,
            create_contract=True,
        )
        result["shellAssetId"] = shell_result.get("edcAssetId")
        result["shellContractId"] = shell_result.get("contractDefinitionId")

        # Register each submodel
        submodels = shell_descriptor.get("submodelDescriptors", [])
        for submodel in submodels:
            submodel_id = submodel.get("id")
            policy_id = (
                submodel_policies.get(submodel_id, contract_policy_id)
                if submodel_policies
                else contract_policy_id
            )

            try:
                sm_result = await self.register_submodel(
                    shell_id,
                    submodel,
                    policy_id=policy_id,
                    create_contract=True,
                )
                result["submodels"].append({
                    "submodelId": submodel_id,
                    "assetId": sm_result.get("edcAssetId"),
                    "contractId": sm_result.get("contractDefinitionId"),
                })
            except Exception as e:
                logger.error("Failed to register submodel %s: %s", submodel_id, str(e))
                result["submodels"].append({
                    "submodelId": submodel_id,
                    "error": str(e),
                })

        logger.info(
            "Created contracts for shell %s with %d submodels",
            shell_id,
            len(result["submodels"]),
        )
        return result

    async def discover_assets_from_registry(
        self,
        specific_asset_ids: list[dict[str, Any]] | None = None,
        semantic_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Discover available assets from registry.

        Uses DTR/Discovery services to find available shells and submodels.

        Args:
            specific_asset_ids: Filter by specific asset IDs
            semantic_id: Filter submodels by semantic ID

        Returns:
            List of discovered assets with metadata
        """
        logger.info("Discovering assets from registry")

        discovered = []

        # Lookup shells
        if specific_asset_ids:
            shell_ids = await self.lookup_shells(specific_asset_ids)
        else:
            # Get all shells if no filter (limited query)
            shell_ids = await self.lookup_shells([])

        for shell_id in shell_ids:
            shell = await self.get_shell_descriptor(shell_id)
            if shell:
                asset_info = {
                    "type": "shell",
                    "id": shell_id,
                    "idShort": shell.get("idShort"),
                    "description": shell.get("description"),
                    "edcAssetId": f"aas-shell-{self.encode_id(shell_id)}",
                    "submodels": [],
                }

                # Get submodels
                submodels = await self.lookup_submodel_descriptors(
                    shell_id,
                    semantic_id=semantic_id,
                )
                for sm in submodels:
                    sm_id = sm.get("id")
                    asset_info["submodels"].append({
                        "id": sm_id,
                        "idShort": sm.get("idShort"),
                        "semanticId": sm.get("semanticId"),
                        "edcAssetId": f"aas-submodel-{self.encode_id(sm_id)}",
                    })

                discovered.append(asset_info)

        logger.info("Discovered %d shells from registry", len(discovered))
        return discovered

    # -------------------------------------------------------------------------
    # Health
    # -------------------------------------------------------------------------

    async def health_check(self) -> bool:
        """
        Check AAS Extension health.

        Returns:
            True if healthy
        """
        client = await self._get_client()

        try:
            # Try extension health endpoint
            response = await client.get("/aas/health")
            if response.status_code < 500:
                return True
        except httpx.HTTPError:
            pass

        # Fall back to EDC health check
        try:
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

    def _build_shell_asset(
        self,
        shell_descriptor: dict[str, Any],
        asset_id: str,
    ) -> dict[str, Any]:
        """Build an EDC asset for an AAS Shell."""
        shell_id = shell_descriptor.get("id", "")

        # Extract specific asset IDs for properties
        specific_ids = shell_descriptor.get("specificAssetIds", [])
        specific_ids_props = {}
        for aid in specific_ids:
            name = aid.get("name", "")
            value = aid.get("value", "")
            if name and value:
                specific_ids_props[f"aas:specificAssetId:{name}"] = value

        # Build base URL for shell endpoint
        # This would typically point to the AAS server
        base_url = f"{self.base_url}/shells/{self.encode_id(shell_id)}"

        asset = {
            "@context": EDC_CONTEXT,
            "@id": asset_id,
            "properties": {
                "name": shell_descriptor.get("idShort", shell_id),
                "contenttype": "application/json",
                "aas:type": "shell",
                "aas:shellId": shell_id,
                **specific_ids_props,
            },
            "dataAddress": {
                "@type": "DataAddress",
                "type": "HttpData",
                "baseUrl": base_url,
                "proxyPath": "true",
                "proxyMethod": "true",
            },
        }

        if "description" in shell_descriptor:
            desc = shell_descriptor["description"]
            if isinstance(desc, list) and desc:
                asset["properties"]["description"] = desc[0].get("text", "")
            elif isinstance(desc, str):
                asset["properties"]["description"] = desc

        return asset

    def _build_submodel_asset(
        self,
        shell_id: str,
        submodel_descriptor: dict[str, Any],
        asset_id: str,
        endpoint_url: str | None = None,
    ) -> dict[str, Any]:
        """Build an EDC asset for a Submodel."""
        submodel_id = submodel_descriptor.get("id", "")

        # Extract semantic ID
        semantic_id = ""
        semantic_ref = submodel_descriptor.get("semanticId", {})
        keys = semantic_ref.get("keys", [])
        if keys:
            semantic_id = keys[0].get("value", "")

        # Build endpoint URL
        if not endpoint_url:
            endpoint_url = f"{self.base_url}/submodels/{self.encode_id(submodel_id)}"

        asset = {
            "@context": EDC_CONTEXT,
            "@id": asset_id,
            "properties": {
                "name": submodel_descriptor.get("idShort", submodel_id),
                "contenttype": "application/json",
                "aas:type": "submodel",
                "aas:submodelId": submodel_id,
                "aas:shellId": shell_id,
            },
            "dataAddress": {
                "@type": "DataAddress",
                "type": "HttpData",
                "baseUrl": endpoint_url,
                "proxyPath": "true",
                "proxyMethod": "true",
            },
        }

        if semantic_id:
            asset["properties"]["aas:semanticId"] = semantic_id

        if "description" in submodel_descriptor:
            desc = submodel_descriptor["description"]
            if isinstance(desc, list) and desc:
                asset["properties"]["description"] = desc[0].get("text", "")
            elif isinstance(desc, str):
                asset["properties"]["description"] = desc

        return asset

    def _build_contract_definition(
        self,
        definition_id: str,
        policy_id: str,
        asset_id: str,
    ) -> dict[str, Any]:
        """Build an EDC contract definition for an AAS asset."""
        return {
            "@context": EDC_CONTEXT,
            "@id": definition_id,
            "accessPolicyId": policy_id,
            "contractPolicyId": policy_id,
            "assetsSelector": [
                {
                    "operandLeft": "https://w3id.org/edc/v0.0.1/ns/id",
                    "operator": "=",
                    "operandRight": asset_id,
                }
            ],
        }

    # -------------------------------------------------------------------------
    # Context Manager Support
    # -------------------------------------------------------------------------

    async def __aenter__(self) -> "AASExtensionClient":
        """Enter async context."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context and close client."""
        await self.close()
