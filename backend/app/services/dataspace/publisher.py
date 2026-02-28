"""
AAS Publisher Service.

Orchestrates the publication of Asset Administration Shells and Submodels
to BaSyx AAS Servers and Digital Twin Registries.

This service:
1. Hydrates form data into complete AAS structures
2. Publishes submodels to BaSyx AAS Server
3. Registers shell/submodel descriptors in DTR
4. Manages the lifecycle of published assets
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any


from app.services.hydrator import HydratorService
from app.services.dataspace.registry.basyx_client import (
    BaSyxClient,
    BaSyxClientError,
    BaSyxConflictError,
)
from app.services.dataspace.registry.dtr_client import (
    DTRClient,
    DTRClientError,
    DTRConflictError,
)

logger = logging.getLogger(__name__)


class AASPublisherError(Exception):
    """Base exception for AAS Publisher errors."""

    def __init__(
        self,
        message: str,
        step: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.step = step
        self.cause = cause


class PublicationResult:
    """Result of a publication operation."""

    def __init__(
        self,
        success: bool,
        aas_id: str,
        submodel_id: str,
        aas_endpoint: str | None = None,
        dtr_registered: bool = False,
        error_message: str | None = None,
    ) -> None:
        self.success = success
        self.aas_id = aas_id
        self.submodel_id = submodel_id
        self.aas_endpoint = aas_endpoint
        self.dtr_registered = dtr_registered
        self.error_message = error_message
        self.published_at = datetime.now(timezone.utc) if success else None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "success": self.success,
            "aas_id": self.aas_id,
            "submodel_id": self.submodel_id,
            "aas_endpoint": self.aas_endpoint,
            "dtr_registered": self.dtr_registered,
            "error_message": self.error_message,
            "published_at": self.published_at.isoformat() if self.published_at else None,
        }


class AASPublisher:
    """
    Service for publishing AAS to BaSyx and DTR.

    Coordinates the hydration of form data and publication to:
    - BaSyx AAS Server (submodel storage and serving)
    - Digital Twin Registry (discovery and lookup)
    """

    def __init__(
        self,
        basyx_client: BaSyxClient,
        dtr_client: DTRClient | None = None,
        hydrator: HydratorService | None = None,
    ) -> None:
        """
        Initialize the AAS Publisher.

        Args:
            basyx_client: BaSyx AAS Server client
            dtr_client: Optional DTR client for registry registration
            hydrator: Optional HydratorService instance
        """
        self.basyx = basyx_client
        self.dtr = dtr_client
        self.hydrator = hydrator or HydratorService()

    async def publish_submodel(
        self,
        template_aasx_bytes: bytes,
        form_data: dict[str, Any],
        aas_id: str | None = None,
        submodel_id: str | None = None,
        asset_ids: list[dict[str, str]] | None = None,
        register_in_dtr: bool = True,
    ) -> PublicationResult:
        """
        Publish a submodel to BaSyx and optionally register in DTR.

        Args:
            template_aasx_bytes: Template AASX file bytes
            form_data: Form data to hydrate into the template
            aas_id: Optional custom AAS ID (auto-generated if not provided)
            submodel_id: Optional custom Submodel ID (auto-generated if not provided)
            asset_ids: Optional specific asset IDs for discovery
            register_in_dtr: Whether to register in DTR (requires dtr_client)

        Returns:
            PublicationResult with publication details

        Raises:
            AASPublisherError: If publication fails
        """
        # Generate IDs if not provided
        if not aas_id:
            aas_id = f"urn:aas:{uuid.uuid4()}"
        if not submodel_id:
            submodel_id = f"urn:submodel:{uuid.uuid4()}"

        logger.info(
            "Publishing submodel: aas_id=%s, submodel_id=%s",
            aas_id,
            submodel_id,
        )

        try:
            # Step 1: Hydrate the template with form data
            hydrated_json = await self._hydrate_to_json(
                template_aasx_bytes,
                form_data,
                aas_id,
                submodel_id,
            )

            # Step 2: Build shell and submodel descriptors
            shell_descriptor = self._build_shell_descriptor(
                aas_id,
                submodel_id,
                hydrated_json,
                asset_ids,
            )
            submodel_descriptor = self._build_submodel_descriptor(
                submodel_id,
                hydrated_json,
            )

            # Step 3: Register AAS Shell in BaSyx
            await self._register_aas_in_basyx(shell_descriptor)

            # Step 4: Register Submodel in BaSyx
            await self._register_submodel_in_basyx(aas_id, submodel_descriptor)

            # Step 5: Optionally register in DTR
            dtr_registered = False
            if register_in_dtr and self.dtr:
                dtr_registered = await self._register_in_dtr(
                    shell_descriptor,
                    submodel_descriptor,
                )

            # Build endpoint URL
            aas_endpoint = f"{self.basyx.base_url}/shells/{BaSyxClient.encode_id(aas_id)}"

            return PublicationResult(
                success=True,
                aas_id=aas_id,
                submodel_id=submodel_id,
                aas_endpoint=aas_endpoint,
                dtr_registered=dtr_registered,
            )

        except AASPublisherError:
            raise
        except Exception as e:
            logger.exception("Failed to publish submodel")
            raise AASPublisherError(
                f"Publication failed: {str(e)}",
                step="unknown",
                cause=e,
            )

    async def update_submodel(
        self,
        aas_id: str,
        submodel_id: str,
        template_aasx_bytes: bytes,
        form_data: dict[str, Any],
    ) -> PublicationResult:
        """
        Update an existing published submodel.

        Args:
            aas_id: Existing AAS ID
            submodel_id: Existing Submodel ID
            template_aasx_bytes: Template AASX file bytes
            form_data: Updated form data

        Returns:
            PublicationResult with update details
        """
        logger.info(
            "Updating submodel: aas_id=%s, submodel_id=%s",
            aas_id,
            submodel_id,
        )

        try:
            # Hydrate with updated data
            hydrated_json = await self._hydrate_to_json(
                template_aasx_bytes,
                form_data,
                aas_id,
                submodel_id,
            )

            # Build updated submodel descriptor
            submodel_descriptor = self._build_submodel_descriptor(
                submodel_id,
                hydrated_json,
            )

            # Update in BaSyx
            await self.basyx.update_submodel(aas_id, submodel_id, submodel_descriptor)

            # Update in DTR if available
            dtr_registered = False
            if self.dtr:
                try:
                    await self.dtr.update_submodel_descriptor(
                        aas_id,
                        submodel_id,
                        submodel_descriptor,
                    )
                    dtr_registered = True
                except DTRClientError as e:
                    logger.warning("Failed to update DTR: %s", e)

            aas_endpoint = f"{self.basyx.base_url}/shells/{BaSyxClient.encode_id(aas_id)}"

            return PublicationResult(
                success=True,
                aas_id=aas_id,
                submodel_id=submodel_id,
                aas_endpoint=aas_endpoint,
                dtr_registered=dtr_registered,
            )

        except Exception as e:
            logger.exception("Failed to update submodel")
            raise AASPublisherError(
                f"Update failed: {str(e)}",
                step="update",
                cause=e,
            )

    async def unpublish_submodel(
        self,
        aas_id: str,
        submodel_id: str,
    ) -> bool:
        """
        Unpublish a submodel from BaSyx and DTR.

        Args:
            aas_id: AAS ID
            submodel_id: Submodel ID

        Returns:
            True if successfully unpublished
        """
        logger.info(
            "Unpublishing submodel: aas_id=%s, submodel_id=%s",
            aas_id,
            submodel_id,
        )

        success = True

        # Remove from DTR first
        if self.dtr:
            try:
                await self.dtr.delete_submodel_descriptor(aas_id, submodel_id)
            except DTRClientError as e:
                logger.warning("Failed to remove from DTR: %s", e)
                success = False

        # Remove from BaSyx
        try:
            await self.basyx.delete_submodel(aas_id, submodel_id)
        except BaSyxClientError as e:
            logger.warning("Failed to remove from BaSyx: %s", e)
            success = False

        # Optionally delete the shell if no more submodels
        try:
            submodels, _ = await self.basyx.get_all_submodels(aas_id)
            if not submodels:
                await self.basyx.delete_aas(aas_id)
                if self.dtr:
                    try:
                        await self.dtr.delete_shell_descriptor(aas_id)
                    except DTRClientError:
                        pass
        except BaSyxClientError:
            pass

        return success

    async def get_publication_status(
        self,
        aas_id: str,
        submodel_id: str,
    ) -> dict[str, Any]:
        """
        Get the status of a published submodel.

        Args:
            aas_id: AAS ID
            submodel_id: Submodel ID

        Returns:
            Status dictionary
        """
        status: dict[str, Any] = {
            "aas_id": aas_id,
            "submodel_id": submodel_id,
            "basyx": {"registered": False},
            "dtr": {"registered": False},
        }

        # Check BaSyx
        submodel = await self.basyx.get_submodel(aas_id, submodel_id)
        if submodel:
            status["basyx"]["registered"] = True
            status["basyx"]["descriptor"] = submodel

        # Check DTR
        if self.dtr:
            submodel_desc = await self.dtr.get_submodel_descriptor(aas_id, submodel_id)
            if submodel_desc:
                status["dtr"]["registered"] = True
                status["dtr"]["descriptor"] = submodel_desc

        return status

    # -------------------------------------------------------------------------
    # Internal Methods
    # -------------------------------------------------------------------------

    async def _hydrate_to_json(
        self,
        template_aasx_bytes: bytes,
        form_data: dict[str, Any],
        aas_id: str,
        submodel_id: str,
    ) -> dict[str, Any]:
        """Hydrate template and return as JSON dict."""
        try:
            # Use hydrator to get JSON string
            json_str = self.hydrator.hydrate_to_json(template_aasx_bytes, form_data)
            parsed = json.loads(json_str)

            # Update IDs in the parsed structure
            for item in parsed.get("assetAdministrationShells", []):
                item["id"] = aas_id

            for item in parsed.get("submodels", []):
                item["id"] = submodel_id

            return parsed
        except Exception as e:
            raise AASPublisherError(
                f"Hydration failed: {str(e)}",
                step="hydrate",
                cause=e,
            )

    def _build_shell_descriptor(
        self,
        aas_id: str,
        submodel_id: str,
        hydrated_json: dict[str, Any],
        asset_ids: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Build AAS Shell Descriptor from hydrated data."""
        # Extract info from hydrated JSON
        aas_data = {}
        for item in hydrated_json.get("assetAdministrationShells", []):
            aas_data = item
            break

        # Build specificAssetIds
        specific_asset_ids = asset_ids or []

        descriptor = {
            "id": aas_id,
            "idShort": aas_data.get("idShort", "DefaultAAS"),
            "description": aas_data.get("description", []),
            "specificAssetIds": specific_asset_ids,
            "submodelDescriptors": [],  # Will be populated separately
            "endpoints": [
                {
                    "interface": "AAS-3.0",
                    "protocolInformation": {
                        "href": f"{self.basyx.base_url}/shells/{BaSyxClient.encode_id(aas_id)}",
                        "endpointProtocol": "HTTP",
                        "endpointProtocolVersion": ["1.1"],
                    },
                }
            ],
        }

        # Add asset information if available
        asset_info = aas_data.get("assetInformation", {})
        if asset_info:
            descriptor["assetKind"] = asset_info.get("assetKind", "Instance")
            if asset_info.get("globalAssetId"):
                descriptor["globalAssetId"] = asset_info["globalAssetId"]

        return descriptor

    def _build_submodel_descriptor(
        self,
        submodel_id: str,
        hydrated_json: dict[str, Any],
    ) -> dict[str, Any]:
        """Build Submodel Descriptor from hydrated data."""
        # Extract info from hydrated JSON
        submodel_data = {}
        for item in hydrated_json.get("submodels", []):
            submodel_data = item
            break

        descriptor = {
            "id": submodel_id,
            "idShort": submodel_data.get("idShort", "DefaultSubmodel"),
            "description": submodel_data.get("description", []),
            "endpoints": [
                {
                    "interface": "SUBMODEL-3.0",
                    "protocolInformation": {
                        "href": f"{self.basyx.base_url}/submodels/{BaSyxClient.encode_id(submodel_id)}",
                        "endpointProtocol": "HTTP",
                        "endpointProtocolVersion": ["1.1"],
                    },
                }
            ],
        }

        # Add semantic ID if available
        semantic_id = submodel_data.get("semanticId")
        if semantic_id:
            descriptor["semanticId"] = semantic_id

        # Add administration if available
        administration = submodel_data.get("administration")
        if administration:
            descriptor["administration"] = administration

        return descriptor

    async def _register_aas_in_basyx(
        self,
        shell_descriptor: dict[str, Any],
    ) -> None:
        """Register AAS in BaSyx, handling conflicts."""
        try:
            await self.basyx.register_aas(shell_descriptor)
        except BaSyxConflictError:
            # AAS already exists, update instead
            aas_id = shell_descriptor["id"]
            logger.info("AAS %s already exists, updating", aas_id)
            await self.basyx.update_aas(aas_id, shell_descriptor)
        except BaSyxClientError as e:
            raise AASPublisherError(
                f"BaSyx AAS registration failed: {str(e)}",
                step="basyx_aas",
                cause=e,
            )

    async def _register_submodel_in_basyx(
        self,
        aas_id: str,
        submodel_descriptor: dict[str, Any],
    ) -> None:
        """Register Submodel in BaSyx, handling conflicts."""
        submodel_id = submodel_descriptor["id"]

        try:
            await self.basyx.register_submodel(aas_id, submodel_descriptor)
        except BaSyxConflictError:
            # Submodel already exists, update instead
            logger.info("Submodel %s already exists, updating", submodel_id)
            await self.basyx.update_submodel(aas_id, submodel_id, submodel_descriptor)
        except BaSyxClientError as e:
            raise AASPublisherError(
                f"BaSyx Submodel registration failed: {str(e)}",
                step="basyx_submodel",
                cause=e,
            )

    async def _register_in_dtr(
        self,
        shell_descriptor: dict[str, Any],
        submodel_descriptor: dict[str, Any],
    ) -> bool:
        """Register in DTR, returning success status."""
        if not self.dtr:
            return False

        aas_id = shell_descriptor["id"]
        submodel_id = submodel_descriptor["id"]

        try:
            # Register shell
            try:
                await self.dtr.create_shell_descriptor(shell_descriptor)
            except DTRConflictError:
                logger.info("Shell %s already exists in DTR, updating", aas_id)
                await self.dtr.update_shell_descriptor(aas_id, shell_descriptor)

            # Register submodel
            try:
                await self.dtr.create_submodel_descriptor(aas_id, submodel_descriptor)
            except DTRConflictError:
                logger.info("Submodel %s already exists in DTR, updating", submodel_id)
                await self.dtr.update_submodel_descriptor(
                    aas_id, submodel_id, submodel_descriptor
                )

            return True

        except DTRClientError as e:
            logger.warning("DTR registration failed: %s", e)
            return False

    # -------------------------------------------------------------------------
    # Context Manager Support
    # -------------------------------------------------------------------------

    async def close(self) -> None:
        """Close all client connections."""
        await self.basyx.close()
        if self.dtr:
            await self.dtr.close()

    async def __aenter__(self) -> "AASPublisher":
        """Enter async context."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context and close clients."""
        await self.close()
