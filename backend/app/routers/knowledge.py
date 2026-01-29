"""
API routes for the Template Knowledge System.

Provides endpoints for:
- Listing indexed templates and fields
- Semantic similarity search
- Semantic ID recommendations
- Index status and management
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.services.template_knowledge import (
    FieldInfo,
    OllamaEmbeddingClient,
    SemanticRecommendation,
    TemplateInfo,
    TemplateKnowledgeIndex,
)
from app.services.template_knowledge.models import IndexStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/knowledge", tags=["Template Knowledge"])


# -------------------------------------------------------------------------
# Dependencies
# -------------------------------------------------------------------------


def get_index_path(settings: Settings) -> Path:
    """Get the path to the knowledge index database."""
    return settings.magic_import_cache_dir / "template_knowledge" / "index.db"


async def get_knowledge_index(
    settings: Annotated[Settings, Depends(get_settings)],
) -> TemplateKnowledgeIndex:
    """
    Get the template knowledge index instance.

    Creates the index with Ollama embedding client for semantic search.
    """
    db_path = get_index_path(settings)

    if not db_path.exists():
        raise HTTPException(
            status_code=503,
            detail="Template knowledge index not built. Run 'python -m app.cli.knowledge_index build' first.",
        )

    embedding_client = OllamaEmbeddingClient(
        base_url=settings.ollama_base_url,
        model="nomic-embed-text",
    )

    return TemplateKnowledgeIndex(db_path=db_path, embedding_client=embedding_client)


# -------------------------------------------------------------------------
# Request/Response Models
# -------------------------------------------------------------------------


class SemanticSearchRequest(BaseModel):
    """Request for semantic similarity search."""

    query: str = Field(description="Search query text", min_length=1, max_length=500)
    top_k: int = Field(default=10, ge=1, le=50, description="Maximum results to return")
    threshold: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Minimum similarity threshold"
    )
    exclude_template: str | None = Field(
        default=None, description="Optionally exclude fields from this template"
    )


class SemanticSearchResult(BaseModel):
    """Single result from semantic search."""

    field: FieldInfo
    similarity: float = Field(ge=0.0, le=1.0, description="Similarity score")


class SemanticSearchResponse(BaseModel):
    """Response from semantic similarity search."""

    query: str
    results: list[SemanticSearchResult]
    total: int
    ollama_available: bool


class RecommendationRequest(BaseModel):
    """Request for semantic ID recommendations."""

    label: str = Field(description="Field label or idShort", min_length=1, max_length=200)
    value: str | None = Field(default=None, description="Optional extracted value")
    context: str | None = Field(
        default=None, max_length=500, description="Optional context (e.g., evidence quote)"
    )
    top_k: int = Field(default=5, ge=1, le=20, description="Maximum recommendations")
    threshold: float = Field(default=0.5, ge=0.0, le=1.0, description="Minimum confidence")
    current_semantic_id: str | None = Field(
        default=None, description="Current semantic ID to mark in results"
    )


class RecommendationResponse(BaseModel):
    """Response with semantic ID recommendations."""

    label: str
    recommendations: list[SemanticRecommendation]


class TemplateListResponse(BaseModel):
    """Response listing indexed templates."""

    templates: list[TemplateInfo]
    total: int


class FieldListResponse(BaseModel):
    """Response listing template fields."""

    template_idta: str
    fields: list[FieldInfo]
    total: int


# -------------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------------


@router.get("/status", response_model=IndexStatus)
async def get_index_status(
    index: Annotated[TemplateKnowledgeIndex, Depends(get_knowledge_index)],
) -> IndexStatus:
    """
    Get template knowledge index status and statistics.

    Returns information about the number of indexed templates, fields,
    embedding model, and Ollama availability.
    """
    return await index.get_status()


@router.get("/templates", response_model=TemplateListResponse)
async def list_indexed_templates(
    index: Annotated[TemplateKnowledgeIndex, Depends(get_knowledge_index)],
) -> TemplateListResponse:
    """
    List all templates in the knowledge index.

    Returns metadata about each indexed IDTA template including
    IDTA number, title, version, and field count.
    """
    templates = index.list_templates()
    return TemplateListResponse(templates=templates, total=len(templates))


@router.get("/templates/{idta_number}", response_model=TemplateInfo)
async def get_template(
    idta_number: str,
    index: Annotated[TemplateKnowledgeIndex, Depends(get_knowledge_index)],
) -> TemplateInfo:
    """
    Get a specific template by IDTA number.

    Args:
        idta_number: The IDTA template number (e.g., "02006")
    """
    template = index.get_template(idta_number)
    if not template:
        raise HTTPException(status_code=404, detail=f"Template {idta_number} not found")
    return template


@router.get("/templates/{idta_number}/fields", response_model=FieldListResponse)
async def get_template_fields(
    idta_number: str,
    index: Annotated[TemplateKnowledgeIndex, Depends(get_knowledge_index)],
) -> FieldListResponse:
    """
    Get all fields for a specific template.

    Returns complete field metadata including semantic IDs, keywords,
    synonyms, and (if available) embedding vectors.
    """
    template = index.get_template(idta_number)
    if not template:
        raise HTTPException(status_code=404, detail=f"Template {idta_number} not found")

    fields = index.get_fields_for_template(idta_number)
    return FieldListResponse(
        template_idta=idta_number,
        fields=fields,
        total=len(fields),
    )


@router.post("/search/semantic", response_model=SemanticSearchResponse)
async def search_by_semantic_similarity(
    request: SemanticSearchRequest,
    index: Annotated[TemplateKnowledgeIndex, Depends(get_knowledge_index)],
) -> SemanticSearchResponse:
    """
    Search fields by semantic similarity to a query.

    Uses Ollama embeddings (nomic-embed-text) for vector similarity search.
    Falls back to keyword search if Ollama is unavailable.
    """
    status = await index.get_status()

    results = await index.find_similar_fields_by_text(
        query=request.query,
        top_k=request.top_k,
        threshold=request.threshold,
        exclude_template=request.exclude_template,
    )

    return SemanticSearchResponse(
        query=request.query,
        results=[
            SemanticSearchResult(field=field, similarity=score) for field, score in results
        ],
        total=len(results),
        ollama_available=status.ollama_available,
    )


@router.post("/recommend", response_model=RecommendationResponse)
async def recommend_semantic_ids(
    request: RecommendationRequest,
    index: Annotated[TemplateKnowledgeIndex, Depends(get_knowledge_index)],
) -> RecommendationResponse:
    """
    Get semantic ID recommendations for a field.

    Based on the field label, optional value, and context, returns
    ranked semantic ID recommendations from the knowledge index.
    """
    recommendations = await index.recommend_semantic_ids(
        label=request.label,
        value=request.value,
        context=request.context,
        top_k=request.top_k,
        threshold=request.threshold,
    )

    # Mark current semantic ID if provided
    if request.current_semantic_id:
        for rec in recommendations:
            rec.is_current = rec.irdi == request.current_semantic_id

    return RecommendationResponse(label=request.label, recommendations=recommendations)


@router.get("/fields/by-semantic-id/{semantic_id:path}")
async def get_fields_by_semantic_id(
    semantic_id: str,
    index: Annotated[TemplateKnowledgeIndex, Depends(get_knowledge_index)],
) -> list[FieldInfo]:
    """
    Get all fields across templates that use a specific semantic ID.

    Useful for understanding how a semantic ID is used across different
    IDTA templates.
    """
    fields = index.get_fields_by_semantic_id(semantic_id)
    return fields


@router.get("/keywords/{idta_number}/{path:path}")
async def get_field_keywords(
    idta_number: str,
    path: str,
    include_similar: bool = Query(default=True, description="Include keywords from similar fields"),
    max_keywords: int = Query(default=20, ge=1, le=50, description="Maximum keywords to return"),
    index: Annotated[TemplateKnowledgeIndex, Depends(get_knowledge_index)],
) -> dict:
    """
    Get extraction keywords for a specific field.

    Returns keywords derived from the field's metadata, synonyms,
    and optionally from semantically similar fields.
    """
    keywords = index.get_keywords_for_field(
        template_idta=idta_number,
        path=path,
        include_similar=include_similar,
        max_keywords=max_keywords,
    )

    return {
        "template_idta": idta_number,
        "path": path,
        "keywords": keywords,
    }
