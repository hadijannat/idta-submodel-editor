"""Router-level tests for template knowledge endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
import tempfile
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
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


def test_semantic_search_reports_fallback_when_ollama_unavailable():
    class FakeIndex:
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
    assert payload["ollama_available"] is False
    assert payload["total"] == 1
