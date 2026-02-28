"""
DPP Builder - Assembles Digital Product Passport packages.

Orchestrates the assembly of multiple submodels into a DPP-ready package,
with validation and export capabilities for EU ESPR compliance.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from io import BytesIO
from typing import TYPE_CHECKING

from app.config import get_settings
from app.services.dpp.models import (
    DPPPackage,
    DPPPackageCreate,
    DPPPackageStatus,
    DPPSubmodelAdd,
    DPPSubmodelRef,
    DPPValidationResult,
)
from app.services.dpp.validator import DPPValidator

if TYPE_CHECKING:
    from app.services.fetcher import TemplateFetcherService
    from app.services.hydrator import HydratorService
    from app.services.parser import ParserService

logger = logging.getLogger(__name__)

# Package ID validation pattern - must match format generated in create_package
_PACKAGE_ID_PATTERN = re.compile(r"^dpp-[a-f0-9]{12}$")


def _validate_package_id(package_id: str) -> None:
    """
    Validate package_id format to prevent path traversal attacks.

    Raises:
        ValueError: If package_id does not match expected format.
    """
    if not _PACKAGE_ID_PATTERN.match(package_id):
        raise ValueError(f"Invalid package ID format: {package_id}")


class DPPBuilder:
    """
    Builder for Digital Product Passport packages.

    Provides:
    - Package creation and management
    - Submodel addition with role assignment
    - Validation against ESPR requirements
    - Export to AASX/JSON formats
    - Publication to dataspace
    """

    def __init__(
        self,
        fetcher: "TemplateFetcherService | None" = None,
        parser: "ParserService | None" = None,
        hydrator: "HydratorService | None" = None,
    ):
        self._fetcher = fetcher
        self._parser = parser
        self._hydrator = hydrator
        self._validator = DPPValidator(fetcher=fetcher, parser=parser)

        # Storage
        settings = get_settings()
        self._cache_dir = settings.dataspace_cache_dir / "dpp"
        self._packages_dir = self._cache_dir / "packages"
        self._packages_dir.mkdir(parents=True, exist_ok=True)

    def create_package(self, request: DPPPackageCreate) -> DPPPackage:
        """
        Create a new DPP package.

        Args:
            request: Package creation request

        Returns:
            Created DPP package
        """
        now = datetime.now(timezone.utc)
        package_id = f"dpp-{uuid.uuid4().hex[:12]}"

        package = DPPPackage(
            package_id=package_id,
            status=DPPPackageStatus.DRAFT,
            created_at=now,
            updated_at=now,
            product_id=request.product_id,
            product_name=request.product_name,
            manufacturer_name=request.manufacturer_name,
            manufacturer_id=request.manufacturer_id,
            notes=request.notes,
        )

        self._save_package(package)
        logger.info("Created DPP package %s", package_id)

        return package

    def get_package(self, package_id: str) -> DPPPackage | None:
        """Get a DPP package by ID."""
        _validate_package_id(package_id)
        package_path = self._packages_dir / f"{package_id}.json"
        if not package_path.exists():
            return None

        data = json.loads(package_path.read_text())
        return DPPPackage.model_validate(data)

    def list_packages(
        self,
        status: DPPPackageStatus | None = None,
        limit: int = 50,
    ) -> list[DPPPackage]:
        """List DPP packages."""
        packages: list[DPPPackage] = []

        for package_path in self._packages_dir.glob("*.json"):
            try:
                data = json.loads(package_path.read_text())
                package = DPPPackage.model_validate(data)

                if status is None or package.status == status:
                    packages.append(package)
            except Exception as e:
                logger.warning("Failed to load package %s: %s", package_path.stem, e)

        # Sort by updated_at descending
        packages.sort(key=lambda p: p.updated_at, reverse=True)
        return packages[:limit]

    def update_package(
        self,
        package_id: str,
        product_id: str | None = None,
        product_name: str | None = None,
        manufacturer_name: str | None = None,
        manufacturer_id: str | None = None,
        notes: str | None = None,
    ) -> DPPPackage | None:
        """Update package metadata."""
        package = self.get_package(package_id)
        if package is None:
            return None

        update_data = {"updated_at": datetime.now(timezone.utc)}
        if product_id is not None:
            update_data["product_id"] = product_id
        if product_name is not None:
            update_data["product_name"] = product_name
        if manufacturer_name is not None:
            update_data["manufacturer_name"] = manufacturer_name
        if manufacturer_id is not None:
            update_data["manufacturer_id"] = manufacturer_id
        if notes is not None:
            update_data["notes"] = notes

        package = package.model_copy(update=update_data)
        self._save_package(package)

        return package

    def delete_package(self, package_id: str) -> bool:
        """Delete a DPP package."""
        _validate_package_id(package_id)
        package_path = self._packages_dir / f"{package_id}.json"
        if not package_path.exists():
            return False

        package_path.unlink()
        logger.info("Deleted DPP package %s", package_id)
        return True

    async def add_submodel(
        self,
        package_id: str,
        request: DPPSubmodelAdd,
    ) -> DPPPackage | None:
        """
        Add a submodel to a DPP package.

        Args:
            package_id: Package ID
            request: Submodel addition request

        Returns:
            Updated package or None if not found
        """
        package = self.get_package(package_id)
        if package is None:
            return None

        # Extract semantic ID from template if possible
        semantic_id = None
        if self._fetcher and self._parser:
            try:
                template_path = f"{request.template_status}/{request.template_name}"
                if request.template_version:
                    template_path = f"{template_path}/{request.template_version}"
                template_bytes = await self._fetcher.fetch_template_aasx(template_path)
                schema = self._parser.parse_aasx_to_ui_schema(template_bytes)
                semantic_id = schema.get("semanticId")
            except Exception as e:
                logger.warning("Failed to extract semantic ID: %s", e)

        # Check if template already added
        for existing in package.submodels:
            if existing.template_name == request.template_name:
                # Update existing
                existing.form_data = request.form_data
                existing.role = request.role
                if semantic_id:
                    existing.semantic_id = semantic_id
                package.updated_at = datetime.now(timezone.utc)
                self._save_package(package)
                return package

        # Add new submodel reference
        submodel_ref = DPPSubmodelRef(
            template_name=request.template_name,
            template_status=request.template_status,
            template_version=request.template_version,
            semantic_id=semantic_id,
            role=request.role,
            form_data=request.form_data,
            is_required=request.role == "identification",
        )

        package.submodels.append(submodel_ref)
        package.updated_at = datetime.now(timezone.utc)

        # Extract product info from identification submodel
        if request.role == "identification":
            self._extract_product_info(package, request.form_data)

        self._save_package(package)
        logger.info(
            "Added submodel %s to package %s as %s",
            request.template_name,
            package_id,
            request.role,
        )

        return package

    def remove_submodel(
        self,
        package_id: str,
        template_name: str,
    ) -> DPPPackage | None:
        """Remove a submodel from a package."""
        package = self.get_package(package_id)
        if package is None:
            return None

        original_count = len(package.submodels)
        package.submodels = [
            sm for sm in package.submodels if sm.template_name != template_name
        ]

        if len(package.submodels) < original_count:
            package.updated_at = datetime.now(timezone.utc)
            self._save_package(package)
            logger.info("Removed submodel %s from package %s", template_name, package_id)

        return package

    async def validate_package(self, package_id: str) -> DPPValidationResult | None:
        """
        Validate a DPP package.

        Args:
            package_id: Package ID

        Returns:
            Validation result or None if package not found
        """
        package = self.get_package(package_id)
        if package is None:
            return None

        package.status = DPPPackageStatus.VALIDATING
        self._save_package(package)

        try:
            result = await self._validator.validate(package)

            package.validation_result = result
            package.status = (
                DPPPackageStatus.VALID if result.is_valid else DPPPackageStatus.INVALID
            )
            package.updated_at = datetime.now(timezone.utc)
            self._save_package(package)

            logger.info(
                "Validated package %s: %s (%s)",
                package_id,
                "valid" if result.is_valid else "invalid",
                result.compliance_level,
            )

            return result

        except Exception:
            package.status = DPPPackageStatus.INVALID
            package.updated_at = datetime.now(timezone.utc)
            self._save_package(package)
            raise

    async def export_package(
        self,
        package_id: str,
        format: str = "aasx",
        include_validation_report: bool = True,
    ) -> bytes | None:
        """
        Export a DPP package to AASX or JSON format.

        Args:
            package_id: Package ID
            format: Export format ("aasx" or "json")
            include_validation_report: Include validation report in export

        Returns:
            Export content as bytes or None if package not found
        """
        package = self.get_package(package_id)
        if package is None:
            return None

        # Validate before export if not already validated
        if package.validation_result is None:
            await self.validate_package(package_id)
            package = self.get_package(package_id)

        if format == "json":
            return self._export_json(package, include_validation_report)
        elif format == "aasx":
            return await self._export_aasx(package, include_validation_report)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _export_json(
        self,
        package: DPPPackage,
        include_validation_report: bool,
    ) -> bytes:
        """Export package to JSON format."""
        export_data = {
            "dpp_version": "1.0.0",
            "package_id": package.package_id,
            "created_at": package.created_at.isoformat(),
            "updated_at": package.updated_at.isoformat(),
            "product": {
                "id": package.product_id,
                "name": package.product_name,
                "manufacturer_name": package.manufacturer_name,
                "manufacturer_id": package.manufacturer_id,
            },
            "submodels": [
                {
                    "template_name": sm.template_name,
                    "semantic_id": sm.semantic_id,
                    "role": sm.role,
                    "form_data": sm.form_data,
                }
                for sm in package.submodels
            ],
        }

        if include_validation_report and package.validation_result:
            export_data["validation"] = {
                "is_valid": package.validation_result.is_valid,
                "compliance_level": package.validation_result.compliance_level.value,
                "completeness_score": package.validation_result.completeness_score,
                "errors": [e.model_dump() for e in package.validation_result.errors],
                "warnings": [w.model_dump() for w in package.validation_result.warnings],
            }

        return json.dumps(export_data, indent=2).encode("utf-8")

    async def _export_aasx(
        self,
        package: DPPPackage,
        include_validation_report: bool,
    ) -> bytes:
        """Export package to AASX format with multiple submodels."""
        import zipfile

        if not self._fetcher or not self._hydrator:
            raise RuntimeError("Fetcher and Hydrator required for AASX export")

        buffer = BytesIO()

        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # Track successful exports for manifest
            successful_exports: list[tuple[DPPSubmodelRef, str]] = []

            # Export each submodel as separate AASX
            for idx, sm in enumerate(package.submodels):
                template_path = f"{sm.template_status}/{sm.template_name}"
                if sm.template_version:
                    template_path = f"{template_path}/{sm.template_version}"

                try:
                    template_bytes = await self._fetcher.fetch_template_aasx(template_path)
                    hydrated = self._hydrator.hydrate_submodel(
                        template_bytes, sm.form_data
                    )

                    filename = f"{sm.role}_{sm.template_name}.aasx"
                    zf.writestr(filename, hydrated)
                    successful_exports.append((sm, filename))
                except Exception as e:
                    logger.warning(
                        "Failed to export submodel %s: %s", sm.template_name, e
                    )

            # Add DPP manifest - only include successfully exported submodels
            manifest = {
                "dpp_version": "1.0.0",
                "package_id": package.package_id,
                "product": {
                    "id": package.product_id,
                    "name": package.product_name,
                    "manufacturer_name": package.manufacturer_name,
                },
                "submodels": [
                    {
                        "template_name": sm.template_name,
                        "semantic_id": sm.semantic_id,
                        "role": sm.role,
                        "file": filename,
                    }
                    for sm, filename in successful_exports
                ],
            }
            zf.writestr("dpp-manifest.json", json.dumps(manifest, indent=2))

            # Add validation report if requested
            if include_validation_report and package.validation_result:
                report = {
                    "is_valid": package.validation_result.is_valid,
                    "compliance_level": package.validation_result.compliance_level.value,
                    "completeness_score": package.validation_result.completeness_score,
                    "errors": [e.model_dump() for e in package.validation_result.errors],
                    "warnings": [
                        w.model_dump() for w in package.validation_result.warnings
                    ],
                }
                zf.writestr("validation-report.json", json.dumps(report, indent=2))

        return buffer.getvalue()

    def _extract_product_info(self, package: DPPPackage, form_data: dict) -> None:
        """Extract product information from identification submodel."""
        elements = form_data.get("elements", {})

        # Try to extract manufacturer name
        if not package.manufacturer_name:
            mfr = self._get_nested_value(elements, "ManufacturerName")
            if mfr:
                package.manufacturer_name = mfr

        # Try to extract serial number as product ID
        if not package.product_id:
            serial = self._get_nested_value(elements, "SerialNumber")
            if serial:
                package.product_id = serial

        # Try to extract product name
        if not package.product_name:
            name = self._get_nested_value(elements, "ProductType")
            if name:
                package.product_name = name

    def _get_nested_value(self, elements: dict, field_name: str) -> str | None:
        """Get a field value from nested elements structure."""
        if field_name in elements:
            value = elements[field_name]
            if isinstance(value, dict):
                return value.get("value")
            return value

        # Check nested structures
        for key, value in elements.items():
            if isinstance(value, dict):
                nested = value.get("elements", {})
                if field_name in nested:
                    nested_value = nested[field_name]
                    if isinstance(nested_value, dict):
                        return nested_value.get("value")
                    return nested_value

        return None

    def _save_package(self, package: DPPPackage) -> None:
        """Save package to disk."""
        package_path = self._packages_dir / f"{package.package_id}.json"
        package_path.write_text(package.model_dump_json(indent=2))
