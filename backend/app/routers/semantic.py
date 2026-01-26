"""Semantic dictionary API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.dependencies import get_semantic_service
from app.errors import APIError, ErrorCode
from app.schemas.semantic import (
    SemanticApplyPreviewRequest,
    SemanticApplyPreviewResponse,
    SemanticBatchResolveItem,
    SemanticBatchResolveRequest,
    SemanticBatchResolveResponse,
    SemanticProviderInfo,
    SemanticKind,
    SemanticResolveResponse,
    SemanticSearchResponse,
)
from app.services.semantic.service import SemanticService
from app.services.semantic.errors import SemanticRateLimitError

router = APIRouter(prefix="/api/semantic", tags=["semantic"])


def _handle_rate_limit(exc: SemanticRateLimitError) -> APIError:
    """Convert rate limit error to APIError with Retry-After header info."""
    return APIError(
        code=ErrorCode.UPSTREAM_RATE_LIMITED,
        message=str(exc),
        detail={"retry_after": exc.retry_after if exc.retry_after is not None else 60},
    )


@router.get("/providers", response_model=list[SemanticProviderInfo])
async def list_providers(
    service: Annotated[SemanticService, Depends(get_semantic_service)],
) -> list[SemanticProviderInfo]:
    """List available semantic providers with status details."""
    return service.providers_info()


@router.get("/search", response_model=SemanticSearchResponse)
async def search_semantics(
    service: Annotated[SemanticService, Depends(get_semantic_service)],
    q: Annotated[str, Query(min_length=2)],
    provider: Annotated[str | None, Query()] = None,
    kind: Annotated[SemanticKind | None, Query()] = None,
    lang: Annotated[str, Query()] = "en",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SemanticSearchResponse:
    """Search semantic dictionaries."""
    try:
        results, total = await service.search(
            q=q,
            provider=provider,
            kind=kind,
            lang=lang,
            limit=limit,
            offset=offset,
        )
        return SemanticSearchResponse(query=q, results=results, total=total)
    except SemanticRateLimitError as exc:
        raise _handle_rate_limit(exc)


@router.get("/resolve", response_model=SemanticResolveResponse)
async def resolve_semantic(
    service: Annotated[SemanticService, Depends(get_semantic_service)],
    identifier: Annotated[str, Query(alias="id")],
    provider: Annotated[str | None, Query()] = None,
    lang: Annotated[str, Query()] = "en",
) -> SemanticResolveResponse:
    """Resolve a semantic ID or IRI to a dictionary entry."""
    try:
        entry = await service.resolve(identifier, provider, lang)
    except SemanticRateLimitError as exc:
        raise _handle_rate_limit(exc)
    if not entry:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Semantic entry not found",
            detail={"identifier": identifier},
        )
    return SemanticResolveResponse(entry=entry)


@router.post("/apply-preview", response_model=SemanticApplyPreviewResponse)
async def apply_preview(
    service: Annotated[SemanticService, Depends(get_semantic_service)],
    payload: SemanticApplyPreviewRequest,
) -> SemanticApplyPreviewResponse:
    """Preview semantic application and type suggestions."""
    try:
        result = await service.apply_preview(
            identifier=payload.identifier,
            provider=payload.provider,
            lang="en",
            element_type=payload.elementType,
            value_type=payload.valueType,
            prefer_iri=payload.preferIri,
        )
    except SemanticRateLimitError as exc:
        raise _handle_rate_limit(exc)
    if result is None:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Semantic entry not found",
            detail={"identifier": payload.identifier},
        )
    return result


@router.post("/batch-resolve", response_model=SemanticBatchResolveResponse)
async def batch_resolve(
    service: Annotated[SemanticService, Depends(get_semantic_service)],
    payload: SemanticBatchResolveRequest,
) -> SemanticBatchResolveResponse:
    """Batch resolve multiple semantic IDs or IRIs.

    Resolves up to 100 identifiers in a single request. Useful for
    enriching auto-mapping with semantic synonyms and preferred names.
    """
    results: list[SemanticBatchResolveItem] = []

    for identifier in payload.identifiers:
        try:
            entry = await service.resolve(identifier, payload.provider, payload.lang)
            results.append(
                SemanticBatchResolveItem(identifier=identifier, entry=entry)
            )
        except SemanticRateLimitError as exc:
            results.append(
                SemanticBatchResolveItem(
                    identifier=identifier,
                    error=f"Rate limited: retry after {exc.retry_after}s",
                )
            )
        except Exception as exc:
            results.append(
                SemanticBatchResolveItem(
                    identifier=identifier,
                    error=str(exc),
                )
            )

    return SemanticBatchResolveResponse(results=results)
