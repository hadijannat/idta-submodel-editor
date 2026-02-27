"""Magic Import API endpoints."""

from __future__ import annotations

import json
import logging
import tempfile
import uuid
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from app.config import get_settings
from app.dependencies import get_current_user
from app.errors import APIError, ErrorCode
from app.schemas.magic_import import (
    EvidenceQuality,
    ExtractionOutcome,
    FieldTypeCategory,
    JobStatus,
    MagicImportPreviewResponse,
    MagicImportJob,
    MagicImportResult,
    QualityMetrics,
    ReExtractRequest,
    Snippet,
    SnippetPreview,
)
from app.services.magic_import.audit_report import AuditReport, AuditReportGenerator
from app.services.magic_import.job_manager import JobManager
from app.services.magic_import.outcome_tracker import OutcomeTracker
from app.utils.upload_security import FileType, UploadValidator, read_upload_file

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/magic-import", tags=["magic-import"])
PYDANTIC_PROTECTED_NAMESPACES = ("model_validate", "model_dump")


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


def _estimate_snippet_tokens(snippets: list[Snippet]) -> int:
    """Estimate token usage for snippet payloads."""
    total_words = sum(len(snippet.text.split()) for snippet in snippets)
    # Conservative approximation for mixed technical docs.
    return max(1, int(total_words * 1.3))


def _parse_snippet_overrides(raw: str | None) -> list[Snippet] | None:
    """Parse and validate user-edited snippet overrides from form input."""
    if raw is None:
        return None
    if not raw.strip():
        return []

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise APIError(
            code=ErrorCode.INVALID_ARGUMENT,
            message="Invalid snippet override payload",
            detail={"error": str(exc)},
        ) from exc

    if not isinstance(payload, list):
        raise APIError(
            code=ErrorCode.INVALID_ARGUMENT,
            message="Snippet overrides must be a JSON list",
        )

    parsed: list[Snippet] = []
    for item in payload:
        try:
            parsed.append(Snippet.model_validate(item))
        except Exception as exc:
            raise APIError(
                code=ErrorCode.INVALID_ARGUMENT,
                message="Snippet override entry is invalid",
                detail={"error": str(exc)},
            ) from exc
    return parsed


@router.post("/jobs/preview", response_model=MagicImportPreviewResponse)
async def preview_job(
    file: Annotated[UploadFile, File(...)],
    template_name: Annotated[str, Form()],
    template_status: Annotated[str, Form()] = "published",
    template_version: Annotated[str | None, Form()] = None,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> MagicImportPreviewResponse:
    """
    Preview the exact snippets that would be sent to the LLM.

    Enables user review/redaction before creating an extraction job.
    """
    settings = get_settings()

    if not settings.magic_import_enabled:
        raise APIError(
            code=ErrorCode.FEATURE_DISABLED,
            message="Magic Import is disabled",
        )

    content = await read_upload_file(
        file,
        max_size_bytes=settings.magic_import_max_pdf_size_mb * 1024 * 1024,
    )
    validator = UploadValidator(
        allowed_types=[FileType.PDF],
        max_size_bytes=settings.magic_import_max_pdf_size_mb * 1024 * 1024,
    )
    validator.validate_and_raise(content, file.filename)

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
            temp_file.write(content)
            temp_path = Path(temp_file.name)

        from app.services.magic_import.pdf_indexer import PDFIndexer
        from app.services.magic_import.retriever import SnippetRetriever
        from app.services.magic_import.schema_resolver import SchemaResolver

        indexer = PDFIndexer()
        index = indexer.index_pdf(temp_path, f"preview-{uuid.uuid4().hex}")

        resolver = SchemaResolver()
        hints = resolver.resolve_hints(
            template_name,
            template_status,
            template_version,
        )

        retriever = SnippetRetriever()
        max_total_snippets = min(200, max(50, len(hints)))
        snippets = retriever.retrieve_snippets(
            index=index,
            hints=hints,
            max_total_snippets=max_total_snippets,
            max_snippets_per_field=3,
        )

        preview_items = [
            SnippetPreview(
                snippet_id=f"snippet-{idx + 1}",
                text=snippet.text,
                page=snippet.page,
                start_word_idx=snippet.start_word_idx,
                end_word_idx=snippet.end_word_idx,
                score=snippet.score,
                context_before=snippet.context_before,
                context_after=snippet.context_after,
            )
            for idx, snippet in enumerate(snippets)
        ]

        return MagicImportPreviewResponse(
            template_name=template_name,
            snippet_count=len(preview_items),
            token_estimate=_estimate_snippet_tokens(snippets),
            snippets=preview_items,
        )
    except APIError:
        raise
    except Exception as e:
        logger.exception("Failed to build Magic Import preview")
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to generate preview snippets",
            detail={"error": str(e)},
        ) from e
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)


@router.post("/jobs", response_model=MagicImportJob)
async def create_job(
    file: Annotated[UploadFile, File(...)],
    template_name: Annotated[str, Form()],
    template_status: Annotated[str, Form()] = "published",
    template_version: Annotated[str | None, Form()] = None,
    snippet_overrides: Annotated[str | None, Form()] = None,
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

    parsed_snippet_overrides = _parse_snippet_overrides(snippet_overrides)

    try:
        idempotency_key = job_manager.compute_idempotency_key(
            content, template_name, template_status, template_version
        )
        existing = (
            None
            if parsed_snippet_overrides is not None
            else job_manager.find_by_idempotency_key(idempotency_key)
        )
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

        if parsed_snippet_overrides is not None:
            job_manager.save_artifact(
                job.job_id,
                "snippet_overrides",
                parsed_snippet_overrides,
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


class ProviderInfoResponse(BaseModel):
    """Detailed provider information."""

    name: str
    available: bool
    model: str | None
    is_local: bool
    privacy_note: str
    error: str | None = None


class ModelRecommendationResponse(BaseModel):
    """Model recommendation with system requirements."""

    model_config = ConfigDict(protected_namespaces=PYDANTIC_PROTECTED_NAMESPACES)

    model_id: str
    display_name: str
    description: str
    min_memory_gb: int
    recommended_memory_gb: int
    quality_tier: str
    parameters: str
    quantization: str | None
    is_available: bool = False


class ProviderDetailResponse(BaseModel):
    """Extended provider details with recommendations."""

    model_config = ConfigDict(protected_namespaces=PYDANTIC_PROTECTED_NAMESPACES)

    providers: list[ProviderInfoResponse]
    active_provider: str | None
    model_recommendations: dict[str, list[ModelRecommendationResponse]]
    fallback_supported: bool


@router.get("/providers/info", response_model=ProviderDetailResponse)
async def get_provider_info(
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> ProviderDetailResponse:
    """
    Get detailed information about all LLM providers.

    Includes:
    - Availability status for each provider
    - Privacy notes (local vs cloud)
    - Model recommendations for local provider
    - Fallback chain support
    """
    from app.services import settings_service
    from app.services.magic_import.llm.factory import get_provider_info
    from app.services.magic_import.llm.local_provider import (
        LocalProvider,
        RECOMMENDED_MODELS,
    )

    # Get provider info
    provider_infos = get_provider_info()

    # Get active provider
    active = settings_service.get_effective_provider()

    # Get model recommendations for local provider
    recommendations: dict[str, list[ModelRecommendationResponse]] = {}

    # Check which local models are available (independent of configured model)
    local_models: set[str] = set()
    try:
        base_url = settings_service.get_effective_base_url("local")
        local = LocalProvider(
            model=settings_service.get_effective_model("local"),
            base_url=base_url,
        )
        available_models = await local.list_available_models()
        local_models = {m.split(":")[0] for m in available_models if m}
    except Exception:
        pass

    for use_case, recs in RECOMMENDED_MODELS.items():
        recommendations[use_case] = [
            ModelRecommendationResponse(
                model_id=r.model_id,
                display_name=r.display_name,
                description=r.description,
                min_memory_gb=r.min_memory_gb,
                recommended_memory_gb=r.recommended_memory_gb,
                quality_tier=r.quality_tier,
                parameters=r.parameters,
                quantization=r.quantization,
                is_available=r.model_id.split(":")[0] in local_models,
            )
            for r in recs
        ]

    return ProviderDetailResponse(
        providers=[
            ProviderInfoResponse(
                name=p.name,
                available=p.available,
                model=p.model,
                is_local=p.is_local,
                privacy_note=p.privacy_note,
                error=p.error,
            )
            for p in provider_infos
        ],
        active_provider=active,
        model_recommendations=recommendations,
        fallback_supported=True,
    )


@router.post("/providers/select")
async def select_provider(
    provider: str = Query(..., description="Provider to select"),
    use_fallback: bool = Query(True, description="Enable fallback if unavailable"),
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> dict:
    """
    Select LLM provider for extraction.

    If use_fallback is True and the selected provider is unavailable,
    will attempt to use fallback providers in order.
    """
    from app.services import settings_service
    from app.services.magic_import.llm.factory import (
        DEFAULT_FALLBACK_ORDER,
        get_provider_with_fallback,
        get_available_providers,
    )

    valid_providers = ["openai", "anthropic", "openrouter", "local"]
    if provider not in valid_providers:
        raise APIError(
            code=ErrorCode.INVALID_ARGUMENT,
            message=f"Invalid provider: {provider}. Must be one of: {valid_providers}",
        )

    # Try to get the provider
    if use_fallback:
        preference = [provider] + [p for p in DEFAULT_FALLBACK_ORDER if p != provider]
        actual_provider, fallback_reason = get_provider_with_fallback(
            preference=preference
        )
        if actual_provider:
            settings_service.set_active_provider(actual_provider.name)
            return {
                "success": True,
                "selected_provider": provider,
                "active_provider": actual_provider.name,
                "model": actual_provider.model,
                "fallback_used": actual_provider.name != provider,
                "fallback_reason": fallback_reason,
            }
    else:
        available = get_available_providers()
        if provider in available:
            settings_service.set_active_provider(provider)
            return {
                "success": True,
                "selected_provider": provider,
                "active_provider": provider,
                "model": settings_service.get_effective_model(provider),
                "fallback_used": False,
                "fallback_reason": None,
            }

    return {
        "success": False,
        "selected_provider": provider,
        "active_provider": None,
        "model": None,
        "fallback_used": False,
        "fallback_reason": f"Provider {provider} not available",
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


# ============================================================================
# Audit Report Endpoints
# ============================================================================


@router.get("/jobs/{job_id}/audit-report")
async def get_audit_report(
    job_id: str,
    format: Annotated[
        Literal["json", "pdf"],
        Query(description="Report format (json or pdf)"),
    ] = "json",
    job_manager: Annotated[JobManager, Depends(get_job_manager)] = None,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> Response:
    """
    Generate an audit report for a completed Magic Import job.

    The audit report provides full traceability of AI extractions:
    - Field values with source quotes from the PDF
    - Page and bounding box locations
    - Confidence breakdown (LLM/Localizer/OCR/Rules)
    - Review status (approved/edited/needs_review)
    - Processing metadata (LLM provider, tokens used, timing)

    This enables "Auditable AI" - showing the reasoning and evidence
    behind each extraction for compliance and trust.

    Args:
        job_id: The Magic Import job ID
        format: Output format - "json" (default) or "pdf"

    Returns:
        Audit report in the requested format
    """
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

    # Load result
    result = job_manager.load_result(job_id)
    if result is None:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Result not found",
            detail={"job_id": job_id},
        )

    try:
        generator = AuditReportGenerator()
        content = generator.generate(job, result, format=format)

        if format == "json":
            return Response(
                content=content,
                media_type="application/json",
                headers={
                    "Content-Disposition": (
                        f'attachment; filename="audit-report-{job_id}.json"'
                    )
                },
            )
        else:  # pdf
            return Response(
                content=content,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": (
                        f'attachment; filename="audit-report-{job_id}.pdf"'
                    )
                },
            )
    except ValueError as e:
        # Specific error for missing dependencies (e.g., reportlab for PDF)
        raise APIError(
            code=ErrorCode.BAD_REQUEST,
            message=str(e),
            detail={"format": format, "suggestion": "Use format=json instead"},
        )
    except Exception as e:
        logger.exception("Failed to generate audit report for job %s", job_id)
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to generate audit report",
            detail={"error": str(e)},
        )


@router.get("/jobs/{job_id}/audit-report/preview", response_model=AuditReport)
async def preview_audit_report(
    job_id: str,
    job_manager: Annotated[JobManager, Depends(get_job_manager)] = None,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> AuditReport:
    """
    Get a preview of the audit report data without generating a file.

    Useful for displaying audit information in the UI before downloading.
    """
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

    # Load result
    result = job_manager.load_result(job_id)
    if result is None:
        raise APIError(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Result not found",
            detail={"job_id": job_id},
        )

    try:
        generator = AuditReportGenerator()
        return generator._build_report(job, result)
    except Exception as e:
        logger.exception("Failed to build audit report for job %s", job_id)
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to build audit report",
            detail={"error": str(e)},
        )


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
