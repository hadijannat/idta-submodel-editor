"""
Celery tasks for Magic Import background processing.

Task flow:
1. process_magic_import_job - Main orchestrator task
2. index_pdf_task - PDF text extraction
3. ocr_task - OCR for scanned pages
4. extract_fields_task - LLM extraction
5. localize_evidence_task - Map quotes to bounding boxes
6. score_confidence_task - Calculate confidence scores
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from celery import shared_task

from app.config import get_settings
from app.schemas.magic_import import (
    JobStatus,
    MagicImportResult,
    FieldExtraction,
    ConfidenceBreakdown,
)

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="magic_import.process_job")
def process_magic_import_job(self, job_id: str) -> dict:
    """
    Main orchestrator task for Magic Import processing.

    Executes the full pipeline:
    PDF Indexing → OCR (if needed) → Field Extraction → Localization → Scoring

    Args:
        job_id: The job ID to process

    Returns:
        Result summary dictionary
    """
    from app.services.magic_import.job_manager import JobManager
    from app.services.magic_import.pdf_indexer import PDFIndexer
    from app.services.magic_import.ocr import OCRProcessor
    from app.services.magic_import.schema_resolver import SchemaResolver
    from app.services.magic_import.retriever import SnippetRetriever
    from app.services.magic_import.extractor import Extractor
    from app.services.magic_import.localizer import EvidenceLocalizer
    from app.services.magic_import.scorer import ConfidenceScorer

    settings = get_settings()
    job_manager = JobManager()
    start_time = time.time()

    # Load job
    job = job_manager.get_job(job_id)
    if job is None:
        logger.error("Job %s not found", job_id)
        return {"error": "Job not found", "job_id": job_id}

    pdf_path = job_manager.get_pdf_path(job_id)
    if pdf_path is None:
        job_manager.update_job_status(
            job_id, JobStatus.FAILED, error_message="PDF file not found"
        )
        return {"error": "PDF file not found", "job_id": job_id}

    try:
        # Step 1: Index PDF
        job_manager.update_job_status(
            job_id,
            JobStatus.INDEXING,
            progress=0.1,
            progress_message="Extracting text from PDF...",
        )

        indexer = PDFIndexer()
        index = indexer.index_pdf(pdf_path, job_id)
        job_manager.save_index(index)

        job_manager.update_job_status(
            job_id,
            JobStatus.INDEXING,
            progress=0.2,
            progress_message=f"Indexed {index.info.total_words} words from {index.info.total_pages} pages",
            pdf_info=index.info,
        )

        # Step 2: OCR if needed
        if index.info.pages_needing_ocr > 0 and settings.magic_import_ocr_enabled:
            job_manager.update_job_status(
                job_id,
                JobStatus.OCR,
                progress=0.25,
                progress_message=f"Running OCR on {index.info.pages_needing_ocr} scanned pages...",
            )

            ocr_processor = OCRProcessor()
            if ocr_processor.is_available:
                index = ocr_processor.process_scanned_pages(pdf_path, index)
                job_manager.save_index(index)

                job_manager.update_job_status(
                    job_id,
                    JobStatus.OCR,
                    progress=0.35,
                    progress_message=f"OCR complete: {index.info.total_words} total words",
                    pdf_info=index.info,
                )
            else:
                logger.warning("OCR needed but Tesseract not available")

        # Step 3: Resolve schema and get extraction hints
        job_manager.update_job_status(
            job_id,
            JobStatus.EXTRACTING,
            progress=0.4,
            progress_message="Resolving template schema...",
        )

        schema_resolver = SchemaResolver()
        hints = schema_resolver.resolve_hints(
            job.template_name,
            job.template_status,
            job.template_version,
        )

        logger.info("Resolved %d extraction hints for template %s", len(hints), job.template_name)

        # Step 4: Retrieve relevant snippets
        job_manager.update_job_status(
            job_id,
            JobStatus.EXTRACTING,
            progress=0.45,
            progress_message="Finding relevant document sections...",
        )

        retriever = SnippetRetriever()
        snippets = retriever.retrieve_snippets(index, hints)

        logger.info("Retrieved %d snippets for extraction", len(snippets))

        # Step 5: LLM extraction
        job_manager.update_job_status(
            job_id,
            JobStatus.EXTRACTING,
            progress=0.5,
            progress_message="Extracting field values with AI...",
        )

        extractor = Extractor()
        llm_extractions = extractor.extract_fields(hints, snippets)

        logger.info("LLM extracted %d fields", len(llm_extractions.extractions))

        # Step 6: Localize evidence (map quotes to bounding boxes)
        job_manager.update_job_status(
            job_id,
            JobStatus.LOCALIZING,
            progress=0.7,
            progress_message="Locating evidence in document...",
        )

        localizer = EvidenceLocalizer()
        hints_by_path = {hint.path: hint for hint in hints}
        extractions_with_evidence = localizer.localize_all(
            llm_extractions.extractions,
            index,
            hints_by_path=hints_by_path,
        )

        # Step 7: Score confidence
        job_manager.update_job_status(
            job_id,
            JobStatus.SCORING,
            progress=0.85,
            progress_message="Calculating confidence scores...",
        )

        scorer = ConfidenceScorer()
        final_extractions = scorer.score_all(
            extractions_with_evidence,
            index,
            settings.magic_import_confidence_threshold,
        )

        # Calculate summary statistics
        fields_needing_review = sum(1 for e in final_extractions if e.needs_review)
        avg_confidence = (
            sum(e.confidence for e in final_extractions) / len(final_extractions)
            if final_extractions
            else 0.0
        )

        processing_time = time.time() - start_time

        # Save result
        result = MagicImportResult(
            job_id=job_id,
            template_name=job.template_name,
            extractions=final_extractions,
            fields_extracted=len(final_extractions),
            fields_needing_review=fields_needing_review,
            average_confidence=avg_confidence,
            llm_provider=settings.magic_import_llm_provider,
            llm_model=settings.magic_import_llm_model,
            processing_time_seconds=processing_time,
        )
        job_manager.save_result(result)

        # Mark job as done
        job_manager.update_job_status(
            job_id,
            JobStatus.DONE,
            progress=1.0,
            progress_message=f"Extracted {len(final_extractions)} fields ({fields_needing_review} need review)",
        )

        logger.info(
            "Job %s complete: %d fields, %.1f%% avg confidence, %.1fs",
            job_id,
            len(final_extractions),
            avg_confidence * 100,
            processing_time,
        )

        return {
            "job_id": job_id,
            "status": "done",
            "fields_extracted": len(final_extractions),
            "fields_needing_review": fields_needing_review,
            "average_confidence": avg_confidence,
            "processing_time_seconds": processing_time,
        }

    except Exception as e:
        logger.exception("Job %s failed", job_id)
        job_manager.update_job_status(
            job_id,
            JobStatus.FAILED,
            error_message=str(e),
        )
        return {"error": str(e), "job_id": job_id}


@shared_task(name="magic_import.cleanup_expired")
def cleanup_expired_jobs() -> dict:
    """Periodic task to clean up expired jobs."""
    from app.services.magic_import.job_manager import JobManager

    job_manager = JobManager()
    deleted = job_manager.cleanup_expired_jobs()
    return {"deleted_count": deleted}
