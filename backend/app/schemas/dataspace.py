"""
Pydantic schemas for Dataspace Connector API.

These are the API-facing models used by the dataspace router.
For internal service models, see app/services/dataspace/models.py
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DataspaceConnectionStatus(str, Enum):
    """Status of a dataspace connection lifecycle."""

    NOT_CONNECTED = "not_connected"
    PROVISIONING_SECRETS = "provisioning_secrets"
    CONFIGURING_EDC = "configuring_edc"
    REGISTERING_CONNECTOR = "registering_connector"
    PUBLISHING_SELF_DESCRIPTION = "publishing_self_description"
    CONNECTED = "connected"
    DEGRADED = "degraded"
    DISCONNECTED = "disconnected"
    FAILED = "failed"


class PublicationStatus(str, Enum):
    """Status of a submodel publication."""

    PENDING = "pending"
    REGISTERING = "registering"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    UPDATING = "updating"
    UNPUBLISHING = "unpublishing"
    UNPUBLISHED = "unpublished"
    FAILED = "failed"


class AccessType(str, Enum):
    """Access type for policy configuration."""

    PUBLIC = "public"
    RESTRICTED = "restricted"
    MEMBERSHIP = "membership"


class ConstraintOperator(str, Enum):
    """ODRL constraint operators."""

    EQ = "eq"
    NEQ = "neq"
    LT = "lt"
    GT = "gt"
    LTEQ = "lteq"
    GTEQ = "gteq"
    IN = "in"
    HAS_PART = "hasPart"
    IS_PART_OF = "isPartOf"
    IS_ALL_OF = "isAllOf"
    IS_ANY_OF = "isAnyOf"
    IS_NONE_OF = "isNoneOf"


# ---------------------------------------------------------------------------
# Base Types
# ---------------------------------------------------------------------------


class EndpointInfo(BaseModel):
    """Information about a service endpoint."""

    url: str = Field(description="Endpoint URL")
    protocol: str | None = Field(default=None, description="Protocol (e.g., HTTPS, IDS)")
    healthy: bool | None = Field(default=None, description="Health status if checked")
    latency_ms: float | None = Field(default=None, description="Last measured latency")


class HealthCheckResult(BaseModel):
    """Result of a component health check."""

    component: str = Field(description="Component name")
    healthy: bool = Field(description="Whether the component is healthy")
    latency_ms: float | None = Field(default=None, description="Response latency")
    message: str | None = Field(default=None, description="Status message or error")
    checked_at: datetime = Field(description="When the check was performed")


# ---------------------------------------------------------------------------
# Policy Configuration
# ---------------------------------------------------------------------------


class PolicyConstraint(BaseModel):
    """A single ODRL constraint for a policy."""

    left_operand: str = Field(
        description="Left operand (e.g., 'BusinessPartnerNumber', 'Membership')"
    )
    operator: ConstraintOperator = Field(description="Constraint operator")
    right_operand: str | list[str] = Field(
        description="Right operand value(s)"
    )


class PolicyConfig(BaseModel):
    """Configuration for access policies on published assets."""

    target_paths: list[str] = Field(
        default_factory=list,
        description="idShortPaths of elements this policy applies to (empty = entire submodel)",
    )
    allowed_partners: list[str] = Field(
        default_factory=list,
        description="List of BPNs allowed access (for RESTRICTED access type)",
    )
    access_type: AccessType = Field(
        default=AccessType.RESTRICTED,
        description="Access type determining policy template",
    )
    constraints: list[PolicyConstraint] = Field(
        default_factory=list,
        description="Additional ODRL constraints",
    )
    valid_from: datetime | None = Field(
        default=None, description="Policy validity start time"
    )
    valid_until: datetime | None = Field(
        default=None, description="Policy validity end time"
    )

    @field_validator("allowed_partners")
    @classmethod
    def validate_bpns(cls, v: list[str]) -> list[str]:
        """Validate BPN format (BPNL followed by alphanumeric)."""
        for bpn in v:
            if not bpn.startswith("BPNL") or len(bpn) < 16:
                raise ValueError(f"Invalid BPN format: {bpn}. Expected BPNL followed by 12+ alphanumeric chars.")
        return v


# ---------------------------------------------------------------------------
# Dataspace Connection
# ---------------------------------------------------------------------------


class DataspaceConnection(BaseModel):
    """A dataspace connection with full status and endpoints."""

    connection_id: str = Field(description="Unique connection identifier")
    status: DataspaceConnectionStatus = Field(description="Current connection status")
    environment: Literal["sandbox", "catena-x-test", "catena-x-prod"] = Field(
        description="Target dataspace environment"
    )
    edc_mode: Literal["tractus-x", "aas-extension"] = Field(
        description="EDC connector mode"
    )
    bpn: str | None = Field(default=None, description="Business Partner Number")
    # Component endpoints (flat fields per spec)
    basyx_url: str | None = Field(default=None, description="BaSyx AAS Server URL")
    dtr_url: str | None = Field(default=None, description="Digital Twin Registry URL")
    edc_control_url: str | None = Field(default=None, description="EDC Control Plane URL")
    edc_data_url: str | None = Field(default=None, description="EDC Data Plane URL")
    # Progress tracking
    progress: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        default=0.0, description="Connection progress (0.0-1.0)"
    )
    progress_message: str | None = Field(
        default=None, description="Human-readable progress status"
    )
    error_message: str | None = Field(
        default=None, description="Error details if status is FAILED"
    )
    last_health_check: datetime | None = Field(
        default=None, description="Timestamp of last health check"
    )
    created_at: datetime = Field(description="Connection creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")

    @field_validator("bpn")
    @classmethod
    def validate_bpn_format(cls, v: str | None) -> str | None:
        """Validate BPN format if provided."""
        if v is not None and not v.startswith("BPNL"):
            raise ValueError(f"Invalid BPN format: {v}. Must start with 'BPNL'.")
        return v


# ---------------------------------------------------------------------------
# Submodel Publication
# ---------------------------------------------------------------------------


class SubmodelPublication(BaseModel):
    """A published submodel in a dataspace."""

    publication_id: str = Field(description="Unique publication identifier")
    connection_id: str = Field(description="Associated dataspace connection ID")
    template_name: str = Field(description="Source template name")
    submodel_id: str = Field(description="Submodel identifier (IRI)")
    status: PublicationStatus = Field(description="Publication status")
    # Endpoint fields (flat per spec)
    aas_endpoint: str | None = Field(
        default=None, description="AAS Repository endpoint for this submodel"
    )
    dtr_asset_id: str | None = Field(
        default=None, description="Asset ID in Digital Twin Registry"
    )
    edc_offer_id: str | None = Field(
        default=None, description="Offer ID in EDC Catalog"
    )
    policy_id: str | None = Field(
        default=None, description="Associated policy configuration ID"
    )
    created_at: datetime = Field(description="Publication creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


# ---------------------------------------------------------------------------
# Request/Response Models
# ---------------------------------------------------------------------------


class CreateConnectionRequest(BaseModel):
    """Request to create a new dataspace connection."""

    environment: Literal["sandbox", "catena-x-test", "catena-x-prod"] = Field(
        description="Target dataspace environment"
    )
    edc_mode: Literal["tractus-x", "aas-extension"] = Field(
        default="tractus-x", description="EDC connector mode"
    )
    bpn: str | None = Field(default=None, description="Business Partner Number (required for Catena-X)")
    credentials: dict[str, str] | None = Field(
        default=None,
        description="Credentials for authentication (API keys, client secrets)",
    )

    @model_validator(mode="after")
    def validate_bpn_required_for_catenax(self) -> "CreateConnectionRequest":
        """Validate BPN is provided for Catena-X environments and has correct format."""
        if self.environment.startswith("catena-x") and not self.bpn:
            raise ValueError("BPN is required for Catena-X environments")
        if self.bpn is not None and not self.bpn.startswith("BPNL"):
            raise ValueError(f"Invalid BPN format: {self.bpn}. Must start with 'BPNL'.")
        return self


class CreateConnectionResponse(BaseModel):
    """Response after initiating a connection."""

    connection: DataspaceConnection = Field(description="Created connection")
    message: str = Field(description="Status message")


class ConnectionStatusResponse(BaseModel):
    """Response with current connection status."""

    connection: DataspaceConnection = Field(description="Connection details")
    health_checks: list[HealthCheckResult] = Field(
        default_factory=list, description="Recent health check results"
    )


class ListConnectionsResponse(BaseModel):
    """Response listing all connections."""

    connections: list[DataspaceConnection] = Field(
        default_factory=list, description="All dataspace connections"
    )
    total: int = Field(description="Total number of connections")


class DisconnectRequest(BaseModel):
    """Request to disconnect from a dataspace."""

    force: bool = Field(
        default=False,
        description="Force disconnect even if publications exist",
    )
    unpublish_all: bool = Field(
        default=False,
        description="Unpublish all assets before disconnecting",
    )


class DisconnectResponse(BaseModel):
    """Response after disconnecting."""

    connection_id: str = Field(description="Disconnected connection ID")
    status: DataspaceConnectionStatus = Field(description="Final connection status")
    unpublished_count: int = Field(
        default=0, description="Number of assets unpublished"
    )
    message: str = Field(description="Status message")


class PublishSubmodelRequest(BaseModel):
    """Request to publish a submodel to a dataspace."""

    connection_id: str = Field(description="Target dataspace connection ID")
    template_name: str = Field(description="Template name")
    template_status: Literal["published", "deprecated"] = Field(
        default="published", description="Template status"
    )
    template_version: str | None = Field(
        default=None, description="Template version"
    )
    form_data: dict = Field(description="Form data for the submodel")
    aas_id: str | None = Field(
        default=None,
        description="AAS identifier (auto-generated if not provided)",
    )
    submodel_id: str | None = Field(
        default=None,
        description="Submodel identifier (auto-generated if not provided)",
    )
    policy: PolicyConfig | None = Field(
        default=None, description="Access policy configuration"
    )


class PublishSubmodelResponse(BaseModel):
    """Response after initiating submodel publication."""

    publication: SubmodelPublication = Field(description="Publication details")
    message: str = Field(description="Status message")


class ListPublicationsRequest(BaseModel):
    """Request to list publications (query parameters)."""

    connection_id: str | None = Field(
        default=None, description="Filter by connection ID"
    )
    template_name: str | None = Field(
        default=None, description="Filter by template name"
    )
    status: PublicationStatus | None = Field(
        default=None, description="Filter by publication status"
    )


class ListPublicationsResponse(BaseModel):
    """Response listing publications."""

    publications: list[SubmodelPublication] = Field(
        default_factory=list, description="Matching publications"
    )
    total: int = Field(description="Total number of matching publications")


class UnpublishRequest(BaseModel):
    """Request to unpublish a submodel."""

    remove_from_registry: bool = Field(
        default=True, description="Remove from Digital Twin Registry"
    )
    remove_from_edc: bool = Field(
        default=True, description="Remove EDC asset and policies"
    )


class UnpublishResponse(BaseModel):
    """Response after unpublishing."""

    publication_id: str = Field(description="Unpublished publication ID")
    status: PublicationStatus = Field(description="Final publication status")
    message: str = Field(description="Status message")


class UpdatePolicyRequest(BaseModel):
    """Request to update a publication's policy."""

    policy: PolicyConfig = Field(description="New policy configuration")


class UpdatePolicyResponse(BaseModel):
    """Response after updating policy."""

    publication_id: str = Field(description="Publication ID")
    policy_id: str = Field(description="New policy ID")
    message: str = Field(description="Status message")


class HealthCheckRequest(BaseModel):
    """Request for health check (query parameters)."""

    components: list[str] | None = Field(
        default=None,
        description="Specific components to check (all if not specified)",
    )


class HealthCheckResponse(BaseModel):
    """Response with health check results."""

    connection_id: str = Field(description="Connection ID")
    overall_healthy: bool = Field(description="Overall health status")
    status: DataspaceConnectionStatus = Field(description="Current connection status")
    checks: list[HealthCheckResult] = Field(description="Individual component checks")
    checked_at: datetime = Field(description="When the check was performed")


class DataspaceCatalogEntry(BaseModel):
    """An entry in the dataspace catalog."""

    asset_id: str = Field(description="EDC asset ID")
    provider_bpn: str = Field(description="Provider's BPN")
    submodel_semantic_id: str | None = Field(
        default=None, description="Semantic ID of the submodel"
    )
    description: str | None = Field(default=None, description="Asset description")
    policy_ids: list[str] = Field(
        default_factory=list, description="Available policy IDs"
    )


class SearchCatalogRequest(BaseModel):
    """Request to search the dataspace catalog."""

    connection_id: str = Field(description="Connection to search from")
    semantic_id: str | None = Field(
        default=None, description="Filter by semantic ID"
    )
    provider_bpn: str | None = Field(
        default=None, description="Filter by provider BPN"
    )
    limit: int = Field(default=50, ge=1, le=200, description="Maximum results")
    offset: int = Field(default=0, ge=0, description="Result offset")


class SearchCatalogResponse(BaseModel):
    """Response from catalog search."""

    entries: list[DataspaceCatalogEntry] = Field(
        default_factory=list, description="Catalog entries"
    )
    total: int = Field(description="Total matching entries")
    has_more: bool = Field(description="Whether more results exist")
