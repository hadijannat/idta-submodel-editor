"""
Template Knowledge System - Comprehensive index of all IDTA submodel templates.

Provides:
- Full metadata extraction from all published IDTA templates
- Ollama-based local embeddings for semantic similarity search
- Dynamic keyword generation from ConceptDescriptions
- Cross-template pattern discovery
"""

from app.services.template_knowledge.models import (
    TemplateInfo,
    FieldInfo,
    ExtractionPattern,
    SemanticRecommendation,
)
from app.services.template_knowledge.index import TemplateKnowledgeIndex
from app.services.template_knowledge.builder import TemplateKnowledgeBuilder
from app.services.template_knowledge.embeddings import OllamaEmbeddingClient

__all__ = [
    "TemplateInfo",
    "FieldInfo",
    "ExtractionPattern",
    "SemanticRecommendation",
    "TemplateKnowledgeIndex",
    "TemplateKnowledgeBuilder",
    "OllamaEmbeddingClient",
]
