"""Tests for template name resolution in the fetcher service."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.services.fetcher import TemplateFetcherService


@pytest.fixture
def fetcher(tmp_path):
    with patch("app.services.fetcher.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            github_token="test-token",
            github_repo="admin-shell-io/submodel-templates",
            cache_dir=tmp_path / "cache",
            cache_ttl_hours=24,
            github_api_version="2022-11-28",
            github_template_ref="main",
            local_templates_enabled=False,
            local_templates_dir=tmp_path / "local",
        )
        return TemplateFetcherService()


def _seed_templates(fetcher: TemplateFetcherService, templates: list[dict]) -> None:
    cache_key = "template_index:published:local=False"
    fetcher._index_cache[cache_key] = (templates, datetime.now())


@pytest.mark.asyncio
async def test_resolve_template_case_insensitive(fetcher):
    templates = [
        {
            "name": "Digital nameplate",
            "path": "published/Digital nameplate",
            "url": "https://github.com/admin-shell-io/submodel-templates",
            "idta_number": "02006",
            "title": "Digital nameplate",
            "sha": None,
            "status": "published",
        }
    ]
    _seed_templates(fetcher, templates)

    resolved = await fetcher.resolve_template("Digital Nameplate", ["published"])
    assert resolved is not None
    assert resolved["name"] == "Digital nameplate"


@pytest.mark.asyncio
async def test_resolve_template_normalized(fetcher):
    templates = [
        {
            "name": "Digital nameplate",
            "path": "published/Digital nameplate",
            "url": "https://github.com/admin-shell-io/submodel-templates",
            "idta_number": "02006",
            "title": "Digital nameplate",
            "sha": None,
            "status": "published",
        }
    ]
    _seed_templates(fetcher, templates)

    resolved = await fetcher.resolve_template("Digital-Nameplate", ["published"])
    assert resolved is not None
    assert resolved["name"] == "Digital nameplate"


@pytest.mark.asyncio
async def test_resolve_template_by_idta_number(fetcher):
    templates = [
        {
            "name": "Digital nameplate",
            "path": "published/Digital nameplate",
            "url": "https://github.com/admin-shell-io/submodel-templates",
            "idta_number": "02006",
            "title": "Digital nameplate",
            "sha": None,
            "status": "published",
        }
    ]
    _seed_templates(fetcher, templates)

    resolved = await fetcher.resolve_template("IDTA 02006", ["published"])
    assert resolved is not None
    assert resolved["name"] == "Digital nameplate"


@pytest.mark.asyncio
async def test_resolve_template_path_preserves_versions(fetcher):
    templates = [
        {
            "name": "Digital nameplate",
            "path": "published/Digital nameplate",
            "url": "https://github.com/admin-shell-io/submodel-templates",
            "idta_number": "02006",
            "title": "Digital nameplate",
            "sha": None,
            "status": "published",
        }
    ]
    _seed_templates(fetcher, templates)

    resolved_path = await fetcher.resolve_template_path(
        "published/Digital Nameplate/3/0/1"
    )
    assert resolved_path == "published/Digital nameplate/3/0/1"


@pytest.mark.asyncio
async def test_resolve_template_path_local_unchanged(fetcher):
    resolved_path = await fetcher.resolve_template_path("local/Digital Nameplate")
    assert resolved_path == "local/Digital Nameplate"
