"""Smart Mapper endpoints."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response

from app.config import get_settings
from app.dependencies import get_current_user, get_mapper_service
from app.errors import APIError, ErrorCode
from app.schemas.mapper import (
    DatasetProfile,
    MapperAutoSuggestRequest,
    MapperAutoSuggestResponse,
    MapperRecipe,
    MapperRecipeList,
    MapperRunRequest,
    MapperRunResponse,
)
from app.services.mapper import MapperService
from app.utils.upload_security import FileType, UploadValidator, read_upload_file

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mapper", tags=["mapper"])


@router.post("/profile", response_model=DatasetProfile)
async def profile_dataset(
    file: Annotated[UploadFile, File(...)],
    sheet: Annotated[str | None, Form()] = None,
    header_row: Annotated[int | None, Form()] = None,
    sample_rows: Annotated[int, Form()] = 200,
    mapper: Annotated[MapperService, Depends(get_mapper_service)] = None,
) -> DatasetProfile:
    settings = get_settings()

    # Read file content for validation with size limit
    contents = await read_upload_file(
        file,
        max_size_bytes=settings.max_upload_size_mb * 1024 * 1024,
    )

    # Validate with magic bytes checking
    validator = UploadValidator(
        allowed_types=[FileType.CSV, FileType.XLSX],
        max_size_bytes=settings.max_upload_size_mb * 1024 * 1024,
    )
    validator.validate_and_raise(contents, file.filename)

    # Reset file position for service to re-read if needed
    await file.seek(0)

    try:
        return await mapper.profile(file, sheet, header_row, sample_rows)
    except APIError:
        raise
    except Exception as exc:
        logger.exception("Failed to profile dataset")
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to profile dataset",
            detail={"error": str(exc)},
        )


@router.post("/auto-suggest", response_model=MapperAutoSuggestResponse)
async def auto_suggest_mappings(
    request: MapperAutoSuggestRequest,
    mapper: Annotated[MapperService, Depends(get_mapper_service)] = None,
) -> MapperAutoSuggestResponse:
    """Auto-suggest column-to-field mappings using semantic enrichment.

    Returns suggested mappings with confidence scores, taking into account:
    - Column name similarity to field idShort and label
    - Semantic ID resolution (preferred names, synonyms from ECLASS/IEC CDD)
    - Type compatibility
    """
    try:
        return await mapper.auto_suggest(request)
    except APIError:
        raise
    except Exception as exc:
        logger.exception("Auto-suggest failed")
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Auto-suggest failed",
            detail={"error": str(exc)},
        )


@router.post("/run")
async def run_mapper(
    request: MapperRunRequest,
    mapper: Annotated[MapperService, Depends(get_mapper_service)] = None,
):
    try:
        if request.output_format == "form":
            result = await mapper.run(request)
            return MapperRunResponse(**result.model_dump())

        content, media_type, filename = await mapper.export(request)
        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except APIError:
        raise
    except Exception as exc:
        logger.exception("Mapper run failed")
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Mapper run failed",
            detail={"error": str(exc)},
        )


@router.get("/recipes", response_model=MapperRecipeList)
async def list_recipes(
    mapper: Annotated[MapperService, Depends(get_mapper_service)] = None,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> MapperRecipeList:
    try:
        return MapperRecipeList(recipes=mapper.list_recipes(user))
    except APIError:
        raise
    except Exception as exc:
        logger.exception("Failed to list recipes")
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to list recipes",
            detail={"error": str(exc)},
        )


@router.post("/recipes", response_model=MapperRecipe)
async def save_recipe(
    recipe: MapperRecipe,
    mapper: Annotated[MapperService, Depends(get_mapper_service)] = None,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> MapperRecipe:
    try:
        return mapper.save_recipe(recipe, user)
    except APIError:
        raise
    except Exception as exc:
        logger.exception("Failed to save recipe")
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to save recipe",
            detail={"error": str(exc)},
        )


@router.get("/recipes/{name}", response_model=MapperRecipe)
async def get_recipe(
    name: str,
    mapper: Annotated[MapperService, Depends(get_mapper_service)] = None,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> MapperRecipe:
    try:
        return mapper.get_recipe(name, user)
    except APIError:
        raise
    except Exception as exc:
        logger.exception("Failed to load recipe")
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to load recipe",
            detail={"recipe_name": name, "error": str(exc)},
        )


@router.delete("/recipes/{name}")
async def delete_recipe(
    name: str,
    mapper: Annotated[MapperService, Depends(get_mapper_service)] = None,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
):
    try:
        mapper.delete_recipe(name, user)
        return {"deleted": name}
    except APIError:
        raise
    except Exception as exc:
        logger.exception("Failed to delete recipe")
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to delete recipe",
            detail={"recipe_name": name, "error": str(exc)},
        )
