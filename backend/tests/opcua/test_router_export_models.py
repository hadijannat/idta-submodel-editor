"""Router tests for OPC UA export request models."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import opcua
from app.services.opcua.exporter import ExportResult, NodeSetExporter


class _DummyFetcher:
    async def get_template(self, _template_name: str, **_kwargs) -> dict:
        return {"idShort": "DemoSubmodel", "submodelElements": []}


class _DummyParser:
    async def parse(self, _template_content: dict) -> dict:
        return {"idShort": "ParsedSubmodel", "elements": []}


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(opcua.router)
    app.dependency_overrides[opcua.get_fetcher] = lambda: _DummyFetcher()
    app.dependency_overrides[opcua.get_parser] = lambda: _DummyParser()
    return app


def test_export_endpoint_passes_model_version(monkeypatch):
    """POST /api/opcua/export forwards request.model_version to exporter."""
    captured: dict[str, str] = {}

    class _Settings:
        opcua_bridge_enabled = True

    def fake_export_template(self, _template: dict, version: str = "1.0.0") -> ExportResult:
        captured["version"] = version
        return ExportResult(
            success=True,
            nodeset_xml="<UANodeSet />",
            warnings=[],
            node_count=1,
            namespace_uri="urn:test:model",
        )

    monkeypatch.setattr(opcua, "get_settings", lambda: _Settings())
    monkeypatch.setattr(NodeSetExporter, "export_template", fake_export_template)

    payload = {
        "template_name": "Digital Nameplate",
        "template_status": "published",
        "model_version": "2.5.0",
    }

    with TestClient(_build_app()) as client:
        response = client.post("/api/opcua/export", json=payload)

    assert response.status_code == 200
    assert captured["version"] == "2.5.0"
    data = response.json()
    assert data["success"] is True
    assert data["namespace_uri"] == "urn:test:model"


def test_direct_export_endpoint_passes_model_version(monkeypatch):
    """POST /api/opcua/export/direct forwards request.model_version to exporter."""
    captured: dict[str, str] = {}

    class _Settings:
        opcua_bridge_enabled = True

    def fake_export_template(self, _template: dict, version: str = "1.0.0") -> ExportResult:
        captured["version"] = version
        return ExportResult(
            success=True,
            nodeset_xml="<UANodeSet />",
            warnings=[],
            node_count=1,
            namespace_uri="urn:test:model",
        )

    monkeypatch.setattr(opcua, "get_settings", lambda: _Settings())
    monkeypatch.setattr(NodeSetExporter, "export_template", fake_export_template)

    payload = {
        "ui_schema": {"idShort": "InlineSchema", "elements": []},
        "model_version": "3.1.4",
    }

    with TestClient(_build_app()) as client:
        response = client.post("/api/opcua/export/direct", json=payload)

    assert response.status_code == 200
    assert captured["version"] == "3.1.4"
    assert response.json()["success"] is True
