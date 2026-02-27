"""Router-level tests for template knowledge endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.dependencies import get_oidc_validator
from app.routers import knowledge
from app.services.template_knowledge.models import FieldInfo, IndexStatus


def _make_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(knowledge.router)
    return app


def test_knowledge_status_returns_503_when_index_missing():
    with tempfile.TemporaryDirectory() as tmp_dir:
        settings = Settings(magic_import_cache_dir=Path(tmp_dir))
        app = _make_test_app()
        app.dependency_overrides[get_settings] = lambda: settings

        with TestClient(app) as client:
            response = client.get("/api/knowledge/status")

        assert response.status_code == 503
        assert "index not built" in response.json()["detail"].lower()


def test_semantic_search_returns_503_when_index_missing():
    with tempfile.TemporaryDirectory() as tmp_dir:
        settings = Settings(magic_import_cache_dir=Path(tmp_dir))
        app = _make_test_app()
        app.dependency_overrides[get_settings] = lambda: settings

        with TestClient(app) as client:
            response = client.post(
                "/api/knowledge/search/semantic",
                json={"query": "manufacturer", "top_k": 5, "threshold": 0.5},
            )

        assert response.status_code == 503
        assert "index not built" in response.json()["detail"].lower()


def test_knowledge_endpoints_require_auth_when_oidc_enabled():
    with tempfile.TemporaryDirectory() as tmp_dir:
        settings = Settings(
            oidc_enabled=True,
            magic_import_cache_dir=Path(tmp_dir),
        )
        app = _make_test_app()
        app.dependency_overrides[get_settings] = lambda: settings

        with patch("app.dependencies.get_settings", return_value=settings):
            get_oidc_validator.cache_clear()
            with TestClient(app) as client:
                response = client.get("/api/knowledge/status")
            get_oidc_validator.cache_clear()

        assert response.status_code == 401
        assert response.json()["detail"] == "Authentication required"


def test_semantic_search_reports_fallback_when_ollama_unavailable():
    class FakeIndex:
        last_ollama_available = False

        async def get_status(self) -> IndexStatus:
            return IndexStatus(
                templates_indexed=1,
                fields_indexed=1,
                patterns_indexed=0,
                last_updated=datetime.now(timezone.utc),
                embedding_model="nomic-embed-text",
                ollama_available=False,
                index_version="1.0",
            )

        async def find_similar_fields_by_text(
            self,
            query: str,
            top_k: int = 5,
            threshold: float = 0.5,
            exclude_template: str | None = None,
        ):
            field = FieldInfo(
                template_idta="02006",
                path="TechnicalData.ManufacturerName",
                id_short="ManufacturerName",
                model_type="Property",
                value_type="xs:string",
                semantic_id=None,
                semantic_label="Manufacturer Name",
                definition="Name of the manufacturer",
                unit=None,
                cardinality="[1]",
                parent_path="TechnicalData",
                keywords=["manufacturer", "name"],
                synonyms=[],
                embedding_vector=None,
                example_values=[],
                value_format=None,
                allowed_values=[],
                is_required=True,
            )
            return [(field, 0.91)]

        async def close(self) -> None:
            return None

    async def override_index():
        index = FakeIndex()
        try:
            yield index
        finally:
            await index.close()

    app = _make_test_app()
    app.dependency_overrides[knowledge.get_knowledge_index] = override_index

    with TestClient(app) as client:
        response = client.post(
            "/api/knowledge/search/semantic",
            json={"query": "manufacturer", "top_k": 5, "threshold": 0.5},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "manufacturer"
    assert payload["ollama_available"] is False
    assert payload["total"] == 1
    assert payload["results"][0]["field"]["path"] == "TechnicalData.ManufacturerName"
    assert payload["results"][0]["similarity"] == 0.91


def test_knowledge_index_is_reused_and_closed_on_shutdown(monkeypatch):
    class FakeIndex:
        init_count = 0
        close = AsyncMock()

        def __init__(self, db_path, embedding_client):
            type(self).init_count += 1

        async def get_status(self) -> IndexStatus:
            return IndexStatus(
                templates_indexed=1,
                fields_indexed=1,
                patterns_indexed=0,
                last_updated=datetime.now(timezone.utc),
                embedding_model="nomic-embed-text",
                ollama_available=True,
                index_version="1.0",
            )

    with tempfile.TemporaryDirectory() as tmp_dir:
        cache_dir = Path(tmp_dir)
        index_dir = cache_dir / "template_knowledge"
        index_dir.mkdir(parents=True, exist_ok=True)
        (index_dir / "index.db").touch()

        settings = Settings(magic_import_cache_dir=cache_dir)
        app = _make_test_app()
        app.dependency_overrides[get_settings] = lambda: settings

        monkeypatch.setattr(knowledge, "TemplateKnowledgeIndex", FakeIndex)
        monkeypatch.setattr(knowledge, "OllamaEmbeddingClient", lambda **kwargs: object())

        with TestClient(app) as client:
            first = client.get("/api/knowledge/status")
            second = client.get("/api/knowledge/status")

        assert first.status_code == 200
        assert second.status_code == 200
        assert FakeIndex.init_count == 1
        FakeIndex.close.assert_not_called()

        import asyncio

        asyncio.run(knowledge.shutdown_knowledge_index(app))
        FakeIndex.close.assert_awaited_once()
