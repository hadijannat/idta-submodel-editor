"""
Extraction Validator - Validate Magic Import extractions against template schema.

Bridges the Magic Import pipeline with the existing form validation infrastructure.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Literal

from app.schemas.magic_import import (
    FieldExtraction,
    ValidationError as MagicImportValidationError,
    ValidationResult,
)
from app.services.fetcher import TemplateFetcherService
from app.services.parser import ParserService

logger = logging.getLogger(__name__)


class ExtractionValidator:
    """Validate extracted fields against template schema."""

    def __init__(self) -> None:
        self._fetcher = None
        self._parser = None

    @property
    def fetcher(self) -> TemplateFetcherService:
        if self._fetcher is None:
            from app.dependencies import get_fetcher
            self._fetcher = get_fetcher()
        return self._fetcher

    @property
    def parser(self) -> ParserService:
        if self._parser is None:
            from app.dependencies import get_parser
            self._parser = get_parser()
        return self._parser

    def validate_extractions(
        self,
        extractions: list[FieldExtraction],
        template_name: str,
        template_status: Literal["published", "deprecated"] = "published",
        template_version: str | None = None,
        mode: Literal["warn", "strict"] = "warn",
    ) -> ValidationResult:
        """
        Validate extractions against template schema.

        Args:
            extractions: List of field extractions from Magic Import
            template_name: Template identifier
            template_status: published or deprecated
            template_version: Optional specific version
            mode: "warn" returns warnings for issues, "strict" returns errors

        Returns:
            ValidationResult with is_valid, errors, and warnings
        """
        errors: list[MagicImportValidationError] = []
        warnings: list[MagicImportValidationError] = []

        try:
            schema = self._load_schema(
                template_name,
                template_status,
                template_version,
            )
            if not schema:
                errors.append(
                    MagicImportValidationError(
                        path="",
                        message=f"Template '{template_name}' not found",
                        code="template_not_found",
                    )
                )
                return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

            schema_elements = schema.get("elements", [])

            # Build lookup of schema elements by path
            schema_by_path = self._build_schema_lookup(schema_elements)

            # Build lookup of extractions by path
            extractions_by_path = {e.path: e for e in extractions}

            # Check each extraction against schema
            for extraction in extractions:
                path = extraction.path
                schema_elem = schema_by_path.get(path)

                if schema_elem is None:
                    # Path not found in schema - could be optional or wrong path
                    target = warnings if mode == "warn" else errors
                    target.append(
                        MagicImportValidationError(
                            path=path,
                            message=f"Field '{path}' not found in template schema",
                            code="unknown_field",
                        )
                    )
                    continue

                # Validate type if specified
                if extraction.value_type and extraction.value_raw:
                    type_errors = self._validate_type(
                        extraction.value_raw,
                        extraction.value_type,
                        path,
                    )
                    for err in type_errors:
                        target = warnings if mode == "warn" else errors
                        target.append(err)

            # Check for required fields that are missing
            required_paths = self._get_required_paths(schema_elements)
            for req_path in required_paths:
                if req_path not in extractions_by_path:
                    target = warnings if mode == "warn" else errors
                    target.append(
                        MagicImportValidationError(
                            path=req_path,
                            message=f"Required field '{req_path}' not extracted",
                            code="missing_required",
                        )
                    )

            is_valid = len(errors) == 0
            return ValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)

        except Exception as e:
            logger.exception("Validation failed for template %s", template_name)
            errors.append(
                MagicImportValidationError(
                    path="",
                    message=f"Validation error: {str(e)}",
                    code="validation_error",
                )
            )
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

    async def _fetch_template(
        self,
        template_name: str,
        template_status: str,
        template_version: str | None,
    ) -> bytes:
        """Fetch template AASX bytes."""
        template_path = f"{template_status}/{template_name}"
        if template_version:
            template_path = f"{template_path}/{template_version}"
        return await self.fetcher.fetch_template_aasx(template_path)

    def _load_schema(
        self,
        template_name: str,
        template_status: str,
        template_version: str | None,
    ) -> dict[str, Any] | None:
        """Load schema using legacy sync fetcher or async AASX fetcher."""
        # Legacy path for tests/mocks
        if self._fetcher is not None and hasattr(self._fetcher, "get_template"):
            template = self._fetcher.get_template(
                template_name, template_status, template_version
            )
            if template is None:
                return None
            parser = self._parser or self.parser
            if hasattr(parser, "parse_template"):
                return parser.parse_template(template)
            return parser.parse_aasx_to_ui_schema(template)

        template_bytes = self._run_async_fetch(
            template_name, template_status, template_version
        )
        if not template_bytes:
            return None
        return self.parser.parse_aasx_to_ui_schema(template_bytes)

    def _run_async_fetch(
        self,
        template_name: str,
        template_status: str,
        template_version: str | None,
    ) -> bytes:
        """Run async fetch in sync context; accept non-awaitable return for tests."""
        result = self.fetcher.fetch_template_aasx(
            f"{template_status}/{template_name}"
            + (f"/{template_version}" if template_version else "")
        )
        if hasattr(result, "__await__"):
            return asyncio.run(result)
        return result

    def _build_schema_lookup(
        self,
        elements: list[dict[str, Any]],
        prefix: str = "",
    ) -> dict[str, dict[str, Any]]:
        """Build a flat lookup of schema elements by their idShortPath."""
        lookup: dict[str, dict[str, Any]] = {}

        for elem in elements:
            id_short = elem.get("idShort", "")
            path = f"{prefix}.{id_short}" if prefix else id_short
            lookup[path] = elem

            model_type = elem.get("modelType")

            if model_type == "SubmodelElementCollection":
                nested = elem.get("elements", [])
                nested_lookup = self._build_schema_lookup(nested, path)
                lookup.update(nested_lookup)

            elif model_type == "SubmodelElementList":
                item_template = elem.get("itemTemplate")
                if item_template:
                    # For lists, we use path[] to indicate list items
                    item_path = f"{path}[]"
                    lookup[item_path] = item_template
                    if item_template.get("modelType") == "SubmodelElementCollection":
                        nested = item_template.get("elements", [])
                        nested_lookup = self._build_schema_lookup(nested, item_path)
                        lookup.update(nested_lookup)

            elif model_type == "Entity":
                statements = elem.get("statements", [])
                statements_lookup = self._build_schema_lookup(statements, path)
                lookup.update(statements_lookup)

        return lookup

    def _get_required_paths(
        self,
        elements: list[dict[str, Any]],
        prefix: str = "",
    ) -> list[str]:
        """Get list of paths for required fields."""
        required: list[str] = []

        for elem in elements:
            id_short = elem.get("idShort", "")
            path = f"{prefix}.{id_short}" if prefix else id_short

            cardinality = elem.get("cardinality", "[1]")
            min_items = self._parse_min_cardinality(cardinality)

            model_type = elem.get("modelType")

            # Properties and similar value-holding elements
            if model_type in ("Property", "MultiLanguageProperty", "File", "ReferenceElement"):
                if min_items >= 1:
                    required.append(path)

            # Recurse into collections
            if model_type == "SubmodelElementCollection":
                nested = elem.get("elements", [])
                required.extend(self._get_required_paths(nested, path))

            elif model_type == "Entity":
                statements = elem.get("statements", [])
                required.extend(self._get_required_paths(statements, path))

        return required

    def _parse_min_cardinality(self, cardinality: str) -> int:
        """Parse minimum from cardinality string."""
        import re

        # Normalize known formats
        mapping = {
            "ZeroToOne": 0,
            "ZeroToMany": 0,
            "OneToMany": 1,
            "One": 1,
            "Zero": 0,
        }
        if cardinality in mapping:
            return mapping[cardinality]

        # Parse [N] or [N..M] or [N..*] format
        match = re.match(r"^\[?(\d+)", str(cardinality))
        if match:
            return int(match.group(1))

        return 1  # Default to required

    def _validate_type(
        self,
        value: str,
        value_type: str,
        path: str,
    ) -> list[MagicImportValidationError]:
        """Validate a value against its expected type."""
        errors: list[MagicImportValidationError] = []

        if not value or not value_type:
            return errors

        type_lower = value_type.lower()

        try:
            if "int" in type_lower or "integer" in type_lower:
                # Try to parse as number
                num = float(value.replace(",", ".").replace(" ", ""))
                if not num.is_integer():
                    errors.append(
                        MagicImportValidationError(
                            path=path,
                            message=f"Value '{value}' is not a valid integer",
                            code="type_mismatch",
                        )
                    )

            elif any(t in type_lower for t in ("float", "double", "decimal")):
                # Try to parse as float
                float(value.replace(",", ".").replace(" ", ""))

            elif "bool" in type_lower:
                if value.lower() not in ("true", "false", "1", "0", "yes", "no"):
                    errors.append(
                        MagicImportValidationError(
                            path=path,
                            message=f"Value '{value}' is not a valid boolean",
                            code="type_mismatch",
                        )
                    )

            elif "date" in type_lower:
                from datetime import datetime

                # Accept various date formats
                parsed = False
                for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S"]:
                    try:
                        datetime.strptime(value.split(".")[0].split("+")[0], fmt)
                        parsed = True
                        break
                    except ValueError:
                        continue

                if not parsed:
                    errors.append(
                        MagicImportValidationError(
                            path=path,
                            message=f"Value '{value}' is not a valid date",
                            code="type_mismatch",
                        )
                    )

        except (ValueError, TypeError):
            errors.append(
                MagicImportValidationError(
                    path=path,
                    message=f"Value '{value}' does not match expected type {value_type}",
                    code="type_mismatch",
                )
            )

        return errors
