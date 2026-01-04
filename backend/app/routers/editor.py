"""
Editor endpoints for parsing, editing, and hydrating submodels.

Provides the core API for the submodel editor functionality.
"""

import logging
from io import BytesIO
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Query
from fastapi.responses import Response
from basyx.aas import model
from basyx.aas.adapter import aasx

from app.config import get_settings
from app.dependencies import get_fetcher, get_hydrator, get_parser
from app.schemas.concept_description import ConceptDescriptionResponse
from app.schemas.form_data import SubmodelFormData, UploadResponse, ValidationResult
from app.schemas.ui_schema import SubmodelUISchema
from app.services.fetcher import TemplateFetcherService
from app.services.hydrator import HydratorService
from app.services.parser import ParserService
from app.utils.aasx_reader import SafeAASXReader
from app.utils.semantic_resolver import (
    concept_description_to_dict,
    resolve_concept_description_by_semantic_id,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/editor", tags=["editor"])


@router.get("/templates/{template_name}/schema", response_model=SubmodelUISchema)
async def get_template_schema(
    template_name: str,
    fetcher: Annotated[TemplateFetcherService, Depends(get_fetcher)],
    parser: Annotated[ParserService, Depends(get_parser)],
) -> SubmodelUISchema:
    """
    Get the UI schema for a template.

    Fetches the template AASX and parses it into a form-renderable schema.
    """
    try:
        aasx_bytes = await fetcher.fetch_template_aasx(f"published/{template_name}")
        schema = parser.parse_aasx_to_ui_schema(aasx_bytes)
        return SubmodelUISchema(**schema)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to get schema for {template_name}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/templates/{template_name}/concept-description",
    response_model=ConceptDescriptionResponse,
)
async def get_concept_description(
    template_name: str,
    semantic_id: Annotated[
        str, Query(description="Semantic ID to resolve against ConceptDescriptions")
    ],
    fetcher: Annotated[TemplateFetcherService, Depends(get_fetcher)],
) -> ConceptDescriptionResponse:
    """
    Resolve a ConceptDescription by semantic ID within a template AASX.
    """
    try:
        aasx_bytes = await fetcher.fetch_template_aasx(f"published/{template_name}")
        object_store: model.DictObjectStore[model.Identifiable] = model.DictObjectStore()
        file_store = aasx.DictSupplementaryFileContainer()

        with SafeAASXReader(BytesIO(aasx_bytes)) as reader:
            reader.read_into(object_store, file_store)

        concept_description = resolve_concept_description_by_semantic_id(
            semantic_id, object_store
        )
        if concept_description is None:
            raise HTTPException(
                status_code=404,
                detail="ConceptDescription not found for semanticId",
            )

        payload = concept_description_to_dict(concept_description)
        return ConceptDescriptionResponse(**payload)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(
            "Failed to resolve ConceptDescription for %s (%s)",
            template_name,
            semantic_id,
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hydrate/{template_name}")
async def hydrate_template(
    template_name: str,
    form_data: SubmodelFormData,
    fetcher: Annotated[TemplateFetcherService, Depends(get_fetcher)],
    hydrator: Annotated[HydratorService, Depends(get_hydrator)],
) -> Response:
    """
    Hydrate a template with form data and return the AASX file.

    Merges user-provided form values into the template while preserving
    all metadata (Qualifiers, EmbeddedDataSpecifications).
    """
    try:
        template_bytes = await fetcher.fetch_template_aasx(f"published/{template_name}")
        hydrated_aasx = hydrator.hydrate_submodel(template_bytes, form_data.model_dump())

        return Response(
            content=hydrated_aasx,
            media_type="application/asset-administration-shell-package+xml",
            headers={
                "Content-Disposition": f'attachment; filename="{template_name}_filled.aasx"'
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to hydrate {template_name}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hydrate/{template_name}/json")
async def hydrate_template_json(
    template_name: str,
    form_data: SubmodelFormData,
    fetcher: Annotated[TemplateFetcherService, Depends(get_fetcher)],
    hydrator: Annotated[HydratorService, Depends(get_hydrator)],
) -> Response:
    """
    Hydrate a template with form data and return as JSON.
    """
    try:
        template_bytes = await fetcher.fetch_template_aasx(f"published/{template_name}")
        json_output = hydrator.hydrate_to_json(template_bytes, form_data.model_dump())

        return Response(
            content=json_output,
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="{template_name}_filled.json"'
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to hydrate {template_name} to JSON")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload", response_model=UploadResponse)
async def upload_aasx(
    file: Annotated[UploadFile, File(...)],
    parser: Annotated[ParserService, Depends(get_parser)],
) -> UploadResponse:
    """
    Upload an AASX file and parse it into a UI schema.

    Allows users to edit existing AASX files rather than starting
    from a template.
    """
    settings = get_settings()

    # Validate file type
    if not file.filename or not file.filename.endswith(".aasx"):
        return UploadResponse(
            success=False,
            error="Only AASX files are accepted",
            filename=file.filename,
        )

    try:
        # Read file with size limit
        contents = await file.read()
        max_size = settings.max_upload_size_mb * 1024 * 1024

        if len(contents) > max_size:
            return UploadResponse(
                success=False,
                error=f"File too large. Maximum size is {settings.max_upload_size_mb}MB",
                filename=file.filename,
            )

        # Parse the AASX
        schema = parser.parse_aasx_to_ui_schema(contents)

        return UploadResponse(
            success=True,
            schema_=schema,
            filename=file.filename,
        )
    except ValueError as e:
        return UploadResponse(
            success=False,
            error=str(e),
            filename=file.filename,
        )
    except Exception as e:
        logger.exception("Failed to parse uploaded AASX")
        return UploadResponse(
            success=False,
            error="Failed to parse AASX file",
            filename=file.filename,
        )


@router.post("/validate/{template_name}", response_model=ValidationResult)
async def validate_form_data(
    template_name: str,
    form_data: SubmodelFormData,
    fetcher: Annotated[TemplateFetcherService, Depends(get_fetcher)],
    parser: Annotated[ParserService, Depends(get_parser)],
) -> ValidationResult:
    """
    Validate form data against the template schema.

    Checks cardinality constraints and value types.
    """
    try:
        aasx_bytes = await fetcher.fetch_template_aasx(f"published/{template_name}")
        schema = parser.parse_aasx_to_ui_schema(aasx_bytes)

        errors = []
        warnings = []

        # Validate elements
        _validate_elements(
            schema.get("elements", []),
            form_data.model_dump().get("elements", {}),
            errors,
            warnings,
            "",
        )

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
    except Exception as e:
        logger.exception(f"Failed to validate form data for {template_name}")
        raise HTTPException(status_code=500, detail=str(e))


def _validate_elements(
    schema_elements: list[dict[str, Any]],
    form_elements: dict[str, Any],
    errors: list,
    warnings: list,
    path: str,
) -> None:
    """Recursively validate form elements against schema."""
    from app.schemas.form_data import ValidationError

    for schema_elem in schema_elements:
        id_short = schema_elem["idShort"]
        elem_path = f"{path}.{id_short}" if path else id_short
        cardinality = schema_elem.get("cardinality", "[1]")
        min_items, max_items = _parse_cardinality(cardinality)

        # Check required elements
        if min_items >= 1:
            if id_short not in form_elements:
                errors.append(
                    ValidationError(
                        field=elem_path,
                        message=f"Required field '{id_short}' is missing",
                        code="required",
                    )
                )
                continue

        if id_short not in form_elements:
            continue

        form_elem = form_elements[id_short]
        model_type = schema_elem.get("modelType")

        # Validate nested elements
        if model_type == "SubmodelElementCollection":
            nested_schema = schema_elem.get("elements", [])
            nested_form = form_elem.get("elements", {}) if form_elem else {}
            _validate_elements(nested_schema, nested_form, errors, warnings, elem_path)

        elif model_type == "SubmodelElementList":
            items = form_elem.get("items", []) if form_elem else []

            # Check minimum items for [1..*]
            if min_items >= 1 and len(items) == 0:
                errors.append(
                    ValidationError(
                        field=elem_path,
                        message="At least one item is required",
                        code="min_items",
                    )
                )
            if max_items is not None and len(items) > max_items:
                errors.append(
                    ValidationError(
                        field=elem_path,
                        message=f"At most {max_items} item(s) are allowed",
                        code="max_items",
                    )
                )

            # Validate each item
            item_template = schema_elem.get("itemTemplate")
            if item_template:
                for idx, item in enumerate(items):
                    item_path = f"{elem_path}[{idx}]"
                    if item_template.get("modelType") == "SubmodelElementCollection":
                        _validate_elements(
                            item_template.get("elements", []),
                            item.get("elements", {}),
                            errors,
                            warnings,
                            item_path,
                        )

        elif model_type == "Property":
            value = form_elem.get("value") if form_elem else None
            if min_items >= 1 and (value is None or value == ""):
                errors.append(
                    ValidationError(
                        field=elem_path,
                        message="Value is required",
                        code="required_value",
                    )
                )
            elif value not in (None, ""):
                value_type = schema_elem.get("valueType")
                if not _value_matches_type(value, value_type):
                    errors.append(
                        ValidationError(
                            field=elem_path,
                            message=f"Value does not match expected type {value_type}",
                            code="type_mismatch",
                        )
                    )

        elif model_type == "MultiLanguageProperty":
            value = form_elem.get("value", {}) if form_elem else {}
            if min_items >= 1 and not any(value.values()):
                errors.append(
                    ValidationError(
                        field=elem_path,
                        message="At least one language translation is required",
                        code="required_translation",
                    )
                )
            elif not any(value.values()):
                warnings.append(
                    ValidationError(
                        field=elem_path,
                        message="At least one language translation is recommended",
                        code="recommended_value",
                    )
                )

        elif model_type == "Range":
            min_val = form_elem.get("min") if form_elem else None
            max_val = form_elem.get("max") if form_elem else None
            value_type = schema_elem.get("valueType")
            if min_items >= 1 and (min_val in (None, "") or max_val in (None, "")):
                errors.append(
                    ValidationError(
                        field=elem_path,
                        message="Both min and max are required",
                        code="required_value",
                    )
                )
            else:
                if min_val not in (None, "") and not _value_matches_type(
                    min_val, value_type
                ):
                    errors.append(
                        ValidationError(
                            field=f"{elem_path}.min",
                            message=f"Min does not match expected type {value_type}",
                            code="type_mismatch",
                        )
                    )
                if max_val not in (None, "") and not _value_matches_type(
                    max_val, value_type
                ):
                    errors.append(
                        ValidationError(
                            field=f"{elem_path}.max",
                            message=f"Max does not match expected type {value_type}",
                            code="type_mismatch",
                        )
                    )

        elif model_type == "File":
            value = form_elem.get("value") if form_elem else None
            if min_items >= 1 and (value is None or value == ""):
                errors.append(
                    ValidationError(
                        field=elem_path,
                        message="File path or URL is required",
                        code="required_value",
                    )
                )

        elif model_type == "ReferenceElement":
            value = form_elem.get("value") if form_elem else None
            if min_items >= 1 and (value is None or value == ""):
                errors.append(
                    ValidationError(
                        field=elem_path,
                        message="Reference is required",
                        code="required_value",
                    )
                )
            elif value and not _is_valid_reference(value):
                errors.append(
                    ValidationError(
                        field=elem_path,
                        message="Reference must be a valid IRI or IRDI",
                        code="invalid_reference",
                    )
                )

        elif model_type in ("RelationshipElement", "AnnotatedRelationshipElement"):
            first = form_elem.get("first") if form_elem else None
            second = form_elem.get("second") if form_elem else None
            if min_items >= 1 and (not first or not second):
                errors.append(
                    ValidationError(
                        field=elem_path,
                        message="Both relationship references are required",
                        code="required_value",
                    )
                )


def _normalize_cardinality_value(value: str | None) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None
    mapping = {
        "ZeroToOne": "[0..1]",
        "ZeroToMany": "[0..*]",
        "OneToMany": "[1..*]",
        "One": "[1]",
        "Zero": "[0]",
    }
    if value in mapping:
        return mapping[value]
    if value.startswith("[") and value.endswith("]"):
        return value
    if ".." in value:
        return f"[{value}]"
    if value.isdigit():
        return f"[{value}]"
    return value


def _parse_cardinality(cardinality: str) -> tuple[int, int | None]:
    import re

    normalized = _normalize_cardinality_value(cardinality) or "[1]"
    match = re.match(r"^\\[(\\d+)(?:\\.\\.(\\d+|\\*))?\\]$", normalized)
    if not match:
        return (1, 1)

    min_items = int(match.group(1))
    max_group = match.group(2)
    if max_group is None:
        return (min_items, min_items)
    if max_group == "*":
        return (min_items, None)
    return (min_items, int(max_group))


def _value_matches_type(value: Any, value_type: str | None) -> bool:
    if value_type is None:
        return True

    type_str = str(value_type).lower()
    try:
        if "int" in type_str or "integer" in type_str:
            num = float(value)
            return num.is_integer()
        if any(t in type_str for t in ("float", "double", "decimal")):
            float(value)
            return True
        if "bool" in type_str:
            if isinstance(value, bool):
                return True
            return str(value).lower() in ("true", "false", "1", "0", "yes", "no")
        if "datetime" in type_str or "date" in type_str:
            from datetime import datetime, date

            if "datetime" in type_str:
                datetime.fromisoformat(str(value))
            else:
                date.fromisoformat(str(value))
            return True
    except Exception:
        return False

    return True


def _is_valid_reference(value: str) -> bool:
    import re

    if not value:
        return True
    iri_pattern = re.compile(r"^https?://.+", re.IGNORECASE)
    irdi_pattern = re.compile(r"^\\d{4}-\\d#\\d{2}-[A-Z]{3}\\d{3}#\\d{3}$")
    return bool(iri_pattern.match(value) or irdi_pattern.match(value))
