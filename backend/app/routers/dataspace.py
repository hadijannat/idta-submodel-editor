"""
Dataspace Connector API endpoints.

Provides REST API for managing dataspace connections, publications,
and policies. Implements the onboarding workflow for connecting to
Manufacturing-X / Catena-X dataspaces.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.config import get_settings
from app.dependencies import get_current_user
from app.errors import APIError, ErrorCode
from app.schemas.dataspace import (
    # Enums
    AccessType,
    AuditEventType as AuditEventTypeSchema,
    DataspaceConnectionStatus,
    NegotiationStatus,
    PublicationStatus,
    TransferStatus,
    # Connection types
    ConnectorCapability,
    ConnectorEndpoint,
    CreateConnectionRequest,
    CreateConnectionResponse,
    ConnectionStatusResponse,
    DataspaceConnection,
    DisconnectRequest,
    DisconnectResponse,
    ListConnectionsResponse,
    SelfDescriptionResponse,
    # Publication types
    ListPublicationsResponse,
    PolicyConfig,
    PublishSubmodelRequest,
    PublishSubmodelResponse,
    SubmodelPublication,
    UnpublishRequest,
    UnpublishResponse,
    HealthCheckResponse,
    HealthCheckResult,
    # Catalog types
    CatalogOffer,
    CatalogProviderInfo,
    ListProvidersResponse,
    NegotiateContractRequest,
    NegotiationResponse,
    SearchCatalogDetailedResponse,
    SearchCatalogRequest,
    # Transfer types
    InitiateTransferRequest,
    ListTransfersResponse,
    Transfer,
    TransferEDR,
    TransferEDRResponse,
    TransferResponse,
    # Audit types
    AuditEvent,
    ListAuditLogsResponse,
)
from app.services.dataspace.catalog_service import CatalogService, CatalogServiceError
from app.services.dataspace.connection_manager import ConnectionManager
from app.services.dataspace.health import DataspaceHealthChecker
from app.services.dataspace.identity.vault_client import VaultClient
from app.services.dataspace.models import (
    AuditEventType as InternalAuditEventType,
    ConnectionStatus as InternalConnectionStatus,
    DataspaceType,
    TransferState as InternalTransferState,
)
from app.services.dataspace.audit_service import AuditService
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


def get_catalog_service() -> CatalogService:
    """Get catalog service instance."""
    return CatalogService()


def get_audit_service() -> AuditService:
    """Get audit service instance."""
    return AuditService()


def _check_dataspace_enabled() -> None:
    """Check if dataspace feature is enabled, raise error if not."""
    from app.services import settings_service
    settings = get_settings()

    if not settings_service.get_effective_feature_flag("dataspace_enabled", settings=settings):
        raise APIError(
            code=ErrorCode.FEATURE_DISABLED,
            message="Dataspace integration is disabled",
            detail={"hint": "Enable Dataspace in Settings or set DATASPACE_ENABLED=true"},
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


def _map_transfer_state(state: InternalTransferState) -> TransferStatus:
    """Map internal transfer state to API status."""
    state_map = {
        InternalTransferState.INITIAL: TransferStatus.INITIAL,
        InternalTransferState.PROVISIONING: TransferStatus.PROVISIONING,
        InternalTransferState.PROVISIONED: TransferStatus.PROVISIONED,
        InternalTransferState.REQUESTING: TransferStatus.REQUESTING,
        InternalTransferState.STARTED: TransferStatus.STARTED,
        InternalTransferState.SUSPENDED: TransferStatus.SUSPENDED,
        InternalTransferState.COMPLETED: TransferStatus.COMPLETED,
        InternalTransferState.TERMINATED: TransferStatus.TERMINATED,
        InternalTransferState.DEPROVISIONING: TransferStatus.DEPROVISIONING,
        InternalTransferState.DEPROVISIONED: TransferStatus.DEPROVISIONED,
        InternalTransferState.ERROR: TransferStatus.ERROR,
    }
    return state_map.get(state, TransferStatus.INITIAL)


def _transfer_to_response(transfer) -> Transfer:
    """Convert internal transfer state to API response model."""
    return Transfer(
        transfer_id=transfer.transfer_id,
        connection_id=transfer.connection_id,
        agreement_id=transfer.agreement_id,
        asset_id=transfer.asset_id,
        provider_bpn=transfer.provider_bpn,
        consumer_bpn=transfer.consumer_bpn,
        state=_map_transfer_state(transfer.state),
        transfer_type=transfer.transfer_type,
        data_destination=transfer.data_destination,
        created_at=transfer.created_at,
        updated_at=transfer.updated_at,
        started_at=transfer.started_at,
        completed_at=transfer.completed_at,
        error_message=transfer.error_message,
    )


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
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
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

        # Log audit event
        audit_service.log_event(
            event_type=InternalAuditEventType.CONNECTION_CREATED,
            action=f"Created connection to {request.environment} environment",
            connection_id=connection.connection_id,
            resource_id=connection.connection_id,
            resource_type="connection",
            actor=_get_owner_id(user),
            details={"environment": request.environment},
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
    except Exception:
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
    except Exception:
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


@router.get("/connections/{connection_id}/self-description", response_model=SelfDescriptionResponse)
async def get_self_description(
    connection_id: str,
    conn_manager: Annotated[ConnectionManager, Depends(get_connection_manager)],
    health_checker: Annotated[DataspaceHealthChecker, Depends(get_health_checker)],
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> SelfDescriptionResponse:
    """
    Get the connector self-description for a connection.

    Returns IDS/Gaia-X style self-description with connector info,
    endpoints, and capabilities.
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

    # Build endpoints list
    endpoints = []
    basyx_url = connection.metadata.get("basyx_url")
    if basyx_url:
        endpoints.append(ConnectorEndpoint(
            name="BaSyx AAS Server",
            url=basyx_url,
            protocol="HTTP/REST",
            healthy=None,
        ))
    if connection.dtr_url:
        endpoints.append(ConnectorEndpoint(
            name="Digital Twin Registry",
            url=connection.dtr_url,
            protocol="HTTP/REST",
            healthy=None,
        ))
    if connection.edc_url:
        endpoints.append(ConnectorEndpoint(
            name="EDC Control Plane",
            url=connection.edc_url,
            protocol="DSP",
            healthy=None,
        ))

    # Get EDC data plane URL from metadata if available
    edc_data_url = connection.metadata.get("edc_data_url")
    if edc_data_url:
        endpoints.append(ConnectorEndpoint(
            name="EDC Data Plane",
            url=edc_data_url,
            protocol="HTTP/REST",
            healthy=None,
        ))

    # Build capabilities list based on connection type
    capabilities = [
        ConnectorCapability(name="AAS Submodel Hosting", version="3.0", enabled=True),
        ConnectorCapability(name="Digital Twin Registry", version="3.0", enabled=bool(connection.dtr_url)),
    ]

    # Add EDC capabilities
    edc_mode = connection.metadata.get("edc_mode", "tractus-x")
    if edc_mode == "tractus-x":
        capabilities.extend([
            ConnectorCapability(name="Tractus-X EDC", version="0.7.x", enabled=True),
            ConnectorCapability(name="ODRL Policy Enforcement", version="2.2", enabled=True),
            ConnectorCapability(name="Contract Negotiation (DSP)", version="2024-1", enabled=True),
            ConnectorCapability(name="Data Transfer (HTTP-PULL)", version="1.0", enabled=True),
        ])
    else:
        capabilities.append(
            ConnectorCapability(name="AAS Extension EDC", version="1.0", enabled=True)
        )

    # Determine environment display name
    env = connection.metadata.get("environment", connection.dataspace_type.value)
    env_names = {
        "sandbox": "Local Sandbox",
        "catena-x-test": "Catena-X Test",
        "catena-x-prod": "Catena-X Production",
        "catena-x": "Catena-X Production",
        "manufacturing-x": "Manufacturing-X",
    }
    env_display = env_names.get(env, env.replace("-", " ").title())

    return SelfDescriptionResponse(
        connection_id=connection.connection_id,
        connector_id=f"urn:connector:{connection.connection_id}",
        bpn=connection.bpn,
        environment=env,
        edc_mode=edc_mode,
        title=f"IDTA Submodel Editor - {env_display}",
        description="Digital twin connector for AAS submodel publication and exchange",
        maintainer="IDTA Submodel Editor",
        endpoints=endpoints,
        capabilities=capabilities,
        security_profile="idsc:BASE_SECURITY_PROFILE",
        created_at=connection.created_at,
        raw_jsonld=None,  # Could be populated from actual IDS self-description
    )


@router.delete("/connections/{connection_id}", response_model=DisconnectResponse)
async def disconnect(
    connection_id: str,
    request: DisconnectRequest | None = None,
    conn_manager: Annotated[ConnectionManager, Depends(get_connection_manager)] = None,
    audit_service: Annotated[AuditService, Depends(get_audit_service)] = None,
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

    # Check for active publications - only block on truly active statuses
    registrations = conn_manager.list_registrations(connection_id=connection_id)
    ACTIVE_STATUSES = {"pending", "registered", "updating"}
    active_registrations = [r for r in registrations if r.status.value in ACTIVE_STATUSES]

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

    audit_service.log_event(
        event_type=InternalAuditEventType.CONNECTION_DISCONNECTED,
        action="Disconnected from dataspace",
        connection_id=connection_id,
        resource_id=connection_id,
        resource_type="connection",
        actor=_get_owner_id(user),
        details={"unpublished_count": unpublished_count},
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
    # Store progress in metadata since ConnectionState has no progress fields
    connection.metadata["progress"] = 0.0
    connection.metadata["progress_message"] = "Reconnecting..."
    conn_manager.update_connection(
        connection_id,
        status=InternalConnectionStatus.CONNECTING,
        error_message=None,
        metadata=connection.metadata,
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
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
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

    audit_service.log_event(
        event_type=InternalAuditEventType.PUBLICATION_STARTED,
        action=f"Started publishing {request.template_name} submodel",
        connection_id=request.connection_id,
        resource_id=registration.registration_id,
        resource_type="publication",
        actor=_get_owner_id(user),
        details={"template_name": request.template_name},
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

    except Exception:
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
            detail={"connection_id": registration.connection_id},
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
            detail={"connection_id": registration.connection_id},
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
    audit_service: Annotated[AuditService, Depends(get_audit_service)] = None,
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
            detail={"connection_id": registration.connection_id},
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

    audit_service.log_event(
        event_type=InternalAuditEventType.PUBLICATION_UNPUBLISHED,
        action="Unpublish initiated for submodel",
        connection_id=registration.connection_id,
        resource_id=publication_id,
        resource_type="publication",
        actor=_get_owner_id(user),
    )

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

    except Exception:
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
    except Exception:
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
    from app.services import settings_service

    dataspace_enabled = settings_service.get_effective_feature_flag(
        "dataspace_enabled",
        settings=settings,
    )

    now = datetime.now(timezone.utc)

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
        overall_healthy=dataspace_enabled,
        status=DataspaceConnectionStatus.NOT_CONNECTED,
        checks=[
            HealthCheckResult(
                component="dataspace_enabled",
                healthy=dataspace_enabled,
                message="Dataspace integration is enabled"
                if dataspace_enabled
                else "Dataspace integration is disabled",
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


# ---------------------------------------------------------------------------
# Catalog Browsing Endpoints
# ---------------------------------------------------------------------------


@router.post("/catalog/search", response_model=SearchCatalogDetailedResponse)
async def search_catalog(
    request: SearchCatalogRequest,
    catalog_service: Annotated[CatalogService, Depends(get_catalog_service)],
    conn_manager: Annotated[ConnectionManager, Depends(get_connection_manager)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> SearchCatalogDetailedResponse:
    """
    Search a provider's catalog for available offers.

    Queries the specified provider's EDC catalog and returns matching offers.
    Requires a provider_address to be specified in the request.
    """
    _check_dataspace_enabled()

    # Verify connection exists and is owned by user
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

    # Provider address is required for catalog search
    if not request.provider_bpn:
        raise APIError(
            code=ErrorCode.BAD_REQUEST,
            message="provider_bpn is required for catalog search",
        )

    # Get known provider address
    providers = await catalog_service.list_providers(request.connection_id)
    provider = next((p for p in providers if p.bpn == request.provider_bpn), None)

    if provider is None:
        raise APIError(
            code=ErrorCode.BAD_REQUEST,
            message="Unknown provider. Add the provider first using /catalog/providers endpoint.",
            detail={"provider_bpn": request.provider_bpn},
        )

    try:
        offers, total = await catalog_service.search_catalog(
            connection_id=request.connection_id,
            provider_address=provider.protocol_address,
            provider_bpn=request.provider_bpn,
            semantic_id=request.semantic_id,
            limit=request.limit,
            offset=request.offset,
        )

        response = SearchCatalogDetailedResponse(
            offers=[
                CatalogOffer(
                    offer_id=o.offer_id,
                    asset_id=o.asset_id,
                    provider_bpn=o.provider_bpn,
                    policy=o.policy,
                    properties=o.properties,
                    content_type=o.content_type,
                    name=o.name,
                    description=o.description,
                )
                for o in offers
            ],
            total=total,
            has_more=total > request.offset + len(offers),
        )

        audit_service.log_event(
            event_type=InternalAuditEventType.CATALOG_SEARCHED,
            action=f"Searched catalog from {request.provider_bpn}",
            connection_id=request.connection_id,
            resource_type="catalog",
            actor=_get_owner_id(user),
            details={
                "provider_bpn": request.provider_bpn,
                "results_count": total,
            },
        )

        return response

    except CatalogServiceError as e:
        logger.exception("Catalog search failed")
        raise APIError(
            code=ErrorCode.UPSTREAM_ERROR,
            message=f"Catalog search failed: {e}",
        )


@router.get(
    "/catalog/{connection_id}/providers",
    response_model=ListProvidersResponse,
)
async def list_catalog_providers(
    connection_id: str,
    catalog_service: Annotated[CatalogService, Depends(get_catalog_service)],
    conn_manager: Annotated[ConnectionManager, Depends(get_connection_manager)],
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> ListProvidersResponse:
    """
    List known catalog providers for a connection.

    Returns providers that have been previously added or discovered.
    """
    _check_dataspace_enabled()

    # Verify connection exists and is owned by user
    connection = conn_manager.get_connection(connection_id)
    if connection is None:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Connection not found",
            detail={"connection_id": connection_id},
        )
    _assert_owner(connection, user)

    providers = await catalog_service.list_providers(connection_id)

    return ListProvidersResponse(
        providers=[
            CatalogProviderInfo(
                bpn=p.bpn,
                name=p.name,
                protocol_address=p.protocol_address,
                last_seen=p.last_seen,
            )
            for p in providers
        ]
    )


@router.post(
    "/catalog/{connection_id}/providers",
    response_model=CatalogProviderInfo,
    status_code=201,
)
async def add_catalog_provider(
    connection_id: str,
    bpn: Annotated[str, Query(description="Provider's Business Partner Number")],
    protocol_address: Annotated[str, Query(description="Provider's DSP protocol address")],
    name: Annotated[str | None, Query(description="Provider display name")] = None,
    catalog_service: Annotated[CatalogService, Depends(get_catalog_service)] = None,
    conn_manager: Annotated[ConnectionManager, Depends(get_connection_manager)] = None,
    audit_service: Annotated[AuditService, Depends(get_audit_service)] = None,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> CatalogProviderInfo:
    """
    Add a provider to the known providers list.

    The provider's address is needed to query their catalog.
    """
    _check_dataspace_enabled()

    # Verify connection exists and is owned by user
    connection = conn_manager.get_connection(connection_id)
    if connection is None:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Connection not found",
            detail={"connection_id": connection_id},
        )
    _assert_owner(connection, user)

    provider = await catalog_service.add_provider(
        connection_id=connection_id,
        bpn=bpn,
        protocol_address=protocol_address,
        name=name,
    )

    response = CatalogProviderInfo(
        bpn=provider.bpn,
        name=provider.name,
        protocol_address=provider.protocol_address,
        last_seen=provider.last_seen,
    )

    audit_service.log_event(
        event_type=InternalAuditEventType.PROVIDER_ADDED,
        action=f"Added catalog provider {provider.bpn}",
        connection_id=connection_id,
        resource_type="catalog",
        actor=_get_owner_id(user),
        details={
            "provider_bpn": provider.bpn,
            "protocol_address": provider.protocol_address,
            "name": provider.name,
        },
    )

    return response


@router.post("/catalog/negotiate", response_model=NegotiationResponse, status_code=201)
async def initiate_catalog_negotiation(
    request: NegotiateContractRequest,
    catalog_service: Annotated[CatalogService, Depends(get_catalog_service)],
    conn_manager: Annotated[ConnectionManager, Depends(get_connection_manager)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> NegotiationResponse:
    """
    Initiate a contract negotiation for a catalog offer.

    Starts the EDC contract negotiation process. The negotiation_id can be
    used to poll for status updates until the contract is finalized.
    """
    _check_dataspace_enabled()

    # Verify connection exists and is owned by user
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

    try:
        negotiation = await catalog_service.initiate_negotiation(
            connection_id=request.connection_id,
            provider_address=request.provider_address,
            offer_id=request.offer_id,
            asset_id=request.asset_id,
            policy=request.policy,
        )

        # Map internal state to API state
        state_map = {
            "initial": NegotiationStatus.INITIAL,
            "requesting": NegotiationStatus.REQUESTING,
            "offered": NegotiationStatus.OFFERED,
            "agreeing": NegotiationStatus.AGREEING,
            "agreed": NegotiationStatus.AGREED,
            "verifying": NegotiationStatus.VERIFYING,
            "verified": NegotiationStatus.VERIFIED,
            "finalized": NegotiationStatus.FINALIZED,
            "terminated": NegotiationStatus.TERMINATED,
            "error": NegotiationStatus.ERROR,
        }

        response = NegotiationResponse(
            negotiation_id=negotiation.negotiation_id,
            state=state_map.get(negotiation.state.value, NegotiationStatus.INITIAL),
            agreement_id=negotiation.agreement_id,
            error_message=negotiation.error_message,
            created_at=negotiation.created_at,
            updated_at=negotiation.updated_at,
        )

        audit_service.log_event(
            event_type=InternalAuditEventType.NEGOTIATION_INITIATED,
            action="Initiated contract negotiation",
            connection_id=request.connection_id,
            resource_type="negotiation",
            actor=_get_owner_id(user),
            details={
                "asset_id": request.asset_id,
                "offer_id": request.offer_id,
                "provider_address": request.provider_address,
            },
        )

        return response

    except CatalogServiceError as e:
        logger.exception("Failed to initiate negotiation")
        raise APIError(
            code=ErrorCode.UPSTREAM_ERROR,
            message=f"Failed to initiate negotiation: {e}",
        )


@router.get("/catalog/negotiations/{negotiation_id}", response_model=NegotiationResponse)
async def get_negotiation_status(
    negotiation_id: str,
    catalog_service: Annotated[CatalogService, Depends(get_catalog_service)],
    conn_manager: Annotated[ConnectionManager, Depends(get_connection_manager)],
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> NegotiationResponse:
    """
    Get the current status of a contract negotiation.

    Polls the EDC for the latest negotiation state.
    """
    _check_dataspace_enabled()

    negotiation = await catalog_service.get_negotiation_status(negotiation_id)
    if negotiation is None:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Negotiation not found",
            detail={"negotiation_id": negotiation_id},
        )

    # Verify ownership
    connection = conn_manager.get_connection(negotiation.connection_id)
    if connection:
        _assert_owner(connection, user)

    # Map internal state to API state
    state_map = {
        "initial": NegotiationStatus.INITIAL,
        "requesting": NegotiationStatus.REQUESTING,
        "offered": NegotiationStatus.OFFERED,
        "agreeing": NegotiationStatus.AGREEING,
        "agreed": NegotiationStatus.AGREED,
        "verifying": NegotiationStatus.VERIFYING,
        "verified": NegotiationStatus.VERIFIED,
        "finalized": NegotiationStatus.FINALIZED,
        "terminated": NegotiationStatus.TERMINATED,
        "error": NegotiationStatus.ERROR,
    }

    return NegotiationResponse(
        negotiation_id=negotiation.negotiation_id,
        state=state_map.get(negotiation.state.value, NegotiationStatus.INITIAL),
        agreement_id=negotiation.agreement_id,
        error_message=negotiation.error_message,
        created_at=negotiation.created_at,
        updated_at=negotiation.updated_at,
    )


# ---------------------------------------------------------------------------
# Transfer Endpoints
# ---------------------------------------------------------------------------


@router.post("/transfers", response_model=TransferResponse, status_code=201)
async def initiate_transfer(
    request: InitiateTransferRequest,
    conn_manager: Annotated[ConnectionManager, Depends(get_connection_manager)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> TransferResponse:
    """
    Initiate a data transfer after contract negotiation.

    Starts the EDC transfer process using a finalized contract agreement.
    The transfer uses the specified transfer type (HttpData-PULL or HttpData-PUSH).
    """
    _check_dataspace_enabled()

    # Verify connection exists and is owned by user
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

    try:
        # Create transfer record
        transfer = conn_manager.create_transfer(
            connection_id=request.connection_id,
            agreement_id=request.agreement_id,
            asset_id=request.asset_id,
            provider_bpn=request.provider_bpn or "unknown",
            consumer_bpn=connection.bpn,
            transfer_type=request.transfer_type,
            data_destination=request.data_destination,
            metadata={
                "provider_address": request.provider_address,
            },
        )

        # Queue background transfer task
        try:
            from app.services.dataspace.tasks import initiate_transfer_task

            initiate_transfer_task.delay(
                transfer.transfer_id,
                request.provider_address,
            )
            logger.info("Queued transfer %s for asset %s", transfer.transfer_id, request.asset_id)
        except Exception as e:
            logger.warning("Celery unavailable for transfer: %s", e)

        response = TransferResponse(
            transfer=_transfer_to_response(transfer),
            message="Transfer initiated. Processing in background.",
        )

        audit_service.log_event(
            event_type=InternalAuditEventType.TRANSFER_INITIATED,
            action="Initiated transfer",
            connection_id=request.connection_id,
            resource_id=transfer.transfer_id,
            resource_type="transfer",
            actor=_get_owner_id(user),
            details={
                "asset_id": request.asset_id,
                "agreement_id": request.agreement_id,
                "provider_bpn": request.provider_bpn,
            },
        )

        return response

    except Exception as e:
        logger.exception("Failed to initiate transfer")
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"Failed to initiate transfer: {e}",
        )


@router.get("/transfers", response_model=ListTransfersResponse)
async def list_transfers(
    conn_manager: Annotated[ConnectionManager, Depends(get_connection_manager)],
    connection_id: Annotated[str | None, Query()] = None,
    status: Annotated[TransferStatus | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> ListTransfersResponse:
    """
    List data transfers.

    Supports filtering by connection ID and transfer status.
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

        # Map API status to internal state
        internal_state = None
        if status:
            state_reverse_map = {
                TransferStatus.INITIAL: InternalTransferState.INITIAL,
                TransferStatus.PROVISIONING: InternalTransferState.PROVISIONING,
                TransferStatus.PROVISIONED: InternalTransferState.PROVISIONED,
                TransferStatus.REQUESTING: InternalTransferState.REQUESTING,
                TransferStatus.STARTED: InternalTransferState.STARTED,
                TransferStatus.SUSPENDED: InternalTransferState.SUSPENDED,
                TransferStatus.COMPLETED: InternalTransferState.COMPLETED,
                TransferStatus.TERMINATED: InternalTransferState.TERMINATED,
                TransferStatus.DEPROVISIONING: InternalTransferState.DEPROVISIONING,
                TransferStatus.DEPROVISIONED: InternalTransferState.DEPROVISIONED,
                TransferStatus.ERROR: InternalTransferState.ERROR,
            }
            internal_state = state_reverse_map.get(status)

        transfers = conn_manager.list_transfers(
            connection_id=connection_id,
            state=internal_state,
            limit=limit,
        )

        # Filter by allowed connections if auth is enabled
        if allowed_connection_ids is not None:
            transfers = [
                t for t in transfers
                if t.connection_id in allowed_connection_ids
            ]

        return ListTransfersResponse(
            transfers=[_transfer_to_response(t) for t in transfers],
            total=len(transfers),
        )

    except APIError:
        raise
    except Exception:
        logger.exception("Failed to list transfers")
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to list transfers",
        )


@router.get("/transfers/{transfer_id}", response_model=Transfer)
async def get_transfer(
    transfer_id: str,
    conn_manager: Annotated[ConnectionManager, Depends(get_connection_manager)],
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> Transfer:
    """
    Get details of a specific transfer.
    """
    _check_dataspace_enabled()

    transfer = conn_manager.get_transfer(transfer_id)
    if transfer is None:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Transfer not found",
            detail={"transfer_id": transfer_id},
        )

    # Verify ownership
    connection = conn_manager.get_connection(transfer.connection_id)
    if connection:
        _assert_owner(connection, user)

    return _transfer_to_response(transfer)


@router.get("/transfers/{transfer_id}/edr", response_model=TransferEDRResponse)
async def get_transfer_edr(
    transfer_id: str,
    conn_manager: Annotated[ConnectionManager, Depends(get_connection_manager)],
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> TransferEDRResponse:
    """
    Get the Endpoint Data Reference (EDR) for accessing transferred data.

    The EDR contains the authentication credentials and endpoint URL
    needed to access the data from the provider.
    """
    _check_dataspace_enabled()

    transfer = conn_manager.get_transfer(transfer_id)
    if transfer is None:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Transfer not found",
            detail={"transfer_id": transfer_id},
        )

    # Verify ownership
    connection = conn_manager.get_connection(transfer.connection_id)
    if connection:
        _assert_owner(connection, user)

    # Check if transfer has EDR
    if not transfer.edr_endpoint or not transfer.edr_token:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="EDR not available for this transfer",
            detail={
                "transfer_id": transfer_id,
                "state": transfer.state.value,
                "hint": "EDR is only available for transfers in STARTED or COMPLETED state",
            },
        )

    # Check if EDR is still valid
    now = datetime.now(timezone.utc)
    expires_at = transfer.edr_expires_at
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    is_valid = expires_at is None or expires_at > now

    return TransferEDRResponse(
        edr=TransferEDR(
            transfer_id=transfer_id,
            endpoint=transfer.edr_endpoint,
            auth_type="bearer",
            auth_token=transfer.edr_token,
            expires_at=transfer.edr_expires_at,
        ),
        valid=is_valid,
    )


@router.post("/transfers/{transfer_id}/terminate", response_model=Transfer)
async def terminate_transfer(
    transfer_id: str,
    conn_manager: Annotated[ConnectionManager, Depends(get_connection_manager)],
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> Transfer:
    """
    Terminate an active transfer.

    Stops the transfer process and releases any resources.
    """
    _check_dataspace_enabled()

    transfer = conn_manager.get_transfer(transfer_id)
    if transfer is None:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Transfer not found",
            detail={"transfer_id": transfer_id},
        )

    # Verify ownership
    connection = conn_manager.get_connection(transfer.connection_id)
    if connection:
        _assert_owner(connection, user)

    # Check if transfer can be terminated
    if transfer.is_terminal:
        raise APIError(
            code=ErrorCode.RESOURCE_CONFLICT,
            message="Transfer is already in a terminal state",
            detail={"current_state": transfer.state.value},
        )

    try:
        # Queue background termination task
        try:
            from app.services.dataspace.tasks import terminate_transfer_task

            terminate_transfer_task.delay(transfer_id)
            logger.info("Queued termination for transfer %s", transfer_id)
        except Exception as e:
            logger.warning("Celery unavailable for termination: %s", e)

        # Update local state
        transfer = conn_manager.update_transfer(
            transfer_id,
            state=InternalTransferState.TERMINATED,
            completed_at=datetime.now(timezone.utc),
        )

        response = _transfer_to_response(transfer)

        audit_service.log_event(
            event_type=InternalAuditEventType.TRANSFER_TERMINATED,
            action="Transfer terminated",
            connection_id=transfer.connection_id,
            resource_id=transfer.transfer_id,
            resource_type="transfer",
            actor=_get_owner_id(user),
        )

        return response

    except APIError:
        raise
    except Exception as e:
        logger.exception("Failed to terminate transfer")
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"Failed to terminate transfer: {e}",
        )


# ---------------------------------------------------------------------------
# Audit Log Endpoints
# ---------------------------------------------------------------------------


@router.get("/audit", response_model=ListAuditLogsResponse)
async def list_audit_logs(
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
    conn_manager: Annotated[ConnectionManager, Depends(get_connection_manager)],
    connection_id: Annotated[str | None, Query()] = None,
    event_type: Annotated[AuditEventTypeSchema | None, Query()] = None,
    resource_type: Annotated[str | None, Query()] = None,
    start_date: Annotated[datetime | None, Query()] = None,
    end_date: Annotated[datetime | None, Query()] = None,
    success: Annotated[bool | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> ListAuditLogsResponse:
    """
    List audit log entries with optional filters.

    Returns audit events for dataspace operations with support for
    filtering by connection, event type, date range, and success status.
    """
    _check_dataspace_enabled()

    try:
        # If user auth is enabled, filter by owned connections
        owner_id = _get_owner_id(user)
        allowed_connection_ids = None
        if owner_id:
            allowed_connection_ids = {
                conn.connection_id
                for conn in conn_manager.list_connections(owner_id=owner_id, limit=100)
            }

        # Verify access to specific connection if provided
        if connection_id and allowed_connection_ids is not None:
            if connection_id not in allowed_connection_ids:
                raise APIError(
                    code=ErrorCode.RESOURCE_NOT_FOUND,
                    message="Access denied for this connection",
                    status_code=403,
                )

        # Map schema event type to internal event type
        internal_event_type = None
        if event_type:
            try:
                internal_event_type = InternalAuditEventType(event_type.value)
            except ValueError:
                pass

        entries, total = audit_service.list_entries(
            connection_id=connection_id,
            event_type=internal_event_type,
            resource_type=resource_type,
            start_date=start_date,
            end_date=end_date,
            success=success,
            limit=limit,
            offset=offset,
        )

        # Filter by allowed connections if auth is enabled
        if allowed_connection_ids is not None and connection_id is None:
            entries = [
                e for e in entries
                if e.connection_id is None or e.connection_id in allowed_connection_ids
            ]
            total = len(entries)

        # Convert to API model
        api_entries = [
            AuditEvent(
                entry_id=e.entry_id,
                event_type=AuditEventTypeSchema(e.event_type.value),
                timestamp=e.timestamp,
                connection_id=e.connection_id,
                resource_id=e.resource_id,
                resource_type=e.resource_type,
                actor=e.actor,
                action=e.action,
                details=e.details,
                success=e.success,
                error_message=e.error_message,
            )
            for e in entries
        ]

        return ListAuditLogsResponse(
            entries=api_entries,
            total=total,
            has_more=offset + len(entries) < total,
        )

    except APIError:
        raise
    except Exception:
        logger.exception("Failed to list audit logs")
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to list audit logs",
        )


@router.get("/audit/{entry_id}", response_model=AuditEvent)
async def get_audit_entry(
    entry_id: str,
    audit_service: Annotated[AuditService, Depends(get_audit_service)],
    conn_manager: Annotated[ConnectionManager, Depends(get_connection_manager)],
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> AuditEvent:
    """
    Get a specific audit log entry.
    """
    _check_dataspace_enabled()

    entry = audit_service.get_entry(entry_id)
    if entry is None:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Audit entry not found",
            detail={"entry_id": entry_id},
        )

    # Verify ownership if entry has a connection_id
    if entry.connection_id:
        connection = conn_manager.get_connection(entry.connection_id)
        if connection:
            _assert_owner(connection, user)

    return AuditEvent(
        entry_id=entry.entry_id,
        event_type=AuditEventTypeSchema(entry.event_type.value),
        timestamp=entry.timestamp,
        connection_id=entry.connection_id,
        resource_id=entry.resource_id,
        resource_type=entry.resource_type,
        actor=entry.actor,
        action=entry.action,
        details=entry.details,
        success=entry.success,
        error_message=entry.error_message,
    )
