"""
Conformance checking using aas-test-engines CLI.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import re
import subprocess
import time
from pathlib import Path

from app.errors import APIError, ErrorCode
from app.schemas.conformance import ConformanceIssue


@dataclass
class ConformanceResult:
    """Internal conformance result."""

    passed: bool
    errors: list[ConformanceIssue]
    warnings: list[ConformanceIssue]
    engine_version: str | None
    duration_ms: int
    format: str


@lru_cache(maxsize=1)
def get_engine_version() -> str | None:
    """Get aas-test-engines version once per process."""
    try:
        proc = subprocess.run(
            ["aas_test_engines", "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        output = (proc.stdout or proc.stderr or "").strip()
        return output or None
    except Exception:
        return None


def _parse_issues(output: str) -> tuple[list[ConformanceIssue], list[ConformanceIssue]]:
    errors: list[ConformanceIssue] = []
    warnings: list[ConformanceIssue] = []

    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if re.search(r"\b(error|failed|fail)\b", line, flags=re.IGNORECASE):
            errors.append(ConformanceIssue(level="error", message=line))
            continue
        if re.search(r"\bwarning\b", line, flags=re.IGNORECASE):
            warnings.append(ConformanceIssue(level="warning", message=line))

    return errors, warnings


def run_conformance_check(file_path: Path, format_name: str) -> ConformanceResult:
    """Run aas-test-engines on an uploaded artifact."""
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            [
                "aas_test_engines",
                "check_file",
                "--format",
                format_name,
                str(file_path),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=90,
        )
    except FileNotFoundError as exc:
        raise APIError(
            code=ErrorCode.UPSTREAM_UNAVAILABLE,
            message="aas-test-engines CLI is not installed",
            detail={"hint": "Install aas-test-engines in the backend environment"},
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise APIError(
            code=ErrorCode.UPSTREAM_UNAVAILABLE,
            message="Conformance check timed out",
            detail={"timeout_seconds": 90},
        ) from exc

    output = "\n".join(
        part for part in [(proc.stdout or "").strip(), (proc.stderr or "").strip()] if part
    )
    errors, warnings = _parse_issues(output)
    if proc.returncode != 0 and not errors:
        errors.append(
            ConformanceIssue(
                level="error",
                message="Conformance check failed without structured error output",
            )
        )

    duration_ms = int((time.perf_counter() - started) * 1000)
    passed = proc.returncode == 0 and len(errors) == 0

    return ConformanceResult(
        passed=passed,
        errors=errors,
        warnings=warnings,
        engine_version=get_engine_version(),
        duration_ms=duration_ms,
        format=format_name,
    )
