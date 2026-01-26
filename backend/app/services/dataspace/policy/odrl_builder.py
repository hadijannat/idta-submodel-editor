"""
ODRL Policy Builder.

Provides a fluent builder API for constructing ODRL policies
for dataspace data contracts.
"""

from __future__ import annotations

import uuid
from typing import Any, Self


class ODRLBuilder:
    """
    Fluent builder for ODRL policies.

    Example usage:
        policy = (ODRLBuilder()
            .set_id("policy-123")
            .as_offer()
            .add_permission("use")
                .with_constraint("Membership", "eq", "active")
                .with_constraint("BPN", "isAnyOf", ["BPNL123", "BPNL456"])
                .done()
            .add_prohibition("transfer")
                .done()
            .build())
    """

    # ODRL namespaces and prefixes
    ODRL_CONTEXT = {
        "@vocab": "https://w3id.org/edc/v0.0.1/ns/",
        "odrl": "http://www.w3.org/ns/odrl/2/",
        "cx-policy": "https://w3id.org/catena-x/policy",
    }

    def __init__(self) -> None:
        """Initialize the policy builder."""
        self._id: str = f"urn:uuid:{uuid.uuid4()}"
        self._type: str = "Set"
        self._profile: str | None = None
        self._permissions: list[dict[str, Any]] = []
        self._prohibitions: list[dict[str, Any]] = []
        self._obligations: list[dict[str, Any]] = []
        self._assigner: str | None = None
        self._assignee: str | None = None

    def set_id(self, policy_id: str) -> Self:
        """
        Set the policy ID.

        Args:
            policy_id: Unique policy identifier

        Returns:
            Self for chaining
        """
        self._id = policy_id
        return self

    def as_set(self) -> Self:
        """Set policy type to Set (general policy)."""
        self._type = "Set"
        return self

    def as_offer(self) -> Self:
        """Set policy type to Offer (provider's offer)."""
        self._type = "Offer"
        return self

    def as_agreement(self) -> Self:
        """Set policy type to Agreement (accepted contract)."""
        self._type = "Agreement"
        return self

    def with_profile(self, profile: str) -> Self:
        """
        Set the ODRL profile.

        Args:
            profile: Profile URI (e.g., Catena-X policy profile)

        Returns:
            Self for chaining
        """
        self._profile = profile
        return self

    def with_catena_x_profile(self) -> Self:
        """Set the Catena-X policy profile."""
        self._profile = "https://w3id.org/catena-x/policy"
        return self

    def set_assigner(self, assigner: str) -> Self:
        """
        Set the policy assigner (provider).

        Args:
            assigner: Assigner identifier (e.g., BPN)

        Returns:
            Self for chaining
        """
        self._assigner = assigner
        return self

    def set_assignee(self, assignee: str) -> Self:
        """
        Set the policy assignee (consumer).

        Args:
            assignee: Assignee identifier (e.g., BPN)

        Returns:
            Self for chaining
        """
        self._assignee = assignee
        return self

    def add_permission(self, action: str) -> RuleBuilder:
        """
        Add a permission rule.

        Args:
            action: Action being permitted (e.g., "use", "read", "transfer")

        Returns:
            RuleBuilder for configuring the permission
        """
        return RuleBuilder(self, "permission", action)

    def add_prohibition(self, action: str) -> RuleBuilder:
        """
        Add a prohibition rule.

        Args:
            action: Action being prohibited

        Returns:
            RuleBuilder for configuring the prohibition
        """
        return RuleBuilder(self, "prohibition", action)

    def add_obligation(self, action: str) -> RuleBuilder:
        """
        Add an obligation rule.

        Args:
            action: Action that must be performed

        Returns:
            RuleBuilder for configuring the obligation
        """
        return RuleBuilder(self, "obligation", action)

    def _add_rule(self, rule_type: str, rule: dict[str, Any]) -> None:
        """Internal method to add a completed rule."""
        if rule_type == "permission":
            self._permissions.append(rule)
        elif rule_type == "prohibition":
            self._prohibitions.append(rule)
        elif rule_type == "obligation":
            self._obligations.append(rule)

    def build(self) -> dict[str, Any]:
        """
        Build the final ODRL policy document.

        Returns:
            Complete ODRL policy as dictionary
        """
        policy: dict[str, Any] = {
            "@context": self.ODRL_CONTEXT,
            "@type": self._type,
            "@id": self._id,
        }

        if self._profile:
            policy["profile"] = self._profile

        if self._assigner:
            policy["assigner"] = self._assigner

        if self._assignee:
            policy["assignee"] = self._assignee

        if self._permissions:
            policy["permission"] = self._permissions

        if self._prohibitions:
            policy["prohibition"] = self._prohibitions

        if self._obligations:
            policy["obligation"] = self._obligations

        return policy


class RuleBuilder:
    """
    Builder for individual policy rules (permissions, prohibitions, obligations).

    Used internally by ODRLBuilder.
    """

    def __init__(
        self,
        parent: ODRLBuilder,
        rule_type: str,
        action: str,
    ) -> None:
        """
        Initialize the rule builder.

        Args:
            parent: Parent ODRLBuilder
            rule_type: Type of rule (permission, prohibition, obligation)
            action: Action for this rule
        """
        self._parent = parent
        self._rule_type = rule_type
        self._action = action
        self._constraints: list[dict[str, Any]] = []
        self._duties: list[dict[str, Any]] = []
        self._target: str | None = None

    def with_constraint(
        self,
        left_operand: str,
        operator: str,
        right_operand: Any,
    ) -> Self:
        """
        Add a constraint to the rule.

        Args:
            left_operand: Constraint left operand (e.g., "Membership", "BPN")
            operator: Constraint operator (e.g., "eq", "isAnyOf")
            right_operand: Constraint right operand value

        Returns:
            Self for chaining
        """
        self._constraints.append({
            "leftOperand": left_operand,
            "operator": operator,
            "rightOperand": right_operand,
        })
        return self

    def with_and_constraints(self, constraints: list[dict[str, Any]]) -> Self:
        """
        Add an AND logical constraint group.

        Args:
            constraints: List of constraints that must all be satisfied

        Returns:
            Self for chaining
        """
        self._constraints.append({"and": constraints})
        return self

    def with_or_constraints(self, constraints: list[dict[str, Any]]) -> Self:
        """
        Add an OR logical constraint group.

        Args:
            constraints: List of constraints where at least one must be satisfied

        Returns:
            Self for chaining
        """
        self._constraints.append({"or": constraints})
        return self

    def with_membership_constraint(self, membership_type: str = "active") -> Self:
        """
        Add a Catena-X membership constraint.

        Args:
            membership_type: Required membership type

        Returns:
            Self for chaining
        """
        return self.with_constraint("Membership", "eq", membership_type)

    def with_bpn_constraint(self, bpns: list[str]) -> Self:
        """
        Add a BPN (Business Partner Number) constraint.

        Args:
            bpns: List of allowed BPNs

        Returns:
            Self for chaining
        """
        if len(bpns) == 1:
            return self.with_constraint("BPN", "eq", bpns[0])
        return self.with_constraint("BPN", "isAnyOf", bpns)

    def with_purpose_constraint(self, purposes: list[str]) -> Self:
        """
        Add a purpose constraint.

        Args:
            purposes: List of allowed purposes

        Returns:
            Self for chaining
        """
        if len(purposes) == 1:
            return self.with_constraint("Purpose", "eq", purposes[0])
        return self.with_constraint("Purpose", "isAnyOf", purposes)

    def with_framework_agreement_constraint(
        self,
        framework: str,
        version: str | None = None,
    ) -> Self:
        """
        Add a framework agreement constraint.

        Args:
            framework: Framework name (e.g., "DataExchange")
            version: Optional framework version

        Returns:
            Self for chaining
        """
        value = framework if version is None else f"{framework}:{version}"
        return self.with_constraint("FrameworkAgreement", "eq", value)

    def with_duty(self, action: str, constraint: dict[str, Any] | None = None) -> Self:
        """
        Add a duty (obligation attached to permission).

        Args:
            action: Duty action
            constraint: Optional constraint for the duty

        Returns:
            Self for chaining
        """
        duty: dict[str, Any] = {"action": action}
        if constraint:
            duty["constraint"] = [constraint]
        self._duties.append(duty)
        return self

    def for_target(self, target: str) -> Self:
        """
        Set the target asset for this rule.

        Args:
            target: Target asset ID

        Returns:
            Self for chaining
        """
        self._target = target
        return self

    def done(self) -> ODRLBuilder:
        """
        Complete the rule and return to parent builder.

        Returns:
            Parent ODRLBuilder for further configuration
        """
        rule: dict[str, Any] = {"action": self._action}

        if self._constraints:
            rule["constraint"] = self._constraints

        if self._duties:
            rule["duty"] = self._duties

        if self._target:
            rule["target"] = self._target

        self._parent._add_rule(self._rule_type, rule)
        return self._parent


# ---------------------------------------------------------------------------
# Convenience Functions for Common ODRL Structures
# ---------------------------------------------------------------------------


def build_bpn_access_policy(
    allowed_bpns: list[str],
    policy_id: str | None = None,
) -> dict[str, Any]:
    """
    Build a BPN (Business Partner Number) allowlist access policy.

    This creates an ODRL policy that restricts access to a specific
    list of business partners identified by their BPN.

    Args:
        allowed_bpns: List of BPNs allowed to access the asset
        policy_id: Optional policy ID (auto-generated if not provided)

    Returns:
        ODRL policy document as dictionary

    Example:
        >>> policy = build_bpn_access_policy(["BPNL00000001AAAA", "BPNL00000001BBBB"])
        >>> policy["permission"][0]["constraint"][0]["leftOperand"]
        'BusinessPartnerNumber'
    """
    builder = ODRLBuilder().as_offer().with_catena_x_profile()

    if policy_id:
        builder.set_id(policy_id)

    if len(allowed_bpns) == 1:
        builder.add_permission("use").with_constraint(
            "BusinessPartnerNumber", "eq", allowed_bpns[0]
        ).done()
    else:
        builder.add_permission("use").with_constraint(
            "BusinessPartnerNumber", "isAnyOf", allowed_bpns
        ).done()

    return builder.build()


def build_contract_policy(
    constraints: list[dict[str, Any]],
    require_membership: bool = True,
    valid_from: str | None = None,
    valid_until: str | None = None,
    policy_id: str | None = None,
) -> dict[str, Any]:
    """
    Build a contract policy with membership and/or time constraints.

    This creates an ODRL policy that defines usage constraints for
    data contracts, including membership requirements and time limits.

    Args:
        constraints: List of additional constraint dicts with keys:
                    - left_operand: Constraint left operand
                    - operator: Constraint operator (eq, isAnyOf, etc.)
                    - right_operand: Constraint value(s)
        require_membership: Whether to require active Catena-X membership
        valid_from: Optional ISO8601 timestamp for validity start
        valid_until: Optional ISO8601 timestamp for validity end
        policy_id: Optional policy ID (auto-generated if not provided)

    Returns:
        ODRL policy document as dictionary

    Example:
        >>> policy = build_contract_policy(
        ...     constraints=[{"left_operand": "Purpose", "operator": "eq", "right_operand": "cx.pcf:1"}],
        ...     require_membership=True,
        ...     valid_until="2025-12-31T23:59:59Z"
        ... )
    """
    builder = ODRLBuilder().as_offer().with_catena_x_profile()

    if policy_id:
        builder.set_id(policy_id)

    perm_builder = builder.add_permission("use")

    # Add membership constraint
    if require_membership:
        perm_builder.with_membership_constraint("active")

    # Add time constraints if provided
    if valid_from:
        perm_builder.with_constraint("dateTime", "gteq", valid_from)

    if valid_until:
        perm_builder.with_constraint("dateTime", "lteq", valid_until)

    # Add additional constraints
    for constraint in constraints:
        left = constraint.get("left_operand", constraint.get("leftOperand"))
        op = constraint.get("operator")
        right = constraint.get("right_operand", constraint.get("rightOperand"))
        if left and op and right is not None:
            perm_builder.with_constraint(left, op, right)

    return perm_builder.done().build()


def build_contract_definition(
    asset_id: str,
    access_policy_id: str,
    contract_policy_id: str,
    definition_id: str | None = None,
) -> dict[str, Any]:
    """
    Build a contract definition linking an asset to policies.

    A contract definition is the EDC entity that links an asset to
    its access policy (who can see) and contract policy (usage terms).

    Args:
        asset_id: ID of the asset being offered
        access_policy_id: ID of the access policy (BPN allowlist)
        contract_policy_id: ID of the contract policy (usage constraints)
        definition_id: Optional definition ID (auto-generated if not provided)

    Returns:
        Contract definition document as dictionary

    Example:
        >>> definition = build_contract_definition(
        ...     asset_id="asset-123",
        ...     access_policy_id="access-policy-456",
        ...     contract_policy_id="contract-policy-789"
        ... )
    """
    if definition_id is None:
        definition_id = f"urn:uuid:{uuid.uuid4()}"

    return {
        "@context": {
            "@vocab": "https://w3id.org/edc/v0.0.1/ns/",
            "odrl": "http://www.w3.org/ns/odrl/2/",
        },
        "@type": "ContractDefinition",
        "@id": definition_id,
        "accessPolicyId": access_policy_id,
        "contractPolicyId": contract_policy_id,
        "assetsSelector": {
            "@type": "CriterionDto",
            "operandLeft": "https://w3id.org/edc/v0.0.1/ns/id",
            "operator": "=",
            "operandRight": asset_id,
        },
    }


def build_asset_entry(
    asset_id: str,
    submodel_endpoint: str,
    semantic_id: str | None = None,
    description: str | None = None,
    properties: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build an EDC asset entry for a submodel or element.

    This creates the EDC asset registration payload that describes
    a Digital Twin asset for catalog publishing.

    Args:
        asset_id: Unique asset identifier
        submodel_endpoint: URL endpoint for the submodel data
        semantic_id: Optional semantic identifier for the submodel
        description: Optional human-readable description
        properties: Optional additional properties

    Returns:
        EDC asset entry as dictionary
    """
    asset_entry: dict[str, Any] = {
        "@context": {
            "@vocab": "https://w3id.org/edc/v0.0.1/ns/",
            "aas": "https://admin-shell.io/aas/3/0/",
            "cx": "https://w3id.org/catena-x/ontology#",
        },
        "@type": "Asset",
        "@id": asset_id,
        "properties": {
            "aas:submodelEndpoint": submodel_endpoint,
        },
    }

    if semantic_id:
        asset_entry["properties"]["aas:semanticId"] = semantic_id

    if description:
        asset_entry["properties"]["description"] = description

    if properties:
        asset_entry["properties"].update(properties)

    return asset_entry


def create_element_assets(
    base_asset_id: str,
    submodel_endpoint: str,
    element_paths: list[str],
    semantic_id: str | None = None,
) -> list[dict[str, Any]]:
    """
    Create assets for granular element-level access control.

    This generates separate EDC assets for specific submodel elements,
    enabling fine-grained access policies per element path.

    Args:
        base_asset_id: Base asset ID prefix for the submodel
        submodel_endpoint: URL endpoint for the submodel
        element_paths: List of idShortPath values for elements to expose
        semantic_id: Optional semantic ID for the submodel

    Returns:
        List of EDC asset entries, one per element path

    Example:
        >>> assets = create_element_assets(
        ...     base_asset_id="urn:asset:nameplate",
        ...     submodel_endpoint="https://basyx.example.com/submodel/1",
        ...     element_paths=["SerialNumber", "ProductType/ManufacturerName"]
        ... )
        >>> len(assets)
        2
        >>> assets[0]["@id"]
        'urn:asset:nameplate:SerialNumber'
    """
    assets = []

    for path in element_paths:
        # Create a sanitized suffix from the path
        path_suffix = path.replace("/", ":")

        asset_id = f"{base_asset_id}:{path_suffix}"
        element_endpoint = f"{submodel_endpoint}/submodel-elements/{path}"

        asset = build_asset_entry(
            asset_id=asset_id,
            submodel_endpoint=element_endpoint,
            semantic_id=semantic_id,
            description=f"Element: {path}",
            properties={
                "aas:idShortPath": path,
                "cx:elementLevel": True,
            },
        )
        assets.append(asset)

    return assets
