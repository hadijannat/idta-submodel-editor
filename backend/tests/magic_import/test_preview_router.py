"""Tests for Magic Import preview and snippet redaction flow."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.routers.magic_import import router as magic_import_router
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
