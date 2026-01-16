"""
Semantic dictionary schemas.

Defines API payloads for semantic dictionary lookup, resolution, and apply preview.
"""

from typing import Literal

from pydantic import BaseModel, Field

SemanticProviderStatus = Literal["ready", "disabled", "error"]
SemanticKind = Literal["property", "class", "unit", "value"]


class SemanticProviderInfo(BaseModel):
    """Provider availability metadata."""

    id: str
    label: str
    status: SemanticProviderStatus
    reason: str | None = None


class SemanticEntry(BaseModel):
    """Normalized semantic entry returned by providers."""

    provider: str
    kind: SemanticKind
    canonicalId: str
    canonicalIri: str | None = None
    preferredName: str | None = None
    definition: str | None = None
    datatypeHint: str | None = None
    unitHint: str | None = None
    labels: dict[str, str] | None = None
    definitions: dict[str, str] | None = None
    synonyms: list[str] | None = None
    score: float | None = None


class SemanticSearchResponse(BaseModel):
    """Search response payload."""

    query: str
    results: list[SemanticEntry]
    total: int


class SemanticResolveResponse(BaseModel):
    """Resolve response payload."""

    entry: SemanticEntry


class SemanticApplyPreviewRequest(BaseModel):
    """Request payload for apply-preview."""

    identifier: str = Field(..., description="Canonical ID or IRI to apply")
    provider: str | None = None
    elementType: str | None = None
    valueType: str | None = None
    preferIri: bool | None = None


class SemanticApplyPreviewResponse(BaseModel):
    """Preview of semantic application and typing recommendations."""

    semanticId: str
    elementType: str | None = None
    valueType: str | None = None
    warnings: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
