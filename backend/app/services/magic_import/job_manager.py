"""
Job Manager - Manages Magic Import job state and persistence.

Handles job lifecycle: UPLOADED → INDEXING → OCR → EXTRACTING → LOCALIZING → SCORING → DONE
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from app.config import get_settings
from app.schemas.magic_import import (
    JobStatus,
    MagicImportJob,
    MagicImportResult,
    PDFIndex,
    PDFIndexInfo,
    FieldExtraction,
)

logger = logging.getLogger(__name__)


class JobManager:
    """Manages Magic Import job state and file storage."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_dir = self.settings.magic_import_cache_dir
        self.jobs_dir = self.base_dir / "jobs"
        self.pdfs_dir = self.base_dir / "pdfs"
        self.indices_dir = self.base_dir / "indices"
        self.results_dir = self.base_dir / "results"

        # Ensure directories exist
        for dir_path in [self.jobs_dir, self.pdfs_dir, self.indices_dir, self.results_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

    def create_job(
        self,
        pdf_content: bytes,
        pdf_filename: str,
        template_name: str,
        template_status: str = "published",
        template_version: str | None = None,
    ) -> MagicImportJob:
        """
        Create a new Magic Import job.

        Args:
            pdf_content: Raw PDF bytes
            pdf_filename: Original filename
            template_name: Target template name
            template_status: Template status (published/deprecated)
            template_version: Optional template version

        Returns:
            Created job object
        """
        job_id = uuid.uuid4().hex
        now = datetime.utcnow()

        # Save PDF file
        pdf_path = self.pdfs_dir / f"{job_id}.pdf"
        pdf_path.write_bytes(pdf_content)

        job = MagicImportJob(
            job_id=job_id,
            status=JobStatus.UPLOADED,
            template_name=template_name,
            template_status=template_status,
            template_version=template_version,
            pdf_filename=pdf_filename,
            pdf_size_bytes=len(pdf_content),
            created_at=now,
            updated_at=now,
            progress=0.0,
            progress_message="Job created",
        )

        self._save_job(job)
        logger.info("Created job %s for %s", job_id, pdf_filename)
        return job

    def get_job(self, job_id: str) -> MagicImportJob | None:
        """Get a job by ID."""
        job_path = self.jobs_dir / f"{job_id}.json"
        if not job_path.exists():
            return None

        data = json.loads(job_path.read_text())
        return MagicImportJob(**data)

    def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        progress: float | None = None,
        progress_message: str | None = None,
        error_message: str | None = None,
        pdf_info: PDFIndexInfo | None = None,
    ) -> MagicImportJob | None:
        """Update job status and optional fields."""
        job = self.get_job(job_id)
        if job is None:
            return None

        update_data = {"status": status, "updated_at": datetime.utcnow()}
        if progress is not None:
            update_data["progress"] = progress
        if progress_message is not None:
            update_data["progress_message"] = progress_message
        if error_message is not None:
            update_data["error_message"] = error_message
        if pdf_info is not None:
            update_data["pdf_info"] = pdf_info

        job = job.model_copy(update=update_data)
        self._save_job(job)

        logger.info("Updated job %s: status=%s, progress=%.2f", job_id, status, job.progress)
        return job

    def save_index(self, index: PDFIndex) -> None:
        """Save PDF index to disk."""
        index_path = self.indices_dir / f"{index.job_id}.json"
        index_path.write_text(index.model_dump_json(indent=2))
        logger.debug("Saved index for job %s", index.job_id)

    def load_index(self, job_id: str) -> PDFIndex | None:
        """Load PDF index from disk."""
        index_path = self.indices_dir / f"{job_id}.json"
        if not index_path.exists():
            return None

        data = json.loads(index_path.read_text())
        return PDFIndex(**data)

    def save_result(self, result: MagicImportResult) -> None:
        """Save extraction result to disk."""
        result_path = self.results_dir / f"{result.job_id}.json"
        result_path.write_text(result.model_dump_json(indent=2))
        logger.debug("Saved result for job %s", result.job_id)

    def load_result(self, job_id: str) -> MagicImportResult | None:
        """Load extraction result from disk."""
        result_path = self.results_dir / f"{job_id}.json"
        if not result_path.exists():
            return None

        data = json.loads(result_path.read_text())
        return MagicImportResult(**data)

    def get_pdf_path(self, job_id: str) -> Path | None:
        """Get path to PDF file for a job."""
        pdf_path = self.pdfs_dir / f"{job_id}.pdf"
        if not pdf_path.exists():
            return None
        return pdf_path

    def delete_job(self, job_id: str) -> bool:
        """Delete a job and all associated files."""
        deleted = False

        # Delete job file
        job_path = self.jobs_dir / f"{job_id}.json"
        if job_path.exists():
            job_path.unlink()
            deleted = True

        # Delete PDF
        pdf_path = self.pdfs_dir / f"{job_id}.pdf"
        if pdf_path.exists():
            pdf_path.unlink()

        # Delete index
        index_path = self.indices_dir / f"{job_id}.json"
        if index_path.exists():
            index_path.unlink()

        # Delete result
        result_path = self.results_dir / f"{job_id}.json"
        if result_path.exists():
            result_path.unlink()

        if deleted:
            logger.info("Deleted job %s", job_id)

        return deleted

    def cleanup_expired_jobs(self) -> int:
        """Remove jobs older than TTL. Returns number of jobs deleted."""
        ttl_hours = self.settings.magic_import_job_ttl_hours
        cutoff = datetime.utcnow() - timedelta(hours=ttl_hours)
        deleted_count = 0

        for job_path in self.jobs_dir.glob("*.json"):
            try:
                data = json.loads(job_path.read_text())
                job = MagicImportJob(**data)

                if job.created_at < cutoff:
                    self.delete_job(job.job_id)
                    deleted_count += 1

            except Exception as e:
                logger.warning("Failed to check job %s: %s", job_path.stem, e)

        if deleted_count > 0:
            logger.info("Cleaned up %d expired jobs", deleted_count)

        return deleted_count

    def list_jobs(
        self,
        limit: int = 50,
        status: JobStatus | None = None,
    ) -> list[MagicImportJob]:
        """List recent jobs, optionally filtered by status."""
        jobs: list[MagicImportJob] = []

        for job_path in self.jobs_dir.glob("*.json"):
            try:
                data = json.loads(job_path.read_text())
                job = MagicImportJob(**data)

                if status is None or job.status == status:
                    jobs.append(job)

            except Exception as e:
                logger.warning("Failed to load job %s: %s", job_path.stem, e)

        # Sort by created_at descending
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs[:limit]

    def _save_job(self, job: MagicImportJob) -> None:
        """Save job to disk."""
        job_path = self.jobs_dir / f"{job.job_id}.json"
        job_path.write_text(job.model_dump_json(indent=2))
