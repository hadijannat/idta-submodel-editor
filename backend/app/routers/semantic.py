"""Semantic dictionary API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import get_semantic_service
from app.schemas.semantic import (
    SemanticApplyPreviewRequest,
    SemanticApplyPreviewResponse,
    SemanticProviderInfo,
    SemanticKind,
    SemanticResolveResponse,
    SemanticSearchResponse,
)
from app.services.semantic.service import SemanticService
from app.services.semantic.errors import SemanticRateLimitError

router = APIRouter(prefix="/api/semantic", tags=["semantic"])


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
        raise HTTPException(
            status_code=429,
            detail=str(exc),
            headers={
                "Retry-After": str(exc.retry_after)
                if exc.retry_after is not None
                else "60"
            },
        )


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
        raise HTTPException(
            status_code=429,
            detail=str(exc),
            headers={
                "Retry-After": str(exc.retry_after)
                if exc.retry_after is not None
                else "60"
            },
        )
    if not entry:
        raise HTTPException(status_code=404, detail="Semantic entry not found")
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
        raise HTTPException(
            status_code=429,
            detail=str(exc),
            headers={
                "Retry-After": str(exc.retry_after)
                if exc.retry_after is not None
                else "60"
            },
        )
    if result is None:
        raise HTTPException(status_code=404, detail="Semantic entry not found")
    return result
