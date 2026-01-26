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
    ERROR = "error"
    AUTHENTICATING = "authenticating"


class RegistrationStatus(str, Enum):
    """Status of an asset registration."""

    PENDING = "pending"
    REGISTERED = "registered"
    FAILED = "failed"
    UPDATING = "updating"


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
