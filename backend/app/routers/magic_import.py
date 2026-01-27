"""Magic Import API endpoints."""

from __future__ import annotations

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.config import get_settings
from app.dependencies import get_current_user
from app.errors import APIError, ErrorCode
from app.schemas.magic_import import (
    EvidenceQuality,
    ExtractionOutcome,
    FieldTypeCategory,
    JobStatus,
    MagicImportJob,
    MagicImportResult,
    QualityMetrics,
    ReExtractRequest,
)
from app.services.magic_import.job_manager import JobManager
from app.services.magic_import.outcome_tracker import OutcomeTracker
from app.utils.upload_security import FileType, UploadValidator, read_upload_file

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/magic-import", tags=["magic-import"])


class RecordCorrectionRequest(BaseModel):
    """Request model for recording a user correction."""

    path: str = Field(description="idShortPath of the field")
    final_value: str | None = Field(description="Final value after user correction")
    action: Literal["accepted", "edited", "deleted", "rejected"] = Field(
        description="Action taken by user on extraction"
    )
    # These fields come from the existing extraction
    original_value: str | None = Field(
        default=None, description="Original extracted value"
    )
    original_confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Confidence of original extraction"
    )
    had_evidence: bool = Field(
        default=False, description="Whether original extraction had evidence"
    )
    evidence_quality: EvidenceQuality = Field(
        default=EvidenceQuality.NONE,
        description="Quality of evidence for original extraction",
    )
    field_type: FieldTypeCategory = Field(
        default=FieldTypeCategory.TEXT_SHORT, description="Category of the field type"
    )
    was_required: bool = Field(
        default=False, description="Whether the field was required"
    )


def get_job_manager() -> JobManager:
    """Get job manager instance."""
    return JobManager()


@router.post("/jobs", response_model=MagicImportJob)
async def create_job(
    file: Annotated[UploadFile, File(...)],
    template_name: Annotated[str, Form()],
    template_status: Annotated[str, Form()] = "published",
    template_version: Annotated[str | None, Form()] = None,
    job_manager: Annotated[JobManager, Depends(get_job_manager)] = None,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> MagicImportJob:
    """
    Create a new Magic Import job by uploading a PDF.

    This starts background processing to extract data from the PDF
    and map it to the specified IDTA template.
    """
    settings = get_settings()

    if not settings.magic_import_enabled:
        raise APIError(
            code=ErrorCode.FEATURE_DISABLED,
            message="Magic Import is disabled",
        )

    # Read file content with size limit
    content = await read_upload_file(
        file,
        max_size_bytes=settings.magic_import_max_pdf_size_mb * 1024 * 1024,
    )

    # Validate upload with magic bytes checking
    validator = UploadValidator(
        allowed_types=[FileType.PDF],
        max_size_bytes=settings.magic_import_max_pdf_size_mb * 1024 * 1024,
    )
    validator.validate_and_raise(content, file.filename)

    try:
        idempotency_key = job_manager.compute_idempotency_key(
            content, template_name, template_status, template_version
        )
        existing = job_manager.find_by_idempotency_key(idempotency_key)
        if existing is not None and existing.status != JobStatus.FAILED:
            logger.info(
                "Reusing Magic Import job %s for idempotency key %s",
                existing.job_id,
                idempotency_key[:8],
            )

            # If the job never advanced beyond UPLOADED, re-queue it to avoid stuck states
            if existing.status == JobStatus.UPLOADED:
                try:
                    from app.services.magic_import.tasks import process_magic_import_job

                    process_magic_import_job.delay(existing.job_id)
                    logger.info("Re-queued stale uploaded job %s", existing.job_id)
                except Exception as e:
                    logger.warning("Celery unavailable, processing synchronously: %s", e)
                    from app.services.magic_import.tasks import process_magic_import_job

                    process_magic_import_job(existing.job_id)

            return existing

        # Create job
        job = job_manager.create_job(
            pdf_content=content,
            pdf_filename=file.filename,
            template_name=template_name,
            template_status=template_status,
            template_version=template_version,
        )

        # Queue background processing
        try:
            from app.services.magic_import.tasks import process_magic_import_job

            process_magic_import_job.delay(job.job_id)
            logger.info("Queued job %s for processing", job.job_id)
        except Exception as e:
            # If Celery is unavailable, run synchronously (for dev/testing)
            logger.warning("Celery unavailable, processing synchronously: %s", e)
            from app.services.magic_import.tasks import process_magic_import_job

            process_magic_import_job(job.job_id)

        return job

    except APIError:
        raise
    except Exception as e:
        logger.exception("Failed to create Magic Import job")
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to create Magic Import job",
            detail={"error": str(e)},
        )


@router.get("/jobs/{job_id}", response_model=MagicImportJob)
async def get_job(
    job_id: str,
    job_manager: Annotated[JobManager, Depends(get_job_manager)] = None,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> MagicImportJob:
    """Get the status of a Magic Import job."""
    job = job_manager.get_job(job_id)
    if job is None:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Job not found",
            detail={"job_id": job_id},
        )
    return job


@router.get("/jobs/{job_id}/result", response_model=MagicImportResult)
async def get_job_result(
    job_id: str,
    job_manager: Annotated[JobManager, Depends(get_job_manager)] = None,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> MagicImportResult:
    """Get the extraction results for a completed job."""
    job = job_manager.get_job(job_id)
    if job is None:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Job not found",
            detail={"job_id": job_id},
        )

    if job.status != JobStatus.DONE:
        raise APIError(
            code=ErrorCode.BAD_REQUEST,
            message=f"Job is not complete. Current status: {job.status}",
            detail={"job_id": job_id, "status": job.status},
        )

    result = job_manager.load_result(job_id)
    if result is None:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Result not found",
            detail={"job_id": job_id},
        )

    return result


@router.post("/jobs/{job_id}/reextract", response_model=MagicImportResult)
async def reextract_fields(
    job_id: str,
    request: ReExtractRequest,
    job_manager: Annotated[JobManager, Depends(get_job_manager)] = None,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> MagicImportResult:
    """
    Re-extract specific fields from an existing job.

    This runs extraction only for the specified paths, optionally
    with a hint to guide the LLM, and updates the result.
    """
    settings = get_settings()

    if not settings.magic_import_enabled:
        raise APIError(
            code=ErrorCode.FEATURE_DISABLED,
            message="Magic Import is disabled",
        )

    # Verify job exists and is complete
    job = job_manager.get_job(job_id)
    if job is None:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Job not found",
            detail={"job_id": job_id},
        )

    if job.status != JobStatus.DONE:
        raise APIError(
            code=ErrorCode.BAD_REQUEST,
            message="Can only re-extract from completed jobs",
            detail={"job_id": job_id, "status": job.status},
        )

    # Load existing result and index
    result = job_manager.load_result(job_id)
    if result is None:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Result not found",
            detail={"job_id": job_id},
        )

    index = job_manager.load_index(job_id)
    if index is None:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="PDF index not found - cannot re-extract",
            detail={"job_id": job_id},
        )

    try:
        from app.services.magic_import.schema_resolver import SchemaResolver
        from app.services.magic_import.retriever import SnippetRetriever
        from app.services.magic_import.extractor import Extractor
        from app.services.magic_import.localizer import EvidenceLocalizer
        from app.services.magic_import.scorer import ConfidenceScorer

        # Resolve hints only for requested paths
        schema_resolver = SchemaResolver()
        all_hints = schema_resolver.resolve_hints(
            job.template_name,
            job.template_status,
            job.template_version,
        )
        hints = [h for h in all_hints if h.path in request.paths]

        if not hints:
            raise APIError(
                code=ErrorCode.BAD_REQUEST,
                message="No valid paths to re-extract",
                detail={"paths": request.paths},
            )

        # Add user hint if provided
        if request.hint:
            for hint in hints:
                hint.user_hint = request.hint

        # Retrieve snippets and re-extract
        retriever = SnippetRetriever()
        snippets = retriever.retrieve_snippets(index, hints)

        extractor = Extractor()
        llm_extractions = extractor.extract_fields(hints, snippets)

        # Localize evidence
        localizer = EvidenceLocalizer()
        hints_by_path = {h.path: h for h in hints}
        extractions_with_evidence = localizer.localize_all(
            llm_extractions.extractions,
            index,
            hints_by_path=hints_by_path,
        )

        # Score confidence
        scorer = ConfidenceScorer()
        new_extractions = scorer.score_all(
            extractions_with_evidence,
            index,
            settings.magic_import_confidence_threshold,
        )

        # Merge new extractions into existing result
        new_paths = {e.path for e in new_extractions}
        merged_extractions = [
            e for e in result.extractions if e.path not in new_paths
        ] + new_extractions

        # Re-validate merged result
        from app.services.magic_import.validator import ExtractionValidator

        validator = ExtractionValidator()
        validation_result = validator.validate_extractions(
            merged_extractions,
            job.template_name,
            job.template_status,
            job.template_version,
            mode="strict",
        )

        # Update statistics
        fields_needing_review = sum(1 for e in merged_extractions if e.needs_review)
        avg_confidence = (
            sum(e.confidence for e in merged_extractions) / len(merged_extractions)
            if merged_extractions
            else 0.0
        )

        # Create updated result
        updated_result = MagicImportResult(
            job_id=job_id,
            template_name=result.template_name,
            extractions=merged_extractions,
            fields_extracted=len(merged_extractions),
            fields_needing_review=fields_needing_review,
            average_confidence=avg_confidence,
            llm_provider=result.llm_provider,
            llm_model=result.llm_model,
            processing_time_seconds=result.processing_time_seconds,
            validation_result=validation_result,
            template_version_used=result.template_version_used,
        )

        # Save updated result
        job_manager.save_result(updated_result)

        logger.info(
            "Re-extracted %d fields for job %s: %s",
            len(new_extractions),
            job_id,
            request.paths,
        )

        return updated_result

    except APIError:
        raise
    except Exception as e:
        logger.exception("Failed to re-extract fields for job %s", job_id)
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to re-extract fields",
            detail={"error": str(e)},
        )


@router.get("/jobs/{job_id}/pdf")
async def get_job_pdf(
    job_id: str,
    job_manager: Annotated[JobManager, Depends(get_job_manager)] = None,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> FileResponse:
    """Get the PDF file for a job (for viewer)."""
    job = job_manager.get_job(job_id)
    if job is None:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Job not found",
            detail={"job_id": job_id},
        )

    pdf_path = job_manager.get_pdf_path(job_id)
    if pdf_path is None:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="PDF file not found",
            detail={"job_id": job_id},
        )

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=job.pdf_filename,
    )


@router.delete("/jobs/{job_id}")
async def delete_job(
    job_id: str,
    job_manager: Annotated[JobManager, Depends(get_job_manager)] = None,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> dict:
    """Delete a Magic Import job and all associated files."""
    if not job_manager.delete_job(job_id):
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Job not found",
            detail={"job_id": job_id},
        )
    return {"deleted": job_id}


@router.get("/jobs", response_model=list[MagicImportJob])
async def list_jobs(
    limit: int = 50,
    status: JobStatus | None = None,
    job_manager: Annotated[JobManager, Depends(get_job_manager)] = None,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> list[MagicImportJob]:
    """List recent Magic Import jobs."""
    return job_manager.list_jobs(limit=limit, status=status)


@router.get("/provider-status")
async def get_provider_status(
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> dict:
    """
    Quick status check for Magic Import panel.

    Returns current provider configuration and health status.
    """
    from app.services import settings_service
    from app.services.magic_import.llm.factory import get_available_providers

    settings = get_settings()

    # Check if any provider is configured
    available = get_available_providers()

    if not available:
        return {
            "configured": False,
            "provider": None,
            "model": None,
            "healthy": False,
            "message": "No LLM provider configured",
        }

    # Get active provider from settings service
    active_provider = settings_service.get_effective_provider()

    # If active provider is not available, fall back to first available
    if active_provider not in available:
        active_provider = available[0]

    model = settings_service.get_effective_model(active_provider)

    # Quick health check
    healthy = True
    message = "Ready"

    try:
        from app.services.magic_import.llm.factory import get_provider

        provider = get_provider()
        if not provider.is_available():
            healthy = False
            message = f"{active_provider.title()} API key not configured"
    except Exception as e:
        healthy = False
        message = str(e)[:100]

    return {
        "configured": True,
        "provider": active_provider,
        "model": model,
        "healthy": healthy,
        "message": message,
        "available_providers": available,
    }


@router.post("/health")
async def health_check() -> dict:
    """Check if Magic Import service is healthy."""
    settings = get_settings()

    status = {
        "enabled": settings.magic_import_enabled,
        "llm_provider": settings.magic_import_llm_provider,
        "llm_model": settings.magic_import_llm_model,
        "ocr_enabled": settings.magic_import_ocr_enabled,
        "celery_available": False,
    }

    # Check Celery connectivity
    try:
        from celery_app import celery_app

        result = celery_app.control.ping(timeout=1.0)
        status["celery_available"] = bool(result)
    except Exception as e:
        logger.debug("Celery health check failed: %s", e)

    return status


# ============================================================================
# Quality Metrics Endpoints
# ============================================================================


@router.get("/jobs/{job_id}/quality-metrics", response_model=QualityMetrics)
async def get_quality_metrics(
    job_id: str,
    job_manager: Annotated[JobManager, Depends(get_job_manager)] = None,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> QualityMetrics:
    """Get quality metrics for a completed job."""
    # Check job exists and is DONE
    job = job_manager.get_job(job_id)
    if job is None:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Job not found",
            detail={"job_id": job_id},
        )

    if job.status != JobStatus.DONE:
        raise APIError(
            code=ErrorCode.BAD_REQUEST,
            message=f"Job is not complete. Current status: {job.status}",
            detail={"job_id": job_id, "status": job.status},
        )

    # Load quality_metrics artifact
    metrics_data = job_manager.load_artifact(job_id, "quality_metrics")
    if metrics_data is None:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Quality metrics not found for this job",
            detail={"job_id": job_id},
        )

    return QualityMetrics.model_validate(metrics_data)


@router.post("/jobs/{job_id}/corrections", response_model=ExtractionOutcome)
async def record_correction(
    job_id: str,
    request: RecordCorrectionRequest,
    job_manager: Annotated[JobManager, Depends(get_job_manager)] = None,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> ExtractionOutcome:
    """Record a user correction for a field extraction."""
    # Check job exists
    job = job_manager.get_job(job_id)
    if job is None:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Job not found",
            detail={"job_id": job_id},
        )

    # Use OutcomeTracker to record correction
    tracker = OutcomeTracker()
    outcome = tracker.record_correction(
        job_id=job_id,
        field_path=request.path,
        original_value=request.original_value,
        final_value=request.final_value,
        original_confidence=request.original_confidence,
        action=request.action,
        had_evidence=request.had_evidence,
        evidence_quality=request.evidence_quality,
        field_type=request.field_type,
        was_required=request.was_required,
        template_name=job.template_name,
        template_status=job.template_status,
        template_version=job.template_version,
    )

    return outcome


@router.get("/analytics/correction-rates")
async def get_correction_rates(
    template_name: str | None = None,
    days: int = 30,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> dict:
    """
    Get historical correction rates for threshold tuning.

    Returns correction rates grouped by confidence bucket to help
    determine optimal confidence thresholds for auto-apply features.

    Args:
        template_name: Optional filter by template name
        days: Number of days to look back (default 30)

    Returns:
        Dict with bucket names as keys, containing total, accepted,
        edited, deleted, rejected counts and correction_rate.
    """
    tracker = OutcomeTracker()
    return tracker.compute_correction_rates(
        template_name=template_name,
        days=days,
    )
