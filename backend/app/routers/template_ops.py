"""
Template Operations router.

Provides import, diff, migrate, and validate operations for templates.
"""

import logging
from io import BytesIO
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, Query, UploadFile

from app.dependencies import get_fetcher, get_parser
from app.errors import APIError, ErrorCode
from app.schemas.template_ops import (
    CardinalityChange,
    ElementChange,
    MigrationMappingItem,
    MigrationPlan,
    MigrationPlanRequest,
    SemanticChange,
    TemplateDiffRequest,
    TemplateDiffResult,
    TemplateImportResult,
    TemplateValidateRequest,
    ValidationDiagnostic,
    ValidationDiagnostics,
)
from app.services.fetcher import TemplateFetcherService
from app.services.parser import ParserService
from app.utils.upload_security import FileType, UploadValidator, read_upload_file
from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/template-ops", tags=["template-ops"])


def _build_path_index(elements: list[dict], prefix: str = "") -> dict[str, dict]:
    """Build a flat index of all elements by their path."""
    index: dict[str, dict] = {}
    for elem in elements:
        id_short = elem.get("idShort", "")
        path = f"{prefix}.{id_short}" if prefix else id_short
        index[path] = elem

        # Recurse into nested elements
        if "elements" in elem and elem["elements"]:
            index.update(_build_path_index(elem["elements"], path))

        # Handle list item templates
        if "itemTemplate" in elem and elem["itemTemplate"]:
            item_template = elem["itemTemplate"]
            item_path = f"{path}[]"
            index[item_path] = item_template
            if "elements" in item_template:
                index.update(_build_path_index(item_template["elements"], item_path))

    return index


def _compute_similarity(source_elem: dict, target_elem: dict) -> float:
    """Compute similarity score between two elements."""
    score = 0.0
    weights_sum = 0.0

    # idShort match (weight: 0.3)
    if source_elem.get("idShort") == target_elem.get("idShort"):
        score += 0.3
    weights_sum += 0.3

    # Model type match (weight: 0.2)
    if source_elem.get("modelType") == target_elem.get("modelType"):
        score += 0.2
    weights_sum += 0.2

    # Value type match (weight: 0.2)
    if source_elem.get("valueType") == target_elem.get("valueType"):
        score += 0.2
    weights_sum += 0.2

    # Semantic ID match (weight: 0.3)
    source_semantic = source_elem.get("semanticId")
    target_semantic = target_elem.get("semanticId")
    if source_semantic and target_semantic and source_semantic == target_semantic:
        score += 0.3
    weights_sum += 0.3

    return score / weights_sum if weights_sum > 0 else 0.0


@router.post("/import", response_model=TemplateImportResult)
async def import_template(
    file: Annotated[UploadFile, File(...)],
    fetcher: Annotated[TemplateFetcherService, Depends(get_fetcher)],
    parser: Annotated[ParserService, Depends(get_parser)],
    name: Annotated[str | None, Query(description="Custom template name")] = None,
    overwrite: Annotated[bool, Query(description="Overwrite existing")] = False,
) -> TemplateImportResult:
    """
    Import an AASX/JSON file as a local template.

    This endpoint allows importing existing AAS packages as editable
    local templates.
    """
    settings = get_settings()

    # Read file content with size limit
    try:
        contents = await read_upload_file(
            file,
            max_size_bytes=settings.max_upload_size_mb * 1024 * 1024,
        )
    except APIError as exc:
        return TemplateImportResult(
            success=False,
            template_name=name or file.filename or "unknown",
            elements_count=0,
            error=exc.message,
        )

    # Validate file type
    validator = UploadValidator(
        allowed_types=[FileType.AASX, FileType.JSON],
        max_size_bytes=settings.max_upload_size_mb * 1024 * 1024,
    )
    result = validator.validate(contents, file.filename)
    if not result.valid:
        return TemplateImportResult(
            success=False,
            template_name=name or file.filename or "unknown",
            elements_count=0,
            error=result.error_message,
        )

    try:
        # Parse to validate and count elements
        schema = parser.parse_aasx_to_ui_schema(contents)
        elements_count = _count_elements(schema.get("elements", []))

        # Determine template name
        template_name = name or file.filename.rsplit(".", 1)[0]

        # Check if template exists
        existing_templates = fetcher._list_local_templates()
        exists = any(t.get("name") == template_name for t in existing_templates)

        warnings: list[str] = []
        if exists and not overwrite:
            return TemplateImportResult(
                success=False,
                template_name=template_name,
                elements_count=elements_count,
                error=f"Template '{template_name}' already exists. Use overwrite=true to replace.",
            )

        if exists:
            warnings.append(f"Overwriting existing template '{template_name}'")

        # Save as local template
        fetcher.save_local_template(template_name, contents)

        return TemplateImportResult(
            success=True,
            template_name=template_name,
            elements_count=elements_count,
            warnings=warnings,
        )

    except ValueError as e:
        return TemplateImportResult(
            success=False,
            template_name=name or file.filename or "unknown",
            elements_count=0,
            error=str(e),
        )
    except Exception as e:
        logger.exception("Failed to import template")
        return TemplateImportResult(
            success=False,
            template_name=name or file.filename or "unknown",
            elements_count=0,
            error=f"Failed to import template: {e}",
        )


def _count_elements(elements: list[dict]) -> int:
    """Recursively count all elements in a schema."""
    count = 0
    for elem in elements:
        count += 1
        if "elements" in elem and elem["elements"]:
            count += _count_elements(elem["elements"])
        if "itemTemplate" in elem:
            count += 1  # Count the template itself
            item_template = elem["itemTemplate"]
            if "elements" in item_template:
                count += _count_elements(item_template["elements"])
    return count


@router.post("/diff", response_model=TemplateDiffResult)
async def diff_templates(
    request: TemplateDiffRequest,
    fetcher: Annotated[TemplateFetcherService, Depends(get_fetcher)],
    parser: Annotated[ParserService, Depends(get_parser)],
) -> TemplateDiffResult:
    """
    Compare two template versions.

    Detects added/removed/modified elements, cardinality changes,
    and semantic ID changes.
    """
    try:
        # Fetch source template
        source_path = f"{request.source_status}/{request.source_template}"
        if request.source_version:
            source_path = f"{source_path}/{request.source_version}"
        source_bytes = await fetcher.fetch_template_aasx(source_path)
        source_schema = parser.parse_aasx_to_ui_schema(source_bytes)

        # Fetch target template
        target_path = f"{request.target_status}/{request.target_template}"
        if request.target_version:
            target_path = f"{target_path}/{request.target_version}"
        target_bytes = await fetcher.fetch_template_aasx(target_path)
        target_schema = parser.parse_aasx_to_ui_schema(target_bytes)

        # Build path indices
        source_index = _build_path_index(source_schema.get("elements", []))
        target_index = _build_path_index(target_schema.get("elements", []))

        source_paths = set(source_index.keys())
        target_paths = set(target_index.keys())

        # Find added/removed
        elements_added = list(target_paths - source_paths)
        elements_removed = list(source_paths - target_paths)

        # Find modified elements
        common_paths = source_paths & target_paths
        elements_modified: list[ElementChange] = []
        cardinality_changes: list[CardinalityChange] = []
        semantic_changes: list[SemanticChange] = []

        for path in common_paths:
            source_elem = source_index[path]
            target_elem = target_index[path]

            # Check for modifications
            changes = _compare_elements(source_elem, target_elem, path)
            elements_modified.extend(changes)

            # Check cardinality
            source_card = source_elem.get("cardinality", "[1]")
            target_card = target_elem.get("cardinality", "[1]")
            if source_card != target_card:
                # Breaking if min increases or max decreases
                breaking = _is_cardinality_breaking(source_card, target_card)
                cardinality_changes.append(
                    CardinalityChange(
                        path=path,
                        old_cardinality=source_card,
                        new_cardinality=target_card,
                        breaking=breaking,
                    )
                )

            # Check semantic IDs
            if request.include_semantic_changes:
                source_semantic = source_elem.get("semanticId")
                target_semantic = target_elem.get("semanticId")
                if source_semantic != target_semantic:
                    semantic_changes.append(
                        SemanticChange(
                            path=path,
                            old_semantic_id=source_semantic,
                            new_semantic_id=target_semantic,
                        )
                    )

        # Determine if breaking
        is_breaking = (
            len(elements_removed) > 0
            or any(c.breaking for c in cardinality_changes)
        )

        # Build summary
        summary_parts = []
        if elements_added:
            summary_parts.append(f"{len(elements_added)} element(s) added")
        if elements_removed:
            summary_parts.append(f"{len(elements_removed)} element(s) removed")
        if elements_modified:
            summary_parts.append(f"{len(elements_modified)} modification(s)")
        if cardinality_changes:
            summary_parts.append(f"{len(cardinality_changes)} cardinality change(s)")
        if semantic_changes:
            summary_parts.append(f"{len(semantic_changes)} semantic change(s)")

        summary = ", ".join(summary_parts) if summary_parts else "No changes detected"

        return TemplateDiffResult(
            source_template=request.source_template,
            source_version=request.source_version,
            target_template=request.target_template,
            target_version=request.target_version,
            elements_added=sorted(elements_added),
            elements_removed=sorted(elements_removed),
            elements_modified=elements_modified,
            cardinality_changes=cardinality_changes,
            semantic_changes=semantic_changes,
            is_breaking=is_breaking,
            summary=summary,
        )

    except APIError:
        raise
    except Exception as e:
        logger.exception("Failed to diff templates")
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to diff templates",
            detail={"error": str(e)},
        )


def _compare_elements(source: dict, target: dict, path: str) -> list[ElementChange]:
    """Compare two elements and return list of changes."""
    changes: list[ElementChange] = []

    # Check value type
    source_vt = source.get("valueType")
    target_vt = target.get("valueType")
    if source_vt != target_vt:
        changes.append(
            ElementChange(
                path=path,
                change_type="modified",
                old_value=source_vt,
                new_value=target_vt,
                details={"field": "valueType"},
            )
        )

    # Check model type
    source_mt = source.get("modelType")
    target_mt = target.get("modelType")
    if source_mt != target_mt:
        changes.append(
            ElementChange(
                path=path,
                change_type="modified",
                old_value=source_mt,
                new_value=target_mt,
                details={"field": "modelType"},
            )
        )

    return changes


def _is_cardinality_breaking(old: str, new: str) -> bool:
    """Check if cardinality change is breaking."""
    import re

    def parse_cardinality(card: str) -> tuple[int, int | None]:
        match = re.match(r"^\[(\d+)(?:\.\.(\d+|\*))?\]$", card)
        if not match:
            return (1, 1)
        min_val = int(match.group(1))
        max_group = match.group(2)
        if max_group is None:
            return (min_val, min_val)
        if max_group == "*":
            return (min_val, None)
        return (min_val, int(max_group))

    old_min, old_max = parse_cardinality(old)
    new_min, new_max = parse_cardinality(new)

    # Breaking if min increases (more required)
    if new_min > old_min:
        return True

    # Breaking if max decreases (less allowed)
    if old_max is None and new_max is not None:
        return True
    if old_max is not None and new_max is not None and new_max < old_max:
        return True

    return False


@router.post("/migrate", response_model=MigrationPlan)
async def generate_migration_plan(
    request: MigrationPlanRequest,
    fetcher: Annotated[TemplateFetcherService, Depends(get_fetcher)],
    parser: Annotated[ParserService, Depends(get_parser)],
) -> MigrationPlan:
    """
    Generate a migration plan between template versions.

    Creates auto-mappings based on exact path matches, semantic ID matches,
    and fuzzy idShort matching.
    """
    try:
        # Fetch source template
        source_path = f"{request.source_status}/{request.source_template}"
        if request.source_version:
            source_path = f"{source_path}/{request.source_version}"
        source_bytes = await fetcher.fetch_template_aasx(source_path)
        source_schema = parser.parse_aasx_to_ui_schema(source_bytes)

        # Fetch target template
        target_path = f"{request.target_status}/{request.target_template}"
        if request.target_version:
            target_path = f"{target_path}/{request.target_version}"
        target_bytes = await fetcher.fetch_template_aasx(target_path)
        target_schema = parser.parse_aasx_to_ui_schema(target_bytes)

        # Build indices
        source_index = _build_path_index(source_schema.get("elements", []))
        target_index = _build_path_index(target_schema.get("elements", []))

        auto_mappings: list[MigrationMappingItem] = []
        mapped_sources: set[str] = set()
        mapped_targets: set[str] = set()

        # Phase 1: Exact path matches
        for source_path, source_elem in source_index.items():
            if source_path in target_index:
                target_elem = target_index[source_path]
                # Only map compatible types
                if source_elem.get("modelType") == target_elem.get("modelType"):
                    auto_mappings.append(
                        MigrationMappingItem(
                            source_path=source_path,
                            target_path=source_path,
                            confidence=1.0,
                            match_reason="exact",
                        )
                    )
                    mapped_sources.add(source_path)
                    mapped_targets.add(source_path)

        # Phase 2: Semantic ID matches
        if request.use_semantics:
            # Build semantic ID index for targets
            target_by_semantic: dict[str, list[tuple[str, dict]]] = {}
            for path, elem in target_index.items():
                if path in mapped_targets:
                    continue
                semantic_id = elem.get("semanticId")
                if semantic_id:
                    if semantic_id not in target_by_semantic:
                        target_by_semantic[semantic_id] = []
                    target_by_semantic[semantic_id].append((path, elem))

            for source_path, source_elem in source_index.items():
                if source_path in mapped_sources:
                    continue
                semantic_id = source_elem.get("semanticId")
                if semantic_id and semantic_id in target_by_semantic:
                    for target_path, target_elem in target_by_semantic[semantic_id]:
                        if target_path in mapped_targets:
                            continue
                        if source_elem.get("modelType") == target_elem.get("modelType"):
                            auto_mappings.append(
                                MigrationMappingItem(
                                    source_path=source_path,
                                    target_path=target_path,
                                    confidence=0.9,
                                    match_reason="semantic",
                                )
                            )
                            mapped_sources.add(source_path)
                            mapped_targets.add(target_path)
                            break

        # Phase 3: Fuzzy matching for remaining
        for source_path, source_elem in source_index.items():
            if source_path in mapped_sources:
                continue

            best_match: tuple[str, float] | None = None
            for target_path, target_elem in target_index.items():
                if target_path in mapped_targets:
                    continue

                similarity = _compute_similarity(source_elem, target_elem)
                if similarity >= request.min_confidence:
                    if best_match is None or similarity > best_match[1]:
                        best_match = (target_path, similarity)

            if best_match:
                auto_mappings.append(
                    MigrationMappingItem(
                        source_path=source_path,
                        target_path=best_match[0],
                        confidence=best_match[1],
                        match_reason="fuzzy",
                    )
                )
                mapped_sources.add(source_path)
                mapped_targets.add(best_match[0])

        # Find unmapped elements
        unmapped_source = [p for p in source_index.keys() if p not in mapped_sources]
        unmapped_target = [p for p in target_index.keys() if p not in mapped_targets]

        # Calculate coverage
        total_source = len(source_index)
        mapping_coverage = len(mapped_sources) / total_source if total_source > 0 else 0.0

        # Warnings
        warnings: list[str] = []
        if unmapped_source:
            warnings.append(f"{len(unmapped_source)} source element(s) could not be mapped")
        if unmapped_target:
            warnings.append(f"{len(unmapped_target)} target element(s) have no mapping")

        return MigrationPlan(
            source_template=request.source_template,
            source_version=request.source_version,
            target_template=request.target_template,
            target_version=request.target_version,
            auto_mappings=auto_mappings,
            unmapped_source=sorted(unmapped_source),
            unmapped_target=sorted(unmapped_target),
            mapping_coverage=mapping_coverage,
            warnings=warnings,
        )

    except APIError:
        raise
    except Exception as e:
        logger.exception("Failed to generate migration plan")
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to generate migration plan",
            detail={"error": str(e)},
        )


@router.post("/validate", response_model=ValidationDiagnostics)
async def validate_template(
    request: TemplateValidateRequest,
    fetcher: Annotated[TemplateFetcherService, Depends(get_fetcher)],
    parser: Annotated[ParserService, Depends(get_parser)],
) -> ValidationDiagnostics:
    """
    Run comprehensive validation diagnostics on a template.

    Checks semantic IDs, cardinality constraints, value types,
    and conformance to AAS spec.
    """
    try:
        # Fetch template
        template_path = f"{request.template_status}/{request.template_name}"
        if request.template_version:
            template_path = f"{template_path}/{request.template_version}"
        template_bytes = await fetcher.fetch_template_aasx(template_path)
        schema = parser.parse_aasx_to_ui_schema(template_bytes)

        errors: list[ValidationDiagnostic] = []
        warnings: list[ValidationDiagnostic] = []
        info: list[ValidationDiagnostic] = []

        elements = schema.get("elements", [])
        element_count = _count_elements(elements)

        # Track semantic coverage
        total_elements = 0
        elements_with_semantic = 0

        def validate_elements(elems: list[dict], prefix: str = "") -> None:
            nonlocal total_elements, elements_with_semantic

            for elem in elems:
                id_short = elem.get("idShort", "unknown")
                path = f"{prefix}.{id_short}" if prefix else id_short
                total_elements += 1

                # Check semantic ID
                if request.check_semantic_ids:
                    semantic_id = elem.get("semanticId")
                    if semantic_id:
                        elements_with_semantic += 1
                        # Validate semantic ID format
                        if not _is_valid_semantic_id(semantic_id):
                            warnings.append(
                                ValidationDiagnostic(
                                    path=path,
                                    severity="warning",
                                    code="INVALID_SEMANTIC_ID",
                                    message=f"Semantic ID may not be a valid IRI or IRDI: {semantic_id}",
                                    suggestion="Use a valid IRI (https://...) or IRDI format",
                                )
                            )
                    else:
                        info.append(
                            ValidationDiagnostic(
                                path=path,
                                severity="info",
                                code="MISSING_SEMANTIC_ID",
                                message="Element has no semantic ID",
                                suggestion="Consider adding a semantic ID from ECLASS or IEC CDD",
                            )
                        )

                # Check cardinality
                if request.check_cardinality:
                    cardinality = elem.get("cardinality")
                    if cardinality:
                        if not _is_valid_cardinality(cardinality):
                            errors.append(
                                ValidationDiagnostic(
                                    path=path,
                                    severity="error",
                                    code="INVALID_CARDINALITY",
                                    message=f"Invalid cardinality format: {cardinality}",
                                    suggestion="Use format like [0..1], [1], [0..*], [1..*]",
                                )
                            )

                # Check value types
                if request.check_value_types:
                    model_type = elem.get("modelType")
                    if model_type == "Property":
                        value_type = elem.get("valueType")
                        if not value_type:
                            warnings.append(
                                ValidationDiagnostic(
                                    path=path,
                                    severity="warning",
                                    code="MISSING_VALUE_TYPE",
                                    message="Property has no valueType specified",
                                    suggestion="Specify a valueType like xs:string, xs:integer, etc.",
                                )
                            )
                        elif not _is_valid_value_type(value_type):
                            errors.append(
                                ValidationDiagnostic(
                                    path=path,
                                    severity="error",
                                    code="INVALID_VALUE_TYPE",
                                    message=f"Unrecognized valueType: {value_type}",
                                    suggestion="Use an XSD type like xs:string, xs:integer, xs:decimal, xs:boolean, xs:date",
                                )
                            )

                # Recurse into nested elements
                if "elements" in elem and elem["elements"]:
                    validate_elements(elem["elements"], path)

                if "itemTemplate" in elem and elem["itemTemplate"]:
                    item_template = elem["itemTemplate"]
                    item_path = f"{path}[]"
                    if "elements" in item_template:
                        validate_elements(item_template["elements"], item_path)

        validate_elements(elements)

        # Calculate semantic coverage
        semantic_coverage = (
            elements_with_semantic / total_elements if total_elements > 0 else 0.0
        )

        # Conformance level
        conformance_level = None
        if request.check_conformance:
            if len(errors) == 0 and semantic_coverage >= 0.8:
                conformance_level = "AAS-compliant"
            elif len(errors) == 0:
                conformance_level = "AAS-valid"
            else:
                conformance_level = "non-conformant"

        return ValidationDiagnostics(
            template_name=request.template_name,
            template_version=request.template_version,
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            info=info,
            element_count=element_count,
            semantic_coverage=semantic_coverage,
            conformance_level=conformance_level,
        )

    except APIError:
        raise
    except Exception as e:
        logger.exception("Failed to validate template")
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to validate template",
            detail={"error": str(e)},
        )


def _is_valid_semantic_id(semantic_id: str) -> bool:
    """Check if semantic ID appears to be a valid IRI or IRDI."""
    import re

    if not semantic_id:
        return False

    # IRI pattern (simplified)
    if semantic_id.startswith(("http://", "https://", "urn:")):
        return True

    # IRDI pattern: ####-##-AA####[-#]#####
    irdi_pattern = re.compile(r"^\d{4}-\d+-[A-Z]{2}\d+(-\d+)?\d*#\d+-\d+#\d+(-\d+)?$")
    if irdi_pattern.match(semantic_id):
        return True

    # ECLASS IRDI pattern
    eclass_pattern = re.compile(r"^0173-1#\d{2}-[A-Z]{3}\d{3}#\d{3}$")
    if eclass_pattern.match(semantic_id):
        return True

    return False


def _is_valid_cardinality(cardinality: str) -> bool:
    """Check if cardinality has valid format."""
    import re

    # Named cardinalities
    if cardinality in ("ZeroToOne", "ZeroToMany", "OneToMany", "One", "Zero"):
        return True

    # Bracket notation
    pattern = re.compile(r"^\[(\d+)(\.\.(\d+|\*))?\]$")
    return bool(pattern.match(cardinality))


def _is_valid_value_type(value_type: str) -> bool:
    """Check if value type is a recognized XSD type."""
    valid_types = {
        "xs:string", "xs:integer", "xs:int", "xs:long", "xs:short", "xs:byte",
        "xs:unsignedInt", "xs:unsignedLong", "xs:unsignedShort", "xs:unsignedByte",
        "xs:decimal", "xs:double", "xs:float",
        "xs:boolean",
        "xs:date", "xs:dateTime", "xs:time", "xs:duration",
        "xs:anyURI", "xs:base64Binary", "xs:hexBinary",
        "xs:nonNegativeInteger", "xs:positiveInteger", "xs:negativeInteger",
        # Without namespace prefix
        "string", "integer", "int", "long", "short", "byte",
        "decimal", "double", "float", "boolean",
        "date", "dateTime", "time", "duration", "anyURI",
    }

    # Normalize
    normalized = value_type.lower().replace("xsd:", "xs:")
    return normalized in valid_types or value_type in valid_types
