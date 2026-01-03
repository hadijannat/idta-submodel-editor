"""
Editor endpoints for parsing, editing, and hydrating submodels.

Provides the core API for the submodel editor functionality.
"""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response

from app.config import get_settings
from app.dependencies import get_fetcher, get_hydrator, get_parser
from app.schemas.form_data import SubmodelFormData, UploadResponse, ValidationResult
from app.schemas.ui_schema import SubmodelUISchema
from app.services.fetcher import TemplateFetcherService
from app.services.hydrator import HydratorService
from app.services.parser import ParserService

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
            schema=schema,
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

        # Check required elements
        if cardinality in ("[1]", "[1..*]"):
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
            if cardinality == "[1..*]" and len(items) == 0:
                errors.append(
                    ValidationError(
                        field=elem_path,
                        message="At least one item is required",
                        code="min_items",
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
            if cardinality in ("[1]", "[1..*]") and (value is None or value == ""):
                errors.append(
                    ValidationError(
                        field=elem_path,
                        message="Value is required",
                        code="required_value",
                    )
                )

        elif model_type == "MultiLanguageProperty":
            value = form_elem.get("value", {}) if form_elem else {}
            if cardinality in ("[1]", "[1..*]") and not any(value.values()):
                warnings.append(
                    ValidationError(
                        field=elem_path,
                        message="At least one language translation is recommended",
                        code="recommended_value",
                    )
                )
