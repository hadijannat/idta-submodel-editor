"""Tests for template listing and cache invalidation routes."""

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.dependencies import get_fetcher
from app.main import app


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "0123456789abcdef0123456789abcdef")
    get_settings.cache_clear()
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_list_templates_excludes_local_entries(client: TestClient):
    class MockFetcher:
        def __init__(self):
            self.calls: list[dict] = []

        async def list_available_templates(self, statuses, include_local=True):
            self.calls.append({"statuses": statuses, "include_local": include_local})
            published_template = {
                "name": "Digital nameplate",
                "path": "published/Digital nameplate",
                "url": "https://github.com/admin-shell-io/submodel-templates",
                "idta_number": "02006",
                "title": "Digital nameplate",
                "sha": "sha1",
                "status": "published",
            }
            local_template = {
                "name": "MyLocalTemplate",
                "path": "local/MyLocalTemplate",
                "url": None,
                "idta_number": None,
                "title": "MyLocalTemplate",
                "sha": None,
                "status": "local",
                "source": "local",
                "file_path": "/tmp/MyLocalTemplate.aasx",
            }
            if include_local:
                return [published_template, local_template], False
            return [published_template], False

    fetcher = MockFetcher()
    app.dependency_overrides[get_fetcher] = lambda: fetcher

    response = client.get("/api/templates")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["templates"]) == 1
    assert data["templates"][0]["name"] == "Digital nameplate"
    assert fetcher.calls[0]["include_local"] is False


def test_invalidate_template_cache_uses_canonical_path(client: TestClient):
    class MockFetcher:
        def __init__(self):
            self.resolve_calls: list[str] = []
            self.invalidate_calls: list[str] = []

        async def resolve_template_path(self, template_path: str) -> str:
            self.resolve_calls.append(template_path)
            return "published/Digital nameplate"

        def invalidate_template(self, template_path: str) -> bool:
            self.invalidate_calls.append(template_path)
            return template_path == "published/Digital nameplate"

    fetcher = MockFetcher()
    app.dependency_overrides[get_fetcher] = lambda: fetcher

    response = client.delete("/api/templates/Digital%20Nameplate/cache")

    assert response.status_code == 200
    assert response.json()["invalidated"] is True
    assert fetcher.resolve_calls == ["published/Digital Nameplate"]
    assert fetcher.invalidate_calls == ["published/Digital nameplate"]
