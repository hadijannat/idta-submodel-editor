"""
Dataspace Connector API endpoints.

Provides REST API for managing dataspace connections, publications,
and policies. Implements the onboarding workflow for connecting to
Manufacturing-X / Catena-X dataspaces.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from app.config import get_settings
from app.dependencies import get_current_user
from app.errors import APIError, ErrorCode
from app.schemas.dataspace import (
    # Enums
    AccessType,
    DataspaceConnectionStatus,
    PublicationStatus,
    # Connection types
    CreateConnectionRequest,
    CreateConnectionResponse,
    ConnectionStatusResponse,
    DataspaceConnection,
    DisconnectRequest,
    DisconnectResponse,
    ListConnectionsResponse,
    # Publication types
    ListPublicationsResponse,
    PolicyConfig,
    PublishSubmodelRequest,
    PublishSubmodelResponse,
    SubmodelPublication,
    UnpublishRequest,
    UnpublishResponse,
    UpdatePolicyRequest,
    UpdatePolicyResponse,
    # Health types
    HealthCheckResponse,
    HealthCheckResult,
)
from app.services.dataspace.connection_manager import ConnectionManager
from app.services.dataspace.health import DataspaceHealthChecker
from app.services.dataspace.identity.vault_client import VaultClient
from app.services.dataspace.models import (
    ConnectionStatus as InternalConnectionStatus,
    DataspaceType,
)
from app.services.dataspace.policy.engine import PolicyEngine
from app.services.dataspace.policy.store import PolicyStore
from app.services.dataspace.policy.odrl_builder import ODRLBuilder
from app.services.dataspace.policy.templates import PolicyTemplates

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dataspace", tags=["dataspace"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def get_connection_manager() -> ConnectionManager:
    """Get connection manager instance."""
    return ConnectionManager()


def get_health_checker() -> DataspaceHealthChecker:
    """Get health checker instance."""
    return DataspaceHealthChecker()


def get_policy_engine() -> PolicyEngine:
    """Get policy engine instance."""
    return PolicyEngine()


def get_policy_store() -> PolicyStore:
    """Get policy store instance."""
    return PolicyStore()


def _check_dataspace_enabled() -> None:
    """Check if dataspace feature is enabled, raise error if not."""
    settings = get_settings()
    if not settings.dataspace_enabled:
        raise APIError(
            code=ErrorCode.FEATURE_DISABLED,
            message="Dataspace integration is disabled",
            detail={"hint": "Set DATASPACE_ENABLED=true to enable"},
        )


def _get_owner_id(user: dict | None) -> str | None:
    """Extract owner identifier from user payload."""
    if not user:
        return None
    return user.get("sub") or user.get("email") or user.get("preferred_username")


def _assert_owner(connection, user: dict | None) -> None:
    """Ensure the current user owns the connection if auth is enabled."""
    owner_id = _get_owner_id(user)
    if owner_id and connection.owner_id and connection.owner_id != owner_id:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Access denied for this connection",
            status_code=403,
        )


def _map_internal_status(status: InternalConnectionStatus) -> DataspaceConnectionStatus:
    """Map internal connection status to API status."""
    status_map = {
        InternalConnectionStatus.DISCONNECTED: DataspaceConnectionStatus.DISCONNECTED,
        InternalConnectionStatus.CONNECTING: DataspaceConnectionStatus.CONFIGURING_EDC,
        InternalConnectionStatus.CONNECTED: DataspaceConnectionStatus.CONNECTED,
        InternalConnectionStatus.DEGRADED: DataspaceConnectionStatus.DEGRADED,
        InternalConnectionStatus.ERROR: DataspaceConnectionStatus.FAILED,
        InternalConnectionStatus.AUTHENTICATING: DataspaceConnectionStatus.PROVISIONING_SECRETS,
    }
    return status_map.get(status, DataspaceConnectionStatus.NOT_CONNECTED)


def _map_dataspace_type(env: str) -> DataspaceType:
    """Map environment string to DataspaceType."""
    if env == "sandbox":
        return DataspaceType.SANDBOX
    elif env.startswith("catena-x"):
        return DataspaceType.CATENA_X
    elif env.startswith("manufacturing-x"):
        return DataspaceType.MANUFACTURING_X
    return DataspaceType.SANDBOX


def _connection_to_response(conn) -> DataspaceConnection:
    """Convert internal connection state to API response model."""
    settings = get_settings()
    return DataspaceConnection(
        connection_id=conn.connection_id,
        status=_map_internal_status(conn.status),
        environment=conn.metadata.get("environment", settings.dataspace_default_environment),
        edc_mode=conn.metadata.get("edc_mode", settings.dataspace_default_edc_mode),
        bpn=conn.bpn,
        basyx_url=conn.metadata.get("basyx_url"),
        dtr_url=conn.dtr_url,
        edc_control_url=conn.edc_url,
        edc_data_url=conn.metadata.get("edc_data_url"),
        progress=conn.metadata.get("progress", 0.0),
        progress_message=conn.metadata.get("progress_message"),
        error_message=conn.error_message,
        last_health_check=conn.last_health_check,
        created_at=conn.created_at,
        updated_at=conn.updated_at,
    )


# ---------------------------------------------------------------------------
# Connection Lifecycle Endpoints
# ---------------------------------------------------------------------------


@router.post("/connections", response_model=CreateConnectionResponse, status_code=201)
async def create_connection(
    request: CreateConnectionRequest,
    conn_manager: Annotated[ConnectionManager, Depends(get_connection_manager)],
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> CreateConnectionResponse:
    """
    Start the dataspace onboarding process.

    Creates a new connection and initiates background provisioning of
    secrets, EDC configuration, connector registration, and self-description
    publication.

    Returns a job_id that can be polled for progress.
    """
    _check_dataspace_enabled()
    settings = get_settings()

    try:
        if request.environment != "sandbox":
            if not request.credentials:
                raise APIError(
                    code=ErrorCode.BAD_REQUEST,
                    message="Credentials are required for non-sandbox environments",
                )
            if not settings.vault_token or not settings.vault_url:
                raise APIError(
                    code=ErrorCode.UPSTREAM_UNAVAILABLE,
                    message="Vault is required for non-sandbox environments",
                    detail={"hint": "Configure VAULT_URL and VAULT_TOKEN"},
                )

        owner_id = _get_owner_id(user)

        # Create connection record
        connection = conn_manager.create_connection(
            dataspace_type=_map_dataspace_type(request.environment),
            dtr_url=settings.dtr_url,
            edc_url=settings.edc_control_plane_url,
            bpn=request.bpn,
            owner_id=owner_id,
            metadata={
                "environment": request.environment,
                "edc_mode": request.edc_mode,
                "basyx_url": settings.basyx_aas_server_url,
                "edc_data_url": settings.edc_data_plane_url,
                "progress": 0.0,
                "progress_message": "Connection created, starting onboarding...",
            },
        )

        # Store credentials in Vault if provided
        if request.credentials:
            vault = VaultClient(
                vault_url=settings.vault_url,
                token=settings.vault_token,
            )
            stored = await vault.store_credentials(connection.connection_id, request.credentials)
            if not stored:
                conn_manager.delete_connection(connection.connection_id)
                raise APIError(
                    code=ErrorCode.UPSTREAM_ERROR,
                    message="Failed to store credentials in Vault",
                )
            conn_manager.update_connection(
                connection.connection_id,
                metadata={
                    **(connection.metadata or {}),
                    "vault_path": f"dataspace/connections/{connection.connection_id}/credentials",
                },
            )

        # Update status to connecting
        conn_manager.update_connection(
            connection.connection_id,
            status=InternalConnectionStatus.CONNECTING,
        )

        # Queue background onboarding task
        try:
            from app.services.dataspace.tasks import onboard_connection

            onboard_connection.delay(connection.connection_id)
            logger.info("Queued onboarding for connection %s", connection.connection_id)
        except Exception as e:
            logger.warning("Celery unavailable, onboarding will need to be triggered manually: %s", e)

        return CreateConnectionResponse(
            connection=_connection_to_response(connection),
            message="Connection created. Onboarding in progress.",
        )

    except APIError:
        raise
    except Exception as e:
        logger.exception("Failed to create dataspace connection")
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to create dataspace connection",
        )


@router.get("/connections", response_model=ListConnectionsResponse)
async def list_connections(
    conn_manager: Annotated[ConnectionManager, Depends(get_connection_manager)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> ListConnectionsResponse:
    """
    List all dataspace connections.

    Returns all connections with their current status and configuration.
    """
    _check_dataspace_enabled()

    try:
        owner_id = _get_owner_id(user)
        connections = conn_manager.list_connections(limit=limit, owner_id=owner_id)
        return ListConnectionsResponse(
            connections=[_connection_to_response(c) for c in connections],
            total=len(connections),
        )
    except Exception as e:
        logger.exception("Failed to list connections")
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to list connections",
        )


@router.get("/connections/{connection_id}", response_model=ConnectionStatusResponse)
async def get_connection(
    connection_id: str,
    conn_manager: Annotated[ConnectionManager, Depends(get_connection_manager)],
    health_checker: Annotated[DataspaceHealthChecker, Depends(get_health_checker)],
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> ConnectionStatusResponse:
    """
    Get the status of a specific connection.

    Returns full connection details including recent health check results.
    """
    _check_dataspace_enabled()

    connection = conn_manager.get_connection(connection_id)
    if connection is None:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Connection not found",
            detail={"connection_id": connection_id},
        )
    _assert_owner(connection, user)
    _assert_owner(connection, user)

    # Get health check results
    settings = get_settings()
    secrets = {}
    vault = VaultClient(
        vault_url=settings.vault_url if hasattr(settings, "vault_url") else None,
        token=settings.vault_token if hasattr(settings, "vault_token") else None,
    )
    if vault.is_configured:
        generic_creds = await vault.get_credentials(connection_id)
        if generic_creds:
            secrets.update(generic_creds)
        edc_creds = await vault.get_edc_credentials(connection_id)
        if edc_creds:
            secrets.setdefault("edc_api_key", edc_creds.get("api_key"))
        dtr_creds = await vault.get_dtr_credentials(connection_id)
        if dtr_creds:
            secrets.setdefault("dtr_token", dtr_creds.get("token"))

    health_results = health_checker.check_connection(connection, secrets=secrets or None)
    api_health_results = [
        HealthCheckResult(
            component=r.component,
            healthy=r.healthy,
            latency_ms=r.latency_ms,
            message=r.message,
            checked_at=r.checked_at,
        )
        for r in health_results
    ]

    return ConnectionStatusResponse(
        connection=_connection_to_response(connection),
        health_checks=api_health_results,
    )


@router.delete("/connections/{connection_id}", response_model=DisconnectResponse)
async def disconnect(
    connection_id: str,
    request: DisconnectRequest | None = None,
    conn_manager: Annotated[ConnectionManager, Depends(get_connection_manager)] = None,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> DisconnectResponse:
    """
    Disconnect from a dataspace.

    Optionally unpublishes all assets and cleans up EDC configuration.
    """
    _check_dataspace_enabled()

    if request is None:
        request = DisconnectRequest()

    connection = conn_manager.get_connection(connection_id)
    if connection is None:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Connection not found",
            detail={"connection_id": connection_id},
        )
    _assert_owner(connection, user)

    # Check for active publications
    registrations = conn_manager.list_registrations(connection_id=connection_id)
    active_registrations = [r for r in registrations if r.status.value != "failed"]

    if active_registrations and not request.force and not request.unpublish_all:
        raise APIError(
            code=ErrorCode.RESOURCE_CONFLICT,
            message=f"Connection has {len(active_registrations)} active publications",
            detail={"hint": "Use force=true or unpublish_all=true to proceed"},
        )

    unpublished_count = 0
    if request.unpublish_all:
        unpublished_count = len(active_registrations)
        try:
            from app.services.dataspace.tasks import unpublish_publication_task

            for registration in active_registrations:
                unpublish_publication_task.delay(
                    registration.registration_id,
                    remove_from_registry=request.unpublish_all,
                    remove_from_edc=True,
                )
            logger.info("Queued unpublish for %d assets", unpublished_count)
        except Exception as e:
            logger.warning("Celery unavailable for unpublish_all: %s", e)

    # Delete the connection
    deleted = conn_manager.delete_connection(connection_id)
    if not deleted:
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to delete connection",
        )

    return DisconnectResponse(
        connection_id=connection_id,
        status=DataspaceConnectionStatus.DISCONNECTED,
        unpublished_count=unpublished_count,
        message="Connection disconnected successfully.",
    )


@router.post("/connections/{connection_id}/reconnect", response_model=CreateConnectionResponse)
async def reconnect(
    connection_id: str,
    conn_manager: Annotated[ConnectionManager, Depends(get_connection_manager)],
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> CreateConnectionResponse:
    """
    Attempt to reconnect a failed or disconnected connection.

    Re-runs the onboarding workflow to restore connectivity.
    """
    _check_dataspace_enabled()

    connection = conn_manager.get_connection(connection_id)
    if connection is None:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Connection not found",
            detail={"connection_id": connection_id},
        )

    # Reset status and re-queue onboarding
    conn_manager.update_connection(
        connection_id,
        status=InternalConnectionStatus.CONNECTING,
        error_message=None,
        progress=0.0,
        progress_message="Reconnecting...",
    )

    # Queue background onboarding task
    try:
        from app.services.dataspace.tasks import onboard_connection

        onboard_connection.delay(connection_id)
        logger.info("Queued reconnection for %s", connection_id)
    except Exception as e:
        logger.warning("Celery unavailable: %s", e)

    # Refresh connection state
    connection = conn_manager.get_connection(connection_id)

    return CreateConnectionResponse(
        connection=_connection_to_response(connection),
        message="Reconnection initiated.",
    )


# ---------------------------------------------------------------------------
# Publication Endpoints
# ---------------------------------------------------------------------------


@router.post("/publications", response_model=PublishSubmodelResponse, status_code=201)
async def publish_submodel(
    request: PublishSubmodelRequest,
    conn_manager: Annotated[ConnectionManager, Depends(get_connection_manager)],
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> PublishSubmodelResponse:
    """
    Publish a submodel to a dataspace.

    Creates an AAS in BaSyx, registers in DTR, creates EDC asset with policy.
    Returns immediately with publication ID; actual publishing happens in background.
    """
    _check_dataspace_enabled()

    # Verify connection exists and is connected
    connection = conn_manager.get_connection(request.connection_id)
    if connection is None:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Connection not found",
            detail={"connection_id": request.connection_id},
        )
    _assert_owner(connection, user)

    if connection.status != InternalConnectionStatus.CONNECTED:
        raise APIError(
            code=ErrorCode.RESOURCE_CONFLICT,
            message="Connection is not active",
            detail={"current_status": connection.status.value},
        )

    import uuid

    # Generate IDs if not provided
    aas_id = request.aas_id or f"urn:aas:{uuid.uuid4()}"
    submodel_id = request.submodel_id or f"urn:submodel:{uuid.uuid4()}"

    # Create registration record
    registration = conn_manager.create_registration(
        connection_id=request.connection_id,
        aas_id=aas_id,
        submodel_id=submodel_id,
        metadata={
            "template_name": request.template_name,
            "template_status": request.template_status,
            "template_version": request.template_version,
            "form_data": request.form_data,
            "policy": request.policy.model_dump() if request.policy else None,
        },
    )

    # Queue background publication task
    try:
        from app.services.dataspace.tasks import publish_submodel_task

        publish_submodel_task.delay(registration.registration_id)
        logger.info("Queued publication for registration %s", registration.registration_id)
    except Exception as e:
        logger.warning("Celery unavailable: %s", e)

    # Build response
    publication = SubmodelPublication(
        publication_id=registration.registration_id,
        connection_id=request.connection_id,
        template_name=request.template_name,
        submodel_id=submodel_id,
        status=PublicationStatus.PENDING,
        created_at=registration.created_at,
        updated_at=registration.updated_at,
    )

    return PublishSubmodelResponse(
        publication=publication,
        message="Publication initiated. Processing in background.",
    )


@router.get("/publications", response_model=ListPublicationsResponse)
async def list_publications(
    conn_manager: Annotated[ConnectionManager, Depends(get_connection_manager)],
    connection_id: Annotated[str | None, Query()] = None,
    template_name: Annotated[str | None, Query()] = None,
    status: Annotated[PublicationStatus | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> ListPublicationsResponse:
    """
    List submodel publications.

    Supports filtering by connection, template, and status.
    """
    _check_dataspace_enabled()

    try:
        owner_id = _get_owner_id(user)
        allowed_connection_ids = None
        if owner_id:
            allowed_connection_ids = {
                conn.connection_id
                for conn in conn_manager.list_connections(owner_id=owner_id, limit=100)
            }

        if connection_id and allowed_connection_ids is not None:
            if connection_id not in allowed_connection_ids:
                raise APIError(
                    code=ErrorCode.RESOURCE_NOT_FOUND,
                    message="Access denied for this connection",
                    status_code=403,
                )

        registrations = conn_manager.list_registrations(
            connection_id=connection_id,
            limit=limit,
        )
        if allowed_connection_ids is not None:
            registrations = [
                reg for reg in registrations
                if reg.connection_id in allowed_connection_ids
            ]

        # Apply filters
        publications = []
        for reg in registrations:
            # Filter by template name
            if template_name and reg.metadata.get("template_name") != template_name:
                continue

            # Map internal status to API status
            pub_status = _map_registration_status(reg.status)

            # Filter by status
            if status and pub_status != status:
                continue

            publications.append(
                SubmodelPublication(
                    publication_id=reg.registration_id,
                    connection_id=reg.connection_id,
                    template_name=reg.metadata.get("template_name", "unknown"),
                    submodel_id=reg.submodel_id,
                    status=pub_status,
                    aas_endpoint=reg.metadata.get("aas_endpoint"),
                    dtr_asset_id=reg.dtr_asset_id,
                    edc_offer_id=reg.edc_asset_id,
                    policy_id=reg.metadata.get("policy_id"),
                    created_at=reg.created_at,
                    updated_at=reg.updated_at,
                )
            )

        return ListPublicationsResponse(
            publications=publications,
            total=len(publications),
        )

    except Exception as e:
        logger.exception("Failed to list publications")
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to list publications",
        )


def _map_registration_status(status) -> PublicationStatus:
    """Map internal registration status to API publication status."""
    from app.services.dataspace.models import RegistrationStatus

    status_map = {
        RegistrationStatus.PENDING: PublicationStatus.PENDING,
        RegistrationStatus.REGISTERED: PublicationStatus.PUBLISHED,
        RegistrationStatus.FAILED: PublicationStatus.FAILED,
        RegistrationStatus.UPDATING: PublicationStatus.UPDATING,
        RegistrationStatus.UNPUBLISHING: PublicationStatus.UNPUBLISHING,
        RegistrationStatus.UNPUBLISHED: PublicationStatus.UNPUBLISHED,
    }
    return status_map.get(status, PublicationStatus.PENDING)


@router.get("/publications/{publication_id}", response_model=SubmodelPublication)
async def get_publication(
    publication_id: str,
    conn_manager: Annotated[ConnectionManager, Depends(get_connection_manager)],
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> SubmodelPublication:
    """
    Get details of a specific publication.
    """
    _check_dataspace_enabled()

    registration = conn_manager.get_registration(publication_id)
    if registration is None:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Publication not found",
            detail={"publication_id": publication_id},
        )
    connection = conn_manager.get_connection(registration.connection_id)
    if connection is None:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Connection not found",
            detail={"connection_id": connection_id},
        )
    _assert_owner(connection, user)

    return SubmodelPublication(
        publication_id=registration.registration_id,
        connection_id=registration.connection_id,
        template_name=registration.metadata.get("template_name", "unknown"),
        submodel_id=registration.submodel_id,
        status=_map_registration_status(registration.status),
        aas_endpoint=registration.metadata.get("aas_endpoint"),
        dtr_asset_id=registration.dtr_asset_id,
        edc_offer_id=registration.edc_asset_id,
        policy_id=registration.metadata.get("policy_id"),
        created_at=registration.created_at,
        updated_at=registration.updated_at,
    )


@router.put("/publications/{publication_id}", response_model=SubmodelPublication)
async def update_publication(
    publication_id: str,
    request: PublishSubmodelRequest,
    conn_manager: Annotated[ConnectionManager, Depends(get_connection_manager)],
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> SubmodelPublication:
    """
    Update a published submodel's data.

    Re-hydrates and re-publishes the submodel with new form data.
    """
    _check_dataspace_enabled()

    registration = conn_manager.get_registration(publication_id)
    if registration is None:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Publication not found",
            detail={"publication_id": publication_id},
        )
    connection = conn_manager.get_connection(registration.connection_id)
    if connection is None:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Connection not found",
            detail={"connection_id": connection_id},
        )
    _assert_owner(connection, user)

    # Update metadata
    from app.services.dataspace.models import RegistrationStatus

    conn_manager.update_registration(
        publication_id,
        status=RegistrationStatus.UPDATING,
    )

    # Update stored form data in metadata
    registration.metadata["form_data"] = request.form_data
    if request.policy:
        registration.metadata["policy"] = request.policy.model_dump()

    # Queue background update task
    try:
        from app.services.dataspace.tasks import update_publication_task

        update_publication_task.delay(publication_id)
        logger.info("Queued update for publication %s", publication_id)
    except Exception as e:
        logger.warning("Celery unavailable: %s", e)

    # Refresh registration
    registration = conn_manager.get_registration(publication_id)

    return SubmodelPublication(
        publication_id=registration.registration_id,
        connection_id=registration.connection_id,
        template_name=registration.metadata.get("template_name", "unknown"),
        submodel_id=registration.submodel_id,
        status=_map_registration_status(registration.status),
        aas_endpoint=registration.metadata.get("aas_endpoint"),
        dtr_asset_id=registration.dtr_asset_id,
        edc_offer_id=registration.edc_asset_id,
        policy_id=registration.metadata.get("policy_id"),
        created_at=registration.created_at,
        updated_at=registration.updated_at,
    )


@router.delete("/publications/{publication_id}", response_model=UnpublishResponse)
async def unpublish(
    publication_id: str,
    request: UnpublishRequest | None = None,
    conn_manager: Annotated[ConnectionManager, Depends(get_connection_manager)] = None,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> UnpublishResponse:
    """
    Unpublish a submodel from the dataspace.

    Removes the asset from EDC and optionally from DTR.
    """
    _check_dataspace_enabled()

    if request is None:
        request = UnpublishRequest()

    registration = conn_manager.get_registration(publication_id)
    if registration is None:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Publication not found",
            detail={"publication_id": publication_id},
        )
    connection = conn_manager.get_connection(registration.connection_id)
    if connection is None:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Connection not found",
            detail={"connection_id": connection_id},
        )
    _assert_owner(connection, user)

    # TODO: Implement actual unpublishing via EDC/DTR clients
    from app.services.dataspace.models import RegistrationStatus

    conn_manager.update_registration(
        publication_id,
        status=RegistrationStatus.UNPUBLISHING,
    )

    try:
        from app.services.dataspace.tasks import unpublish_publication_task

        unpublish_publication_task.delay(
            publication_id,
            remove_from_registry=request.remove_from_registry if request else True,
            remove_from_edc=request.remove_from_edc if request else True,
        )
        logger.info("Queued unpublish for publication %s", publication_id)
    except Exception as e:
        logger.warning("Celery unavailable: %s", e)

    return UnpublishResponse(
        publication_id=publication_id,
        status=PublicationStatus.UNPUBLISHING,
        message="Publication unpublish initiated.",
    )


# ---------------------------------------------------------------------------
# Policy Endpoints
# ---------------------------------------------------------------------------


@router.get("/policies/templates")
async def get_policy_templates(
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> list[dict]:
    """
    Get available policy templates.

    Returns a list of pre-built policy templates for common use cases.
    """
    _check_dataspace_enabled()

    return [
        {
            "id": "unrestricted",
            "name": "Unrestricted Use",
            "description": "Allows any consumer to use the data without constraints. Use with caution.",
            "access_type": AccessType.PUBLIC.value,
        },
        {
            "id": "membership_required",
            "name": "Membership Required",
            "description": "Restricts access to consumers with active dataspace membership.",
            "access_type": AccessType.MEMBERSHIP.value,
        },
        {
            "id": "bpn_restricted",
            "name": "BPN Restricted",
            "description": "Restricts access to specific Business Partner Numbers.",
            "access_type": AccessType.RESTRICTED.value,
        },
        {
            "id": "pcf_data_exchange",
            "name": "PCF Data Exchange",
            "description": "Policy for Product Carbon Footprint data exchange per Catena-X guidelines.",
            "access_type": AccessType.MEMBERSHIP.value,
        },
        {
            "id": "digital_twin_access",
            "name": "Digital Twin Access",
            "description": "Standard policy for Digital Twin / AAS data sharing.",
            "access_type": AccessType.MEMBERSHIP.value,
        },
        {
            "id": "traceability_data",
            "name": "Traceability Data",
            "description": "Policy for supply chain traceability data exchange.",
            "access_type": AccessType.MEMBERSHIP.value,
        },
    ]


@router.post("/policies/preview")
async def preview_policy(
    policy_config: PolicyConfig,
    policy_engine: Annotated[PolicyEngine, Depends(get_policy_engine)],
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> dict:
    """
    Preview the ODRL policy that would be generated from the configuration.

    Returns the full ODRL policy document without actually creating it.
    """
    _check_dataspace_enabled()

    try:
        # Build ODRL based on access type and configuration
        if policy_config.access_type == AccessType.PUBLIC:
            odrl = PolicyTemplates.unrestricted_use()
        elif policy_config.access_type == AccessType.MEMBERSHIP:
            odrl = PolicyTemplates.membership_required()
        elif policy_config.access_type == AccessType.RESTRICTED:
            if policy_config.allowed_partners:
                odrl = PolicyTemplates.bpn_restricted(policy_config.allowed_partners)
            else:
                odrl = PolicyTemplates.membership_required()
        else:
            odrl = PolicyTemplates.membership_required()

        # Add custom constraints if provided
        if policy_config.constraints:
            # Build custom policy with additional constraints
            builder = ODRLBuilder().as_offer().with_catena_x_profile()
            perm_builder = builder.add_permission("use")

            for constraint in policy_config.constraints:
                perm_builder.with_constraint(
                    constraint.left_operand,
                    constraint.operator.value,
                    constraint.right_operand,
                )

            if policy_config.access_type == AccessType.MEMBERSHIP:
                perm_builder.with_membership_constraint("active")

            if policy_config.allowed_partners:
                perm_builder.with_bpn_constraint(policy_config.allowed_partners)

            odrl = perm_builder.done().build()

        # Validate the generated policy
        is_valid, errors = policy_engine.validate_policy(odrl)

        return {
            "odrl": odrl,
            "valid": is_valid,
            "validation_errors": errors if not is_valid else [],
        }

    except Exception as e:
        logger.exception("Failed to preview policy")
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to preview policy",
        )


@router.post("/policies", status_code=201)
async def create_policy(
    policy_config: PolicyConfig,
    policy_engine: Annotated[PolicyEngine, Depends(get_policy_engine)],
    policy_store: Annotated[PolicyStore, Depends(get_policy_store)],
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> dict:
    """
    Create a new policy from configuration.

    Generates ODRL policy and stores it for use with publications.
    """
    _check_dataspace_enabled()

    import uuid

    try:
        policy_id = f"urn:policy:{uuid.uuid4()}"

        # Build ODRL based on access type
        if policy_config.access_type == AccessType.PUBLIC:
            odrl = PolicyTemplates.unrestricted_use(policy_id=policy_id)
        elif policy_config.access_type == AccessType.RESTRICTED and policy_config.allowed_partners:
            odrl = PolicyTemplates.bpn_restricted(
                policy_config.allowed_partners,
                policy_id=policy_id,
            )
        else:
            odrl = PolicyTemplates.membership_required(policy_id=policy_id)

        # Validate
        is_valid, errors = policy_engine.validate_policy(odrl)
        if not is_valid:
            raise APIError(
                code=ErrorCode.VALIDATION_FAILED,
                message="Invalid policy configuration",
                detail={"errors": errors},
            )

        record = policy_store.create(
            policy_id=policy_id,
            config=policy_config.model_dump(),
            odrl=odrl,
            owner_id=_get_owner_id(user),
        )

        return record

    except APIError:
        raise
    except Exception as e:
        logger.exception("Failed to create policy")
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to create policy",
        )


@router.get("/policies/{policy_id}")
async def get_policy(
    policy_id: str,
    policy_store: Annotated[PolicyStore, Depends(get_policy_store)],
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> dict:
    """
    Get a policy by ID.

    Returns the ODRL policy document and configuration.
    """
    _check_dataspace_enabled()

    record = policy_store.get(policy_id)
    if record is None:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Policy not found",
            detail={"policy_id": policy_id},
        )
    owner_id = _get_owner_id(user)
    if owner_id and record.get("owner_id") and record.get("owner_id") != owner_id:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Access denied for this policy",
            status_code=403,
        )
    return record


@router.put("/policies/{policy_id}")
async def update_policy(
    policy_id: str,
    policy_config: PolicyConfig,
    policy_store: Annotated[PolicyStore, Depends(get_policy_store)],
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> dict:
    """
    Update an existing policy.

    Regenerates the ODRL policy with new configuration.
    """
    _check_dataspace_enabled()

    record = policy_store.get(policy_id)
    if record is None:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Policy not found",
            detail={"policy_id": policy_id},
        )
    owner_id = _get_owner_id(user)
    if owner_id and record.get("owner_id") and record.get("owner_id") != owner_id:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Access denied for this policy",
            status_code=403,
        )

    # Rebuild ODRL based on access type
    if policy_config.access_type == AccessType.PUBLIC:
        odrl = PolicyTemplates.unrestricted_use(policy_id=policy_id)
    elif policy_config.access_type == AccessType.RESTRICTED and policy_config.allowed_partners:
        odrl = PolicyTemplates.bpn_restricted(
            policy_config.allowed_partners,
            policy_id=policy_id,
        )
    else:
        odrl = PolicyTemplates.membership_required(policy_id=policy_id)

    updated = policy_store.update(
        policy_id=policy_id,
        config=policy_config.model_dump(),
        odrl=odrl,
    )
    if updated is None:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Policy not found",
            detail={"policy_id": policy_id},
        )
    return updated


@router.delete("/policies/{policy_id}")
async def delete_policy(
    policy_id: str,
    conn_manager: Annotated[ConnectionManager, Depends(get_connection_manager)] = None,
    policy_store: Annotated[PolicyStore, Depends(get_policy_store)] = None,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> dict:
    """
    Delete a policy.

    Policies in use by active publications cannot be deleted.
    """
    _check_dataspace_enabled()

    record = policy_store.get(policy_id)
    if record is None:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Policy not found",
            detail={"policy_id": policy_id},
        )
    owner_id = _get_owner_id(user)
    if owner_id and record.get("owner_id") and record.get("owner_id") != owner_id:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Access denied for this policy",
            status_code=403,
        )

    registrations = conn_manager.list_registrations(limit=200)
    for reg in registrations:
        if reg.metadata.get("policy_id") == policy_id and reg.status.value not in ("failed", "unpublished"):
            raise APIError(
                code=ErrorCode.RESOURCE_CONFLICT,
                message="Policy is in use by active publications",
                detail={"policy_id": policy_id},
            )

    deleted = policy_store.delete(policy_id)
    if not deleted:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Policy not found",
            detail={"policy_id": policy_id},
        )
    return {"policy_id": policy_id, "deleted": True}


# ---------------------------------------------------------------------------
# Health & Discovery Endpoints
# ---------------------------------------------------------------------------


@router.get("/health", response_model=HealthCheckResponse)
async def check_health(
    connection_id: Annotated[str | None, Query()] = None,
    conn_manager: Annotated[ConnectionManager, Depends(get_connection_manager)] = None,
    health_checker: Annotated[DataspaceHealthChecker, Depends(get_health_checker)] = None,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> HealthCheckResponse:
    """
    Check health of dataspace components.

    If connection_id is provided, checks that specific connection.
    Otherwise, returns general dataspace subsystem health.
    """
    _check_dataspace_enabled()
    settings = get_settings()

    now = datetime.utcnow()

    if connection_id:
        connection = conn_manager.get_connection(connection_id)
        if connection is None:
            raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Connection not found",
            detail={"connection_id": connection_id},
        )
        _assert_owner(connection, user)

        secrets = {}
        vault = VaultClient(
            vault_url=settings.vault_url if hasattr(settings, "vault_url") else None,
            token=settings.vault_token if hasattr(settings, "vault_token") else None,
        )
        if vault.is_configured:
            generic_creds = await vault.get_credentials(connection_id)
            if generic_creds:
                secrets.update(generic_creds)
            edc_creds = await vault.get_edc_credentials(connection_id)
            if edc_creds:
                secrets.setdefault("edc_api_key", edc_creds.get("api_key"))
            dtr_creds = await vault.get_dtr_credentials(connection_id)
            if dtr_creds:
                secrets.setdefault("dtr_token", dtr_creds.get("token"))

        health_results = health_checker.check_connection(connection, secrets=secrets or None)
        overall_healthy = all(r.healthy for r in health_results)

        # Update connection with health check timestamp
        conn_manager.update_connection(
            connection_id,
            last_health_check=now,
        )

        return HealthCheckResponse(
            connection_id=connection_id,
            overall_healthy=overall_healthy,
            status=_map_internal_status(connection.status),
            checks=[
                HealthCheckResult(
                    component=r.component,
                    healthy=r.healthy,
                    latency_ms=r.latency_ms,
                    message=r.message,
                    checked_at=r.checked_at,
                )
                for r in health_results
            ],
            checked_at=now,
        )

    # General health check (no specific connection)
    return HealthCheckResponse(
        connection_id="system",
        overall_healthy=settings.dataspace_enabled,
        status=DataspaceConnectionStatus.NOT_CONNECTED,
        checks=[
            HealthCheckResult(
                component="dataspace_enabled",
                healthy=settings.dataspace_enabled,
                message="Dataspace integration is enabled" if settings.dataspace_enabled else "Dataspace integration is disabled",
                checked_at=now,
            ),
        ],
        checked_at=now,
    )


@router.get("/environments")
async def get_environments(
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> list[dict]:
    """
    Get available dataspace environments.

    Returns configured environments that can be connected to.
    """
    _check_dataspace_enabled()
    settings = get_settings()

    environments = [
        {
            "id": "sandbox",
            "name": "Sandbox",
            "description": "Local development sandbox environment",
            "requires_bpn": False,
            "requires_credentials": False,
            "is_default": settings.dataspace_default_environment == "sandbox",
        },
        {
            "id": "catena-x-test",
            "name": "Catena-X Test",
            "description": "Catena-X integration testing environment",
            "requires_bpn": True,
            "requires_credentials": True,
            "is_default": settings.dataspace_default_environment == "catena-x-test",
        },
        {
            "id": "catena-x-prod",
            "name": "Catena-X Production",
            "description": "Catena-X production environment",
            "requires_bpn": True,
            "requires_credentials": True,
            "is_default": settings.dataspace_default_environment == "catena-x-prod",
        },
        {
            "id": "manufacturing-x",
            "name": "Manufacturing-X",
            "description": "Manufacturing-X dataspace environment",
            "requires_bpn": True,
            "requires_credentials": True,
            "is_default": settings.dataspace_default_environment == "manufacturing-x",
        },
    ]

    return environments


@router.get("/edc-modes")
async def get_edc_modes(
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> list[dict]:
    """
    Get available EDC connector modes.

    Returns the EDC integration modes supported by the system.
    """
    _check_dataspace_enabled()
    settings = get_settings()

    modes = [
        {
            "id": "tractus-x",
            "name": "Tractus-X EDC",
            "description": "Standard Tractus-X EDC connector with separate control and data planes",
            "is_default": settings.dataspace_default_edc_mode == "tractus-x",
        },
        {
            "id": "aas-extension",
            "name": "EDC AAS Extension",
            "description": "EDC with AAS submodel extension for direct AAS endpoint integration",
            "is_default": settings.dataspace_default_edc_mode == "aas-extension",
        },
    ]

    return modes
