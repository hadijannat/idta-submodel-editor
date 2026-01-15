"""
Editor endpoints for parsing, editing, and hydrating submodels.

Provides the core API for the submodel editor functionality.
"""

import logging
from io import BytesIO
from typing import Annotated, Literal

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
from app.services.validation import validate_form_data
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
    status: Annotated[
        Literal["published", "deprecated"],
        Query(description="Template status filter"),
    ] = "published",
    version: Annotated[str | None, Query(description="Template version")] = None,
    fetcher: Annotated[TemplateFetcherService, Depends(get_fetcher)],
    parser: Annotated[ParserService, Depends(get_parser)],
) -> SubmodelUISchema:
    """
    Get the UI schema for a template.

    Fetches the template AASX and parses it into a form-renderable schema.
    """
    try:
        template_path = f"{status}/{template_name}"
        if version:
            template_path = f"{template_path}/{version}"
        aasx_bytes = await fetcher.fetch_template_aasx(template_path)
        schema = parser.parse_aasx_to_ui_schema(aasx_bytes)
        schema["templateName"] = template_name
        schema["templatePath"] = template_path
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
    status: Annotated[
        Literal["published", "deprecated"],
        Query(description="Template status filter"),
    ] = "published",
    version: Annotated[str | None, Query(description="Template version")] = None,
    fetcher: Annotated[TemplateFetcherService, Depends(get_fetcher)],
) -> ConceptDescriptionResponse:
    """
    Resolve a ConceptDescription by semantic ID within a template AASX.
    """
    try:
        template_path = f"{status}/{template_name}"
        if version:
            template_path = f"{template_path}/{version}"
        aasx_bytes = await fetcher.fetch_template_aasx(template_path)
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
    status: Annotated[
        Literal["published", "deprecated"],
        Query(description="Template status filter"),
    ] = "published",
    version: Annotated[str | None, Query(description="Template version")] = None,
    fetcher: Annotated[TemplateFetcherService, Depends(get_fetcher)],
    hydrator: Annotated[HydratorService, Depends(get_hydrator)],
    parser: Annotated[ParserService, Depends(get_parser)],
) -> Response:
    """
    Hydrate a template with form data and return the AASX file.

    Merges user-provided form values into the template while preserving
    all metadata (Qualifiers, EmbeddedDataSpecifications).
    """
    try:
        template_path = f"{status}/{template_name}"
        if version:
            template_path = f"{template_path}/{version}"
        template_bytes = await fetcher.fetch_template_aasx(template_path)
        schema = parser.parse_aasx_to_ui_schema(template_bytes)
        errors, warnings = validate_form_data(schema, form_data.model_dump())
        if errors:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Validation failed",
                    "errors": [e.model_dump() for e in errors],
                    "warnings": [w.model_dump() for w in warnings],
                },
            )
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
    status: Annotated[
        Literal["published", "deprecated"],
        Query(description="Template status filter"),
    ] = "published",
    version: Annotated[str | None, Query(description="Template version")] = None,
    fetcher: Annotated[TemplateFetcherService, Depends(get_fetcher)],
    hydrator: Annotated[HydratorService, Depends(get_hydrator)],
    parser: Annotated[ParserService, Depends(get_parser)],
) -> Response:
    """
    Hydrate a template with form data and return as JSON.
    """
    try:
        template_path = f"{status}/{template_name}"
        if version:
            template_path = f"{template_path}/{version}"
        template_bytes = await fetcher.fetch_template_aasx(template_path)
        schema = parser.parse_aasx_to_ui_schema(template_bytes)
        errors, warnings = validate_form_data(schema, form_data.model_dump())
        if errors:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Validation failed",
                    "errors": [e.model_dump() for e in errors],
                    "warnings": [w.model_dump() for w in warnings],
                },
            )
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
    status: Annotated[
        Literal["published", "deprecated"],
        Query(description="Template status filter"),
    ] = "published",
    version: Annotated[str | None, Query(description="Template version")] = None,
    fetcher: Annotated[TemplateFetcherService, Depends(get_fetcher)],
    parser: Annotated[ParserService, Depends(get_parser)],
) -> ValidationResult:
    """
    Validate form data against the template schema.

    Checks cardinality constraints and value types.
    """
    try:
        template_path = f"{status}/{template_name}"
        if version:
            template_path = f"{template_path}/{version}"
        aasx_bytes = await fetcher.fetch_template_aasx(template_path)
        schema = parser.parse_aasx_to_ui_schema(aasx_bytes)

        errors, warnings = validate_form_data(schema, form_data.model_dump())

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
    except Exception as e:
        logger.exception(f"Failed to validate form data for {template_name}")
        raise HTTPException(status_code=500, detail=str(e))
