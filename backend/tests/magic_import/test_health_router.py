"""Tests for Magic Import health endpoint."""

from __future__ import annotations

import sys
import types

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.routers.magic_import import router as magic_import_router


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(magic_import_router)
    return app


def test_magic_import_health_sets_celery_available_true_on_ping(monkeypatch):
    settings = Settings(
        magic_import_enabled=True,
        magic_import_llm_provider="openai",
        magic_import_llm_model="gpt-5.5",
        magic_import_ocr_enabled=True,
    )

    class _Control:
        @staticmethod
        def ping(timeout: float):
            assert timeout == 1.0
            return [{"worker": "pong"}]

    fake_module = types.SimpleNamespace(celery_app=types.SimpleNamespace(control=_Control()))
    monkeypatch.setitem(sys.modules, "celery_app", fake_module)
    monkeypatch.setattr("app.routers.magic_import.get_settings", lambda: settings)

    with TestClient(_build_app()) as client:
        response = client.post("/api/magic-import/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    assert payload["celery_available"] is True
    assert payload["llm_provider"] == "openai"


def test_magic_import_health_sets_celery_available_false_on_ping_exception(monkeypatch):
    settings = Settings(
        magic_import_enabled=True,
        magic_import_llm_provider="openai",
        magic_import_llm_model="gpt-5.5",
        magic_import_ocr_enabled=False,
    )

    class _Control:
        @staticmethod
        def ping(timeout: float):
            assert timeout == 1.0
            raise RuntimeError("ping failed")

    fake_module = types.SimpleNamespace(celery_app=types.SimpleNamespace(control=_Control()))
    monkeypatch.setitem(sys.modules, "celery_app", fake_module)
    monkeypatch.setattr("app.routers.magic_import.get_settings", lambda: settings)

    with TestClient(_build_app()) as client:
        response = client.post("/api/magic-import/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    assert payload["ocr_enabled"] is False
    assert payload["celery_available"] is False
