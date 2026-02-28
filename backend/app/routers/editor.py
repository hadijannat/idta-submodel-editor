"""
Editor endpoints for parsing, editing, and hydrating submodels.

Provides the core API for the submodel editor functionality.
"""

import logging
from io import BytesIO
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, UploadFile, Query
from fastapi.responses import Response
from basyx.aas import model
from basyx.aas.adapter import aasx

from app.config import get_settings
from app.dependencies import get_fetcher, get_hydrator, get_parser
from app.errors import APIError, ErrorCode
from app.schemas.concept_description import ConceptDescriptionResponse
from app.schemas.form_data import (
    LocalTemplateInfo,
    LocalTemplateUploadResponse,
    SubmodelFormData,
    UploadResponse,
    ValidationResult,
)
from app.schemas.ui_schema import SubmodelUISchema
from app.services.fetcher import TemplateFetcherService
from app.services.hydrator import HydratorService
from app.services.parser import ParserService
from app.services.pcf.activity_list import ensure_activity_list_schema
from app.services.pcf.validator import is_pcf_template
from app.services.validation import validate_form_data as run_validation
from app.utils.aasx_reader import SafeAASXReader
from app.utils.semantic_resolver import (
    concept_description_to_dict,
    resolve_concept_description_by_semantic_id,
)
from app.utils.upload_security import FileType, UploadValidator, read_upload_file

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/editor", tags=["editor"])


@router.get("/templates/{template_name}/schema", response_model=SubmodelUISchema)
async def get_template_schema(
    template_name: str,
    fetcher: Annotated[TemplateFetcherService, Depends(get_fetcher)],
    parser: Annotated[ParserService, Depends(get_parser)],
    status: Annotated[
        Literal["published", "deprecated"],
        Query(description="Template status filter"),
    ] = "published",
    version: Annotated[str | None, Query(description="Template version")] = None,
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
        if is_pcf_template(schema):
            schema = ensure_activity_list_schema(schema)
        schema["templateName"] = template_name
        schema["templatePath"] = template_path
        return SubmodelUISchema(**schema)
    except ValueError as e:
        raise APIError(
            code=ErrorCode.BAD_REQUEST,
            message=str(e),
            detail={"template_name": template_name},
        )
    except APIError:
        raise
    except Exception as e:
        logger.exception(f"Failed to get schema for {template_name}")
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to get template schema",
            detail={"template_name": template_name, "error": str(e)},
        )


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
    status: Annotated[
        Literal["published", "deprecated"],
        Query(description="Template status filter"),
    ] = "published",
    version: Annotated[str | None, Query(description="Template version")] = None,
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
            raise APIError(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message="ConceptDescription not found for semanticId",
                detail={"semantic_id": semantic_id, "template_name": template_name},
            )

        payload = concept_description_to_dict(concept_description)
        return ConceptDescriptionResponse(**payload)
    except APIError:
        raise
    except ValueError as e:
        raise APIError(
            code=ErrorCode.BAD_REQUEST,
            message=str(e),
            detail={"template_name": template_name, "semantic_id": semantic_id},
        )
    except Exception as e:
        logger.exception(
            "Failed to resolve ConceptDescription for %s (%s)",
            template_name,
            semantic_id,
        )
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to resolve ConceptDescription",
            detail={"template_name": template_name, "semantic_id": semantic_id, "error": str(e)},
        )


@router.post("/hydrate/{template_name}")
async def hydrate_template(
    template_name: str,
    form_data: SubmodelFormData,
    fetcher: Annotated[TemplateFetcherService, Depends(get_fetcher)],
    hydrator: Annotated[HydratorService, Depends(get_hydrator)],
    parser: Annotated[ParserService, Depends(get_parser)],
    status: Annotated[
        Literal["published", "deprecated"],
        Query(description="Template status filter"),
    ] = "published",
    version: Annotated[str | None, Query(description="Template version")] = None,
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
        if is_pcf_template(schema):
            schema = ensure_activity_list_schema(schema)
        errors, warnings = run_validation(schema, form_data.model_dump())
        if errors:
            raise APIError(
                code=ErrorCode.VALIDATION_FAILED,
                message="Validation failed",
                detail={
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
    except APIError:
        raise
    except ValueError as e:
        raise APIError(
            code=ErrorCode.BAD_REQUEST,
            message=str(e),
            detail={"template_name": template_name},
        )
    except Exception as e:
        logger.exception(f"Failed to hydrate {template_name}")
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to hydrate template",
            detail={"template_name": template_name, "error": str(e)},
        )


@router.post("/hydrate/{template_name}/json")
async def hydrate_template_json(
    template_name: str,
    form_data: SubmodelFormData,
    fetcher: Annotated[TemplateFetcherService, Depends(get_fetcher)],
    hydrator: Annotated[HydratorService, Depends(get_hydrator)],
    parser: Annotated[ParserService, Depends(get_parser)],
    status: Annotated[
        Literal["published", "deprecated"],
        Query(description="Template status filter"),
    ] = "published",
    version: Annotated[str | None, Query(description="Template version")] = None,
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
        if is_pcf_template(schema):
            schema = ensure_activity_list_schema(schema)
        errors, warnings = run_validation(schema, form_data.model_dump())
        if errors:
            raise APIError(
                code=ErrorCode.VALIDATION_FAILED,
                message="Validation failed",
                detail={
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
    except APIError:
        raise
    except ValueError as e:
        raise APIError(
            code=ErrorCode.BAD_REQUEST,
            message=str(e),
            detail={"template_name": template_name},
        )
    except Exception as e:
        logger.exception(f"Failed to hydrate {template_name} to JSON")
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to hydrate template to JSON",
            detail={"template_name": template_name, "error": str(e)},
        )


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

    # Read file content with size limit
    try:
        contents = await read_upload_file(
            file,
            max_size_bytes=settings.max_upload_size_mb * 1024 * 1024,
        )
    except APIError as exc:
        return UploadResponse(
            success=False,
            error=exc.message,
            filename=file.filename,
        )

    # Validate with magic bytes checking
    validator = UploadValidator(
        allowed_types=[FileType.AASX],
        max_size_bytes=settings.max_upload_size_mb * 1024 * 1024,
    )
    result = validator.validate(contents, file.filename)
    if not result.valid:
        return UploadResponse(
            success=False,
            error=result.error_message,
            filename=file.filename,
        )

    try:
        # Parse the AASX
        schema = parser.parse_aasx_to_ui_schema(contents)
        if is_pcf_template(schema):
            schema = ensure_activity_list_schema(schema)

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
    except Exception:
        logger.exception("Failed to parse uploaded AASX")
        return UploadResponse(
            success=False,
            error="Failed to parse AASX file",
            filename=file.filename,
        )


@router.post("/validate/{template_name}", response_model=ValidationResult)
async def validate_template_form_data(
    template_name: str,
    form_data: SubmodelFormData,
    fetcher: Annotated[TemplateFetcherService, Depends(get_fetcher)],
    parser: Annotated[ParserService, Depends(get_parser)],
    status: Annotated[
        Literal["published", "deprecated"],
        Query(description="Template status filter"),
    ] = "published",
    version: Annotated[str | None, Query(description="Template version")] = None,
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
        if is_pcf_template(schema):
            schema = ensure_activity_list_schema(schema)

        errors, warnings = run_validation(schema, form_data.model_dump())

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
    except APIError:
        raise
    except Exception as e:
        logger.exception(f"Failed to validate form data for {template_name}")
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to validate form data",
            detail={"template_name": template_name, "error": str(e)},
        )


# -----------------------------------------------------------------------------
# Local Template Management
# -----------------------------------------------------------------------------


@router.get("/templates/local", response_model=list[LocalTemplateInfo])
async def list_local_templates(
    fetcher: Annotated[TemplateFetcherService, Depends(get_fetcher)],
) -> list[LocalTemplateInfo]:
    """
    List all local templates.

    Returns templates stored in the local templates directory.
    """
    local_templates = fetcher._list_local_templates()
    return [LocalTemplateInfo(**t) for t in local_templates]


@router.post("/templates/local", response_model=LocalTemplateUploadResponse)
async def upload_local_template(
    file: Annotated[UploadFile, File(...)],
    fetcher: Annotated[TemplateFetcherService, Depends(get_fetcher)],
    parser: Annotated[ParserService, Depends(get_parser)],
    name: Annotated[str | None, Query(description="Custom template name")] = None,
) -> LocalTemplateUploadResponse:
    """
    Upload an AASX file as a local template.

    The template will be stored locally and available for use alongside
    GitHub templates. If no name is provided, the filename will be used.
    """
    settings = get_settings()

    # Read file content with size limit
    try:
        contents = await read_upload_file(
            file,
            max_size_bytes=settings.max_upload_size_mb * 1024 * 1024,
        )
    except APIError as exc:
        return LocalTemplateUploadResponse(
            success=False,
            error=exc.message,
        )

    # Validate with magic bytes checking
    validator = UploadValidator(
        allowed_types=[FileType.AASX],
        max_size_bytes=settings.max_upload_size_mb * 1024 * 1024,
    )
    result = validator.validate(contents, file.filename)
    if not result.valid:
        return LocalTemplateUploadResponse(
            success=False,
            error=result.error_message,
        )

    try:
        # Validate that it's a parseable AASX
        try:
            parser.parse_aasx_to_ui_schema(contents)
        except Exception as parse_error:
            return LocalTemplateUploadResponse(
                success=False,
                error=f"Invalid AASX file: {parse_error}",
            )

        # Determine template name
        template_name = name or file.filename.rsplit(".", 1)[0]

        # Save as local template
        template_info = fetcher.save_local_template(template_name, contents)

        return LocalTemplateUploadResponse(
            success=True,
            template=LocalTemplateInfo(**template_info),
        )

    except ValueError as e:
        return LocalTemplateUploadResponse(
            success=False,
            error=str(e),
        )
    except Exception:
        logger.exception("Failed to upload local template")
        return LocalTemplateUploadResponse(
            success=False,
            error="Failed to save template",
        )


@router.delete("/templates/local/{template_name}")
async def delete_local_template(
    template_name: str,
    fetcher: Annotated[TemplateFetcherService, Depends(get_fetcher)],
) -> dict:
    """
    Delete a local template.

    Removes the template from the local templates directory.
    """
    try:
        deleted = fetcher.delete_local_template(template_name)
        if deleted:
            return {"success": True, "message": f"Template '{template_name}' deleted"}
        else:
            raise APIError(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message="Template not found",
                detail={"template_name": template_name},
            )
    except APIError:
        raise
    except ValueError as e:
        raise APIError(
            code=ErrorCode.BAD_REQUEST,
            message=str(e),
            detail={"template_name": template_name},
        )
    except Exception as e:
        logger.exception(f"Failed to delete local template: {template_name}")
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to delete local template",
            detail={"template_name": template_name, "error": str(e)},
        )
