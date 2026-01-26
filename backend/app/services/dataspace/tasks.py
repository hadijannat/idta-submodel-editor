"""
Celery tasks for Dataspace connectivity background processing.

Task flow:
1. onboard_to_dataspace - Main orchestrator for establishing connection
2. publish_submodel - Hydrate → BaSyx push → DTR register → EDC offer
3. health_check_all - Periodic health check for all connections
4. register_asset_task - Register Digital Twin in DTR
5. negotiate_contract_task - Negotiate data contract via EDC
6. sync_registrations_task - Sync registration state with DTR
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any

from celery import shared_task

from app.config import get_settings

logger = logging.getLogger(__name__)


def run_async(coro):
    """Helper to run async code in sync context."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def get_provider_for_connection(connection):
    """
    Get the appropriate dataspace provider for a connection.

    Args:
        connection: ConnectionState object

    Returns:
        DataspaceProvider instance
    """
    from app.services.dataspace.models import DataspaceType
    from app.services.dataspace.providers import SandboxProvider, CatenaXProvider

    if connection.dataspace_type == DataspaceType.SANDBOX:
        return SandboxProvider()
    elif connection.dataspace_type == DataspaceType.CATENA_X:
        return CatenaXProvider()
    else:
        # Default to sandbox for unknown types
        logger.warning(
            "Unknown dataspace type %s, defaulting to sandbox",
            connection.dataspace_type,
        )
        return SandboxProvider()


@shared_task(bind=True, name="dataspace.onboard")
def onboard_to_dataspace(self, connection_id: str) -> dict:
    """
    Main orchestrator task for establishing a dataspace connection.

    Orchestrates the full onboarding flow:
    1. Load secrets from Vault (if configured)
    2. Configure EDC connector
    3. Register with DTR
    4. Perform health check

    Args:
        connection_id: The connection ID to onboard

    Returns:
        Result summary dictionary
    """
    from app.services.dataspace.connection_manager import ConnectionManager
    from app.services.dataspace.health import DataspaceHealthChecker
    from app.services.dataspace.identity.vault_client import VaultClient
    from app.services.dataspace.models import ConnectionStatus, DataspaceType
    from app.services.dataspace.providers.provider_base import DataspaceConnectionError

    settings = get_settings()
    manager = ConnectionManager()
    start_time = time.time()

    # Load connection
    connection = manager.get_connection(connection_id)
    if connection is None:
        logger.error("Connection %s not found", connection_id)
        return {"error": "Connection not found", "connection_id": connection_id}

    try:
        # Step 1: Update status to connecting
        logger.info("Starting onboarding for connection %s", connection_id)
        manager.update_connection(
            connection_id,
            status=ConnectionStatus.CONNECTING,
        )

        # Step 2: Load secrets from Vault (if configured)
        vault = VaultClient(
            vault_url=settings.vault_url if hasattr(settings, 'vault_url') else None,
            token=settings.vault_token if hasattr(settings, 'vault_token') else None,
        )

        secrets: dict[str, Any] = {}
        if vault.is_configured:
            logger.info("Loading secrets from Vault for connection %s", connection_id)
            manager.update_connection(
                connection_id,
                status=ConnectionStatus.AUTHENTICATING,
            )

            # Try to load generic credentials first, then fall back to EDC/DTR
            generic_creds = run_async(vault.get_credentials(connection_id))
            edc_creds = run_async(vault.get_edc_credentials(connection_id))
            dtr_creds = run_async(vault.get_dtr_credentials(connection_id))

            if generic_creds:
                secrets.update(generic_creds)
            if edc_creds:
                secrets.setdefault('edc_api_key', edc_creds.get('api_key'))
                if edc_creds.get('api_secret'):
                    secrets.setdefault('edc_api_secret', edc_creds.get('api_secret'))
            if dtr_creds:
                secrets.setdefault('dtr_token', dtr_creds.get('token'))
        else:
            logger.debug("Vault not configured, skipping secrets retrieval")

        if connection.dataspace_type != DataspaceType.SANDBOX:
            if not vault.is_configured:
                raise DataspaceConnectionError("Vault is required for non-sandbox environments.")
            if not secrets:
                raise DataspaceConnectionError("Missing credentials for non-sandbox environment.")

        # Step 3: Get provider and establish connection
        provider = get_provider_for_connection(connection)

        logger.info(
            "Connecting to %s dataspace using %s provider",
            connection.dataspace_type.value,
            provider.name,
        )

        # Use the provider to establish connection
        updated_connection = run_async(provider.connect(connection, secrets=secrets or None))

        # Save updated connection state
        manager.update_connection(
            connection_id,
            status=updated_connection.status,
            dtr_url=updated_connection.dtr_url,
            edc_url=updated_connection.edc_url,
            bpn=updated_connection.bpn,
            last_health_check=updated_connection.last_health_check,
        )

        # Step 4: Perform initial health check
        logger.info("Performing initial health check for connection %s", connection_id)
        health_checker = DataspaceHealthChecker()
        health_results = health_checker.check_connection(updated_connection, secrets=secrets or None)

        all_healthy = all(r.healthy for r in health_results)

        if not all_healthy:
            unhealthy = [r for r in health_results if not r.healthy]
            logger.warning(
                "Some health checks failed for connection %s: %s",
                connection_id,
                [r.component for r in unhealthy],
            )

        # Final status update
        processing_time = time.time() - start_time
        final_status = ConnectionStatus.CONNECTED if all_healthy else ConnectionStatus.DEGRADED

        manager.update_connection(
            connection_id,
            status=final_status,
            last_health_check=datetime.utcnow(),
            error_message=None if all_healthy else "Some health checks failed",
        )

        logger.info(
            "Connection %s onboarding completed in %.1fs with status %s",
            connection_id,
            processing_time,
            final_status.value,
        )

        return {
            "connection_id": connection_id,
            "status": final_status.value,
            "provider": provider.name,
            "health_checks": [r.to_dict() for r in health_results],
            "processing_time_seconds": processing_time,
        }

    except Exception as e:
        logger.exception("Connection %s onboarding failed", connection_id)
        manager.update_connection(
            connection_id,
            status=ConnectionStatus.ERROR,
            error_message=str(e),
        )
        return {"error": str(e), "connection_id": connection_id}


@shared_task(bind=True, name="dataspace.publish_submodel")
def publish_submodel(
    self,
    connection_id: str,
    publication_config: dict[str, Any],
) -> dict:
    """
    Publish a submodel to the dataspace.

    Executes the full publication flow:
    1. Hydrate submodel from form data
    2. Push to BaSyx/DTR
    3. Register in Digital Twin Registry
    4. Create EDC offer for data sharing

    Args:
        connection_id: The connection ID to use
        publication_config: Configuration dict containing:
            - template_name: Name of the template
            - template_status: Template status (published/deprecated)
            - template_version: Optional template version
            - form_data: The form data to hydrate
            - aas_id: AAS identifier
            - submodel_id: Submodel identifier
            - policy_type: Optional policy type for EDC offer
            - metadata: Optional additional metadata

    Returns:
        Result summary dictionary
    """
    from app.services.dataspace.connection_manager import ConnectionManager
    from app.services.dataspace.models import ConnectionStatus, RegistrationStatus
    from app.services.fetcher import TemplateFetcherService
    from app.services.hydrator import HydratorService

    manager = ConnectionManager()
    fetcher = TemplateFetcherService()
    hydrator = HydratorService()
    start_time = time.time()

    # Load connection
    connection = manager.get_connection(connection_id)
    if connection is None:
        logger.error("Connection %s not found", connection_id)
        return {"error": "Connection not found", "connection_id": connection_id}

    if connection.status != ConnectionStatus.CONNECTED:
        logger.error("Connection %s is not connected (status: %s)", connection_id, connection.status.value)
        return {
            "error": f"Connection not connected (status: {connection.status.value})",
            "connection_id": connection_id,
        }

    # Extract config
    template_name = publication_config.get("template_name")
    template_status = publication_config.get("template_status", "published")
    template_version = publication_config.get("template_version")
    form_data = publication_config.get("form_data", {})
    aas_id = publication_config.get("aas_id")
    submodel_id = publication_config.get("submodel_id")
    metadata = publication_config.get("metadata", {})

    if not all([template_name, aas_id, submodel_id]):
        return {
            "error": "Missing required fields: template_name, aas_id, submodel_id",
            "connection_id": connection_id,
        }

    try:
        # Step 1: Fetch template bytes
        logger.info(
            "Fetching template %s for hydration",
            template_name,
        )

        try:
            template_bytes = fetcher.get_template_aasx(
                template_name,
                status=template_status,
                version=template_version,
            )
            if template_bytes is None:
                return {
                    "error": f"Template {template_name} not found",
                    "connection_id": connection_id,
                }
        except Exception as e:
            logger.error("Failed to fetch template: %s", e)
            return {
                "error": f"Template fetch failed: {e}",
                "connection_id": connection_id,
            }

        # Step 2: Hydrate submodel from form data
        logger.info(
            "Hydrating submodel %s for template %s",
            submodel_id,
            template_name,
        )

        try:
            # hydrate_submodel returns AASX bytes, but we need JSON for registration
            aas_json = hydrator.hydrate_to_json(template_bytes, form_data)
        except Exception as e:
            logger.error("Failed to hydrate submodel: %s", e)
            return {
                "error": f"Hydration failed: {e}",
                "connection_id": connection_id,
            }

        # Step 3: Create registration record
        registration = manager.create_registration(
            connection_id=connection_id,
            aas_id=aas_id,
            submodel_id=submodel_id,
            metadata=metadata,
        )

        logger.info(
            "Created registration %s for AAS %s, submodel %s",
            registration.registration_id,
            aas_id,
            submodel_id,
        )

        # Step 4: Get provider and register asset
        provider = get_provider_for_connection(connection)

        logger.info(
            "Registering asset with %s provider",
            provider.name,
        )

        updated_registration = run_async(
            provider.register_asset(connection, registration, aas_json)
        )

        # Save registration state
        manager.update_registration(
            registration.registration_id,
            status=updated_registration.status,
            dtr_asset_id=updated_registration.dtr_asset_id,
            edc_asset_id=updated_registration.edc_asset_id,
        )

        processing_time = time.time() - start_time

        logger.info(
            "Publication completed for registration %s in %.1fs",
            registration.registration_id,
            processing_time,
        )

        return {
            "connection_id": connection_id,
            "registration_id": registration.registration_id,
            "status": updated_registration.status.value,
            "dtr_asset_id": updated_registration.dtr_asset_id,
            "edc_asset_id": updated_registration.edc_asset_id,
            "processing_time_seconds": processing_time,
        }

    except Exception as e:
        logger.exception("Publication failed for connection %s", connection_id)
        return {
            "error": str(e),
            "connection_id": connection_id,
        }


@shared_task(name="dataspace.health_check_all")
def health_check_all() -> dict:
    """
    Periodic health check for all active dataspace connections.

    Iterates through all connected connections and runs health checks.
    Updates connection status based on results.

    Returns:
        Health check summary for all connections
    """
    from app.services.dataspace.connection_manager import ConnectionManager
    from app.services.dataspace.health import DataspaceHealthChecker
    from app.services.dataspace.identity.vault_client import VaultClient
    from app.services.dataspace.models import ConnectionStatus

    settings = get_settings()
    manager = ConnectionManager()
    health_checker = DataspaceHealthChecker()
    vault = VaultClient(
        vault_url=settings.vault_url if hasattr(settings, 'vault_url') else None,
        token=settings.vault_token if hasattr(settings, 'vault_token') else None,
    )

    # Get all active connections
    connections = [
        conn
        for conn in manager.list_connections()
        if conn.status in (ConnectionStatus.CONNECTED, ConnectionStatus.DEGRADED)
    ]

    if not connections:
        logger.debug("No active connections to health check")
        return {"connections_checked": 0, "results": []}

    logger.info("Running health check for %d connections", len(connections))

    results = []
    healthy_count = 0
    unhealthy_count = 0

    for connection in connections:
        try:
            secrets: dict[str, Any] = {}
            if vault.is_configured:
                generic_creds = run_async(vault.get_credentials(connection.connection_id))
                if generic_creds:
                    secrets.update(generic_creds)
                edc_creds = run_async(vault.get_edc_credentials(connection.connection_id))
                if edc_creds:
                    secrets.setdefault('edc_api_key', edc_creds.get('api_key'))
                dtr_creds = run_async(vault.get_dtr_credentials(connection.connection_id))
                if dtr_creds:
                    secrets.setdefault('dtr_token', dtr_creds.get('token'))

            health_results = health_checker.check_connection(connection, secrets=secrets or None)
            all_healthy = all(r.healthy for r in health_results)

            # Update connection status
            new_status = ConnectionStatus.CONNECTED if all_healthy else ConnectionStatus.DEGRADED
            error_msg = None if all_healthy else "Health check failed"

            manager.update_connection(
                connection.connection_id,
                status=new_status,
                last_health_check=datetime.utcnow(),
                error_message=error_msg,
            )

            if all_healthy:
                healthy_count += 1
            else:
                unhealthy_count += 1

            results.append({
                "connection_id": connection.connection_id,
                "dataspace_type": connection.dataspace_type.value,
                "healthy": all_healthy,
                "checks": [r.to_dict() for r in health_results],
            })

        except Exception as e:
            logger.warning(
                "Health check failed for connection %s: %s",
                connection.connection_id,
                e,
            )
            unhealthy_count += 1

            manager.update_connection(
                connection.connection_id,
                status=ConnectionStatus.DEGRADED,
                last_health_check=datetime.utcnow(),
                error_message=f"Health check error: {e}",
            )

            results.append({
                "connection_id": connection.connection_id,
                "dataspace_type": connection.dataspace_type.value,
                "healthy": False,
                "error": str(e),
            })

    logger.info(
        "Health check complete: %d healthy, %d unhealthy",
        healthy_count,
        unhealthy_count,
    )

    return {
        "connections_checked": len(results),
        "healthy_count": healthy_count,
        "unhealthy_count": unhealthy_count,
        "results": results,
    }


@shared_task(bind=True, name="dataspace.connect")
def connect_dataspace_task(self, connection_id: str) -> dict:
    """
    Establish a dataspace connection (simplified version of onboard).

    Use onboard_to_dataspace for full orchestration with secrets and health checks.
    This task provides a simpler connection flow.

    Args:
        connection_id: The connection ID to establish

    Returns:
        Result summary dictionary
    """
    from app.services.dataspace.connection_manager import ConnectionManager
    from app.services.dataspace.models import ConnectionStatus

    manager = ConnectionManager()
    start_time = time.time()

    # Load connection
    connection = manager.get_connection(connection_id)
    if connection is None:
        logger.error("Connection %s not found", connection_id)
        return {"error": "Connection not found", "connection_id": connection_id}

    try:
        # Update status to connecting
        manager.update_connection(
            connection_id,
            status=ConnectionStatus.CONNECTING,
        )

        # Get provider and connect
        provider = get_provider_for_connection(connection)
        updated_connection = run_async(provider.connect(connection))

        processing_time = time.time() - start_time

        manager.update_connection(
            connection_id,
            status=updated_connection.status,
            dtr_url=updated_connection.dtr_url,
            edc_url=updated_connection.edc_url,
            bpn=updated_connection.bpn,
            last_health_check=datetime.utcnow(),
        )

        logger.info(
            "Connection %s established in %.1fs",
            connection_id,
            processing_time,
        )

        return {
            "connection_id": connection_id,
            "status": updated_connection.status.value,
            "provider": provider.name,
            "processing_time_seconds": processing_time,
        }

    except Exception as e:
        logger.exception("Connection %s failed", connection_id)
        manager.update_connection(
            connection_id,
            status=ConnectionStatus.ERROR,
            error_message=str(e),
        )
        return {"error": str(e), "connection_id": connection_id}


@shared_task(bind=True, name="dataspace.register_asset")
def register_asset_task(self, registration_id: str) -> dict:
    """
    Register a Digital Twin asset in the Digital Twin Registry.

    Executes the registration flow:
    Load AAS → Create DTR Entry → Create EDC Asset → Link → Verify

    Args:
        registration_id: The registration ID to process

    Returns:
        Result summary dictionary
    """
    from app.services.dataspace.connection_manager import ConnectionManager
    from app.services.dataspace.models import RegistrationStatus

    manager = ConnectionManager()
    start_time = time.time()

    # Load registration
    registration = manager.get_registration(registration_id)
    if registration is None:
        logger.error("Registration %s not found", registration_id)
        return {"error": "Registration not found", "registration_id": registration_id}

    # Load parent connection
    connection = manager.get_connection(registration.connection_id)
    if connection is None:
        logger.error("Parent connection %s not found", registration.connection_id)
        return {
            "error": "Parent connection not found",
            "registration_id": registration_id,
        }

    try:
        # Get provider and register
        provider = get_provider_for_connection(connection)

        # Use empty AAS data since we're registering an existing asset
        aas_data = {
            "aas_id": registration.aas_id,
            "submodel_id": registration.submodel_id,
        }

        updated_registration = run_async(
            provider.register_asset(connection, registration, aas_data)
        )

        processing_time = time.time() - start_time

        manager.update_registration(
            registration_id,
            status=updated_registration.status,
            dtr_asset_id=updated_registration.dtr_asset_id,
            edc_asset_id=updated_registration.edc_asset_id,
        )

        logger.info(
            "Registration %s completed in %.1fs",
            registration_id,
            processing_time,
        )

        return {
            "registration_id": registration_id,
            "status": updated_registration.status.value,
            "dtr_asset_id": updated_registration.dtr_asset_id,
            "edc_asset_id": updated_registration.edc_asset_id,
            "processing_time_seconds": processing_time,
        }

    except Exception as e:
        logger.exception("Registration %s failed", registration_id)
        manager.update_registration(
            registration_id,
            status=RegistrationStatus.FAILED,
            error_message=str(e),
        )
        return {"error": str(e), "registration_id": registration_id}


@shared_task(bind=True, name="dataspace.negotiate_contract")
def negotiate_contract_task(self, negotiation_id: str) -> dict:
    """
    Negotiate a data contract via the EDC Connector.

    Executes the negotiation flow:
    Request Catalog → Select Offer → Send Request → Await Agreement → Verify

    Args:
        negotiation_id: The negotiation ID to process

    Returns:
        Result summary dictionary
    """
    from app.services.dataspace.connection_manager import ConnectionManager
    from app.services.dataspace.models import ContractState

    manager = ConnectionManager()
    start_time = time.time()

    # Load negotiation
    negotiation = manager.get_negotiation(negotiation_id)
    if negotiation is None:
        logger.error("Negotiation %s not found", negotiation_id)
        return {"error": "Negotiation not found", "negotiation_id": negotiation_id}

    # Load parent connection
    connection = manager.get_connection(negotiation.connection_id)
    if connection is None:
        logger.error("Parent connection %s not found", negotiation.connection_id)
        return {
            "error": "Parent connection not found",
            "negotiation_id": negotiation_id,
        }

    try:
        # Get provider
        provider = get_provider_for_connection(connection)

        # Build default policy if none specified
        policy = {
            "@type": "odrl:Set",
            "@id": f"policy-{negotiation_id[:8]}",
            "permission": [
                {
                    "action": "use",
                    "constraint": [],
                }
            ],
        }

        # Execute negotiation
        updated_negotiation = run_async(
            provider.negotiate_contract(connection, negotiation, policy)
        )

        processing_time = time.time() - start_time

        logger.info(
            "Negotiation %s completed in %.1fs with state %s",
            negotiation_id,
            processing_time,
            updated_negotiation.state.value,
        )

        return {
            "negotiation_id": negotiation_id,
            "status": updated_negotiation.state.value,
            "offer_id": updated_negotiation.offer_id,
            "agreement_id": updated_negotiation.agreement_id,
            "processing_time_seconds": processing_time,
        }

    except Exception as e:
        logger.exception("Negotiation %s failed", negotiation_id)
        return {"error": str(e), "negotiation_id": negotiation_id}


@shared_task(name="dataspace.health_check")
def health_check_task(connection_id: str | None = None) -> dict:
    """
    Health check for specific or all dataspace connections.

    If connection_id is provided, checks only that connection.
    Otherwise, delegates to health_check_all.

    Args:
        connection_id: Optional specific connection to check

    Returns:
        Health check results
    """
    if connection_id is None:
        return health_check_all()

    from app.services.dataspace.connection_manager import ConnectionManager
    from app.services.dataspace.health import DataspaceHealthChecker
    from app.services.dataspace.identity.vault_client import VaultClient
    from app.services.dataspace.models import ConnectionStatus

    settings = get_settings()
    manager = ConnectionManager()
    health_checker = DataspaceHealthChecker()
    vault = VaultClient(
        vault_url=settings.vault_url if hasattr(settings, 'vault_url') else None,
        token=settings.vault_token if hasattr(settings, 'vault_token') else None,
    )

    connection = manager.get_connection(connection_id)
    if connection is None:
        return {"error": "Connection not found", "connection_id": connection_id}

    try:
        secrets: dict[str, Any] = {}
        if vault.is_configured:
            generic_creds = run_async(vault.get_credentials(connection.connection_id))
            if generic_creds:
                secrets.update(generic_creds)
            edc_creds = run_async(vault.get_edc_credentials(connection.connection_id))
            if edc_creds:
                secrets.setdefault('edc_api_key', edc_creds.get('api_key'))
            dtr_creds = run_async(vault.get_dtr_credentials(connection.connection_id))
            if dtr_creds:
                secrets.setdefault('dtr_token', dtr_creds.get('token'))

        health_results = health_checker.check_connection(connection, secrets=secrets or None)
        all_healthy = all(r.healthy for r in health_results)

        manager.update_connection(
            connection.connection_id,
            status=ConnectionStatus.CONNECTED if all_healthy else ConnectionStatus.DEGRADED,
            last_health_check=datetime.utcnow(),
            error_message=None if all_healthy else "Health check failed",
        )

        return {
            "connection_id": connection.connection_id,
            "healthy": all_healthy,
            "checks": [r.to_dict() for r in health_results],
        }

    except Exception as e:
        logger.warning(
            "Health check failed for connection %s: %s",
            connection.connection_id,
            e,
        )
        return {
            "connection_id": connection.connection_id,
            "healthy": False,
            "error": str(e),
        }


@shared_task(name="dataspace.sync_registrations")
def sync_registrations_task(connection_id: str) -> dict:
    """
    Sync registration state with the Digital Twin Registry.

    Fetches current state from DTR and updates local registrations.

    Args:
        connection_id: Connection to sync registrations for

    Returns:
        Sync results
    """
    from app.services.dataspace.connection_manager import ConnectionManager
    from app.services.dataspace.models import RegistrationStatus

    manager = ConnectionManager()

    connection = manager.get_connection(connection_id)
    if connection is None:
        return {"error": "Connection not found", "connection_id": connection_id}

    registrations = manager.list_registrations(connection_id=connection_id)

    if not registrations:
        return {
            "connection_id": connection_id,
            "registrations_synced": 0,
            "message": "No registrations to sync",
        }

    # Get provider for checking DTR state
    provider = get_provider_for_connection(connection)

    synced_count = 0
    errors = []

    for registration in registrations:
        try:
            # For now, just verify the registration is still valid
            # Future: Query DTR to verify asset exists
            if registration.status == RegistrationStatus.REGISTERED:
                synced_count += 1

        except Exception as e:
            logger.warning(
                "Failed to sync registration %s: %s",
                registration.registration_id,
                e,
            )
            errors.append({
                "registration_id": registration.registration_id,
                "error": str(e),
            })

    return {
        "connection_id": connection_id,
        "registrations_synced": synced_count,
        "total_registrations": len(registrations),
        "errors": errors if errors else None,
    }


@shared_task(name="dataspace.disconnect")
def disconnect_dataspace_task(connection_id: str) -> dict:
    """
    Disconnect from a dataspace.

    Gracefully closes the connection and cleans up resources.

    Args:
        connection_id: Connection to disconnect

    Returns:
        Disconnect result
    """
    from app.services.dataspace.connection_manager import ConnectionManager
    from app.services.dataspace.models import ConnectionStatus

    manager = ConnectionManager()

    connection = manager.get_connection(connection_id)
    if connection is None:
        return {"error": "Connection not found", "connection_id": connection_id}

    try:
        provider = get_provider_for_connection(connection)
        updated_connection = run_async(provider.disconnect(connection))

        manager.update_connection(
            connection_id,
            status=ConnectionStatus.DISCONNECTED,
        )

        logger.info("Connection %s disconnected", connection_id)

        return {
            "connection_id": connection_id,
            "status": "disconnected",
        }

    except Exception as e:
        logger.exception("Failed to disconnect connection %s", connection_id)
        return {
            "error": str(e),
            "connection_id": connection_id,
        }
