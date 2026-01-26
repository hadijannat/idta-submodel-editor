"""
ODRL Policy Engine.

Provides policy evaluation and validation for dataspace data contracts.
Implements a subset of ODRL (Open Digital Rights Language) relevant
for Manufacturing-X / Catena-X use cases.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable

from app.services.dataspace.providers.provider_base import PolicyError

if TYPE_CHECKING:
    from app.schemas.dataspace import PolicyConfig

logger = logging.getLogger(__name__)


@dataclass
class TranslatedPolicy:
    """
    Result of translating a UI PolicyConfig to ODRL artifacts.

    Contains all the EDC-ready artifacts needed to publish an asset
    with access control: assets, access policy, contract policy,
    and contract definitions.
    """

    assets: list[dict[str, Any]] = field(default_factory=list)
    """List of EDC asset entries to register."""

    access_policy: dict[str, Any] = field(default_factory=dict)
    """ODRL access policy (who can see the asset in catalog)."""

    access_policy_id: str = ""
    """ID of the access policy."""

    contract_policy: dict[str, Any] = field(default_factory=dict)
    """ODRL contract policy (usage terms/constraints)."""

    contract_policy_id: str = ""
    """ID of the contract policy."""

    contract_definitions: list[dict[str, Any]] = field(default_factory=list)
    """Contract definitions linking assets to policies."""

    element_level: bool = False
    """Whether this uses element-level granular access control."""

    target_paths: list[str] = field(default_factory=list)
    """idShortPaths targeted by this policy (empty = entire submodel)."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "assets": self.assets,
            "access_policy": self.access_policy,
            "access_policy_id": self.access_policy_id,
            "contract_policy": self.contract_policy,
            "contract_policy_id": self.contract_policy_id,
            "contract_definitions": self.contract_definitions,
            "element_level": self.element_level,
            "target_paths": self.target_paths,
        }


class PolicyEngine:
    """
    ODRL Policy Engine for dataspace contracts.

    Evaluates and validates ODRL policies for data sharing agreements.
    Supports common constraint types used in Manufacturing-X / Catena-X.
    """

    # ODRL context and types
    ODRL_CONTEXT = "http://www.w3.org/ns/odrl/2/"
    ODRL_PROFILE = "https://w3id.org/catena-x/policy"

    # Common constraint operators
    OPERATORS = {
        "eq": lambda a, b: a == b,
        "neq": lambda a, b: a != b,
        "lt": lambda a, b: a < b,
        "gt": lambda a, b: a > b,
        "lteq": lambda a, b: a <= b,
        "gteq": lambda a, b: a >= b,
        "isA": lambda a, b: a == b,
        "hasPart": lambda a, b: b in a if isinstance(a, (list, set)) else False,
        "isPartOf": lambda a, b: a in b if isinstance(b, (list, set)) else False,
        "isAllOf": lambda a, b: all(x in a for x in b) if isinstance(a, (list, set)) else False,
        "isAnyOf": lambda a, b: any(x in a for x in b) if isinstance(a, (list, set)) else False,
        "isNoneOf": lambda a, b: not any(x in a for x in b) if isinstance(a, (list, set)) else True,
    }

    def __init__(self) -> None:
        """Initialize the policy engine."""
        self._custom_evaluators: dict[str, Callable[..., bool]] = {}

    def validate_policy(self, policy: dict[str, Any]) -> tuple[bool, list[str]]:
        """
        Validate an ODRL policy structure.

        Args:
            policy: ODRL policy document

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Check required fields
        if "@context" not in policy:
            errors.append("Missing @context field")

        if "@type" not in policy:
            errors.append("Missing @type field")
        elif policy["@type"] not in ("Set", "Offer", "Agreement"):
            errors.append(f"Invalid policy type: {policy['@type']}")

        if "@id" not in policy:
            errors.append("Missing @id field")

        # Check for permission, prohibition, or obligation
        has_rules = any(
            key in policy
            for key in ("permission", "prohibition", "obligation")
        )
        if not has_rules:
            errors.append("Policy must have at least one permission, prohibition, or obligation")

        # Validate permissions
        for perm in policy.get("permission", []):
            perm_errors = self._validate_rule(perm, "permission")
            errors.extend(perm_errors)

        # Validate prohibitions
        for prohib in policy.get("prohibition", []):
            prohib_errors = self._validate_rule(prohib, "prohibition")
            errors.extend(prohib_errors)

        return len(errors) == 0, errors

    def _validate_rule(self, rule: dict[str, Any], rule_type: str) -> list[str]:
        """
        Validate a policy rule (permission, prohibition, obligation).

        Args:
            rule: Rule to validate
            rule_type: Type of rule

        Returns:
            List of validation errors
        """
        errors = []

        # Check required action
        if "action" not in rule:
            errors.append(f"{rule_type} missing required 'action' field")

        # Validate constraints if present
        for constraint in rule.get("constraint", []):
            constraint_errors = self._validate_constraint(constraint)
            errors.extend(constraint_errors)

        return errors

    def _validate_constraint(self, constraint: dict[str, Any]) -> list[str]:
        """
        Validate a constraint.

        Args:
            constraint: Constraint to validate

        Returns:
            List of validation errors
        """
        errors = []

        # Check for logical constraint (and/or/xone)
        if any(key in constraint for key in ("and", "or", "xone")):
            # Logical constraint - validate nested constraints
            for key in ("and", "or", "xone"):
                if key in constraint:
                    for nested in constraint[key]:
                        errors.extend(self._validate_constraint(nested))
            return errors

        # Atomic constraint must have leftOperand, operator, rightOperand
        required = ("leftOperand", "operator", "rightOperand")
        for field in required:
            if field not in constraint:
                errors.append(f"Constraint missing required '{field}' field")

        # Validate operator
        if "operator" in constraint:
            op = constraint["operator"]
            if op not in self.OPERATORS:
                errors.append(f"Unknown constraint operator: {op}")

        return errors

    def evaluate_policy(
        self,
        policy: dict[str, Any],
        context: dict[str, Any],
    ) -> tuple[bool, str]:
        """
        Evaluate a policy against a context.

        Args:
            policy: ODRL policy to evaluate
            context: Context values for constraint evaluation
                     (e.g., {"BPN": "BPNL123", "Membership": "active"})

        Returns:
            Tuple of (is_allowed, reason)
        """
        # First validate the policy
        is_valid, errors = self.validate_policy(policy)
        if not is_valid:
            return False, f"Invalid policy: {'; '.join(errors)}"

        # Check prohibitions first (deny takes precedence)
        for prohibition in policy.get("prohibition", []):
            if self._evaluate_rule(prohibition, context):
                action = prohibition.get("action", "unknown")
                return False, f"Action '{action}' is prohibited"

        # Check permissions
        for permission in policy.get("permission", []):
            if self._evaluate_rule(permission, context):
                action = permission.get("action", "unknown")
                return True, f"Action '{action}' is permitted"

        # No matching permission found
        return False, "No matching permission found"

    def _evaluate_rule(
        self,
        rule: dict[str, Any],
        context: dict[str, Any],
    ) -> bool:
        """
        Evaluate a rule against context.

        Args:
            rule: Rule to evaluate
            context: Context values

        Returns:
            True if rule matches
        """
        # If no constraints, rule matches
        constraints = rule.get("constraint", [])
        if not constraints:
            return True

        # All constraints must be satisfied
        return all(
            self._evaluate_constraint(c, context)
            for c in constraints
        )

    def _evaluate_constraint(
        self,
        constraint: dict[str, Any],
        context: dict[str, Any],
    ) -> bool:
        """
        Evaluate a constraint against context.

        Args:
            constraint: Constraint to evaluate
            context: Context values

        Returns:
            True if constraint is satisfied
        """
        # Handle logical constraints
        if "and" in constraint:
            return all(
                self._evaluate_constraint(c, context)
                for c in constraint["and"]
            )
        if "or" in constraint:
            return any(
                self._evaluate_constraint(c, context)
                for c in constraint["or"]
            )
        if "xone" in constraint:
            matches = sum(
                1 for c in constraint["xone"]
                if self._evaluate_constraint(c, context)
            )
            return matches == 1

        # Atomic constraint
        left_operand = constraint.get("leftOperand")
        operator = constraint.get("operator")
        right_operand = constraint.get("rightOperand")

        # Get value from context
        left_value = context.get(left_operand)
        if left_value is None:
            logger.debug("Constraint operand '%s' not found in context", left_operand)
            return False

        # Get operator function
        op_func = self.OPERATORS.get(operator)
        if op_func is None:
            logger.warning("Unknown operator '%s'", operator)
            return False

        # Evaluate
        try:
            return op_func(left_value, right_operand)
        except Exception as e:
            logger.warning("Constraint evaluation failed: %s", e)
            return False

    def register_evaluator(
        self,
        operand: str,
        evaluator: callable,
    ) -> None:
        """
        Register a custom evaluator for a specific operand.

        Args:
            operand: Left operand name
            evaluator: Function(context, operator, right_operand) -> bool
        """
        self._custom_evaluators[operand] = evaluator

    def check_compatibility(
        self,
        policy_a: dict[str, Any],
        policy_b: dict[str, Any],
    ) -> tuple[bool, str]:
        """
        Check if two policies are compatible for negotiation.

        Args:
            policy_a: First policy (typically offer)
            policy_b: Second policy (typically request)

        Returns:
            Tuple of (is_compatible, reason)
        """
        valid_a, errors_a = self.validate_policy(policy_a)
        if not valid_a:
            return False, f"Policy A invalid: {'; '.join(errors_a)}"
        valid_b, errors_b = self.validate_policy(policy_b)
        if not valid_b:
            return False, f"Policy B invalid: {'; '.join(errors_b)}"

        def _extract_bpns(policy: dict[str, Any]) -> set[str]:
            bpns: set[str] = set()
            for perm in policy.get("permission", []):
                for constraint in perm.get("constraint", []):
                    left = constraint.get("leftOperand")
                    if left not in ("BusinessPartnerNumber", "BPN", "BPNL"):
                        continue
                    right = constraint.get("rightOperand")
                    if isinstance(right, list):
                        bpns.update(right)
                    elif isinstance(right, str):
                        bpns.add(right)
            return bpns

        bpns_a = _extract_bpns(policy_a)
        bpns_b = _extract_bpns(policy_b)

        if bpns_a and bpns_b and not (bpns_a & bpns_b):
            return False, "No overlapping BPN constraints"

        return True, "Policies are compatible"

    def translate(
        self,
        ui_policy: "PolicyConfig",
        base_asset_id: str,
        submodel_endpoint: str,
        semantic_id: str | None = None,
    ) -> TranslatedPolicy:
        """
        Translate a UI PolicyConfig to ODRL artifacts for EDC.

        This is the main entry point for converting user-facing policy
        configuration into the EDC-ready ODRL policies and contract definitions.

        Args:
            ui_policy: User-facing policy configuration from the UI
            base_asset_id: Base asset ID for the submodel
            submodel_endpoint: URL endpoint for the submodel data
            semantic_id: Optional semantic identifier

        Returns:
            TranslatedPolicy containing all EDC artifacts

        Raises:
            PolicyError: If translation fails

        Example:
            >>> from app.schemas.dataspace import PolicyConfig, AccessType
            >>> engine = PolicyEngine()
            >>> config = PolicyConfig(
            ...     access_type=AccessType.RESTRICTED,
            ...     allowed_partners=["BPNL00000001AAAA"]
            ... )
            >>> result = engine.translate(config, "urn:asset:1", "https://basyx/sm/1")
        """
        from app.schemas.dataspace import AccessType
        from app.services.dataspace.policy.odrl_builder import (
            build_asset_entry,
            build_bpn_access_policy,
            build_contract_definition,
            build_contract_policy,
            create_element_assets,
        )
        from app.services.dataspace.policy.templates import PolicyTemplates

        result = TranslatedPolicy()
        result.target_paths = ui_policy.target_paths.copy()

        # Generate policy IDs
        access_policy_id = f"urn:uuid:{uuid.uuid4()}"
        contract_policy_id = f"urn:uuid:{uuid.uuid4()}"

        result.access_policy_id = access_policy_id
        result.contract_policy_id = contract_policy_id

        # Determine if this is element-level or submodel-level
        if ui_policy.target_paths:
            # Element-level access control
            result.element_level = True
            result.assets = create_element_assets(
                base_asset_id=base_asset_id,
                submodel_endpoint=submodel_endpoint,
                element_paths=ui_policy.target_paths,
                semantic_id=semantic_id,
            )
        else:
            # Submodel-level access control
            result.element_level = False
            asset = build_asset_entry(
                asset_id=base_asset_id,
                submodel_endpoint=submodel_endpoint,
                semantic_id=semantic_id,
            )
            result.assets = [asset]

        # Build access policy based on access type
        if ui_policy.access_type == AccessType.PUBLIC:
            # Public access - no BPN restriction
            result.access_policy = PolicyTemplates.unrestricted_use(
                policy_id=access_policy_id
            )
        elif ui_policy.access_type == AccessType.MEMBERSHIP:
            # Membership required - any member can access
            result.access_policy = PolicyTemplates.membership_required(
                policy_id=access_policy_id
            )
        elif ui_policy.access_type == AccessType.RESTRICTED:
            # BPN-restricted access
            if ui_policy.allowed_partners:
                result.access_policy = build_bpn_access_policy(
                    allowed_bpns=ui_policy.allowed_partners,
                    policy_id=access_policy_id,
                )
            else:
                # No partners specified - default to membership only
                result.access_policy = PolicyTemplates.membership_required(
                    policy_id=access_policy_id
                )
        else:
            raise PolicyError(f"Unknown access type: {ui_policy.access_type}")

        # Build contract policy with constraints
        additional_constraints = []

        # Convert UI constraints to ODRL format
        for constraint in ui_policy.constraints:
            additional_constraints.append({
                "left_operand": constraint.left_operand,
                "operator": constraint.operator.value,
                "right_operand": constraint.right_operand,
            })

        # Build contract policy with time constraints
        valid_from_str = (
            ui_policy.valid_from.isoformat()
            if ui_policy.valid_from
            else None
        )
        valid_until_str = (
            ui_policy.valid_until.isoformat()
            if ui_policy.valid_until
            else None
        )

        result.contract_policy = build_contract_policy(
            constraints=additional_constraints,
            require_membership=(ui_policy.access_type != AccessType.PUBLIC),
            valid_from=valid_from_str,
            valid_until=valid_until_str,
            policy_id=contract_policy_id,
        )

        # Build contract definitions for each asset
        for asset in result.assets:
            asset_id = asset["@id"]
            definition_id = f"urn:uuid:{uuid.uuid4()}"

            contract_def = build_contract_definition(
                asset_id=asset_id,
                access_policy_id=access_policy_id,
                contract_policy_id=contract_policy_id,
                definition_id=definition_id,
            )
            result.contract_definitions.append(contract_def)

        return result

    def validate_translated_policy(
        self,
        translated: TranslatedPolicy,
    ) -> tuple[bool, list[str]]:
        """
        Validate a translated policy bundle.

        Checks that all artifacts are valid and consistent.

        Args:
            translated: TranslatedPolicy to validate

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Validate access policy
        if translated.access_policy:
            valid, policy_errors = self.validate_policy(translated.access_policy)
            if not valid:
                errors.extend([f"Access policy: {e}" for e in policy_errors])

        # Validate contract policy
        if translated.contract_policy:
            valid, policy_errors = self.validate_policy(translated.contract_policy)
            if not valid:
                errors.extend([f"Contract policy: {e}" for e in policy_errors])

        # Validate assets
        for i, asset in enumerate(translated.assets):
            if "@id" not in asset:
                errors.append(f"Asset {i}: missing @id")
            if "properties" not in asset:
                errors.append(f"Asset {i}: missing properties")

        # Validate contract definitions
        for i, contract_def in enumerate(translated.contract_definitions):
            if "@id" not in contract_def:
                errors.append(f"Contract definition {i}: missing @id")
            if "accessPolicyId" not in contract_def:
                errors.append(f"Contract definition {i}: missing accessPolicyId")
            if "contractPolicyId" not in contract_def:
                errors.append(f"Contract definition {i}: missing contractPolicyId")

        # Cross-check references
        if translated.access_policy_id != translated.access_policy.get("@id", ""):
            errors.append("Access policy ID mismatch")

        if translated.contract_policy_id != translated.contract_policy.get("@id", ""):
            errors.append("Contract policy ID mismatch")

        return len(errors) == 0, errors
