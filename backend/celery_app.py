"""
Celery application configuration for background task processing.

This module sets up Celery with Redis as the message broker and result backend.
Supports both Magic Import and Dataspace connectivity background tasks.
"""

from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()

# Create Celery app
celery_app = Celery(
    "idta_submodel_editor",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Task execution settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_time_limit=600,  # 10 minutes max per task
    task_soft_time_limit=540,  # 9 minutes soft limit
    # Worker settings
    worker_prefetch_multiplier=1,
    worker_concurrency=2,
    # Result settings
    result_expires=3600,  # Results expire after 1 hour
    # Retry settings
    task_default_retry_delay=30,
    task_max_retries=3,
)

# Auto-discover tasks from both magic_import and dataspace modules
celery_app.autodiscover_tasks([
    "app.services.magic_import",
    "app.services.dataspace",
])

# Celery Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    # Periodic health check for all dataspace connections
    # Runs every 5 minutes to monitor connection health
    "dataspace-health-check-all": {
        "task": "dataspace.health_check_all",
        "schedule": crontab(minute="*/5"),
        "options": {
            "expires": 240,  # Task expires after 4 minutes if not started
        },
    },
    # Cleanup expired Magic Import jobs
    # Runs daily at 3 AM UTC
    "magic-import-cleanup-expired": {
        "task": "magic_import.cleanup_expired",
        "schedule": crontab(hour=3, minute=0),
        "options": {
            "expires": 3600,  # Task expires after 1 hour
        },
    },
}


@celery_app.task(bind=True, name="celery.health_check")
def health_check(self):
    """Health check task for monitoring Celery workers."""
    return {"status": "healthy", "worker_id": self.request.id}


@celery_app.task(bind=True, name="magic_import.health_check")
def magic_import_health_check(self):
    """Health check task for Magic Import workers (backward compatibility)."""
    return {"status": "healthy", "worker_id": self.request.id}
