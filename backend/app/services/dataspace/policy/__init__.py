"""
ODRL Policy engine and management.

Provides tools for creating, validating, and managing ODRL policies
for dataspace data contracts:

- PolicyEngine: Policy evaluation and translation
- TranslatedPolicy: Result of UI config to ODRL translation
- ODRLBuilder: Fluent builder for ODRL policies
- PolicyTemplates: Pre-built policy templates for common use cases
- Builder functions: build_bpn_access_policy, build_contract_policy, etc.
"""

from app.services.dataspace.policy.engine import PolicyEngine, TranslatedPolicy
from app.services.dataspace.policy.odrl_builder import (
    ODRLBuilder,
    RuleBuilder,
    build_asset_entry,
    build_bpn_access_policy,
    build_contract_definition,
    build_contract_policy,
    create_element_assets,
)
from app.services.dataspace.policy.templates import PolicyTemplates

__all__ = [
    # Engine
    "PolicyEngine",
    "TranslatedPolicy",
    # Builder
    "ODRLBuilder",
    "RuleBuilder",
    # Convenience functions
    "build_bpn_access_policy",
    "build_contract_policy",
    "build_contract_definition",
    "build_asset_entry",
    "create_element_assets",
    # Templates
    "PolicyTemplates",
]
