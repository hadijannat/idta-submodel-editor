"""
Tests for DPP Validator.

Tests EU ESPR compliance validation including:
- Required submodels check
- Mandatory fields validation
- Cross-submodel consistency
- Compliance level determination
"""

import pytest
from datetime import datetime, timezone

from app.services.dpp.models import (
    DPPPackage,
    DPPPackageStatus,
    DPPSubmodelRef,
    ESPRComplianceLevel,
)
from app.services.dpp.validator import DPPValidator


@pytest.fixture
def validator() -> DPPValidator:
    """Create a DPP validator instance."""
    return DPPValidator()


@pytest.fixture
def base_package() -> DPPPackage:
    """Create a base DPP package for testing."""
    now = datetime.now(timezone.utc)
    return DPPPackage(
        package_id="test-pkg-123",
        status=DPPPackageStatus.DRAFT,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def nameplate_submodel() -> DPPSubmodelRef:
    """Create a nameplate submodel reference with data."""
    return DPPSubmodelRef(
        template_name="IDTA-02006-2-0-Nameplate",
        template_status="published",
        role="identification",
        form_data={
            "elements": {
                "ManufacturerName": {"value": "ACME Corp"},
                "SerialNumber": {"value": "SN-12345"},
                "ProductType": {"value": "Industrial Controller"},
            }
        },
        is_required=True,
    )


@pytest.fixture
def pcf_submodel() -> DPPSubmodelRef:
    """Create a carbon footprint submodel reference."""
    return DPPSubmodelRef(
        template_name="IDTA-02023-0-9-CarbonFootprint",
        template_status="published",
        role="sustainability",
        form_data={
            "elements": {
                "PCFCalculationMethod": {"value": "GHG Protocol"},
                "CO2eq": {"value": "150.5"},
            }
        },
        is_required=False,
    )


class TestMissingIdentification:
    """Test validation when identification submodel is missing."""

    @pytest.mark.asyncio
    async def test_no_submodels_is_non_compliant(self, validator, base_package):
        """Test that package with no submodels is non-compliant."""
        result = await validator.validate(base_package)

        assert not result.is_valid
        assert result.compliance_level == ESPRComplianceLevel.NON_COMPLIANT
        assert "identification" in result.missing_required_submodels
        assert any(e.code == "MISSING_IDENTIFICATION" for e in result.errors)

    @pytest.mark.asyncio
    async def test_only_sustainability_is_non_compliant(
        self, validator, base_package, pcf_submodel
    ):
        """Test that package with only sustainability is non-compliant."""
        base_package.submodels = [pcf_submodel]

        result = await validator.validate(base_package)

        assert not result.is_valid
        assert result.compliance_level == ESPRComplianceLevel.NON_COMPLIANT
        assert "identification" in result.missing_required_submodels


class TestIdentificationSubmodel:
    """Test validation of identification submodel."""

    @pytest.mark.asyncio
    async def test_valid_identification_is_minimal(
        self, validator, base_package, nameplate_submodel
    ):
        """Test that valid identification alone is minimal compliance."""
        base_package.submodels = [nameplate_submodel]

        result = await validator.validate(base_package)

        # Should be valid but only minimal compliance (no sustainability)
        assert result.is_valid
        assert result.compliance_level in [
            ESPRComplianceLevel.MINIMAL,
            ESPRComplianceLevel.PARTIAL,
        ]

    @pytest.mark.asyncio
    async def test_missing_manufacturer_is_error(self, validator, base_package):
        """Test that missing manufacturer name is an error."""
        incomplete = DPPSubmodelRef(
            template_name="IDTA-02006-2-0-Nameplate",
            template_status="published",
            role="identification",
            form_data={
                "elements": {
                    "SerialNumber": {"value": "SN-12345"},
                }
            },
        )
        base_package.submodels = [incomplete]

        result = await validator.validate(base_package)

        # Should have error for missing manufacturer
        assert any(e.code == "MISSING_MANUFACTURER" for e in result.errors)

    @pytest.mark.asyncio
    async def test_missing_serial_is_error(self, validator, base_package):
        """Test that missing serial number is an error."""
        incomplete = DPPSubmodelRef(
            template_name="IDTA-02006-2-0-Nameplate",
            template_status="published",
            role="identification",
            form_data={
                "elements": {
                    "ManufacturerName": {"value": "ACME Corp"},
                }
            },
        )
        base_package.submodels = [incomplete]

        result = await validator.validate(base_package)

        # Should have error for missing product ID
        assert any(e.code == "MISSING_PRODUCT_ID" for e in result.errors)


class TestFullCompliance:
    """Test full EU ESPR compliance."""

    @pytest.mark.asyncio
    async def test_full_compliance_with_both_roles(
        self, validator, base_package, nameplate_submodel, pcf_submodel
    ):
        """Test that identification + sustainability = full compliance."""
        base_package.submodels = [nameplate_submodel, pcf_submodel]

        result = await validator.validate(base_package)

        assert result.is_valid
        assert result.compliance_level == ESPRComplianceLevel.FULL
        assert len(result.errors) == 0


class TestCrossConsistency:
    """Test cross-submodel consistency validation."""

    @pytest.mark.asyncio
    async def test_inconsistent_manufacturer_warning(self, validator, base_package):
        """Test that inconsistent manufacturer names generate warning."""
        nameplate1 = DPPSubmodelRef(
            template_name="IDTA-02006-2-0-Nameplate",
            template_status="published",
            role="identification",
            form_data={
                "elements": {
                    "ManufacturerName": {"value": "ACME Corp"},
                    "SerialNumber": {"value": "SN-12345"},
                }
            },
        )
        tech_data = DPPSubmodelRef(
            template_name="IDTA-02004-1-2-TechnicalData",
            template_status="published",
            role="technical",
            form_data={
                "elements": {
                    "ManufacturerName": {"value": "Different Corp"},
                }
            },
        )
        base_package.submodels = [nameplate1, tech_data]

        result = await validator.validate(base_package)

        # Should have warning for inconsistent manufacturer
        assert any(e.code == "INCONSISTENT_MANUFACTURER" for e in result.warnings)

    @pytest.mark.asyncio
    async def test_package_manufacturer_overrides(
        self, validator, base_package, nameplate_submodel
    ):
        """Test that package-level manufacturer is considered."""
        base_package.manufacturer_name = "Package Manufacturer"
        base_package.submodels = [nameplate_submodel]

        result = await validator.validate(base_package)

        # Different manufacturers should trigger warning
        assert any(e.code == "INCONSISTENT_MANUFACTURER" for e in result.warnings)


class TestMissingSustainability:
    """Test validation when sustainability information is missing."""

    @pytest.mark.asyncio
    async def test_missing_sustainability_is_warning(
        self, validator, base_package, nameplate_submodel
    ):
        """Test that missing sustainability generates warning."""
        base_package.submodels = [nameplate_submodel]

        result = await validator.validate(base_package)

        # Should have warning (not error) for missing sustainability
        assert any(e.code == "MISSING_SUSTAINABILITY" for e in result.warnings)


class TestComplianceLevelDetermination:
    """Test compliance level determination logic."""

    @pytest.mark.asyncio
    async def test_empty_package_is_non_compliant(self, validator, base_package):
        """Test empty package is non-compliant."""
        result = await validator.validate(base_package)
        assert result.compliance_level == ESPRComplianceLevel.NON_COMPLIANT

    @pytest.mark.asyncio
    async def test_identification_only_is_minimal_or_partial(
        self, validator, base_package, nameplate_submodel
    ):
        """Test identification only is minimal or partial."""
        base_package.submodels = [nameplate_submodel]

        result = await validator.validate(base_package)

        assert result.compliance_level in [
            ESPRComplianceLevel.MINIMAL,
            ESPRComplianceLevel.PARTIAL,
        ]

    @pytest.mark.asyncio
    async def test_both_roles_is_full(
        self, validator, base_package, nameplate_submodel, pcf_submodel
    ):
        """Test identification + sustainability is full compliance."""
        base_package.submodels = [nameplate_submodel, pcf_submodel]

        result = await validator.validate(base_package)

        assert result.compliance_level == ESPRComplianceLevel.FULL


class TestCompletenessScore:
    """Test completeness score calculation."""

    @pytest.mark.asyncio
    async def test_completeness_with_errors(self, validator, base_package):
        """Test that errors reduce completeness score."""
        result = await validator.validate(base_package)

        # Empty package should have low completeness
        assert result.completeness_score < 1.0

    @pytest.mark.asyncio
    async def test_full_completeness(
        self, validator, base_package, nameplate_submodel, pcf_submodel
    ):
        """Test that valid package has high completeness."""
        base_package.submodels = [nameplate_submodel, pcf_submodel]

        result = await validator.validate(base_package)

        assert result.completeness_score == 1.0


class TestSubmodelStatuses:
    """Test per-submodel status tracking."""

    @pytest.mark.asyncio
    async def test_submodel_statuses_included(
        self, validator, base_package, nameplate_submodel
    ):
        """Test that submodel statuses are tracked."""
        base_package.submodels = [nameplate_submodel]

        result = await validator.validate(base_package)

        assert nameplate_submodel.template_name in result.submodel_statuses
