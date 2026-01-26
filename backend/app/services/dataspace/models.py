"""
Internal dataclasses and enums for dataspace connectivity.

These are internal models used within the dataspace module.
For API-facing schemas, see app/schemas/dataspace.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ConnectionStatus(str, Enum):
    """Status of a dataspace connection."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DEGRADED = "degraded"
    ERROR = "error"
    AUTHENTICATING = "authenticating"


class RegistrationStatus(str, Enum):
    """Status of an asset registration."""

    PENDING = "pending"
    REGISTERED = "registered"
    FAILED = "failed"
    UPDATING = "updating"
    UNPUBLISHING = "unpublishing"
    UNPUBLISHED = "unpublished"


class ContractState(str, Enum):
    """State of a data contract negotiation."""

    INITIAL = "initial"
    REQUESTING = "requesting"
    OFFERED = "offered"
    AGREEING = "agreeing"
    AGREED = "agreed"
    VERIFYING = "verifying"
    VERIFIED = "verified"
    FINALIZED = "finalized"
    TERMINATED = "terminated"
    ERROR = "error"


class DataspaceType(str, Enum):
    """Type of dataspace environment."""

    SANDBOX = "sandbox"
    CATENA_X = "catena-x"
    MANUFACTURING_X = "manufacturing-x"


class PolicyType(str, Enum):
    """Type of ODRL policy."""

    USE = "use"
    ACCESS = "access"
    TRANSFER = "transfer"


@dataclass
class ConnectionState:
    """
    Internal state for a dataspace connection.

    Persisted to cache directory for recovery across restarts.
    """

    connection_id: str
    dataspace_type: DataspaceType
    owner_id: str | None = None
    status: ConnectionStatus = ConnectionStatus.DISCONNECTED
    provider_url: str | None = None
    dtr_url: str | None = None
    edc_url: str | None = None
    bpn: str | None = None  # Business Partner Number
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_health_check: datetime | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON persistence."""
        return {
            "connection_id": self.connection_id,
            "owner_id": self.owner_id,
            "dataspace_type": self.dataspace_type.value,
            "status": self.status.value,
            "provider_url": self.provider_url,
            "dtr_url": self.dtr_url,
            "edc_url": self.edc_url,
            "bpn": self.bpn,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_health_check": self.last_health_check.isoformat() if self.last_health_check else None,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConnectionState":
        """Deserialize from dictionary."""
        return cls(
            connection_id=data["connection_id"],
            owner_id=data.get("owner_id"),
            dataspace_type=DataspaceType(data["dataspace_type"]),
            status=ConnectionStatus(data["status"]),
            provider_url=data.get("provider_url"),
            dtr_url=data.get("dtr_url"),
            edc_url=data.get("edc_url"),
            bpn=data.get("bpn"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            last_health_check=(
                datetime.fromisoformat(data["last_health_check"])
                if data.get("last_health_check")
                else None
            ),
            error_message=data.get("error_message"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class AssetRegistration:
    """
    Internal state for a registered asset.

    Tracks the registration of a Digital Twin in a DTR.
    """

    registration_id: str
    connection_id: str
    aas_id: str
    submodel_id: str
    status: RegistrationStatus = RegistrationStatus.PENDING
    dtr_asset_id: str | None = None  # ID assigned by the registry
    edc_asset_id: str | None = None  # ID assigned by EDC
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON persistence."""
        return {
            "registration_id": self.registration_id,
            "connection_id": self.connection_id,
            "aas_id": self.aas_id,
            "submodel_id": self.submodel_id,
            "status": self.status.value,
            "dtr_asset_id": self.dtr_asset_id,
            "edc_asset_id": self.edc_asset_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "error_message": self.error_message,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AssetRegistration":
        """Deserialize from dictionary."""
        return cls(
            registration_id=data["registration_id"],
            connection_id=data["connection_id"],
            aas_id=data["aas_id"],
            submodel_id=data["submodel_id"],
            status=RegistrationStatus(data["status"]),
            dtr_asset_id=data.get("dtr_asset_id"),
            edc_asset_id=data.get("edc_asset_id"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            error_message=data.get("error_message"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ContractNegotiation:
    """
    Internal state for a contract negotiation.

    Tracks the negotiation of a data contract with a provider.
    """

    negotiation_id: str
    connection_id: str
    asset_id: str
    provider_bpn: str
    consumer_bpn: str
    state: ContractState = ContractState.INITIAL
    offer_id: str | None = None
    agreement_id: str | None = None
    policy_id: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON persistence."""
        return {
            "negotiation_id": self.negotiation_id,
            "connection_id": self.connection_id,
            "asset_id": self.asset_id,
            "provider_bpn": self.provider_bpn,
            "consumer_bpn": self.consumer_bpn,
            "state": self.state.value,
            "offer_id": self.offer_id,
            "agreement_id": self.agreement_id,
            "policy_id": self.policy_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "error_message": self.error_message,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ContractNegotiation":
        """Deserialize from dictionary."""
        return cls(
            negotiation_id=data["negotiation_id"],
            connection_id=data["connection_id"],
            asset_id=data["asset_id"],
            provider_bpn=data["provider_bpn"],
            consumer_bpn=data["consumer_bpn"],
            state=ContractState(data["state"]),
            offer_id=data.get("offer_id"),
            agreement_id=data.get("agreement_id"),
            policy_id=data.get("policy_id"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            error_message=data.get("error_message"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class HealthCheckResult:
    """Result of a dataspace health check."""

    component: str
    healthy: bool
    latency_ms: float | None = None
    message: str | None = None
    checked_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "component": self.component,
            "healthy": self.healthy,
            "latency_ms": self.latency_ms,
            "message": self.message,
            "checked_at": self.checked_at.isoformat(),
        }


class TransferState(str, Enum):
    """State of a data transfer process."""

    INITIAL = "initial"
    PROVISIONING = "provisioning"
    PROVISIONED = "provisioned"
    REQUESTING = "requesting"
    STARTED = "started"
    SUSPENDED = "suspended"
    COMPLETED = "completed"
    TERMINATED = "terminated"
    DEPROVISIONING = "deprovisioning"
    DEPROVISIONED = "deprovisioned"
    ERROR = "error"


@dataclass
class TransferProcess:
    """
    Internal state for a data transfer process.

    Tracks the transfer of data from a provider to consumer after
    a contract has been negotiated.
    """

    transfer_id: str
    connection_id: str
    agreement_id: str
    asset_id: str
    provider_bpn: str
    consumer_bpn: str | None = None
    state: TransferState = TransferState.INITIAL
    edc_transfer_id: str | None = None  # ID assigned by EDC
    edr_endpoint: str | None = None  # Endpoint Data Reference URL
    edr_token: str | None = None  # EDR auth token
    edr_expires_at: datetime | None = None
    data_destination: str | None = None  # Where to send the data
    transfer_type: str = "HttpData-PULL"  # HttpData-PULL, HttpData-PUSH, etc.
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON persistence."""
        return {
            "transfer_id": self.transfer_id,
            "connection_id": self.connection_id,
            "agreement_id": self.agreement_id,
            "asset_id": self.asset_id,
            "provider_bpn": self.provider_bpn,
            "consumer_bpn": self.consumer_bpn,
            "state": self.state.value,
            "edc_transfer_id": self.edc_transfer_id,
            "edr_endpoint": self.edr_endpoint,
            "edr_token": self.edr_token,
            "edr_expires_at": self.edr_expires_at.isoformat() if self.edr_expires_at else None,
            "data_destination": self.data_destination,
            "transfer_type": self.transfer_type,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TransferProcess":
        """Deserialize from dictionary."""
        return cls(
            transfer_id=data["transfer_id"],
            connection_id=data["connection_id"],
            agreement_id=data["agreement_id"],
            asset_id=data["asset_id"],
            provider_bpn=data["provider_bpn"],
            consumer_bpn=data.get("consumer_bpn"),
            state=TransferState(data["state"]),
            edc_transfer_id=data.get("edc_transfer_id"),
            edr_endpoint=data.get("edr_endpoint"),
            edr_token=data.get("edr_token"),
            edr_expires_at=(
                datetime.fromisoformat(data["edr_expires_at"])
                if data.get("edr_expires_at")
                else None
            ),
            data_destination=data.get("data_destination"),
            transfer_type=data.get("transfer_type", "HttpData-PULL"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            started_at=(
                datetime.fromisoformat(data["started_at"])
                if data.get("started_at")
                else None
            ),
            completed_at=(
                datetime.fromisoformat(data["completed_at"])
                if data.get("completed_at")
                else None
            ),
            error_message=data.get("error_message"),
            metadata=data.get("metadata", {}),
        )

    @property
    def is_terminal(self) -> bool:
        """Check if transfer is in a terminal state."""
        return self.state in (
            TransferState.COMPLETED,
            TransferState.TERMINATED,
            TransferState.ERROR,
        )

    @property
    def is_active(self) -> bool:
        """Check if transfer is actively in progress."""
        return self.state in (
            TransferState.PROVISIONING,
            TransferState.REQUESTING,
            TransferState.STARTED,
        )


class AuditEventType(str, Enum):
    """Type of audit event."""

    # Connection events
    CONNECTION_CREATED = "connection_created"
    CONNECTION_CONNECTED = "connection_connected"
    CONNECTION_DISCONNECTED = "connection_disconnected"
    CONNECTION_FAILED = "connection_failed"
    CONNECTION_HEALTH_CHECK = "connection_health_check"

    # Publication events
    PUBLICATION_STARTED = "publication_started"
    PUBLICATION_COMPLETED = "publication_completed"
    PUBLICATION_FAILED = "publication_failed"
    PUBLICATION_UPDATED = "publication_updated"
    PUBLICATION_UNPUBLISHED = "publication_unpublished"

    # Catalog events
    CATALOG_SEARCHED = "catalog_searched"
    PROVIDER_ADDED = "provider_added"

    # Negotiation events
    NEGOTIATION_INITIATED = "negotiation_initiated"
    NEGOTIATION_COMPLETED = "negotiation_completed"
    NEGOTIATION_FAILED = "negotiation_failed"
    NEGOTIATION_TERMINATED = "negotiation_terminated"

    # Transfer events
    TRANSFER_INITIATED = "transfer_initiated"
    TRANSFER_STARTED = "transfer_started"
    TRANSFER_COMPLETED = "transfer_completed"
    TRANSFER_FAILED = "transfer_failed"
    TRANSFER_TERMINATED = "transfer_terminated"

    # Policy events
    POLICY_CREATED = "policy_created"
    POLICY_UPDATED = "policy_updated"
    POLICY_DELETED = "policy_deleted"

    # General events
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class AuditLogEntry:
    """
    Audit log entry for dataspace events.

    Provides a complete audit trail of all dataspace operations.
    """

    entry_id: str
    event_type: AuditEventType
    timestamp: datetime = field(default_factory=datetime.utcnow)
    connection_id: str | None = None
    resource_id: str | None = None
    resource_type: str | None = None  # connection, publication, transfer, negotiation, policy
    actor: str | None = None  # User or system ID
    action: str = ""  # Human-readable action description
    details: dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON persistence."""
        return {
            "entry_id": self.entry_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "connection_id": self.connection_id,
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "actor": self.actor,
            "action": self.action,
            "details": self.details,
            "success": self.success,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuditLogEntry":
        """Deserialize from dictionary."""
        return cls(
            entry_id=data["entry_id"],
            event_type=AuditEventType(data["event_type"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            connection_id=data.get("connection_id"),
            resource_id=data.get("resource_id"),
            resource_type=data.get("resource_type"),
            actor=data.get("actor"),
            action=data.get("action", ""),
            details=data.get("details", {}),
            success=data.get("success", True),
            error_message=data.get("error_message"),
        )
