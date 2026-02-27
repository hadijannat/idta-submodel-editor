"""
Template listing and discovery endpoints.

Provides API endpoints for browsing available IDTA submodel templates.
"""

import logging
from typing import Annotated, Literal

import httpx
from fastapi import APIRouter, Depends, Query

from app.dependencies import get_fetcher
from app.errors import APIError, ErrorCode
from app.schemas.ui_schema import TemplateInfo, TemplateListResponse, TemplateVersionInfo
from app.services.fetcher import TemplateFetcherService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/templates", tags=["templates"])


def _map_upstream_http_error(
    exc: httpx.HTTPStatusError,
    *,
    fallback_message: str,
    detail: dict | None = None,
) -> APIError:
    status = exc.response.status_code
    response_text = exc.response.text[:500] if exc.response is not None else None
    context = {
        "upstream_status": status,
        "upstream_url": str(exc.request.url),
        "upstream_body": response_text,
        **(detail or {}),
    }

    if status == 404:
        return APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Requested template resource was not found upstream",
            detail=context,
        )
    if status == 429:
        return APIError(
            code=ErrorCode.UPSTREAM_RATE_LIMITED,
            message="Template upstream is rate limited",
            detail=context,
        )
    if status in {502, 503, 504}:
        return APIError(
            code=ErrorCode.UPSTREAM_UNAVAILABLE,
            message="Template upstream is currently unavailable",
            detail=context,
        )
    return APIError(
        code=ErrorCode.UPSTREAM_ERROR,
        message=fallback_message,
        detail=context,
    )


@router.get("", response_model=TemplateListResponse)
async def list_templates(
    fetcher: Annotated[TemplateFetcherService, Depends(get_fetcher)],
    search: Annotated[str | None, Query(description="Search filter")] = None,
    idta_number: Annotated[
        str | None, Query(description="Filter by IDTA number")
    ] = None,
    status: Annotated[
        Literal["published", "deprecated", "all"] | None,
        Query(description="Template status filter"),
    ] = None,
) -> TemplateListResponse:
    """
    List all available IDTA submodel templates.

    Templates are fetched from the admin-shell-io/submodel-templates
    GitHub repository and cached locally.
    """
    try:
        if status == "deprecated":
            statuses = ["deprecated"]
        elif status == "all":
            statuses = ["published", "deprecated"]
        else:
            statuses = ["published"]

        templates, cached = await fetcher.list_available_templates(statuses)

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
            cached=cached,
        )
    except APIError:
        raise
    except httpx.HTTPStatusError as e:
        raise _map_upstream_http_error(
            e,
            fallback_message="Failed to fetch templates",
        )
    except Exception as e:
        logger.exception("Failed to list templates")
        raise APIError(
            code=ErrorCode.UPSTREAM_ERROR,
            message="Failed to fetch templates",
            detail={"error": str(e)},
        )


@router.get("/{template_name}")
async def get_template_info(
    template_name: str,
    fetcher: Annotated[TemplateFetcherService, Depends(get_fetcher)],
    status: Annotated[
        Literal["published", "deprecated", "all"] | None,
        Query(description="Template status filter"),
    ] = None,
) -> TemplateInfo:
    """
    Get information about a specific template.
    """
    try:
        if status == "deprecated":
            statuses = ["deprecated"]
        elif status == "all":
            statuses = ["published", "deprecated"]
        else:
            statuses = ["published"]

        template = await fetcher.resolve_template(template_name, statuses)

        if not template:
            raise APIError(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message="Template not found",
                detail={"template_name": template_name},
            )

        return TemplateInfo(**template)
    except APIError:
        raise
    except httpx.HTTPStatusError as e:
        raise _map_upstream_http_error(
            e,
            fallback_message="Failed to fetch template info",
            detail={"template_name": template_name},
        )
    except Exception as e:
        logger.exception(f"Failed to get template info for {template_name}")
        raise APIError(
            code=ErrorCode.UPSTREAM_ERROR,
            message="Failed to fetch template info",
            detail={"template_name": template_name, "error": str(e)},
        )


@router.get("/{template_name}/versions", response_model=list[TemplateVersionInfo])
async def get_template_versions(
    template_name: str,
    fetcher: Annotated[TemplateFetcherService, Depends(get_fetcher)],
    status: Annotated[
        Literal["published", "deprecated"],
        Query(description="Template status filter"),
    ] = "published",
) -> list[TemplateVersionInfo]:
    """
    Get available versions for a template.
    """
    try:
        versions = await fetcher.get_template_versions(f"{status}/{template_name}")
        return [TemplateVersionInfo(**v) for v in versions]
    except APIError:
        raise
    except httpx.HTTPStatusError as e:
        raise _map_upstream_http_error(
            e,
            fallback_message="Failed to fetch template versions",
            detail={"template_name": template_name},
        )
    except Exception as e:
        logger.exception(f"Failed to get versions for {template_name}")
        raise APIError(
            code=ErrorCode.UPSTREAM_ERROR,
            message="Failed to fetch template versions",
            detail={"template_name": template_name, "error": str(e)},
        )


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
