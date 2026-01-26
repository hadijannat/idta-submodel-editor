"""Prometheus metrics for observability.

Provides custom metrics for:
- Magic Import job processing
- Dataspace publications
- Template fetching
- Semantic lookups
"""

import time
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Generator

from prometheus_client import Counter, Histogram, Info

# Application info
app_info = Info("idta_submodel_editor", "IDTA Submodel Editor application info")

# Magic Import metrics
magic_import_jobs_total = Counter(
    "magic_import_jobs_total",
    "Total number of Magic Import jobs by status and template",
    ["status", "template_name"],
)

magic_import_job_duration_seconds = Histogram(
    "magic_import_job_duration_seconds",
    "Time spent processing Magic Import jobs",
    ["template_name"],
    buckets=(1, 5, 10, 30, 60, 120, 300, 600),  # up to 10 minutes
)

# Dataspace publication metrics
dataspace_publications_total = Counter(
    "dataspace_publications_total",
    "Total number of dataspace publications by status and environment",
    ["status", "environment"],
)

dataspace_publication_duration_seconds = Histogram(
    "dataspace_publication_duration_seconds",
    "Time spent publishing to dataspace",
    ["environment"],
    buckets=(0.5, 1, 2, 5, 10, 30, 60),
)

# Template fetch metrics
template_fetch_total = Counter(
    "template_fetch_total",
    "Total number of template fetches by source and cache status",
    ["source", "cache_hit"],
)

template_fetch_duration_seconds = Histogram(
    "template_fetch_duration_seconds",
    "Time spent fetching templates",
    ["source"],
    buckets=(0.1, 0.5, 1, 2, 5, 10, 30),
)

# Semantic lookup metrics
semantic_lookup_total = Counter(
    "semantic_lookup_total",
    "Total number of semantic lookups by provider and cache status",
    ["provider", "cache_hit"],
)

semantic_lookup_duration_seconds = Histogram(
    "semantic_lookup_duration_seconds",
    "Time spent on semantic lookups",
    ["provider"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)

# Validation metrics
validation_total = Counter(
    "validation_total",
    "Total number of form validations by result",
    ["template_name", "result"],  # result: pass, error, warning
)

# Export metrics
export_total = Counter(
    "export_total",
    "Total number of exports by format and template",
    ["format", "template_name"],
)


def set_app_info(version: str, environment: str) -> None:
    """Set application info labels."""
    app_info.info({"version": version, "environment": environment})


@contextmanager
def track_duration(histogram: Histogram, **labels: str) -> Generator[None, None, None]:
    """Context manager to track duration with a histogram.

    Usage:
        with track_duration(magic_import_job_duration_seconds, template_name="PCF"):
            # do work
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        duration = time.perf_counter() - start
        histogram.labels(**labels).observe(duration)


def timed(histogram: Histogram, label_getter: Callable[[Any], dict[str, str]] | None = None):
    """Decorator to track function execution time.

    Args:
        histogram: Prometheus histogram to record timing
        label_getter: Optional function to extract labels from args

    Usage:
        @timed(magic_import_job_duration_seconds, lambda args: {"template_name": args[0]})
        def process_job(template_name: str):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            labels = label_getter(args) if label_getter else {}
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                duration = time.perf_counter() - start
                histogram.labels(**labels).observe(duration)
        return wrapper
    return decorator


# Convenience functions for common metric operations
def record_magic_import_job(status: str, template_name: str) -> None:
    """Record a Magic Import job completion."""
    magic_import_jobs_total.labels(status=status, template_name=template_name).inc()


def record_dataspace_publication(status: str, environment: str) -> None:
    """Record a dataspace publication."""
    dataspace_publications_total.labels(status=status, environment=environment).inc()


def record_template_fetch(source: str, cache_hit: bool) -> None:
    """Record a template fetch."""
    template_fetch_total.labels(source=source, cache_hit=str(cache_hit).lower()).inc()


def record_semantic_lookup(provider: str, cache_hit: bool) -> None:
    """Record a semantic lookup."""
    semantic_lookup_total.labels(provider=provider, cache_hit=str(cache_hit).lower()).inc()


def record_validation(template_name: str, has_errors: bool, has_warnings: bool) -> None:
    """Record a validation result."""
    if has_errors:
        result = "error"
    elif has_warnings:
        result = "warning"
    else:
        result = "pass"
    validation_total.labels(template_name=template_name, result=result).inc()


def record_export(format_type: str, template_name: str) -> None:
    """Record an export."""
    export_total.labels(format=format_type, template_name=template_name).inc()
