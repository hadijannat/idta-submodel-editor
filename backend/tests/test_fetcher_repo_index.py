"""Tests for template discovery through the repository index."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.services.fetcher import TemplateFetcherService

NAMEPLATE = "published/Digital nameplate"


def _settings(tmp_path, **overrides):
    values = dict(
        github_token=None,
        github_repo="admin-shell-io/submodel-templates",
        cache_dir=tmp_path / "cache",
        cache_ttl_hours=24,
        github_api_version="2022-11-28",
        github_template_ref="main",
        local_templates_enabled=False,
        local_templates_dir=tmp_path / "local",
        template_repo_index_enabled=True,
        template_repo_dir=None,
    )
    values.update(overrides)
    return MagicMock(**values)


def _make_fetcher(tmp_path, **overrides) -> TemplateFetcherService:
    with patch("app.services.fetcher.get_settings") as mock_settings:
        mock_settings.return_value = _settings(tmp_path, **overrides)
        return TemplateFetcherService()


def _write(root, relative: str, content: bytes = b"x") -> None:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)


@pytest.fixture
def mirror(tmp_path):
    root = tmp_path / "mirror"
    _write(root, f"{NAMEPLATE}/3/0/IDTA 02006-3-0_Template_Digital Nameplate.aasx", b"v3.0")
    _write(root, f"{NAMEPLATE}/3/0/IDTA 02006-3-0_Submodel_Digital Nameplate.pdf", b"%PDF-spec")
    _write(root, f"{NAMEPLATE}/3/0/3/IDTA 02006-3-0-3_Template_Digital Nameplate.aasx", b"v3.0.3")
    _write(root, f"{NAMEPLATE}/3/0/3/IDTA 02006-3-0-3_Template_Digital Nameplate.json", b"{}")
    _write(
        root,
        "published/Digital Battery Passport/7_Circularity/1/0/IDTA 02035-7_DBP-Part-7_Circularity.aasx",
        b"part7",
    )
    _write(root, "deprecated/Old Template/1/0/IDTA 02999-1-0_Template_Old.aasx", b"old")
    return root


@pytest.mark.asyncio
async def test_local_mirror_serves_latest_release_without_network(tmp_path, mirror):
    fetcher = _make_fetcher(tmp_path, template_repo_dir=mirror)

    with patch("app.services.fetcher.httpx.AsyncClient") as client:
        templates, cached = await fetcher.list_available_templates(
            ["published"], include_local=False
        )
        latest = await fetcher.fetch_template_aasx(NAMEPLATE)
        pinned = await fetcher.fetch_template_aasx(NAMEPLATE, "3.0")
        by_path = await fetcher.fetch_template_aasx(f"{NAMEPLATE}/3/0/3")
        part = await fetcher.fetch_template_aasx(
            "published/Digital Battery Passport~7_Circularity"
        )

    client.assert_not_called()
    assert cached is False
    assert latest == b"v3.0.3"
    assert pinned == b"v3.0"
    assert by_path == b"v3.0.3"
    assert part == b"part7"

    by_name = {template["name"]: template for template in templates}
    nameplate = by_name["Digital nameplate"]
    assert nameplate["idta_number"] == "02006"
    assert nameplate["latest_version"] == "3.0.3"
    assert nameplate["versions"] == ["3.0.3", "3.0"]
    assert nameplate["has_specification"] is True
    assert by_name["Digital Battery Passport~7_Circularity"]["group"] == "Digital Battery Passport"
    assert "Old Template" not in by_name


@pytest.mark.asyncio
async def test_templates_are_sorted_by_idta_number(tmp_path, mirror):
    fetcher = _make_fetcher(tmp_path, template_repo_dir=mirror)

    templates, _ = await fetcher.list_available_templates(
        ["published", "deprecated"], include_local=False
    )

    assert [template["idta_number"] for template in templates] == [
        "02006",
        "02035-7",
        "02999",
    ]
    assert templates[-1]["status"] == "deprecated"


@pytest.mark.asyncio
async def test_unknown_template_raises_value_error(tmp_path, mirror):
    fetcher = _make_fetcher(tmp_path, template_repo_dir=mirror)

    with pytest.raises(ValueError, match="Template not found"):
        await fetcher.fetch_template_aasx("published/Does Not Exist")


@pytest.mark.asyncio
async def test_versions_and_description_come_from_the_index(tmp_path, mirror):
    fetcher = _make_fetcher(tmp_path, template_repo_dir=mirror)

    versions = await fetcher.get_template_versions(NAMEPLATE)
    description = await fetcher.describe_template(NAMEPLATE)
    document = await fetcher.fetch_template_document(NAMEPLATE, "specification")

    assert [(v["version"], v["latest"]) for v in versions] == [("3.0.3", True), ("3.0", False)]
    assert description is not None
    assert description["version"] == "3.0.3"
    assert description["isLatest"] is True
    assert description["idtaNumber"] == "02006"
    assert description["documents"]["specification"]["name"].endswith("Digital Nameplate.pdf")
    assert description["documents"]["json"]["name"].endswith("3-0-3_Template_Digital Nameplate.json")
    assert document is not None
    assert document[1] == b"%PDF-spec"

    pinned = await fetcher.describe_template(NAMEPLATE, "3.0")
    assert pinned is not None
    assert pinned["isLatest"] is False
    assert pinned["latestVersion"] == "3.0.3"


def _tree_response(paths: list[str]) -> MagicMock:
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status = MagicMock()
    response.json.return_value = {
        "truncated": False,
        "tree": [
            {"path": path, "type": "blob", "sha": f"sha{i:040d}", "size": 10}
            for i, path in enumerate(paths)
        ]
        + [{"path": "published", "type": "tree", "sha": "t"}],
    }
    return response


class _FakeClient:
    """Minimal httpx.AsyncClient stand-in recording requested URLs."""

    def __init__(self, handler, calls):
        self._handler = handler
        self._calls = calls

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, **kwargs):
        self._calls.append(url)
        return self._handler(url)


@pytest.mark.asyncio
async def test_github_index_uses_one_tree_request_and_raw_downloads(tmp_path):
    fetcher = _make_fetcher(tmp_path)
    paths = [
        f"{NAMEPLATE}/3/0/IDTA 02006-3-0_Template_Digital Nameplate.aasx",
        f"{NAMEPLATE}/3/0/3/IDTA 02006-3-0-3_Template_Digital Nameplate.aasx",
    ]
    calls: list[str] = []

    def handler(url: str):
        if "/git/trees/" in url:
            return _tree_response(paths)
        response = MagicMock()
        response.status_code = 200
        response.raise_for_status = MagicMock()
        response.content = b"aasx-bytes"
        return response

    with patch(
        "app.services.fetcher.httpx.AsyncClient",
        side_effect=lambda *a, **k: _FakeClient(handler, calls),
    ):
        templates, _ = await fetcher.list_available_templates(["published"], include_local=False)
        first = await fetcher.fetch_template_aasx(NAMEPLATE)
        second = await fetcher.fetch_template_aasx(NAMEPLATE)

    assert [template["latest_version"] for template in templates] == ["3.0.3"]
    assert first == second == b"aasx-bytes"
    tree_calls = [url for url in calls if "/git/trees/" in url]
    raw_calls = [url for url in calls if "raw.githubusercontent.com" in url]
    assert len(tree_calls) == 1
    # The newest release is downloaded once; the second fetch is served from cache.
    assert len(raw_calls) == 1
    assert raw_calls[0].endswith(
        "/main/published/Digital%20nameplate/3/0/3/"
        "IDTA%2002006-3-0-3_Template_Digital%20Nameplate.aasx"
    )
    assert fetcher._repo_index_cache_file.exists()


@pytest.mark.asyncio
async def test_saved_index_is_used_when_github_is_unreachable(tmp_path):
    paths = [f"{NAMEPLATE}/3/0/3/IDTA 02006-3-0-3_Template_Digital Nameplate.aasx"]
    calls: list[str] = []

    online = _make_fetcher(tmp_path)
    with patch(
        "app.services.fetcher.httpx.AsyncClient",
        side_effect=lambda *a, **k: _FakeClient(lambda url: _tree_response(paths), calls),
    ):
        await online.list_available_templates(["published"], include_local=False)

    def unreachable(url: str):
        raise httpx.ConnectError("offline")

    offline = _make_fetcher(tmp_path)
    with patch(
        "app.services.fetcher.httpx.AsyncClient",
        side_effect=lambda *a, **k: _FakeClient(unreachable, calls),
    ):
        templates, _ = await offline.list_available_templates(
            ["published"], include_local=False
        )
        description = await offline.describe_template(NAMEPLATE)

    assert [template["name"] for template in templates] == ["Digital nameplate"]
    assert description is not None
    assert description["stale"] is True
    assert description["source"] == "github-cached"


@pytest.mark.asyncio
async def test_index_disabled_keeps_per_directory_listing(tmp_path):
    fetcher = _make_fetcher(tmp_path, template_repo_index_enabled=False)

    assert await fetcher.get_repo_index() is None
    assert await fetcher.describe_template(NAMEPLATE) is None


@pytest.mark.asyncio
async def test_legacy_search_prefers_newest_version_folder(tmp_path):
    """Without the index, numeric subfolders are searched newest first."""
    fetcher = _make_fetcher(tmp_path, template_repo_index_enabled=False)
    listings = {
        "https://api.example/3": [
            {"type": "dir", "name": "0", "url": "https://api.example/3/0"},
        ],
        "https://api.example/3/0": [
            {
                "type": "file",
                "name": "IDTA 02006-3-0_Template.aasx",
                "download_url": "https://dl.example/3.0.aasx",
                "sha": "base",
            },
            {"type": "dir", "name": "2", "url": "https://api.example/3/0/2"},
            {"type": "dir", "name": "10", "url": "https://api.example/3/0/10"},
            {"type": "dir", "name": "docs", "url": "https://api.example/3/0/docs"},
        ],
        "https://api.example/3/0/10": [
            {
                "type": "file",
                "name": "IDTA 02006-3-0-10_Template.aasx",
                "download_url": "https://dl.example/3.0.10.aasx",
                "sha": "patch10",
            }
        ],
        "https://api.example/1": [
            {
                "type": "file",
                "name": "IDTA 02006-1-0_Template.aasx",
                "download_url": "https://dl.example/1.0.aasx",
                "sha": "v1",
            }
        ],
    }
    calls: list[str] = []

    def handler(url: str):
        response = MagicMock()
        base = url.split("?")[0]
        response.status_code = 200 if base in listings else 404
        response.json.return_value = listings.get(base, [])
        return response

    items = [
        {"type": "dir", "name": "1", "url": "https://api.example/1"},
        {"type": "dir", "name": "3", "url": "https://api.example/3"},
    ]
    with patch(
        "app.services.fetcher.httpx.AsyncClient",
        side_effect=lambda *a, **k: _FakeClient(handler, calls),
    ):
        url, sha = await fetcher._find_aasx_file_with_sha(items)

    assert url == "https://dl.example/3.0.10.aasx"
    assert sha == "patch10"


def test_empty_mirror_setting_means_not_configured(monkeypatch):
    from app.config import Settings

    monkeypatch.setenv("TEMPLATE_REPO_DIR", "")
    assert Settings().template_repo_dir is None

    monkeypatch.setenv("TEMPLATE_REPO_DIR", "  /srv/templates ")
    assert str(Settings().template_repo_dir) == "/srv/templates"


@pytest.mark.asyncio
async def test_directory_without_template_folders_is_not_used_as_mirror(tmp_path):
    not_a_checkout = tmp_path / "empty"
    not_a_checkout.mkdir()
    fetcher = _make_fetcher(tmp_path, template_repo_dir=not_a_checkout)
    calls: list[str] = []
    paths = [f"{NAMEPLATE}/3/0/IDTA 02006-3-0_Template_Digital Nameplate.aasx"]

    with patch(
        "app.services.fetcher.httpx.AsyncClient",
        side_effect=lambda *a, **k: _FakeClient(lambda url: _tree_response(paths), calls),
    ):
        templates, _ = await fetcher.list_available_templates(
            ["published"], include_local=False
        )

    assert [template["name"] for template in templates] == ["Digital nameplate"]
    assert any("/git/trees/" in url for url in calls)
