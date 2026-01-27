"""
Magic Import - PDF-to-AAS data extraction using LLM-powered extraction.

This module provides:
- PDF indexing with text extraction and OCR fallback
- Schema-aware target field resolution
- Snippet retrieval for privacy-preserving LLM queries
- Multi-provider LLM extraction (OpenAI, Anthropic, Local)
- Evidence localization for source highlighting
- Confidence scoring for human review
- Quality metrics computation for extraction analysis
"""

from app.services.magic_import.job_manager import JobManager
from app.services.magic_import.pdf_indexer import PDFIndexer
from app.services.magic_import.schema_resolver import SchemaResolver
from app.services.magic_import.retriever import SnippetRetriever
from app.services.magic_import.extractor import Extractor
from app.services.magic_import.localizer import EvidenceLocalizer
from app.services.magic_import.scorer import ConfidenceScorer
from app.services.magic_import.metrics_calculator import MetricsCalculator

__all__ = [
    "JobManager",
    "PDFIndexer",
    "SchemaResolver",
    "SnippetRetriever",
    "Extractor",
    "EvidenceLocalizer",
    "ConfidenceScorer",
    "MetricsCalculator",
]
