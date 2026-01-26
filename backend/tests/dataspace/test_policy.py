"""
Tests for the dataspace policy module.

Tests ODRL builder, policy engine, and templates.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.schemas.dataspace import (
    AccessType,
    ConstraintOperator,
    PolicyConfig,
    PolicyConstraint,
)
from app.services.dataspace.policy import (
    ODRLBuilder,
    PolicyEngine,
    PolicyTemplates,
    TranslatedPolicy,
    build_asset_entry,
    build_bpn_access_policy,
    build_contract_definition,
    build_contract_policy,
    create_element_assets,
)


# ---------------------------------------------------------------------------
# ODRLBuilder Tests
# ---------------------------------------------------------------------------


class TestODRLBuilder:
    """Tests for ODRLBuilder."""

    def test_basic_policy_structure(self):
        """Test building a basic policy with required ODRL structure."""
        policy = (
            ODRLBuilder()
            .set_id("test-policy-1")
            .as_offer()
            .add_permission("use")
            .done()
            .build()
        )

        assert policy["@id"] == "test-policy-1"
        assert policy["@type"] == "Offer"
        assert "@context" in policy
        assert "permission" in policy
        assert len(policy["permission"]) == 1
        assert policy["permission"][0]["action"] == "use"

    def test_catena_x_profile(self):
        """Test setting Catena-X profile."""
        policy = (
            ODRLBuilder()
            .as_offer()
            .with_catena_x_profile()
            .add_permission("use")
            .done()
            .build()
        )

        assert policy["profile"] == "https://w3id.org/catena-x/policy"

    def test_policy_types(self):
        """Test different policy types (Set, Offer, Agreement)."""
        set_policy = ODRLBuilder().as_set().add_permission("use").done().build()
        assert set_policy["@type"] == "Set"

        offer_policy = ODRLBuilder().as_offer().add_permission("use").done().build()
        assert offer_policy["@type"] == "Offer"

        agreement = ODRLBuilder().as_agreement().add_permission("use").done().build()
        assert agreement["@type"] == "Agreement"

    def test_permission_with_constraint(self):
        """Test adding constraints to permissions."""
        policy = (
            ODRLBuilder()
            .as_offer()
            .add_permission("use")
            .with_constraint("Membership", "eq", "active")
            .done()
            .build()
        )

        constraint = policy["permission"][0]["constraint"][0]
        assert constraint["leftOperand"] == "Membership"
        assert constraint["operator"] == "eq"
        assert constraint["rightOperand"] == "active"

    def test_bpn_constraint_single(self):
        """Test BPN constraint with single BPN."""
        policy = (
            ODRLBuilder()
            .as_offer()
            .add_permission("use")
            .with_bpn_constraint(["BPNL00000001AAAA"])
            .done()
            .build()
        )

        constraint = policy["permission"][0]["constraint"][0]
        assert constraint["leftOperand"] == "BPN"
        assert constraint["operator"] == "eq"
        assert constraint["rightOperand"] == "BPNL00000001AAAA"

    def test_bpn_constraint_multiple(self):
        """Test BPN constraint with multiple BPNs."""
        bpns = ["BPNL00000001AAAA", "BPNL00000001BBBB"]
        policy = (
            ODRLBuilder()
            .as_offer()
            .add_permission("use")
            .with_bpn_constraint(bpns)
            .done()
            .build()
        )

        constraint = policy["permission"][0]["constraint"][0]
        assert constraint["leftOperand"] == "BPN"
        assert constraint["operator"] == "isAnyOf"
        assert constraint["rightOperand"] == bpns

    def test_purpose_constraint(self):
        """Test purpose constraint."""
        policy = (
            ODRLBuilder()
            .as_offer()
            .add_permission("use")
            .with_purpose_constraint(["cx.pcf:1"])
            .done()
            .build()
        )

        constraint = policy["permission"][0]["constraint"][0]
        assert constraint["leftOperand"] == "Purpose"
        assert constraint["rightOperand"] == "cx.pcf:1"

    def test_framework_agreement_constraint(self):
        """Test framework agreement constraint."""
        policy = (
            ODRLBuilder()
            .as_offer()
            .add_permission("use")
            .with_framework_agreement_constraint("DataExchange", "1.0")
            .done()
            .build()
        )

        constraint = policy["permission"][0]["constraint"][0]
        assert constraint["leftOperand"] == "FrameworkAgreement"
        assert constraint["rightOperand"] == "DataExchange:1.0"

    def test_multiple_constraints(self):
        """Test multiple constraints on a permission."""
        policy = (
            ODRLBuilder()
            .as_offer()
            .add_permission("use")
            .with_membership_constraint("active")
            .with_bpn_constraint(["BPNL00000001AAAA"])
            .with_purpose_constraint(["cx.pcf:1"])
            .done()
            .build()
        )

        constraints = policy["permission"][0]["constraint"]
        assert len(constraints) == 3

    def test_prohibition(self):
        """Test adding a prohibition."""
        policy = (
            ODRLBuilder()
            .as_offer()
            .add_permission("use")
            .done()
            .add_prohibition("transfer")
            .done()
            .build()
        )

        assert "prohibition" in policy
        assert policy["prohibition"][0]["action"] == "transfer"

    def test_assigner_assignee(self):
        """Test setting assigner and assignee."""
        policy = (
            ODRLBuilder()
            .as_agreement()
            .set_assigner("BPNL00000001PROV")
            .set_assignee("BPNL00000001CONS")
            .add_permission("use")
            .done()
            .build()
        )

        assert policy["assigner"] == "BPNL00000001PROV"
        assert policy["assignee"] == "BPNL00000001CONS"

    def test_rule_target(self):
        """Test setting target on a rule."""
        policy = (
            ODRLBuilder()
            .as_offer()
            .add_permission("use")
            .for_target("urn:asset:123")
            .done()
            .build()
        )

        assert policy["permission"][0]["target"] == "urn:asset:123"

    def test_auto_generated_id(self):
        """Test that ID is auto-generated if not set."""
        policy = ODRLBuilder().as_offer().add_permission("use").done().build()

        assert policy["@id"].startswith("urn:uuid:")
        assert len(policy["@id"]) > 20


# ---------------------------------------------------------------------------
# Builder Functions Tests
# ---------------------------------------------------------------------------


class TestBuilderFunctions:
    """Tests for convenience builder functions."""

    def test_build_bpn_access_policy_single(self):
        """Test building BPN access policy with single BPN."""
        policy = build_bpn_access_policy(
            allowed_bpns=["BPNL00000001AAAA"],
            policy_id="access-policy-1",
        )

        assert policy["@id"] == "access-policy-1"
        assert policy["@type"] == "Offer"
        constraint = policy["permission"][0]["constraint"][0]
        assert constraint["leftOperand"] == "BusinessPartnerNumber"
        assert constraint["operator"] == "eq"

    def test_build_bpn_access_policy_multiple(self):
        """Test building BPN access policy with multiple BPNs."""
        bpns = ["BPNL00000001AAAA", "BPNL00000001BBBB", "BPNL00000001CCCC"]
        policy = build_bpn_access_policy(allowed_bpns=bpns)

        constraint = policy["permission"][0]["constraint"][0]
        assert constraint["operator"] == "isAnyOf"
        assert constraint["rightOperand"] == bpns

    def test_build_contract_policy_minimal(self):
        """Test building minimal contract policy."""
        policy = build_contract_policy(constraints=[])

        assert "permission" in policy
        # Should have membership constraint by default
        constraint = policy["permission"][0]["constraint"][0]
        assert constraint["leftOperand"] == "Membership"

    def test_build_contract_policy_with_time(self):
        """Test building contract policy with time constraints."""
        policy = build_contract_policy(
            constraints=[],
            valid_from="2024-01-01T00:00:00Z",
            valid_until="2024-12-31T23:59:59Z",
        )

        constraints = policy["permission"][0]["constraint"]
        # Membership + valid_from + valid_until
        assert len(constraints) >= 3

        # Find time constraints
        time_constraints = [c for c in constraints if c["leftOperand"] == "dateTime"]
        assert len(time_constraints) == 2

    def test_build_contract_policy_with_custom_constraints(self):
        """Test building contract policy with custom constraints."""
        policy = build_contract_policy(
            constraints=[
                {
                    "left_operand": "Purpose",
                    "operator": "eq",
                    "right_operand": "cx.pcf:1",
                }
            ],
        )

        constraints = policy["permission"][0]["constraint"]
        purpose_constraint = next(
            (c for c in constraints if c["leftOperand"] == "Purpose"),
            None,
        )
        assert purpose_constraint is not None
        assert purpose_constraint["rightOperand"] == "cx.pcf:1"

    def test_build_contract_definition(self):
        """Test building contract definition."""
        contract_def = build_contract_definition(
            asset_id="urn:asset:123",
            access_policy_id="access-policy-456",
            contract_policy_id="contract-policy-789",
            definition_id="def-001",
        )

        assert contract_def["@id"] == "def-001"
        assert contract_def["@type"] == "ContractDefinition"
        assert contract_def["accessPolicyId"] == "access-policy-456"
        assert contract_def["contractPolicyId"] == "contract-policy-789"
        assert "assetsSelector" in contract_def

    def test_build_asset_entry(self):
        """Test building asset entry."""
        asset = build_asset_entry(
            asset_id="urn:asset:test",
            submodel_endpoint="https://basyx.example.com/submodel/1",
            semantic_id="https://example.com/semantic/1",
            description="Test asset",
            properties={"custom": "value"},
        )

        assert asset["@id"] == "urn:asset:test"
        assert asset["@type"] == "Asset"
        assert "aas:submodelEndpoint" in asset["properties"]
        assert asset["properties"]["aas:semanticId"] == "https://example.com/semantic/1"
        assert asset["properties"]["description"] == "Test asset"
        assert asset["properties"]["custom"] == "value"

    def test_create_element_assets(self):
        """Test creating element-level assets."""
        assets = create_element_assets(
            base_asset_id="urn:asset:nameplate",
            submodel_endpoint="https://basyx.example.com/submodel/1",
            element_paths=["SerialNumber", "ProductType/ManufacturerName"],
            semantic_id="https://example.com/semantic/1",
        )

        assert len(assets) == 2

        # Check first asset
        assert assets[0]["@id"] == "urn:asset:nameplate:SerialNumber"
        assert "SerialNumber" in assets[0]["properties"]["aas:submodelEndpoint"]
        assert assets[0]["properties"]["aas:idShortPath"] == "SerialNumber"
        assert assets[0]["properties"]["cx:elementLevel"] is True

        # Check second asset with nested path
        assert assets[1]["@id"] == "urn:asset:nameplate:ProductType:ManufacturerName"
        assert (
            "ProductType/ManufacturerName"
            in assets[1]["properties"]["aas:submodelEndpoint"]
        )


# ---------------------------------------------------------------------------
# PolicyTemplates Tests
# ---------------------------------------------------------------------------


class TestPolicyTemplates:
    """Tests for PolicyTemplates."""

    def test_unrestricted_use(self):
        """Test unrestricted use template."""
        policy = PolicyTemplates.unrestricted_use(policy_id="unrestricted-1")

        assert policy["@id"] == "unrestricted-1"
        assert policy["permission"][0]["action"] == "use"
        # Should have no constraints
        assert "constraint" not in policy["permission"][0] or len(
            policy["permission"][0].get("constraint", [])
        ) == 0

    def test_membership_required(self):
        """Test membership required template."""
        policy = PolicyTemplates.membership_required(
            membership_type="active",
            policy_id="membership-1",
        )

        constraint = policy["permission"][0]["constraint"][0]
        assert constraint["leftOperand"] == "Membership"
        assert constraint["rightOperand"] == "active"

    def test_bpn_restricted(self):
        """Test BPN restricted template."""
        policy = PolicyTemplates.bpn_restricted(
            allowed_bpns=["BPNL00000001AAAA"],
            policy_id="bpn-1",
        )

        constraint = policy["permission"][0]["constraint"][0]
        assert constraint["leftOperand"] == "BPN"

    def test_purpose_restricted(self):
        """Test purpose restricted template."""
        policy = PolicyTemplates.purpose_restricted(
            allowed_purposes=["cx.pcf:1", "cx.quality:1"],
            require_membership=True,
        )

        constraints = policy["permission"][0]["constraint"]
        purpose_constraint = next(
            (c for c in constraints if c["leftOperand"] == "Purpose"),
            None,
        )
        assert purpose_constraint is not None
        assert purpose_constraint["operator"] == "isAnyOf"

    def test_framework_agreement(self):
        """Test framework agreement template."""
        policy = PolicyTemplates.framework_agreement(
            framework="DataExchange",
            version="1.0",
        )

        constraints = policy["permission"][0]["constraint"]
        framework_constraint = next(
            (c for c in constraints if c["leftOperand"] == "FrameworkAgreement"),
            None,
        )
        assert framework_constraint is not None
        assert framework_constraint["rightOperand"] == "DataExchange:1.0"

    def test_pcf_data_exchange(self):
        """Test PCF data exchange template."""
        policy = PolicyTemplates.pcf_data_exchange(
            allowed_bpns=["BPNL00000001AAAA"],
        )

        constraints = policy["permission"][0]["constraint"]
        purpose_constraint = next(
            (c for c in constraints if c["leftOperand"] == "Purpose"),
            None,
        )
        assert purpose_constraint is not None
        assert "cx.pcf:1" in purpose_constraint["rightOperand"]

    def test_digital_twin_access(self):
        """Test digital twin access template."""
        policy = PolicyTemplates.digital_twin_access(
            require_membership=True,
            allowed_bpns=["BPNL00000001AAAA"],
        )

        constraints = policy["permission"][0]["constraint"]
        assert len(constraints) >= 2  # Membership + BPN

    def test_traceability_data(self):
        """Test traceability data template."""
        policy = PolicyTemplates.traceability_data()

        constraints = policy["permission"][0]["constraint"]
        purpose_constraint = next(
            (c for c in constraints if c["leftOperand"] == "Purpose"),
            None,
        )
        framework_constraint = next(
            (c for c in constraints if c["leftOperand"] == "FrameworkAgreement"),
            None,
        )
        assert purpose_constraint is not None
        assert framework_constraint is not None

    def test_time_limited_access(self):
        """Test time-limited access template."""
        policy = PolicyTemplates.time_limited_access(
            valid_from="2024-01-01T00:00:00Z",
            valid_until="2024-12-31T23:59:59Z",
            require_membership=True,
        )

        constraints = policy["permission"][0]["constraint"]
        time_constraints = [c for c in constraints if c["leftOperand"] == "dateTime"]
        assert len(time_constraints) == 2

    def test_bpn_allowlist(self):
        """Test BPN allowlist template."""
        policy = PolicyTemplates.bpn_allowlist(
            allowed_bpns=["BPNL00000001AAAA", "BPNL00000001BBBB"],
            require_membership=False,
        )

        constraints = policy["permission"][0]["constraint"]
        # Should only have BPN constraint
        assert len(constraints) == 1
        assert constraints[0]["leftOperand"] == "BPN"

    def test_membership_credential(self):
        """Test membership credential template."""
        policy = PolicyTemplates.membership_credential(
            credential_type="MembershipCredential",
            issuer="did:web:catena-x.net",
        )

        constraints = policy["permission"][0]["constraint"]
        type_constraint = next(
            (c for c in constraints if "VerifiableCredential.type" in c["leftOperand"]),
            None,
        )
        issuer_constraint = next(
            (
                c
                for c in constraints
                if "VerifiableCredential.issuer" in c["leftOperand"]
            ),
            None,
        )
        assert type_constraint is not None
        assert issuer_constraint is not None

    def test_combined_constraints(self):
        """Test combined constraints template."""
        policy = PolicyTemplates.combined_constraints(
            membership_required=True,
            allowed_bpns=["BPNL00000001AAAA"],
            allowed_purposes=["cx.pcf:1"],
            framework="DataExchange",
        )

        constraints = policy["permission"][0]["constraint"]
        # Should have membership, BPN, purpose, framework
        assert len(constraints) >= 4


# ---------------------------------------------------------------------------
# PolicyEngine Tests
# ---------------------------------------------------------------------------


class TestPolicyEngine:
    """Tests for PolicyEngine."""

    def test_validate_valid_policy(self):
        """Test validating a valid policy."""
        engine = PolicyEngine()
        policy = PolicyTemplates.membership_required()

        is_valid, errors = engine.validate_policy(policy)

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_missing_context(self):
        """Test validating policy missing context."""
        engine = PolicyEngine()
        policy = {
            "@type": "Offer",
            "@id": "test-1",
            "permission": [{"action": "use"}],
        }

        is_valid, errors = engine.validate_policy(policy)

        assert is_valid is False
        assert any("@context" in e for e in errors)

    def test_validate_missing_type(self):
        """Test validating policy missing type."""
        engine = PolicyEngine()
        policy = {
            "@context": {},
            "@id": "test-1",
            "permission": [{"action": "use"}],
        }

        is_valid, errors = engine.validate_policy(policy)

        assert is_valid is False
        assert any("@type" in e for e in errors)

    def test_validate_invalid_type(self):
        """Test validating policy with invalid type."""
        engine = PolicyEngine()
        policy = {
            "@context": {},
            "@type": "InvalidType",
            "@id": "test-1",
            "permission": [{"action": "use"}],
        }

        is_valid, errors = engine.validate_policy(policy)

        assert is_valid is False
        assert any("Invalid policy type" in e for e in errors)

    def test_validate_missing_rules(self):
        """Test validating policy with no rules."""
        engine = PolicyEngine()
        policy = {
            "@context": {},
            "@type": "Offer",
            "@id": "test-1",
        }

        is_valid, errors = engine.validate_policy(policy)

        assert is_valid is False
        assert any("at least one" in e for e in errors)

    def test_evaluate_policy_allowed(self):
        """Test evaluating policy that allows access."""
        engine = PolicyEngine()
        policy = PolicyTemplates.membership_required(membership_type="active")
        context = {"Membership": "active"}

        is_allowed, reason = engine.evaluate_policy(policy, context)

        assert is_allowed is True
        assert "permitted" in reason.lower()

    def test_evaluate_policy_denied_membership(self):
        """Test evaluating policy that denies access due to membership."""
        engine = PolicyEngine()
        policy = PolicyTemplates.membership_required(membership_type="active")
        context = {"Membership": "inactive"}

        is_allowed, reason = engine.evaluate_policy(policy, context)

        assert is_allowed is False

    def test_evaluate_policy_bpn_allowed(self):
        """Test evaluating BPN policy with matching BPN."""
        engine = PolicyEngine()
        policy = PolicyTemplates.bpn_restricted(
            allowed_bpns=["BPNL00000001AAAA", "BPNL00000001BBBB"]
        )
        context = {"BPN": ["BPNL00000001AAAA"]}

        is_allowed, reason = engine.evaluate_policy(policy, context)

        assert is_allowed is True

    def test_evaluate_policy_bpn_denied(self):
        """Test evaluating BPN policy with non-matching BPN."""
        engine = PolicyEngine()
        policy = PolicyTemplates.bpn_restricted(allowed_bpns=["BPNL00000001AAAA"])
        context = {"BPN": "BPNL00000001XXXX"}

        is_allowed, reason = engine.evaluate_policy(policy, context)

        assert is_allowed is False


# ---------------------------------------------------------------------------
# PolicyEngine.translate() Tests
# ---------------------------------------------------------------------------


class TestPolicyEngineTranslate:
    """Tests for PolicyEngine.translate() method."""

    def test_translate_public_policy(self):
        """Test translating a public access policy."""
        engine = PolicyEngine()
        config = PolicyConfig(access_type=AccessType.PUBLIC)

        result = engine.translate(
            ui_policy=config,
            base_asset_id="urn:asset:test",
            submodel_endpoint="https://basyx.example.com/submodel/1",
        )

        assert isinstance(result, TranslatedPolicy)
        assert len(result.assets) == 1
        assert result.assets[0]["@id"] == "urn:asset:test"
        assert result.access_policy_id.startswith("urn:uuid:")
        assert result.contract_policy_id.startswith("urn:uuid:")
        assert len(result.contract_definitions) == 1
        assert result.element_level is False

    def test_translate_membership_policy(self):
        """Test translating a membership access policy."""
        engine = PolicyEngine()
        config = PolicyConfig(access_type=AccessType.MEMBERSHIP)

        result = engine.translate(
            ui_policy=config,
            base_asset_id="urn:asset:test",
            submodel_endpoint="https://basyx.example.com/submodel/1",
        )

        # Access policy should require membership
        assert "permission" in result.access_policy
        constraints = result.access_policy["permission"][0].get("constraint", [])
        membership_constraint = next(
            (c for c in constraints if c.get("leftOperand") == "Membership"),
            None,
        )
        assert membership_constraint is not None

    def test_translate_restricted_policy_with_bpns(self):
        """Test translating a restricted policy with BPN list."""
        engine = PolicyEngine()
        config = PolicyConfig(
            access_type=AccessType.RESTRICTED,
            allowed_partners=["BPNL00000001AAAA", "BPNL00000001BBBB"],
        )

        result = engine.translate(
            ui_policy=config,
            base_asset_id="urn:asset:test",
            submodel_endpoint="https://basyx.example.com/submodel/1",
        )

        # Access policy should have BPN constraint
        constraints = result.access_policy["permission"][0]["constraint"]
        bpn_constraint = next(
            (c for c in constraints if c.get("leftOperand") == "BusinessPartnerNumber"),
            None,
        )
        assert bpn_constraint is not None
        assert bpn_constraint["operator"] == "isAnyOf"

    def test_translate_with_time_constraints(self):
        """Test translating a policy with time constraints."""
        engine = PolicyEngine()
        now = datetime.now(timezone.utc)
        future = now + timedelta(days=365)

        config = PolicyConfig(
            access_type=AccessType.MEMBERSHIP,
            valid_from=now,
            valid_until=future,
        )

        result = engine.translate(
            ui_policy=config,
            base_asset_id="urn:asset:test",
            submodel_endpoint="https://basyx.example.com/submodel/1",
        )

        # Contract policy should have time constraints
        constraints = result.contract_policy["permission"][0]["constraint"]
        time_constraints = [c for c in constraints if c.get("leftOperand") == "dateTime"]
        assert len(time_constraints) == 2

    def test_translate_with_custom_constraints(self):
        """Test translating a policy with custom constraints."""
        engine = PolicyEngine()
        config = PolicyConfig(
            access_type=AccessType.MEMBERSHIP,
            constraints=[
                PolicyConstraint(
                    left_operand="Purpose",
                    operator=ConstraintOperator.EQ,
                    right_operand="cx.pcf:1",
                )
            ],
        )

        result = engine.translate(
            ui_policy=config,
            base_asset_id="urn:asset:test",
            submodel_endpoint="https://basyx.example.com/submodel/1",
        )

        # Contract policy should have purpose constraint
        constraints = result.contract_policy["permission"][0]["constraint"]
        purpose_constraint = next(
            (c for c in constraints if c.get("leftOperand") == "Purpose"),
            None,
        )
        assert purpose_constraint is not None
        assert purpose_constraint["rightOperand"] == "cx.pcf:1"

    def test_translate_element_level_policy(self):
        """Test translating an element-level policy."""
        engine = PolicyEngine()
        config = PolicyConfig(
            access_type=AccessType.RESTRICTED,
            allowed_partners=["BPNL00000001AAAA"],
            target_paths=["SerialNumber", "ProductType/ManufacturerName"],
        )

        result = engine.translate(
            ui_policy=config,
            base_asset_id="urn:asset:nameplate",
            submodel_endpoint="https://basyx.example.com/submodel/1",
        )

        assert result.element_level is True
        assert len(result.assets) == 2
        assert result.target_paths == ["SerialNumber", "ProductType/ManufacturerName"]
        assert len(result.contract_definitions) == 2

        # Verify asset IDs include element paths
        asset_ids = [a["@id"] for a in result.assets]
        assert "urn:asset:nameplate:SerialNumber" in asset_ids
        assert "urn:asset:nameplate:ProductType:ManufacturerName" in asset_ids

    def test_translate_with_semantic_id(self):
        """Test translating a policy with semantic ID."""
        engine = PolicyEngine()
        config = PolicyConfig(access_type=AccessType.PUBLIC)

        result = engine.translate(
            ui_policy=config,
            base_asset_id="urn:asset:test",
            submodel_endpoint="https://basyx.example.com/submodel/1",
            semantic_id="https://admin-shell.io/idta/Nameplate/3/0",
        )

        assert "aas:semanticId" in result.assets[0]["properties"]
        assert (
            result.assets[0]["properties"]["aas:semanticId"]
            == "https://admin-shell.io/idta/Nameplate/3/0"
        )

    def test_validate_translated_policy(self):
        """Test validating a translated policy."""
        engine = PolicyEngine()
        config = PolicyConfig(
            access_type=AccessType.RESTRICTED,
            allowed_partners=["BPNL00000001AAAA"],
        )

        result = engine.translate(
            ui_policy=config,
            base_asset_id="urn:asset:test",
            submodel_endpoint="https://basyx.example.com/submodel/1",
        )

        is_valid, errors = engine.validate_translated_policy(result)

        assert is_valid is True
        assert len(errors) == 0

    def test_translated_policy_to_dict(self):
        """Test TranslatedPolicy serialization."""
        engine = PolicyEngine()
        config = PolicyConfig(access_type=AccessType.PUBLIC)

        result = engine.translate(
            ui_policy=config,
            base_asset_id="urn:asset:test",
            submodel_endpoint="https://basyx.example.com/submodel/1",
        )

        data = result.to_dict()

        assert "assets" in data
        assert "access_policy" in data
        assert "access_policy_id" in data
        assert "contract_policy" in data
        assert "contract_policy_id" in data
        assert "contract_definitions" in data
        assert "element_level" in data
        assert "target_paths" in data


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------


class TestPolicyIntegration:
    """Integration tests for the policy module."""

    def test_full_policy_workflow(self):
        """Test complete policy creation and validation workflow."""
        engine = PolicyEngine()

        # Create UI config
        config = PolicyConfig(
            access_type=AccessType.RESTRICTED,
            allowed_partners=["BPNL00000001AAAA", "BPNL00000001BBBB"],
            constraints=[
                PolicyConstraint(
                    left_operand="Purpose",
                    operator=ConstraintOperator.EQ,
                    right_operand="cx.pcf:1",
                ),
                PolicyConstraint(
                    left_operand="FrameworkAgreement",
                    operator=ConstraintOperator.EQ,
                    right_operand="DataExchange:1.0",
                ),
            ],
            valid_until=datetime(2025, 12, 31, tzinfo=timezone.utc),
        )

        # Translate to ODRL
        result = engine.translate(
            ui_policy=config,
            base_asset_id="urn:asset:pcf-data",
            submodel_endpoint="https://basyx.example.com/submodel/pcf",
            semantic_id="https://admin-shell.io/idta/CarbonFootprint/1/0",
        )

        # Validate translated policy
        is_valid, errors = engine.validate_translated_policy(result)
        assert is_valid is True, f"Validation errors: {errors}"

        # Validate individual policies
        access_valid, _ = engine.validate_policy(result.access_policy)
        assert access_valid is True

        contract_valid, _ = engine.validate_policy(result.contract_policy)
        assert contract_valid is True

        # Verify contract definition links
        for contract_def in result.contract_definitions:
            assert contract_def["accessPolicyId"] == result.access_policy_id
            assert contract_def["contractPolicyId"] == result.contract_policy_id

    def test_policy_evaluation_matches_translation(self):
        """Test that translated policy evaluates correctly."""
        engine = PolicyEngine()

        # Create and translate policy
        config = PolicyConfig(
            access_type=AccessType.RESTRICTED,
            allowed_partners=["BPNL00000001AAAA"],
        )

        result = engine.translate(
            ui_policy=config,
            base_asset_id="urn:asset:test",
            submodel_endpoint="https://basyx.example.com/submodel/1",
        )

        # Evaluate with matching BPN (single value for "eq" operator)
        context_allowed = {"BusinessPartnerNumber": "BPNL00000001AAAA"}
        is_allowed, _ = engine.evaluate_policy(result.access_policy, context_allowed)
        assert is_allowed is True

        # Evaluate with non-matching BPN
        context_denied = {"BusinessPartnerNumber": "BPNL00000001XXXX"}
        is_allowed, _ = engine.evaluate_policy(result.access_policy, context_denied)
        assert is_allowed is False
