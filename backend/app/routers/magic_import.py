"""Magic Import API endpoints."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response

from app.config import get_settings
from app.dependencies import get_current_user
from app.schemas.magic_import import (
    JobStatus,
    MagicImportJob,
    MagicImportJobCreate,
    MagicImportResult,
    MagicImportApplyRequest,
)
from app.services.magic_import.job_manager import JobManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/magic-import", tags=["magic-import"])


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
        raise HTTPException(status_code=503, detail="Magic Import is disabled")

    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    # Validate content type
    if file.content_type and "pdf" not in file.content_type.lower():
        raise HTTPException(status_code=400, detail="Invalid content type, expected PDF")

    # Read and validate file size
    content = await file.read()
    max_size = settings.magic_import_max_pdf_size_mb * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {settings.magic_import_max_pdf_size_mb}MB",
        )

    try:
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

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to create Magic Import job")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/{job_id}", response_model=MagicImportJob)
async def get_job(
    job_id: str,
    job_manager: Annotated[JobManager, Depends(get_job_manager)] = None,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> MagicImportJob:
    """Get the status of a Magic Import job."""
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
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
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != JobStatus.DONE:
        raise HTTPException(
            status_code=400,
            detail=f"Job is not complete. Current status: {job.status}",
        )

    result = job_manager.load_result(job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")

    return result


@router.get("/jobs/{job_id}/pdf")
async def get_job_pdf(
    job_id: str,
    job_manager: Annotated[JobManager, Depends(get_job_manager)] = None,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> FileResponse:
    """Get the PDF file for a job (for viewer)."""
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    pdf_path = job_manager.get_pdf_path(job_id)
    if pdf_path is None:
        raise HTTPException(status_code=404, detail="PDF file not found")

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
        raise HTTPException(status_code=404, detail="Job not found")
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
