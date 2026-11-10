"""API tests for template release information, documents and specification notes."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.dependencies import get_fetcher
from app.main import app
from app.services.fetcher import TemplateFetcherService
from tests.test_spec_pdf import _header, _render, _row
from tests.test_template_requirements import (
    _build_aasx,
    _concept_descriptions,
    _template_elements,
)

TEMPLATE_DIR = "published/Test Template"

def _spec_pdf() -> bytes:
    """A specification PDF in the IDTA table layout (idShorts hard-wrapped as in real specs)."""
    return _render(
        "<table>"
        + _header("TestTemplate", semantic_id="https://example.org/SubmodelTemplate/Test/1/0")
        + _row(
            "[Prop]<br>CountryOf<br>Origin",
            "urn:cd:country<br>country where the product was manufactured<br>"
            "Note: only countries of the customs union are allowed",
            "[String]<br>FR",
            "1",
        )
        + _row(
            "[Prop]<br>Conformity",
            "urn:cd:conformity<br>result of the conformity assessment",
            "[String]<br>pass",
            "1",
        )
        + "</table>"
    )


@pytest.fixture
def mirror(tmp_path):
    root = tmp_path / "mirror"
    release = root / TEMPLATE_DIR / "1" / "0" / "1"
    release.mkdir(parents=True)
    aasx_bytes = _build_aasx(_template_elements(), _concept_descriptions())
    (release / "IDTA 02999-1-0-1_Template_Test.aasx").write_bytes(aasx_bytes)
    (release / "IDTA 02999-1-0-1_Template_Test.json").write_text("{}")
    older = root / TEMPLATE_DIR / "1" / "0"
    (older / "IDTA 02999-1-0_Template_Test.aasx").write_bytes(aasx_bytes)
    return root


@pytest.fixture
def client(tmp_path, mirror, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "0123456789abcdef0123456789abcdef")
    get_settings.cache_clear()
    with patch("app.services.fetcher.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            github_token=None,
            github_repo="admin-shell-io/submodel-templates",
            cache_dir=tmp_path / "cache",
            cache_ttl_hours=24,
            github_api_version="2022-11-28",
            github_template_ref="main",
            local_templates_enabled=False,
            local_templates_dir=tmp_path / "local",
            template_repo_index_enabled=True,
            template_repo_dir=mirror,
        )
        fetcher = TemplateFetcherService()
    app.dependency_overrides[get_fetcher] = lambda: fetcher
    yield TestClient(app)
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def test_template_list_reports_releases(client):
    response = client.get("/api/templates")

    assert response.status_code == 200
    [template] = response.json()["templates"]
    assert template["name"] == "Test Template"
    assert template["idta_number"] == "02999"
    assert template["latest_version"] == "1.0.1"
    assert template["versions"] == ["1.0.1", "1.0"]
    assert template["has_specification"] is False


def test_versions_endpoint_lists_full_versions(client):
    response = client.get("/api/templates/Test Template/versions")

    assert response.status_code == 200
    assert [(v["version"], v["latest"]) for v in response.json()] == [
        ("1.0.1", True),
        ("1.0", False),
    ]


def test_schema_names_the_release_and_carries_requirements(client):
    response = client.get("/api/editor/templates/Test Template/schema")

    assert response.status_code == 200
    schema = response.json()
    assert schema["template"]["version"] == "1.0.1"
    assert schema["template"]["isLatest"] is True
    assert schema["template"]["idtaNumber"] == "02999"
    assert schema["template"]["documents"]["json"]["name"].endswith("_Template_Test.json")
    assert schema["template"]["documents"]["specification"] is None
    country = next(e for e in schema["elements"] if e["idShort"] == "CountryOfOrigin")
    assert country["valueType"] == "xs:string"
    assert country["formatHint"]["id"] == "iso3166-1-alpha2"
    assert country["exampleValues"] == ["DE"]

    pinned = client.get(
        "/api/editor/templates/Test Template/schema", params={"version": "1.0"}
    ).json()
    assert pinned["template"]["version"] == "1.0"
    assert pinned["template"]["isLatest"] is False
    assert pinned["template"]["latestVersion"] == "1.0.1"


def test_unknown_template_is_a_client_error(client):
    response = client.get("/api/editor/templates/Missing Template/schema")

    assert response.status_code == 400
    assert "Template not found" in response.json()["message"]


def test_validation_endpoint_enforces_template_requirements(client):
    form = {
        "elements": {
            "Conformity": {"value": "maybe"},
            "ManufacturerName": {"value": {"en": "ACME"}},
            "ComponentName": {"value": "Cell"},
        }
    }

    response = client.post("/api/editor/validate/Test Template", json=form)

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert [(e["field"], e["code"]) for e in body["errors"]] == [("Conformity", "not_allowed")]


def test_document_download(client, mirror):
    aasx = client.get("/api/templates/Test Template/documents/aasx")
    assert aasx.status_code == 200
    assert aasx.content[:2] == b"PK"
    assert "IDTA 02999-1-0-1_Template_Test.aasx" in aasx.headers["content-disposition"]

    json_doc = client.get("/api/templates/Test Template/documents/json")
    assert json_doc.status_code == 200
    assert json_doc.headers["content-type"].startswith("application/json")

    # No PDF is published for this template.
    missing = client.get("/api/templates/Test Template/documents/specification")
    assert missing.status_code == 404

    unknown = client.get("/api/templates/Missing Template/documents/aasx")
    assert unknown.status_code == 404


def test_specification_notes_unavailable_without_pdf(client):
    response = client.get("/api/editor/templates/Test Template/specification-notes")

    assert response.status_code == 200
    assert response.json() == {
        "available": False,
        "document": None,
        "pageCount": None,
        "matched": 0,
        "total": 0,
        "notes": {},
    }


def test_specification_notes_are_read_from_the_pdf_and_cached(client, mirror, tmp_path):
    pdf_name = "IDTA 02999-1-0_Submodel_Test.pdf"
    (mirror / TEMPLATE_DIR / "1" / "0" / pdf_name).write_bytes(_spec_pdf())
    client.post("/api/templates/refresh")

    schema = client.get("/api/editor/templates/Test Template/schema").json()
    # The patch release has no PDF of its own: the one of its release line applies.
    assert schema["template"]["documents"]["specification"]["name"] == pdf_name

    pdf = client.get("/api/templates/Test Template/documents/specification")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.headers["content-disposition"].startswith("inline")

    response = client.get("/api/editor/templates/Test Template/specification-notes")
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["document"]["name"] == pdf_name
    assert body["pageCount"] == 1

    country = body["notes"]["CountryOfOrigin"]
    assert country["notes"] == ["only countries of the customs union are allowed"]
    assert country["example"] == "FR"
    assert country["page"] == 1
    # The PDF says mandatory, the package says optional: both are reported.
    assert country["cardinality"] == "[1]"
    assert country["templateCardinality"] == "[0..1]"
    assert body["notes"]["Conformity"]["cardinality"] == "[1]"

    cached = list((tmp_path / "cache").glob("*.spec.json"))
    assert len(cached) == 1
    again = client.get("/api/editor/templates/Test Template/specification-notes")
    assert again.json() == body
