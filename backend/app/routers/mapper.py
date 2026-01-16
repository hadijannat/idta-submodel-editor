"""Smart Mapper endpoints."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from app.dependencies import get_current_user, get_mapper_service
from app.schemas.mapper import (
    DatasetProfile,
    MapperRecipe,
    MapperRecipeList,
    MapperRunRequest,
    MapperRunResponse,
)
from app.services.mapper import MapperService

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
    try:
        return await mapper.profile(file, sheet, header_row, sample_rows)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to profile dataset")
        raise HTTPException(status_code=500, detail=str(exc))


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

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Mapper run failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/recipes", response_model=MapperRecipeList)
async def list_recipes(
    mapper: Annotated[MapperService, Depends(get_mapper_service)] = None,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> MapperRecipeList:
    try:
        return MapperRecipeList(recipes=mapper.list_recipes(user))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to list recipes")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/recipes", response_model=MapperRecipe)
async def save_recipe(
    recipe: MapperRecipe,
    mapper: Annotated[MapperService, Depends(get_mapper_service)] = None,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> MapperRecipe:
    try:
        return mapper.save_recipe(recipe, user)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to save recipe")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/recipes/{name}", response_model=MapperRecipe)
async def get_recipe(
    name: str,
    mapper: Annotated[MapperService, Depends(get_mapper_service)] = None,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> MapperRecipe:
    try:
        return mapper.get_recipe(name, user)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to load recipe")
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/recipes/{name}")
async def delete_recipe(
    name: str,
    mapper: Annotated[MapperService, Depends(get_mapper_service)] = None,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
):
    try:
        mapper.delete_recipe(name, user)
        return {"deleted": name}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to delete recipe")
        raise HTTPException(status_code=500, detail=str(exc))
