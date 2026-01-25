"""
Celery application configuration for background task processing.

This module sets up Celery with Redis as the message broker and result backend.
"""

from celery import Celery

from app.config import get_settings

settings = get_settings()

# Create Celery app
celery_app = Celery(
    "magic_import",
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

# Auto-discover tasks from the magic_import module
celery_app.autodiscover_tasks(["app.services.magic_import"])


@celery_app.task(bind=True, name="magic_import.health_check")
def health_check(self):
    """Health check task for monitoring."""
    return {"status": "healthy", "worker_id": self.request.id}
