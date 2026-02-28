"""
Tests for DPP Builder service.

Tests DPP package management including:
- Package creation and lifecycle
- Submodel addition and removal
- Export functionality
- Security: Package ID validation
"""

import json
import pytest

from app.services.dpp.builder import DPPBuilder, _validate_package_id
from app.services.dpp.models import (
    DPPPackageCreate,
    DPPPackageStatus,
    DPPSubmodelAdd,
)


@pytest.fixture
def builder(tmp_path) -> DPPBuilder:
    """Create a DPP builder with temp storage."""
    # Patch the cache dir
    from app.config import get_settings
    settings = get_settings()
    original_cache_dir = settings.dataspace_cache_dir

    # Use tmp_path for testing
    settings.dataspace_cache_dir = tmp_path

    builder = DPPBuilder()

    yield builder

    # Restore
    settings.dataspace_cache_dir = original_cache_dir


class TestPackageCreation:
    """Test DPP package creation."""

    def test_create_empty_package(self, builder):
        """Test creating an empty package."""
        request = DPPPackageCreate()
        package = builder.create_package(request)

        assert package.package_id.startswith("dpp-")
        assert package.status == DPPPackageStatus.DRAFT
        assert len(package.submodels) == 0
        assert package.created_at is not None
        assert package.updated_at is not None

    def test_create_package_with_metadata(self, builder):
        """Test creating a package with product metadata."""
        request = DPPPackageCreate(
            product_id="PROD-123",
            product_name="Test Product",
            manufacturer_name="Test Manufacturer",
            manufacturer_id="MFR-456",
            notes="Test notes",
        )
        package = builder.create_package(request)

        assert package.product_id == "PROD-123"
        assert package.product_name == "Test Product"
        assert package.manufacturer_name == "Test Manufacturer"
        assert package.manufacturer_id == "MFR-456"
        assert package.notes == "Test notes"

    def test_package_persists(self, builder):
        """Test that package is persisted to disk."""
        request = DPPPackageCreate(product_name="Persistent Product")
        created = builder.create_package(request)

        # Retrieve should return same data
        retrieved = builder.get_package(created.package_id)

        assert retrieved is not None
        assert retrieved.package_id == created.package_id
        assert retrieved.product_name == "Persistent Product"


class TestPackageRetrieval:
    """Test package retrieval and listing."""

    def test_get_nonexistent_package(self, builder):
        """Test getting a package that doesn't exist."""
        # Use a valid format ID that doesn't exist (matches dpp-[a-f0-9]{12})
        package = builder.get_package("dpp-000000000000")
        assert package is None

    def test_list_packages(self, builder):
        """Test listing packages."""
        # Create multiple packages
        for i in range(3):
            builder.create_package(DPPPackageCreate(product_name=f"Product {i}"))

        packages = builder.list_packages()

        assert len(packages) == 3

    def test_list_packages_with_status_filter(self, builder):
        """Test listing packages filtered by status."""
        builder.create_package(DPPPackageCreate(product_name="Draft Package"))

        # All new packages are DRAFT
        draft_packages = builder.list_packages(status=DPPPackageStatus.DRAFT)
        valid_packages = builder.list_packages(status=DPPPackageStatus.VALID)

        assert len(draft_packages) == 1
        assert len(valid_packages) == 0

    def test_list_packages_with_limit(self, builder):
        """Test listing packages with limit."""
        for i in range(5):
            builder.create_package(DPPPackageCreate(product_name=f"Product {i}"))

        packages = builder.list_packages(limit=3)

        assert len(packages) == 3


class TestPackageUpdate:
    """Test package updates."""

    def test_update_metadata(self, builder):
        """Test updating package metadata."""
        package = builder.create_package(DPPPackageCreate())

        updated = builder.update_package(
            package.package_id,
            product_name="Updated Name",
            manufacturer_name="Updated Manufacturer",
        )

        assert updated is not None
        assert updated.product_name == "Updated Name"
        assert updated.manufacturer_name == "Updated Manufacturer"
        assert updated.updated_at > package.updated_at

    def test_update_nonexistent_package(self, builder):
        """Test updating a package that doesn't exist."""
        # Use a valid format ID that doesn't exist (matches dpp-[a-f0-9]{12})
        result = builder.update_package("dpp-000000000000", product_name="Test")
        assert result is None


class TestPackageDeletion:
    """Test package deletion."""

    def test_delete_package(self, builder):
        """Test deleting a package."""
        package = builder.create_package(DPPPackageCreate())

        assert builder.delete_package(package.package_id) is True
        assert builder.get_package(package.package_id) is None

    def test_delete_nonexistent_package(self, builder):
        """Test deleting a package that doesn't exist."""
        # Use a valid format ID that doesn't exist (matches dpp-[a-f0-9]{12})
        assert builder.delete_package("dpp-000000000000") is False


class TestSubmodelManagement:
    """Test submodel addition and removal."""

    @pytest.mark.asyncio
    async def test_add_submodel(self, builder):
        """Test adding a submodel to a package."""
        package = builder.create_package(DPPPackageCreate())

        request = DPPSubmodelAdd(
            template_name="IDTA-02006-2-0-Nameplate",
            role="identification",
            form_data={
                "elements": {
                    "ManufacturerName": {"value": "Test Corp"},
                    "SerialNumber": {"value": "SN-123"},
                }
            },
        )

        updated = await builder.add_submodel(package.package_id, request)

        assert updated is not None
        assert len(updated.submodels) == 1
        assert updated.submodels[0].template_name == "IDTA-02006-2-0-Nameplate"
        assert updated.submodels[0].role == "identification"

    @pytest.mark.asyncio
    async def test_add_submodel_extracts_product_info(self, builder):
        """Test that adding identification submodel extracts product info."""
        package = builder.create_package(DPPPackageCreate())

        request = DPPSubmodelAdd(
            template_name="IDTA-02006-2-0-Nameplate",
            role="identification",
            form_data={
                "elements": {
                    "ManufacturerName": {"value": "Extracted Corp"},
                    "SerialNumber": {"value": "EXT-789"},
                    "ProductType": {"value": "Extracted Product"},
                }
            },
        )

        updated = await builder.add_submodel(package.package_id, request)

        assert updated.manufacturer_name == "Extracted Corp"
        assert updated.product_id == "EXT-789"
        assert updated.product_name == "Extracted Product"

    @pytest.mark.asyncio
    async def test_add_multiple_submodels(self, builder):
        """Test adding multiple submodels."""
        package = builder.create_package(DPPPackageCreate())

        await builder.add_submodel(
            package.package_id,
            DPPSubmodelAdd(
                template_name="IDTA-02006-2-0-Nameplate",
                role="identification",
                form_data={"elements": {}},
            ),
        )

        updated = await builder.add_submodel(
            package.package_id,
            DPPSubmodelAdd(
                template_name="IDTA-02023-0-9-CarbonFootprint",
                role="sustainability",
                form_data={"elements": {}},
            ),
        )

        assert len(updated.submodels) == 2

    @pytest.mark.asyncio
    async def test_add_submodel_to_nonexistent_package(self, builder):
        """Test adding submodel to nonexistent package."""
        request = DPPSubmodelAdd(
            template_name="IDTA-02006-2-0-Nameplate",
            role="identification",
            form_data={},
        )

        # Use a valid format ID that doesn't exist (matches dpp-[a-f0-9]{12})
        result = await builder.add_submodel("dpp-000000000000", request)
        assert result is None

    def test_remove_submodel(self, builder):
        """Test removing a submodel from a package."""
        package = builder.create_package(DPPPackageCreate())

        # Manually add a submodel for this test
        package.submodels.append(
            __import__("app.services.dpp.models", fromlist=["DPPSubmodelRef"]).DPPSubmodelRef(
                template_name="IDTA-02006-2-0-Nameplate",
                role="identification",
                form_data={},
            )
        )
        builder._save_package(package)

        updated = builder.remove_submodel(
            package.package_id, "IDTA-02006-2-0-Nameplate"
        )

        assert updated is not None
        assert len(updated.submodels) == 0


class TestValidation:
    """Test package validation."""

    @pytest.mark.asyncio
    async def test_validate_empty_package(self, builder):
        """Test validating an empty package."""
        package = builder.create_package(DPPPackageCreate())

        result = await builder.validate_package(package.package_id)

        assert result is not None
        assert not result.is_valid

    @pytest.mark.asyncio
    async def test_validate_updates_package_status(self, builder):
        """Test that validation updates package status."""
        package = builder.create_package(DPPPackageCreate())

        await builder.validate_package(package.package_id)

        # Reload package
        updated = builder.get_package(package.package_id)

        assert updated.status == DPPPackageStatus.INVALID
        assert updated.validation_result is not None


class TestExport:
    """Test package export."""

    @pytest.mark.asyncio
    async def test_export_json(self, builder):
        """Test exporting package as JSON."""
        package = builder.create_package(
            DPPPackageCreate(
                product_id="JSON-TEST",
                product_name="JSON Test Product",
            )
        )

        content = await builder.export_package(
            package.package_id,
            format="json",
            include_validation_report=False,
        )

        assert content is not None
        data = json.loads(content.decode("utf-8"))

        assert data["package_id"] == package.package_id
        assert data["product"]["id"] == "JSON-TEST"
        assert data["product"]["name"] == "JSON Test Product"

    @pytest.mark.asyncio
    async def test_export_nonexistent_package(self, builder):
        """Test exporting a nonexistent package."""
        # Use a valid format ID that doesn't exist (matches dpp-[a-f0-9]{12})
        content = await builder.export_package("dpp-000000000000", format="json")
        assert content is None

    @pytest.mark.asyncio
    async def test_export_validates_first(self, builder):
        """Test that export validates if not already validated."""
        package = builder.create_package(DPPPackageCreate())

        # Export should trigger validation
        await builder.export_package(package.package_id, format="json")

        # Reload and check
        updated = builder.get_package(package.package_id)
        assert updated.validation_result is not None


class TestPackageIdValidation:
    """Test security validation of package IDs to prevent path traversal."""

    def test_valid_package_id_passes(self):
        """Test that valid package IDs pass validation."""
        # Valid formats
        _validate_package_id("dpp-abcdef123456")
        _validate_package_id("dpp-000000000000")
        _validate_package_id("dpp-ffffffffffff")

    def test_path_traversal_blocked(self, builder):
        """Test that path traversal attempts are blocked."""
        traversal_ids = [
            "../etc/passwd",
            "../../secrets",
            "dpp-../../../../etc/passwd",
            "..",
            "/etc/passwd",
            "dpp-abc/../../../etc/passwd",
        ]
        for bad_id in traversal_ids:
            with pytest.raises(ValueError, match="Invalid package ID format"):
                _validate_package_id(bad_id)

    def test_invalid_format_blocked(self, builder):
        """Test that invalid ID formats are blocked."""
        invalid_ids = [
            "invalid-id",
            "dpp-",  # Too short
            "dpp-abc",  # Too short
            "dpp-ABCDEF123456",  # Uppercase not allowed
            "dpp-abcdefghijkl",  # Contains non-hex chars
            "dpp-abcdef12345",  # Too short (11 chars)
            "dpp-abcdef1234567",  # Too long (13 chars)
            "DPP-abcdef123456",  # Wrong prefix case
            "dpp_abcdef123456",  # Wrong separator
            "",  # Empty
        ]
        for bad_id in invalid_ids:
            with pytest.raises(ValueError, match="Invalid package ID format"):
                _validate_package_id(bad_id)

    def test_get_with_invalid_id_raises(self, builder):
        """Test that get_package raises on invalid ID format."""
        with pytest.raises(ValueError, match="Invalid package ID format"):
            builder.get_package("../etc/passwd")

    def test_delete_with_invalid_id_raises(self, builder):
        """Test that delete_package raises on invalid ID format."""
        with pytest.raises(ValueError, match="Invalid package ID format"):
            builder.delete_package("../etc/passwd")
