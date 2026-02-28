"""Tests for Magic Import preview and snippet redaction flow."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.config import Settings
from app.errors import APIError, ErrorCode
from app.routers.magic_import import (
    MAX_SNIPPET_OVERRIDE_COUNT,
    _parse_snippet_overrides,
    router as magic_import_router,
)
from app.schemas.magic_import import ExtractionHint, Snippet
from app.services.magic_import.job_manager import JobManager


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(magic_import_router)
    return app


def _pdf_payload() -> bytes:
    return b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"


def test_preview_endpoint_returns_snippets_and_token_estimate(monkeypatch):
    settings = Settings(
        magic_import_enabled=True,
        magic_import_max_pdf_size_mb=5,
    )

    with patch("app.routers.magic_import.get_settings", return_value=settings):
        from app.services.magic_import import pdf_indexer, retriever, schema_resolver

        monkeypatch.setattr(
            pdf_indexer.PDFIndexer,
            "index_pdf",
            lambda self, pdf_path, job_id: MagicMock(),
        )
        monkeypatch.setattr(
            schema_resolver.SchemaResolver,
            "resolve_hints",
            lambda self, *_args, **_kwargs: [
                ExtractionHint(
                    path="ManufacturerName",
                    label="ManufacturerName",
                    element_type="Property",
                    keywords=["manufacturer", "name"],
                )
            ],
        )
        monkeypatch.setattr(
            retriever.SnippetRetriever,
            "retrieve_snippets",
            lambda self, **_kwargs: [
                Snippet(
                    text="Manufacturer: ACME GmbH",
                    page=0,
                    start_word_idx=0,
                    end_word_idx=3,
                    score=1.0,
                )
            ],
        )

        with TestClient(_build_app()) as client:
            response = client.post(
                "/api/magic-import/jobs/preview",
                files={"file": ("datasheet.pdf", _pdf_payload(), "application/pdf")},
                data={"template_name": "Digital Nameplate", "template_status": "published"},
            )

    assert response.status_code == 200
    payload = response.json()
    assert payload["snippet_count"] == 1
    assert payload["token_estimate"] > 0
    assert payload["snippets"][0]["text"] == "Manufacturer: ACME GmbH"


def test_create_job_persists_snippet_overrides(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp_dir:
        settings = Settings(
            magic_import_enabled=True,
            magic_import_max_pdf_size_mb=5,
            magic_import_cache_dir=Path(tmp_dir),
        )

        class _FakeTask:
            def delay(self, *_args, **_kwargs):
                return None

            def __call__(self, *_args, **_kwargs):
                return None

        with (
            patch("app.routers.magic_import.get_settings", return_value=settings),
            patch("app.services.magic_import.job_manager.get_settings", return_value=settings),
            patch("app.services.magic_import.tasks.process_magic_import_job", _FakeTask()),
        ):
            snippets = [
                {
                    "text": "[REDACTED]",
                    "page": 0,
                    "start_word_idx": 0,
                    "end_word_idx": 2,
                    "score": 1.0,
                    "context_before": "",
                    "context_after": "",
                }
            ]

            with TestClient(_build_app()) as client:
                response = client.post(
                    "/api/magic-import/jobs",
                    files={"file": ("datasheet.pdf", _pdf_payload(), "application/pdf")},
                    data={
                        "template_name": "Digital Nameplate",
                        "template_status": "published",
                        "snippet_overrides": json.dumps(snippets),
                    },
                )

            assert response.status_code == 200
            job_id = response.json()["job_id"]

            manager = JobManager()
            artifact = manager.load_artifact(job_id, "snippet_overrides")
            assert artifact is not None
            parsed = [Snippet.model_validate(item) for item in artifact]
            assert parsed[0].text == "[REDACTED]"


def test_create_job_rejects_excessive_snippet_overrides():
    snippets = [
        {
            "text": "value",
            "page": 0,
            "start_word_idx": 0,
            "end_word_idx": 1,
            "score": 1.0,
            "context_before": "",
            "context_after": "",
        }
        for _ in range(MAX_SNIPPET_OVERRIDE_COUNT + 1)
    ]

    with pytest.raises(APIError) as exc_info:
        _parse_snippet_overrides(json.dumps(snippets))

    assert exc_info.value.code == ErrorCode.BAD_REQUEST
    assert exc_info.value.message == "Too many snippet overrides"


def test_parse_snippet_overrides_rejects_invalid_json_payload():
    with pytest.raises(APIError) as exc_info:
        _parse_snippet_overrides("{invalid-json")

    assert exc_info.value.code == ErrorCode.BAD_REQUEST
    assert exc_info.value.message == "Invalid snippet override payload"


def test_parse_snippet_overrides_rejects_non_list_payload():
    with pytest.raises(APIError) as exc_info:
        _parse_snippet_overrides(json.dumps({"text": "not-a-list"}))

    assert exc_info.value.code == ErrorCode.BAD_REQUEST
    assert exc_info.value.message == "Snippet overrides must be a JSON list"


def test_parse_snippet_overrides_rejects_invalid_position_metadata():
    snippets = [
        {
            "text": "value",
            "page": 0,
            "start_word_idx": 5,
            "end_word_idx": 1,
            "score": 1.0,
            "context_before": "",
            "context_after": "",
        }
    ]

    with pytest.raises(APIError) as exc_info:
        _parse_snippet_overrides(json.dumps(snippets))

    assert exc_info.value.code == ErrorCode.BAD_REQUEST
    assert exc_info.value.message == "Snippet override entry contains invalid position metadata"


def test_preview_endpoint_rejects_when_magic_import_disabled():
    settings = Settings(
        magic_import_enabled=False,
        magic_import_max_pdf_size_mb=5,
    )

    with patch("app.routers.magic_import.get_settings", return_value=settings):
        with TestClient(_build_app()) as client:
            with pytest.raises(APIError) as exc_info:
                client.post(
                    "/api/magic-import/jobs/preview",
                    files={"file": ("datasheet.pdf", _pdf_payload(), "application/pdf")},
                    data={"template_name": "Digital Nameplate", "template_status": "published"},
                )

    assert exc_info.value.code == ErrorCode.FEATURE_DISABLED


def test_preview_endpoint_hides_internal_errors(monkeypatch):
    settings = Settings(
        magic_import_enabled=True,
        magic_import_max_pdf_size_mb=5,
    )

    with patch("app.routers.magic_import.get_settings", return_value=settings):
        from app.services.magic_import import pdf_indexer

        def _raise_index_error(self, pdf_path, job_id):
            raise RuntimeError("secret trace")

        monkeypatch.setattr(pdf_indexer.PDFIndexer, "index_pdf", _raise_index_error)

        with TestClient(_build_app(), raise_server_exceptions=False) as client:
            response = client.post(
                "/api/magic-import/jobs/preview",
                files={"file": ("datasheet.pdf", _pdf_payload(), "application/pdf")},
                data={"template_name": "Digital Nameplate", "template_status": "published"},
            )

    assert response.status_code == 500
    assert "secret trace" not in response.text
