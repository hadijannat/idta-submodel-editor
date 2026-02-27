"""Router tests for Magic Import provider info endpoint."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.magic_import import router as magic_import_router
from app.services import settings_service
from app.services.magic_import.llm import factory
from app.services.magic_import.llm.factory import ProviderInfo
from app.services.magic_import.llm.local_provider import LocalProvider


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(magic_import_router)
    return app


def test_provider_info_serializes_model_recommendations(monkeypatch):
    """GET /providers/info includes expected model_* recommendation fields."""
    provider_infos = [
        ProviderInfo(
            name="openai",
            available=True,
            model="gpt-4o-mini",
            is_local=False,
            privacy_note="Data sent to OpenAI servers",
            error=None,
        ),
        ProviderInfo(
            name="local",
            available=True,
            model="llama3.1:8b-instruct-q8_0",
            is_local=True,
            privacy_note="All data stays on your machine",
            error=None,
        ),
    ]
    monkeypatch.setattr(factory, "get_provider_info", lambda: provider_infos)
    monkeypatch.setattr(settings_service, "get_effective_provider", lambda: "local")
    monkeypatch.setattr(
        settings_service, "get_effective_model", lambda _provider: "llama3.1:8b-instruct-q8_0"
    )
    monkeypatch.setattr(
        settings_service, "get_effective_base_url", lambda _provider: "http://ollama.local:11434"
    )

    async def fake_list_available_models(self) -> list[str]:
        return ["llama3.1:8b-instruct-q8_0", "mistral:7b-instruct-v0.3-q4_0"]

    monkeypatch.setattr(LocalProvider, "list_available_models", fake_list_available_models)

    with TestClient(_build_app()) as client:
        response = client.get("/api/magic-import/providers/info")

    assert response.status_code == 200
    data = response.json()
    assert data["active_provider"] == "local"
    assert "model_recommendations" in data
    assert "extraction" in data["model_recommendations"]

    extraction_recommendations = data["model_recommendations"]["extraction"]
    assert extraction_recommendations

    recommendation = extraction_recommendations[0]
    assert "model_id" in recommendation
    assert "display_name" in recommendation
    assert "recommended_memory_gb" in recommendation
    assert "is_available" in recommendation

    selected = next(
        rec for rec in extraction_recommendations if rec["model_id"] == "llama3.1:8b-instruct-q8_0"
    )
    assert selected["is_available"] is True
