"""
Data models for the Template Knowledge System.

These models represent the indexed knowledge about IDTA submodel templates,
including field metadata, semantic information, and extraction patterns.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TemplateInfo(BaseModel):
    """Metadata for a single IDTA template."""

    idta_number: str = Field(description="IDTA template number (e.g., '02006', '02023')")
    title: str = Field(description="Human-readable template title")
    version: str = Field(description="Template version string")
    semantic_id: str | None = Field(default=None, description="Submodel semantic ID")
    status: Literal["published", "deprecated"] = Field(
        default="published", description="Template publication status"
    )
    field_count: int = Field(default=0, description="Total number of extractable fields")
    last_indexed: datetime = Field(
        default_factory=datetime.utcnow, description="When this template was last indexed"
    )
    source_path: str | None = Field(
        default=None, description="Path/URL where template was fetched from"
    )
    description: str | None = Field(
        default=None, description="Template description from metadata"
    )


class FieldInfo(BaseModel):
    """Comprehensive field metadata from a template."""

    model_config = ConfigDict(protected_namespaces=())

    template_idta: str = Field(description="Parent template IDTA number")
    path: str = Field(description="Full idShortPath to the field")
    id_short: str = Field(description="Element idShort name")
    model_type: str = Field(description="AAS element type (Property, SMC, etc.)")
    value_type: str | None = Field(default=None, description="XSD value type for Properties")
    semantic_id: str | None = Field(default=None, description="ECLASS/IEC CDD IRDI")
    semantic_label: str | None = Field(
        default=None, description="Human-readable label from ConceptDescription"
    )
    definition: str | None = Field(
        default=None, description="Multi-language definition text"
    )
    unit: str | None = Field(default=None, description="Unit of measurement")
    cardinality: str = Field(default="[1]", description="Cardinality constraint")
    parent_path: str | None = Field(
        default=None, description="Path to parent collection/list"
    )
    keywords: list[str] = Field(
        default_factory=list, description="Derived extraction keywords"
    )
    synonyms: list[str] = Field(
        default_factory=list, description="Synonyms from ConceptDescription"
    )
    embedding_vector: list[float] | None = Field(
        default=None, description="Ollama embedding vector (768 dims for nomic-embed-text)"
    )
    # Additional metadata for extraction
    example_values: list[str] = Field(
        default_factory=list, description="Example values from ConceptDescription"
    )
    value_format: str | None = Field(
        default=None, description="Value format pattern (regex)"
    )
    allowed_values: list[str] = Field(
        default_factory=list, description="Allowed enumeration values"
    )
    is_required: bool = Field(default=False, description="Whether field is required")

    def get_embedding_text(self) -> str:
        """Build text for embedding generation."""
        parts = [
            self.id_short,
            self.semantic_label or "",
            self.definition or "",
            " ".join(self.keywords),
            " ".join(self.synonyms),
        ]
        return " ".join(filter(None, parts))


class ExtractionPattern(BaseModel):
    """Learned extraction pattern for a field type."""

    field_path: str = Field(description="idShortPath pattern (may include wildcards)")
    context_type: str = Field(
        description="Context category (ContactInformation, TechnicalData, etc.)"
    )
    keywords: list[str] = Field(default_factory=list, description="High-value keywords")
    regex_patterns: list[str] = Field(
        default_factory=list, description="Value regex patterns (dates, numbers, etc.)"
    )
    table_hints: list[str] = Field(
        default_factory=list, description="Table header patterns to look for"
    )
    confidence_weight: float = Field(
        default=1.0, ge=0.0, le=2.0, description="Pattern reliability weight"
    )
    example_matches: list[str] = Field(
        default_factory=list, description="Example values this pattern has matched"
    )


class SemanticRecommendation(BaseModel):
    """A recommended semantic ID for a field."""

    irdi: str = Field(description="ECLASS/IEC CDD IRDI")
    label: str = Field(description="Human-readable preferred name")
    definition: str | None = Field(default=None, description="Definition text")
    confidence: float = Field(ge=0.0, le=1.0, description="Similarity confidence score")
    source_template: str | None = Field(
        default=None, description="Template where this semantic ID was found"
    )
    is_current: bool = Field(
        default=False, description="Whether this matches the field's current semantic ID"
    )
    # Additional context
    source_field_path: str | None = Field(
        default=None, description="Path of the field that has this semantic ID"
    )
    usage_count: int = Field(
        default=1, description="How many templates use this semantic ID"
    )


class IndexStatus(BaseModel):
    """Status of the template knowledge index."""

    templates_indexed: int = Field(default=0, description="Number of templates indexed")
    fields_indexed: int = Field(default=0, description="Total fields indexed")
    patterns_indexed: int = Field(default=0, description="Extraction patterns indexed")
    last_updated: datetime | None = Field(
        default=None, description="When index was last updated"
    )
    embedding_model: str = Field(
        default="nomic-embed-text", description="Ollama embedding model used"
    )
    ollama_available: bool = Field(
        default=False, description="Whether Ollama server is reachable"
    )
    index_version: str = Field(default="1.0", description="Index schema version")
