"""Smart Mapper endpoints."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from app.dependencies import get_mapper_service
from app.schemas.mapper import DatasetProfile, MapperRunRequest, MapperRunResponse
from app.services.mapper import MapperService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mapper", tags=["mapper"])


@router.post("/profile", response_model=DatasetProfile)
async def profile_dataset(
    file: Annotated[UploadFile, File(...)],
    sheet: Annotated[str | None, Form(None)] = None,
    header_row: Annotated[int | None, Form(None)] = None,
    sample_rows: Annotated[int, Form(200)] = 200,
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
