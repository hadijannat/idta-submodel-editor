"""
Conformance checking using aas-test-engines CLI.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from importlib import metadata
import re
import subprocess
import time
from pathlib import Path
from typing import Any

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


ENGINE_LEVEL_WARNING = 1
ENGINE_LEVEL_ERROR = 2
CONFORMANCE_TIMEOUT_SECONDS = 90


@lru_cache(maxsize=1)
def get_engine_version() -> str | None:
    """Get aas-test-engines version once per process."""
    try:
        version = metadata.version("aas-test-engines")
    except metadata.PackageNotFoundError:
        return None

    return f"aas-test-engines {version}"


def _combined_output(proc: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(
        part for part in [(proc.stdout or "").strip(), (proc.stderr or "").strip()] if part
    )


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


def _load_json_payload(output: str) -> Any | None:
    text = output.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Some wrappers prepend or append diagnostic text. Try the obvious JSON span.
    starts = [idx for idx in (text.find("{"), text.find("[")) if idx >= 0]
    if not starts:
        return None
    start = min(starts)
    end = max(text.rfind("}"), text.rfind("]"))
    if end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def _json_children(node: dict[str, Any]) -> list[Any]:
    for key in ("s", "children", "checks", "results", "items"):
        children = node.get(key)
        if isinstance(children, list):
            return children
    return []


def _json_message(node: dict[str, Any]) -> str:
    for key in ("m", "message", "msg", "description", "name", "title"):
        value = node.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _json_level(node: dict[str, Any], message: str) -> str | None:
    raw_level = None
    has_level = False
    for key in ("l", "level", "severity", "status"):
        if key in node:
            raw_level = node[key]
            has_level = True
            break

    if isinstance(raw_level, int):
        if raw_level >= ENGINE_LEVEL_ERROR:
            return "error"
        if raw_level == ENGINE_LEVEL_WARNING:
            return "warning"
        return None
    elif isinstance(raw_level, str):
        normalized = raw_level.lower()
        if normalized.isdigit():
            return _json_level({"l": int(normalized)}, message)
        if any(token in normalized for token in ("error", "fail", "fatal", "critical")):
            return "error"
        if "warn" in normalized:
            return "warning"
        if normalized in {"ok", "pass", "passed", "success", "info"}:
            return None

    if has_level:
        return None
    if re.search(r"\b(error|failed|fail)\b", message, flags=re.IGNORECASE):
        return "error"
    if re.search(r"\bwarning\b", message, flags=re.IGNORECASE):
        return "warning"
    return None


def _parse_json_issues(output: str) -> tuple[list[ConformanceIssue], list[ConformanceIssue]] | None:
    payload = _load_json_payload(output)
    if payload is None:
        return None

    errors: list[ConformanceIssue] = []
    warnings: list[ConformanceIssue] = []
    seen: set[tuple[str, str]] = set()

    def collect(node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                collect(item)
            return
        if not isinstance(node, dict):
            return

        message = _json_message(node)
        level = _json_level(node, message)
        if message and level in {"error", "warning"}:
            key = (level, message)
            if key not in seen:
                seen.add(key)
                issue = ConformanceIssue(level=level, message=message)
                if level == "error":
                    errors.append(issue)
                else:
                    warnings.append(issue)

        for child in _json_children(node):
            collect(child)

    collect(payload)
    return errors, warnings


def _json_output_unsupported(proc: subprocess.CompletedProcess[str]) -> bool:
    if proc.returncode == 0:
        return False
    output = _combined_output(proc).lower()
    return "--output" in output and (
        "unrecognized" in output
        or "no such option" in output
        or "invalid choice" in output
        or "unexpected option" in output
    )


def _runtime_failure_issue(
    proc: subprocess.CompletedProcess[str], output: str
) -> ConformanceIssue:
    detail = output.strip()
    if detail:
        detail = re.sub(r"\s+", " ", detail)
        if len(detail) > 500:
            detail = f"{detail[:497]}..."
        message = f"Conformance check failed with exit code {proc.returncode}: {detail}"
    else:
        message = f"Conformance check failed with exit code {proc.returncode}"
    return ConformanceIssue(level="error", message=message)


def run_conformance_check(file_path: Path, format_name: str) -> ConformanceResult:
    """Run aas-test-engines on an uploaded artifact."""
    started = time.perf_counter()
    base_cmd = [
        "aas_test_engines",
        "check_file",
        "--format",
        format_name,
    ]
    try:
        proc = subprocess.run(
            [*base_cmd, "--output", "json", str(file_path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=CONFORMANCE_TIMEOUT_SECONDS,
        )
        if _json_output_unsupported(proc):
            proc = subprocess.run(
                [*base_cmd, str(file_path)],
                check=False,
                capture_output=True,
                text=True,
                timeout=CONFORMANCE_TIMEOUT_SECONDS,
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
            detail={"timeout_seconds": CONFORMANCE_TIMEOUT_SECONDS},
        ) from exc

    output = _combined_output(proc)
    parsed_json = _parse_json_issues(output)
    if parsed_json is not None:
        errors, warnings = parsed_json
    else:
        errors, warnings = _parse_issues(output)

    if proc.returncode != 0 and not errors:
        errors.append(_runtime_failure_issue(proc, output))

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
