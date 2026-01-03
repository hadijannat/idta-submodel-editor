"""
Template listing and discovery endpoints.

Provides API endpoints for browsing available IDTA submodel templates.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import get_fetcher
from app.schemas.ui_schema import TemplateInfo, TemplateListResponse, TemplateVersionInfo
from app.services.fetcher import TemplateFetcherService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("", response_model=TemplateListResponse)
async def list_templates(
    fetcher: Annotated[TemplateFetcherService, Depends(get_fetcher)],
    search: Annotated[str | None, Query(description="Search filter")] = None,
    idta_number: Annotated[
        str | None, Query(description="Filter by IDTA number")
    ] = None,
) -> TemplateListResponse:
    """
    List all available IDTA submodel templates.

    Templates are fetched from the admin-shell-io/submodel-templates
    GitHub repository and cached locally.
    """
    try:
        templates = await fetcher.list_available_templates()

        # Apply filters
        if search:
            search_lower = search.lower()
            templates = [
                t
                for t in templates
                if search_lower in t["name"].lower()
                or search_lower in (t.get("title") or "").lower()
            ]

        if idta_number:
            templates = [
                t for t in templates if t.get("idta_number") == idta_number
            ]

        return TemplateListResponse(
            templates=[TemplateInfo(**t) for t in templates],
            total=len(templates),
            cached=True,
        )
    except Exception as e:
        logger.exception("Failed to list templates")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{template_name}")
async def get_template_info(
    template_name: str,
    fetcher: Annotated[TemplateFetcherService, Depends(get_fetcher)],
) -> TemplateInfo:
    """
    Get information about a specific template.
    """
    try:
        templates = await fetcher.list_available_templates()
        template = next((t for t in templates if t["name"] == template_name), None)

        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        return TemplateInfo(**template)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get template info for {template_name}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{template_name}/versions", response_model=list[TemplateVersionInfo])
async def get_template_versions(
    template_name: str,
    fetcher: Annotated[TemplateFetcherService, Depends(get_fetcher)],
) -> list[TemplateVersionInfo]:
    """
    Get available versions for a template.
    """
    try:
        versions = await fetcher.get_template_versions(f"published/{template_name}")
        return [TemplateVersionInfo(**v) for v in versions]
    except Exception as e:
        logger.exception(f"Failed to get versions for {template_name}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh")
async def refresh_template_cache(
    fetcher: Annotated[TemplateFetcherService, Depends(get_fetcher)],
) -> dict[str, int]:
    """
    Clear the template cache and refresh from GitHub.

    Returns the number of cached files that were cleared.
    """
    count = fetcher.clear_cache()
    return {"cleared": count}


@router.delete("/{template_name}/cache")
async def invalidate_template_cache(
    template_name: str,
    fetcher: Annotated[TemplateFetcherService, Depends(get_fetcher)],
) -> dict[str, bool]:
    """
    Invalidate cache for a specific template.
    """
    result = fetcher.invalidate_template(f"published/{template_name}")
    return {"invalidated": result}
