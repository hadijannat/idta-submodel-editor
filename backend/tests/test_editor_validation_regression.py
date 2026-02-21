"""Regression tests for editor validation endpoint edge cases."""

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.dependencies import get_fetcher, get_parser
from app.main import app


class _MockFetcher:
    async def fetch_template_aasx(self, template_path: str) -> bytes:
        return b"mock-template"


class _MockParser:
    def __init__(self, schema: dict):
        self._schema = schema

    def parse_aasx_to_ui_schema(self, aasx_bytes: bytes) -> dict:
        return self._schema


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


def _set_overrides(schema: dict) -> None:
    app.dependency_overrides[get_fetcher] = lambda: _MockFetcher()
    app.dependency_overrides[get_parser] = lambda: _MockParser(schema)


def test_validate_collection_with_empty_payload_does_not_500(client: TestClient):
    schema = {
        "submodelId": "urn:test",
        "idShort": "Test",
        "elements": [
            {
                "idShort": "Coll",
                "modelType": "SubmodelElementCollection",
                "cardinality": "[0..1]",
                "elements": [
                    {
                        "idShort": "Inner",
                        "modelType": "Property",
                        "cardinality": "[1]",
                        "valueType": "xs:string",
                    }
                ],
            }
        ],
    }
    _set_overrides(schema)

    response = client.post(
        "/api/editor/validate/TestTemplate",
        json={"elements": {"Coll": {}}},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert any(
        err["field"] == "Coll.Inner" and err["code"] == "required"
        for err in data["errors"]
    )


def test_validate_entity_with_empty_payload_does_not_500(client: TestClient):
    schema = {
        "submodelId": "urn:test",
        "idShort": "Test",
        "elements": [
            {
                "idShort": "EntityX",
                "modelType": "Entity",
                "cardinality": "[0..1]",
                "statements": [
                    {
                        "idShort": "Inner",
                        "modelType": "Property",
                        "cardinality": "[1]",
                        "valueType": "xs:string",
                    }
                ],
            }
        ],
    }
    _set_overrides(schema)

    response = client.post(
        "/api/editor/validate/TestTemplate",
        json={"elements": {"EntityX": {}}},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert any(
        err["field"] == "EntityX.Inner" and err["code"] == "required"
        for err in data["errors"]
    )
