"""
ODRL Policy Engine.

Provides policy evaluation and validation for dataspace data contracts.
Implements a subset of ODRL (Open Digital Rights Language) relevant
for Manufacturing-X / Catena-X use cases.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from app.services.dataspace.providers.provider_base import PolicyError

logger = logging.getLogger(__name__)


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
        self._custom_evaluators: dict[str, callable] = {}

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
        # TODO: Implement policy compatibility checking
        # This would compare constraints and ensure they can be satisfied together

        return True, "Compatibility check not yet implemented"
