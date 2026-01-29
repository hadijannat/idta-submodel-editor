"""
Template Knowledge Index - Main interface for template knowledge operations.

Provides semantic similarity search, field lookup, and pattern retrieval
for the Magic Import extraction pipeline.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from app.services.template_knowledge.embeddings import OllamaEmbeddingClient
from app.services.template_knowledge.models import (
    ExtractionPattern,
    FieldInfo,
    IndexStatus,
    SemanticRecommendation,
    TemplateInfo,
)
from app.services.template_knowledge.storage import TemplateKnowledgeStorage

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class TemplateKnowledgeIndex:
    """
    Main interface for template knowledge operations.

    Provides:
    - Template and field metadata lookup
    - Semantic similarity search via embeddings
    - Full-text keyword search
    - Extraction pattern retrieval
    """

    def __init__(
        self,
        db_path: Path | str | None = None,
        embedding_client: OllamaEmbeddingClient | None = None,
    ) -> None:
        """
        Initialize the knowledge index.

        Args:
            db_path: Path to SQLite database. Defaults to ./cache/template_knowledge.db
            embedding_client: Ollama client for embedding operations
        """
        if db_path is None:
            db_path = Path("./cache/template_knowledge/index.db")

        self.storage = TemplateKnowledgeStorage(db_path)
        self.embedding_client = embedding_client or OllamaEmbeddingClient()

        # In-memory embedding cache for fast similarity search
        self._embedding_cache: list[tuple[FieldInfo, list[float]]] | None = None

    # -------------------------------------------------------------------------
    # Template operations
    # -------------------------------------------------------------------------

    def add_template(self, template: TemplateInfo) -> None:
        """Add or update a template in the index."""
        self.storage.add_template(template)

    def get_template(self, idta_number: str) -> TemplateInfo | None:
        """Get template by IDTA number."""
        return self.storage.get_template(idta_number)

    def list_templates(self) -> list[TemplateInfo]:
        """List all indexed templates."""
        return self.storage.list_templates()

    @property
    def template_count(self) -> int:
        """Number of indexed templates."""
        return self.storage.get_status().templates_indexed

    # -------------------------------------------------------------------------
    # Field operations
    # -------------------------------------------------------------------------

    def add_field(self, field: FieldInfo) -> int:
        """Add or update a field in the index."""
        # Invalidate embedding cache
        self._embedding_cache = None
        return self.storage.add_field(field)

    def get_field(self, template_idta: str, path: str) -> FieldInfo | None:
        """Get a specific field by template and path."""
        return self.storage.get_field(template_idta, path)

    def get_fields_for_template(self, template_idta: str) -> list[FieldInfo]:
        """Get all fields for a template."""
        return self.storage.get_fields_for_template(template_idta)

    def get_fields_by_semantic_id(self, semantic_id: str) -> list[FieldInfo]:
        """Get all fields across templates with a specific semantic ID."""
        return self.storage.get_fields_by_semantic_id(semantic_id)

    @property
    def field_count(self) -> int:
        """Total number of indexed fields."""
        return self.storage.get_status().fields_indexed

    # -------------------------------------------------------------------------
    # Pattern operations
    # -------------------------------------------------------------------------

    def add_pattern(self, pattern: ExtractionPattern) -> int:
        """Add an extraction pattern."""
        return self.storage.add_pattern(pattern)

    def get_patterns_for_context(self, context_type: str) -> list[ExtractionPattern]:
        """Get extraction patterns for a context type."""
        return self.storage.get_patterns_for_context(context_type)

    # -------------------------------------------------------------------------
    # Semantic search
    # -------------------------------------------------------------------------

    async def find_similar_fields(
        self,
        embedding: list[float],
        top_k: int = 5,
        threshold: float = 0.5,
        exclude_template: str | None = None,
    ) -> list[tuple[FieldInfo, float]]:
        """
        Find fields similar to a given embedding vector.

        Args:
            embedding: Query embedding vector
            top_k: Maximum number of results
            threshold: Minimum similarity score (0-1)
            exclude_template: Optionally exclude fields from this template

        Returns:
            List of (FieldInfo, similarity_score) tuples, sorted by score desc
        """
        # Load embedding cache if needed
        if self._embedding_cache is None:
            self._embedding_cache = self.storage.get_all_fields_with_embeddings()

        if not self._embedding_cache:
            logger.warning("No embeddings in index. Run index build with embeddings enabled.")
            return []

        # Compute similarities
        results = []
        for field, field_embedding in self._embedding_cache:
            # Skip if excluded template
            if exclude_template and field.template_idta == exclude_template:
                continue

            similarity = OllamaEmbeddingClient.cosine_similarity(embedding, field_embedding)

            if similarity >= threshold:
                results.append((field, similarity))

        # Sort by similarity descending
        results.sort(key=lambda x: x[1], reverse=True)

        return results[:top_k]

    async def find_similar_fields_by_text(
        self,
        query: str,
        top_k: int = 5,
        threshold: float = 0.5,
        exclude_template: str | None = None,
    ) -> list[tuple[FieldInfo, float]]:
        """
        Find fields semantically similar to a text query.

        Args:
            query: Text query to search for
            top_k: Maximum number of results
            threshold: Minimum similarity score
            exclude_template: Optionally exclude fields from this template

        Returns:
            List of (FieldInfo, similarity_score) tuples
        """
        # Check Ollama availability
        if not await self.embedding_client.is_available():
            logger.warning("Ollama not available. Falling back to keyword search.")
            return self._fallback_keyword_search(query, top_k, exclude_template)

        try:
            # Generate query embedding
            query_embedding = await self.embedding_client.embed(query)

            # Search by embedding
            return await self.find_similar_fields(
                embedding=query_embedding,
                top_k=top_k,
                threshold=threshold,
                exclude_template=exclude_template,
            )

        except Exception as e:
            logger.warning("Embedding search failed: %s. Falling back to keywords.", e)
            return self._fallback_keyword_search(query, top_k, exclude_template)

    def _fallback_keyword_search(
        self,
        query: str,
        top_k: int,
        exclude_template: str | None,
    ) -> list[tuple[FieldInfo, float]]:
        """Fallback to full-text search when embeddings unavailable."""
        try:
            fields = self.storage.search_fields_fts(query, limit=top_k * 2)

            results = []
            for field in fields:
                if exclude_template and field.template_idta == exclude_template:
                    continue

                # Estimate relevance score based on keyword match
                score = self._estimate_keyword_score(query, field)
                results.append((field, score))

            results.sort(key=lambda x: x[1], reverse=True)
            return results[:top_k]

        except Exception as e:
            logger.error("Fallback keyword search failed: %s", e)
            return []

    @staticmethod
    def _estimate_keyword_score(query: str, field: FieldInfo) -> float:
        """Estimate relevance score based on keyword overlap."""
        query_terms = set(query.lower().split())
        field_terms = set(field.keywords + [field.id_short.lower()])

        if field.semantic_label:
            field_terms.update(field.semantic_label.lower().split())

        if not query_terms:
            return 0.0

        overlap = len(query_terms & field_terms)
        return overlap / len(query_terms)

    # -------------------------------------------------------------------------
    # Semantic ID recommendations
    # -------------------------------------------------------------------------

    async def recommend_semantic_ids(
        self,
        label: str,
        value: str | None = None,
        context: str | None = None,
        top_k: int = 5,
        threshold: float = 0.5,
    ) -> list[SemanticRecommendation]:
        """
        Recommend semantic IDs for a field based on its label and value.

        Args:
            label: Field label or idShort
            value: Optional extracted value
            context: Optional context (e.g., evidence quote)
            top_k: Maximum recommendations
            threshold: Minimum similarity threshold

        Returns:
            List of SemanticRecommendation objects
        """
        # Build query from available information
        query_parts = [label]
        if value:
            query_parts.append(value[:100])  # Limit value length
        if context:
            query_parts.append(context[:200])  # Limit context length

        query = " ".join(filter(None, query_parts))

        # Find similar fields
        similar_fields = await self.find_similar_fields_by_text(
            query=query,
            top_k=top_k * 2,  # Get more candidates for deduplication
            threshold=threshold,
        )

        # Convert to recommendations, deduplicating by semantic ID
        seen_semantic_ids: set[str] = set()
        recommendations = []

        for field, score in similar_fields:
            if not field.semantic_id:
                continue

            if field.semantic_id in seen_semantic_ids:
                continue

            seen_semantic_ids.add(field.semantic_id)

            # Count usage across templates
            usage_count = len(self.get_fields_by_semantic_id(field.semantic_id))

            recommendations.append(
                SemanticRecommendation(
                    irdi=field.semantic_id,
                    label=field.semantic_label or field.id_short,
                    definition=field.definition,
                    confidence=score,
                    source_template=field.template_idta,
                    is_current=False,  # Caller should check against current value
                    source_field_path=field.path,
                    usage_count=usage_count,
                )
            )

            if len(recommendations) >= top_k:
                break

        return recommendations

    # -------------------------------------------------------------------------
    # Dynamic keyword generation
    # -------------------------------------------------------------------------

    def get_keywords_for_field(
        self,
        template_idta: str,
        path: str,
        include_similar: bool = True,
        max_keywords: int = 20,
    ) -> list[str]:
        """
        Get extraction keywords for a field, including similar fields.

        Args:
            template_idta: Template IDTA number
            path: Field path
            include_similar: Whether to include keywords from similar fields
            max_keywords: Maximum keywords to return

        Returns:
            List of keywords for extraction
        """
        field = self.get_field(template_idta, path)
        if not field:
            return []

        keywords = set(field.keywords)
        keywords.update(field.synonyms)

        # Add similar field keywords if embedding available
        if include_similar and field.embedding_vector:
            try:
                # Synchronous version for keyword generation
                similar = self._sync_find_similar(field.embedding_vector, top_k=3)
                for sim_field, score in similar:
                    if score > 0.7:  # Only high-confidence matches
                        keywords.update(sim_field.keywords[:5])
            except Exception:
                pass  # Ignore embedding errors

        return list(keywords)[:max_keywords]

    def _sync_find_similar(
        self,
        embedding: list[float],
        top_k: int = 3,
    ) -> list[tuple[FieldInfo, float]]:
        """Synchronous version of find_similar_fields for keyword generation."""
        if self._embedding_cache is None:
            self._embedding_cache = self.storage.get_all_fields_with_embeddings()

        results = []
        for field, field_embedding in self._embedding_cache:
            similarity = OllamaEmbeddingClient.cosine_similarity(embedding, field_embedding)
            if similarity >= 0.5:
                results.append((field, similarity))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    # -------------------------------------------------------------------------
    # Status and maintenance
    # -------------------------------------------------------------------------

    async def get_status(self) -> IndexStatus:
        """Get index status with Ollama availability check."""
        status = self.storage.get_status()
        status.ollama_available = await self.embedding_client.is_available()
        return status

    def get_status_sync(self) -> IndexStatus:
        """Get index status without async Ollama check."""
        return self.storage.get_status()

    @property
    def last_updated(self) -> str | None:
        """When the index was last updated."""
        status = self.storage.get_status()
        return status.last_updated.isoformat() if status.last_updated else None

    @property
    def embedding_model(self) -> str:
        """Embedding model used for the index."""
        return self.storage.get_status().embedding_model

    def clear(self) -> None:
        """Clear all data from the index."""
        self._embedding_cache = None
        self.storage.clear_all()

    def vacuum(self) -> None:
        """Optimize database storage."""
        self.storage.vacuum()
