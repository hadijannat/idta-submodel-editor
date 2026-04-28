"""Tests for conformance service subprocess integration."""

from importlib import metadata
from pathlib import Path
import subprocess
from subprocess import CompletedProcess
from unittest.mock import patch

import pytest

from app.errors import APIError
from app.services.conformance import get_engine_version, run_conformance_check


@pytest.fixture(autouse=True)
def clear_engine_version_cache():
    """Avoid cross-test pollution from the cached CLI version lookup."""
    get_engine_version.cache_clear()
    yield
    get_engine_version.cache_clear()


def test_run_conformance_check_success(tmp_path: Path):
    artifact = tmp_path / "artifact.aasx"
    artifact.write_bytes(b"PK\x03\x04dummy")

    def fake_run(*args, **kwargs):
        return CompletedProcess(
            args[0],
            0,
            stdout="Conformance check completed\nWARNING minor issue",
            stderr="",
        )

    with (
        patch("app.services.conformance.metadata.version", return_value="1.2.3"),
        patch("app.services.conformance.subprocess.run", side_effect=fake_run),
    ):
        result = run_conformance_check(artifact, "aasx")

    assert result.passed is True
    assert result.format == "aasx"
    assert result.engine_version == "aas-test-engines 1.2.3"
    assert len(result.warnings) == 1


def test_run_conformance_check_parses_json_output(tmp_path: Path):
    artifact = tmp_path / "artifact.json"
    artifact.write_text("{}")
    check_commands: list[list[str]] = []

    def fake_run(*args, **kwargs):
        cmd = args[0]
        if cmd[:2] == ["aas_test_engines", "--version"]:
            return CompletedProcess(cmd, 0, stdout="aas-test-engines 1.0.3", stderr="")
        check_commands.append(cmd)
        return CompletedProcess(
            cmd,
            1,
            stdout=(
                '{"m":"Check","l":0,"s":['
                '{"m":"AASd-001 missing idShort","l":2,"s":[]},'
                '{"m":"Optional semanticId warning","l":1,"s":[]}'
                "]}"
            ),
            stderr="",
        )

    with patch("app.services.conformance.subprocess.run", side_effect=fake_run):
        result = run_conformance_check(artifact, "json")

    assert check_commands == [
        ["aas_test_engines", "check_file", "--format", "json", "--output", "json", str(artifact)]
    ]
    assert result.passed is False
    assert [issue.message for issue in result.errors] == ["AASd-001 missing idShort"]
    assert [issue.message for issue in result.warnings] == ["Optional semanticId warning"]


def test_run_conformance_check_falls_back_when_json_output_unsupported(tmp_path: Path):
    artifact = tmp_path / "artifact.aasx"
    artifact.write_bytes(b"PK\x03\x04dummy")
    check_commands: list[list[str]] = []

    def fake_run(*args, **kwargs):
        cmd = args[0]
        if cmd[:2] == ["aas_test_engines", "--version"]:
            return CompletedProcess(cmd, 0, stdout="v", stderr="")
        check_commands.append(cmd)
        if "--output" in cmd:
            return CompletedProcess(
                cmd,
                2,
                stdout="",
                stderr="error: unrecognized arguments: --output json",
            )
        return CompletedProcess(cmd, 0, stdout="WARNING legacy warning", stderr="")

    with patch("app.services.conformance.subprocess.run", side_effect=fake_run):
        result = run_conformance_check(artifact, "aasx")

    assert check_commands == [
        ["aas_test_engines", "check_file", "--format", "aasx", "--output", "json", str(artifact)],
        ["aas_test_engines", "check_file", "--format", "aasx", str(artifact)],
    ]
    assert result.passed is True
    assert [issue.message for issue in result.warnings] == ["WARNING legacy warning"]


def test_run_conformance_check_failure_without_structured_output(tmp_path: Path):
    artifact = tmp_path / "artifact.json"
    artifact.write_text("{}")

    def fake_run(*args, **kwargs):
        return CompletedProcess(args[0], 2, stdout="", stderr="")

    with (
        patch("app.services.conformance.metadata.version", return_value="1.2.3"),
        patch("app.services.conformance.subprocess.run", side_effect=fake_run),
    ):
        result = run_conformance_check(artifact, "json")

    assert result.passed is False
    assert len(result.errors) == 1
    assert result.errors[0].message == "Conformance check failed with exit code 2"


def test_run_conformance_check_nonzero_runtime_failure_includes_output(tmp_path: Path):
    artifact = tmp_path / "artifact.json"
    artifact.write_text("{}")

    def fake_run(*args, **kwargs):
        cmd = args[0]
        if cmd[:2] == ["aas_test_engines", "--version"]:
            return CompletedProcess(cmd, 0, stdout="v", stderr="")
        return CompletedProcess(
            cmd,
            2,
            stdout="",
            stderr="Traceback: incompatible Python runtime",
        )

    with patch("app.services.conformance.subprocess.run", side_effect=fake_run):
        result = run_conformance_check(artifact, "json")

    assert result.passed is False
    assert len(result.errors) == 1
    assert result.errors[0].message == (
        "Conformance check failed with exit code 2: Traceback: incompatible Python runtime"
    )


def test_run_conformance_check_missing_cli(tmp_path: Path):
    artifact = tmp_path / "artifact.aasx"
    artifact.write_bytes(b"PK\x03\x04dummy")

    with patch("app.services.conformance.subprocess.run", side_effect=FileNotFoundError()):
        with pytest.raises(APIError) as exc_info:
            run_conformance_check(artifact, "aasx")

    assert exc_info.value.code.value == "UPSTREAM_UNAVAILABLE"


def test_run_conformance_check_timeout(tmp_path: Path):
    artifact = tmp_path / "artifact.aasx"
    artifact.write_bytes(b"PK\x03\x04dummy")

    with patch(
        "app.services.conformance.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="aas_test_engines", timeout=90),
    ):
        with pytest.raises(APIError) as exc_info:
            run_conformance_check(artifact, "aasx")

    assert exc_info.value.code.value == "UPSTREAM_UNAVAILABLE"
    assert exc_info.value.message == "Conformance check timed out"


def test_run_conformance_check_marks_error_output_as_failure(tmp_path: Path):
    artifact = tmp_path / "artifact.json"
    artifact.write_text("{}")

    def fake_run(*args, **kwargs):
        return CompletedProcess(args[0], 0, stdout="ERROR: missing semanticId", stderr="")

    with (
        patch("app.services.conformance.metadata.version", return_value="1.2.3"),
        patch("app.services.conformance.subprocess.run", side_effect=fake_run),
    ):
        result = run_conformance_check(artifact, "json")

    assert result.passed is False
    assert len(result.errors) == 1


def test_get_engine_version_reads_installed_package_metadata():
    with patch("app.services.conformance.metadata.version", return_value="1.0.3"):
        version = get_engine_version()

    assert version == "aas-test-engines 1.0.3"


def test_get_engine_version_returns_none_when_package_missing():
    with patch(
        "app.services.conformance.metadata.version",
        side_effect=metadata.PackageNotFoundError,
    ):
        version = get_engine_version()

    assert version is None


def test_run_conformance_check_parses_stderr_issues(tmp_path: Path):
    artifact = tmp_path / "artifact.aasx"
    artifact.write_bytes(b"PK\x03\x04dummy")

    def fake_run(*args, **kwargs):
        return CompletedProcess(
            args[0],
            1,
            stdout="",
            stderr="FAILED check AAS shell\nWARNING minor field issue",
        )

    with (
        patch("app.services.conformance.metadata.version", return_value="1.0.3"),
        patch("app.services.conformance.subprocess.run", side_effect=fake_run),
    ):
        result = run_conformance_check(artifact, "aasx")

    assert result.passed is False
    assert len(result.errors) == 1
    assert len(result.warnings) == 1
