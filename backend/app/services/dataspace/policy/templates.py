"""
Pre-built policy templates for common dataspace use cases.

Provides ready-to-use ODRL policy templates for Manufacturing-X / Catena-X
scenarios that can be customized for specific needs.
"""

from __future__ import annotations

from typing import Any

from app.services.dataspace.policy.odrl_builder import ODRLBuilder


class PolicyTemplates:
    """
    Collection of pre-built policy templates.

    Templates cover common Manufacturing-X / Catena-X scenarios:
    - Public access policies
    - Membership-restricted policies
    - BPN-restricted policies
    - Purpose-based policies
    - Framework agreement policies
    """

    @staticmethod
    def unrestricted_use(policy_id: str | None = None) -> dict[str, Any]:
        """
        Create an unrestricted use policy.

        Allows any consumer to use the data without constraints.
        Use with caution - typically only for public/non-sensitive data.

        Args:
            policy_id: Optional policy ID

        Returns:
            ODRL policy document
        """
        builder = ODRLBuilder().as_offer()

        if policy_id:
            builder.set_id(policy_id)

        return (
            builder
            .add_permission("use")
            .done()
            .build()
        )

    @staticmethod
    def membership_required(
        membership_type: str = "active",
        policy_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a policy requiring dataspace membership.

        Restricts access to consumers with active membership in the dataspace.

        Args:
            membership_type: Required membership type
            policy_id: Optional policy ID

        Returns:
            ODRL policy document
        """
        builder = ODRLBuilder().as_offer().with_catena_x_profile()

        if policy_id:
            builder.set_id(policy_id)

        return (
            builder
            .add_permission("use")
            .with_membership_constraint(membership_type)
            .done()
            .build()
        )

    @staticmethod
    def bpn_restricted(
        allowed_bpns: list[str],
        policy_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a policy restricting access to specific Business Partner Numbers.

        Args:
            allowed_bpns: List of allowed BPNs
            policy_id: Optional policy ID

        Returns:
            ODRL policy document
        """
        builder = ODRLBuilder().as_offer().with_catena_x_profile()

        if policy_id:
            builder.set_id(policy_id)

        return (
            builder
            .add_permission("use")
            .with_bpn_constraint(allowed_bpns)
            .done()
            .build()
        )

    @staticmethod
    def purpose_restricted(
        allowed_purposes: list[str],
        require_membership: bool = True,
        policy_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a policy restricting access by purpose.

        Common purposes include:
        - "cx.core.industrycore:1" - Industry Core
        - "cx.pcf:1" - Product Carbon Footprint
        - "cx.quality:1" - Quality Management
        - "cx.traceability:1" - Traceability

        Args:
            allowed_purposes: List of allowed purpose identifiers
            require_membership: Whether to also require membership
            policy_id: Optional policy ID

        Returns:
            ODRL policy document
        """
        builder = ODRLBuilder().as_offer().with_catena_x_profile()

        if policy_id:
            builder.set_id(policy_id)

        perm_builder = builder.add_permission("use")
        perm_builder.with_purpose_constraint(allowed_purposes)

        if require_membership:
            perm_builder.with_membership_constraint("active")

        return perm_builder.done().build()

    @staticmethod
    def framework_agreement(
        framework: str,
        version: str | None = None,
        require_membership: bool = True,
        policy_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a policy requiring a framework agreement.

        Common frameworks include:
        - "DataExchange" - General data exchange
        - "Traceability" - Traceability use case
        - "QualityManagement" - Quality use case
        - "PCF" - Product Carbon Footprint

        Args:
            framework: Framework agreement name
            version: Optional framework version
            require_membership: Whether to also require membership
            policy_id: Optional policy ID

        Returns:
            ODRL policy document
        """
        builder = ODRLBuilder().as_offer().with_catena_x_profile()

        if policy_id:
            builder.set_id(policy_id)

        perm_builder = builder.add_permission("use")
        perm_builder.with_framework_agreement_constraint(framework, version)

        if require_membership:
            perm_builder.with_membership_constraint("active")

        return perm_builder.done().build()

    @staticmethod
    def pcf_data_exchange(
        allowed_bpns: list[str] | None = None,
        policy_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a policy for Product Carbon Footprint data exchange.

        Implements the Catena-X PCF Exchange use case requirements.

        Args:
            allowed_bpns: Optional list of allowed BPNs (if None, any member)
            policy_id: Optional policy ID

        Returns:
            ODRL policy document
        """
        builder = ODRLBuilder().as_offer().with_catena_x_profile()

        if policy_id:
            builder.set_id(policy_id)

        perm_builder = (
            builder
            .add_permission("use")
            .with_purpose_constraint(["cx.pcf:1"])
            .with_membership_constraint("active")
        )

        if allowed_bpns:
            perm_builder.with_bpn_constraint(allowed_bpns)

        return perm_builder.done().build()

    @staticmethod
    def digital_twin_access(
        require_membership: bool = True,
        allowed_bpns: list[str] | None = None,
        policy_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a standard policy for Digital Twin access.

        Suitable for general AAS/Digital Twin data sharing.

        Args:
            require_membership: Whether to require dataspace membership
            allowed_bpns: Optional list of allowed BPNs
            policy_id: Optional policy ID

        Returns:
            ODRL policy document
        """
        builder = ODRLBuilder().as_offer().with_catena_x_profile()

        if policy_id:
            builder.set_id(policy_id)

        perm_builder = builder.add_permission("use")

        if require_membership:
            perm_builder.with_membership_constraint("active")

        if allowed_bpns:
            perm_builder.with_bpn_constraint(allowed_bpns)

        return perm_builder.done().build()

    @staticmethod
    def traceability_data(
        allowed_bpns: list[str] | None = None,
        policy_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a policy for traceability data exchange.

        Implements requirements for supply chain traceability use cases.

        Args:
            allowed_bpns: Optional list of allowed BPNs
            policy_id: Optional policy ID

        Returns:
            ODRL policy document
        """
        builder = ODRLBuilder().as_offer().with_catena_x_profile()

        if policy_id:
            builder.set_id(policy_id)

        perm_builder = (
            builder
            .add_permission("use")
            .with_purpose_constraint(["cx.traceability:1"])
            .with_framework_agreement_constraint("Traceability")
            .with_membership_constraint("active")
        )

        if allowed_bpns:
            perm_builder.with_bpn_constraint(allowed_bpns)

        return perm_builder.done().build()

    @staticmethod
    def combined_constraints(
        membership_required: bool = True,
        allowed_bpns: list[str] | None = None,
        allowed_purposes: list[str] | None = None,
        framework: str | None = None,
        policy_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a policy with multiple combined constraints.

        Flexible template for combining various constraint types.

        Args:
            membership_required: Whether to require membership
            allowed_bpns: Optional list of allowed BPNs
            allowed_purposes: Optional list of allowed purposes
            framework: Optional framework agreement
            policy_id: Optional policy ID

        Returns:
            ODRL policy document
        """
        builder = ODRLBuilder().as_offer().with_catena_x_profile()

        if policy_id:
            builder.set_id(policy_id)

        perm_builder = builder.add_permission("use")

        if membership_required:
            perm_builder.with_membership_constraint("active")

        if allowed_bpns:
            perm_builder.with_bpn_constraint(allowed_bpns)

        if allowed_purposes:
            perm_builder.with_purpose_constraint(allowed_purposes)

        if framework:
            perm_builder.with_framework_agreement_constraint(framework)

        return perm_builder.done().build()
