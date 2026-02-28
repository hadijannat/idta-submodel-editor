"""Tests for conformance check API."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.config import Settings
from app.dependencies import get_oidc_validator
from app.errors import APIError, ErrorCode
from app.main import create_application
from app.services.conformance import ConformanceResult
from app.schemas.conformance import ConformanceIssue


def _client() -> TestClient:
    app = create_application()
    return TestClient(app)


def test_conformance_check_aasx_success():
    result = ConformanceResult(
        passed=True,
        errors=[],
        warnings=[ConformanceIssue(level="warning", message="Non-blocking warning")],
        engine_version="aas-test-engines 0.0.0",
        duration_ms=123,
        format="aasx",
    )
    with patch("app.routers.conformance.run_conformance_check", return_value=result):
        with _client() as client:
            response = client.post(
                "/api/conformance/check",
                files={"file": ("sample.aasx", b"PK\x03\x04dummy", "application/octet-stream")},
                data={"format_name": "aasx"},
            )

    assert response.status_code == 200
    payload = response.json()
    assert payload["passed"] is True
    assert payload["format"] == "aasx"
    assert payload["duration_ms"] == 123
    assert payload["engine_version"] == "aas-test-engines 0.0.0"
    assert len(payload["warnings"]) == 1


def test_conformance_check_json_infers_format():
    base = ConformanceResult(
        passed=True,
        errors=[],
        warnings=[],
        engine_version="test",
        duration_ms=10,
        format="json",
    )
    with patch("app.routers.conformance.run_conformance_check", return_value=base):
        with _client() as client:
            response = client.post(
                "/api/conformance/check",
                files={"file": ("artifact.json", b'{"ok":true}', "application/json")},
            )

    assert response.status_code == 200
    payload = response.json()
    assert payload["format"] == "json"
    assert payload["passed"] is True


def test_conformance_check_rejects_invalid_json():
    with _client() as client:
        response = client.post(
            "/api/conformance/check",
            files={"file": ("artifact.json", b"{not-json}", "application/json")},
            data={"format_name": "json"},
        )

    assert response.status_code == 400
    payload = response.json()
    assert payload["code"] == "INVALID_FILE_TYPE"


def test_conformance_check_rejects_unknown_extension_without_format():
    with _client() as client:
        response = client.post(
            "/api/conformance/check",
            files={"file": ("artifact.bin", b"abc", "application/octet-stream")},
        )

    assert response.status_code == 400
    payload = response.json()
    assert payload["code"] == "INVALID_FILE_TYPE"


def test_conformance_check_honors_explicit_format_over_filename():
    base = ConformanceResult(
        passed=True,
        errors=[],
        warnings=[],
        engine_version="test",
        duration_ms=10,
        format="json",
    )
    with patch("app.routers.conformance.run_conformance_check", return_value=base):
        with _client() as client:
            response = client.post(
                "/api/conformance/check",
                files={"file": ("artifact.bin", b'{"ok":true}', "application/octet-stream")},
                data={"format_name": "json"},
            )

    assert response.status_code == 200
    payload = response.json()
    assert payload["format"] == "json"
    assert payload["passed"] is True


def test_conformance_check_requires_auth_when_oidc_enabled():
    settings = Settings(oidc_enabled=True)
    with patch("app.dependencies.get_settings", return_value=settings):
        get_oidc_validator.cache_clear()
        with _client() as client:
            response = client.post(
                "/api/conformance/check",
                files={"file": ("sample.aasx", b"PK\x03\x04dummy", "application/octet-stream")},
                data={"format_name": "aasx"},
            )
        get_oidc_validator.cache_clear()

    assert response.status_code == 401
    payload = response.json()
    assert payload["message"] == "Authentication required"


def test_conformance_check_hides_unexpected_internal_errors():
    with patch("app.routers.conformance.run_conformance_check", side_effect=RuntimeError("secret trace")):
        with _client() as client:
            response = client.post(
                "/api/conformance/check",
                files={"file": ("sample.aasx", b"PK\x03\x04dummy", "application/octet-stream")},
                data={"format_name": "aasx"},
            )

    assert response.status_code == 500
    payload = response.json()
    assert payload["code"] == "INTERNAL_ERROR"
    assert payload["message"] == "Conformance check failed"
    assert payload["detail"] is None


def test_conformance_check_propagates_api_errors():
    with patch(
        "app.routers.conformance.run_conformance_check",
        side_effect=APIError(
            code=ErrorCode.UPSTREAM_UNAVAILABLE,
            message="aas-test-engines CLI is not installed",
        ),
    ):
        with _client() as client:
            response = client.post(
                "/api/conformance/check",
                files={"file": ("sample.aasx", b"PK\x03\x04dummy", "application/octet-stream")},
                data={"format_name": "aasx"},
            )

    assert response.status_code == 503
    payload = response.json()
    assert payload["code"] == "UPSTREAM_UNAVAILABLE"
