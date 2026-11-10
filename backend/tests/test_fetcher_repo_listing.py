"""Fetcher behaviour against a fake GitHub rebuilt from the upstream path snapshot."""

from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import quote, unquote

import httpx
import pytest

from app.services.fetcher import TemplateFetcherService

SNAPSHOT = Path(__file__).parent / "fixtures" / "upstream" / "idta-aasx-paths.txt"
REPO = "admin-shell-io/submodel-templates"
API = f"https://api.github.com/repos/{REPO}"
RAW = f"https://raw.githubusercontent.com/{REPO}/main/"


def _snapshot_paths() -> list[str]:
    return [
        line
        for line in SNAPSHOT.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    ]


def _sha(path: str) -> str:
    return hashlib.sha1(path.encode()).hexdigest()


class FakeGitHub:
    """Serves the tree API, the contents API and raw downloads for a set of paths."""

    def __init__(self, paths: list[str]):
        self.paths = list(paths)
        self.requests: list[str] = []
        self.tree_status = 200
        self.tree_truncated = False
        self.revision = "r1"

    # -- helpers -----------------------------------------------------------
    def count(self, prefix: str) -> int:
        return sum(1 for url in self.requests if url.startswith(prefix))

    def blob_sha(self, path: str) -> str:
        return _sha(f"{self.revision}:{path}")

    def _contents(self, directory: str) -> list[dict] | None:
        prefix = directory.rstrip("/") + "/"
        children: dict[str, str] = {}
        for path in self.paths:
            if not path.startswith(prefix):
                continue
            head, _, rest = path[len(prefix) :].partition("/")
            children.setdefault(head, "dir" if rest else "file")
        if not children:
            return None
        items = []
        for name in sorted(children):
            child = f"{prefix}{name}"
            is_file = children[name] == "file"
            items.append(
                {
                    "name": name,
                    "path": child,
                    "type": "file" if is_file else "dir",
                    "sha": self.blob_sha(child) if is_file else _sha(child),
                    "url": f"{API}/contents/{quote(child)}?ref=main",
                    "download_url": RAW + quote(child) if is_file else None,
                }
            )
        return items

    # -- request handling --------------------------------------------------
    def handle(self, url: str) -> httpx.Response:
        self.requests.append(url)
        request = httpx.Request("GET", url)
        if url.startswith(f"{API}/git/trees/"):
            if self.tree_status != 200:
                return httpx.Response(self.tree_status, request=request, text="unavailable")
            tree = [
                {"path": path, "type": "blob", "sha": self.blob_sha(path)}
                for path in self.paths
            ]
            tree.append({"path": "published", "type": "tree", "sha": "t"})
            return httpx.Response(
                200, request=request, json={"tree": tree, "truncated": self.tree_truncated}
            )
        if url.startswith(f"{API}/contents/"):
            directory = unquote(url[len(f"{API}/contents/") :].split("?")[0])
            items = self._contents(directory)
            if items is None:
                return httpx.Response(404, request=request, json={"message": "Not Found"})
            return httpx.Response(200, request=request, json=items)
        if url.startswith(RAW):
            path = unquote(url[len(RAW) :])
            if path not in self.paths:
                return httpx.Response(404, request=request, text="missing")
            return httpx.Response(200, request=request, content=f"AASX:{path}".encode())
        return httpx.Response(500, request=request, text=f"unexpected url {url}")

    def client_class(self):
        github = self

        class _Client:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def get(self, url, headers=None, **kwargs):
                return github.handle(str(url))

        return _Client


@pytest.fixture
def github():
    return FakeGitHub(_snapshot_paths())


@pytest.fixture
def fetcher(tmp_path, github):
    with patch("app.services.fetcher.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            github_token=None,
            github_repo=REPO,
            cache_dir=tmp_path / "cache",
            cache_ttl_hours=24,
            github_api_version="2022-11-28",
            github_template_ref="main",
            local_templates_enabled=False,
            local_templates_dir=tmp_path / "local",
        )
        service = TemplateFetcherService()
    with patch("app.services.fetcher.httpx.AsyncClient", github.client_class()):
        yield service


def _expire(path: Path, hours: int = 25) -> None:
    old = time.time() - hours * 3600
    os.utime(path, (old, old))


class TestListing:
    @pytest.mark.asyncio
    async def test_lists_every_template_with_one_request(self, fetcher, github):
        templates, cached = await fetcher.list_available_templates(
            ["published"], include_local=False
        )

        assert cached is False
        assert len(templates) == 66
        assert github.requests == [f"{API}/git/trees/main?recursive=1"]

        by_name = {t["name"]: t for t in templates}
        nameplate = by_name["Digital nameplate"]
        assert nameplate["path"] == "published/Digital nameplate"
        assert nameplate["idta_number"] == "02006"
        assert nameplate["latest_version"] == "3.0.3"
        assert nameplate["part"] is None
        assert nameplate["url"].endswith("/tree/main/published/Digital%20nameplate")

        part = by_name["Digital Battery Passport - 6_Material Composition"]
        assert part["path"] == "published/Digital Battery Passport/6_Material Composition"
        assert part["folder"] == "Digital Battery Passport"
        assert part["title"] == "Digital Battery Passport: Material Composition"

    @pytest.mark.asyncio
    async def test_parts_stay_in_part_order(self, fetcher):
        templates, _ = await fetcher.list_available_templates(
            ["published"], include_local=False
        )
        battery = [t["part"] for t in templates if t["folder"] == "Digital Battery Passport"]
        assert battery == sorted(battery)
        assert len(battery) == 7

    @pytest.mark.asyncio
    async def test_deprecated_templates_are_listed_separately(self, fetcher):
        templates, _ = await fetcher.list_available_templates(
            ["deprecated"], include_local=False
        )
        assert len(templates) == 8
        assert {t["status"] for t in templates} == {"deprecated"}

    @pytest.mark.asyncio
    async def test_falls_back_to_directory_listing_when_tree_is_unavailable(
        self, fetcher, github
    ):
        github.tree_status = 503

        templates, _ = await fetcher.list_available_templates(
            ["published"], include_local=False
        )

        # The directory listing only knows folders, not their parts.
        assert len(templates) == 56
        assert "Digital Battery Passport" in {t["name"] for t in templates}
        assert github.count(f"{API}/contents/published") == 1

    @pytest.mark.asyncio
    async def test_truncated_listing_is_not_trusted(self, fetcher, github):
        github.tree_truncated = True

        templates, _ = await fetcher.list_available_templates(
            ["published"], include_local=False
        )

        assert len(templates) == 56

    @pytest.mark.asyncio
    async def test_failed_listing_is_not_retried_immediately(self, fetcher, github):
        github.tree_status = 503

        await fetcher.list_available_templates(["published"], include_local=False)
        await fetcher.list_available_templates(["deprecated"], include_local=False)

        assert github.count(f"{API}/git/trees/") == 1


class TestResolution:
    @pytest.mark.asyncio
    async def test_folder_name_resolves_to_first_part(self, fetcher):
        resolved = await fetcher.resolve_template("Digital Battery Passport", ["published"])
        assert resolved["name"] == "Digital Battery Passport - 1_Digital Nameplate"

        path = await fetcher.resolve_template_path("published/digital battery passport")
        assert path == "published/Digital Battery Passport/1_Digital Nameplate"

    @pytest.mark.asyncio
    async def test_folder_name_prefers_the_folders_own_template(self, fetcher):
        resolved = await fetcher.resolve_template(
            "hierarchical structures enabling bills of material", ["published"]
        )
        assert resolved["part"] is None

    @pytest.mark.asyncio
    async def test_part_name_resolves_to_part_directory(self, fetcher):
        path = await fetcher.resolve_template_path(
            "published/Digital Battery Passport - 6_Material Composition/1/0"
        )
        assert path == "published/Digital Battery Passport/6_Material Composition/1/0"

    @pytest.mark.asyncio
    async def test_repository_path_of_a_part_is_left_alone(self, fetcher):
        path = "published/Digital Battery Passport/6_Material Composition"
        assert await fetcher.resolve_template_path(path) == path

    @pytest.mark.asyncio
    async def test_version_is_kept_for_plain_templates(self, fetcher):
        assert (
            await fetcher.resolve_template_path("published/Digital Nameplate/3")
            == "published/Digital nameplate/3"
        )
        assert (
            await fetcher.resolve_template_path("published/Digital nameplate/3")
            == "published/Digital nameplate/3"
        )


class TestFetch:
    @pytest.mark.asyncio
    async def test_downloads_newest_patch(self, fetcher, github):
        content = await fetcher.fetch_template_aasx("published/Digital nameplate")

        expected = (
            "published/Digital nameplate/3/0/3/"
            "IDTA 02006-3-0-3_Template_Digital Nameplate.aasx"
        )
        assert content == f"AASX:{expected}".encode()
        assert github.count(f"{API}/contents/") == 0

    @pytest.mark.asyncio
    async def test_downloads_newest_minor_not_the_first(self, fetcher):
        content = await fetcher.fetch_template_aasx("published/Asset Interfaces Description")
        assert b"/1/2/1/" in content

    @pytest.mark.asyncio
    async def test_explicit_version_is_respected(self, fetcher):
        content = await fetcher.fetch_template_aasx(
            "published/Asset Interfaces Description/1/1"
        )
        assert b"/1/1/IDTA 02017-1-1_Template" in content

    @pytest.mark.asyncio
    async def test_every_listed_template_can_be_fetched(self, fetcher):
        templates, _ = await fetcher.list_available_templates(
            ["published", "deprecated"], include_local=False
        )
        for template in templates:
            content = await fetcher.fetch_template_aasx(
                f"{template['status']}/{template['name']}"
            )
            assert content.startswith(f"AASX:{template['path']}/".encode()), template["name"]

    @pytest.mark.asyncio
    async def test_unchanged_file_is_not_downloaded_again(self, fetcher, github):
        path = "published/Digital nameplate"
        first = await fetcher.fetch_template_aasx(path)
        _expire(fetcher._get_cache_path(path))

        second = await fetcher.fetch_template_aasx(path)

        assert second == first
        assert github.count(RAW) == 1

    @pytest.mark.asyncio
    async def test_changed_file_is_downloaded_again(self, fetcher, github):
        path = "published/Digital nameplate"
        await fetcher.fetch_template_aasx(path)
        _expire(fetcher._get_cache_path(path))
        github.revision = "r2"
        fetcher.clear_cache()

        await fetcher.fetch_template_aasx(path)

        assert github.count(RAW) == 2

    @pytest.mark.asyncio
    async def test_unknown_template_reports_missing_file(self, fetcher):
        with pytest.raises(httpx.HTTPStatusError):
            await fetcher.fetch_template_aasx("published/No Such Template")

    @pytest.mark.asyncio
    async def test_navigation_fallback_also_finds_newest_patch(self, fetcher, github):
        github.tree_status = 503

        nameplate = await fetcher.fetch_template_aasx("published/Digital nameplate")
        assert b"/3/0/3/IDTA 02006-3-0-3_Template_Digital Nameplate.aasx" in nameplate

        interfaces = await fetcher.fetch_template_aasx(
            "published/Asset Interfaces Description"
        )
        assert b"/1/2/1/" in interfaces

    @pytest.mark.asyncio
    async def test_navigation_fallback_reaches_deep_parts(self, fetcher, github):
        github.tree_status = 503

        passport = await fetcher.fetch_template_aasx("published/Digital Product Passport")

        assert b"Digital Product Passport Part-1/1/0/2/" in passport


class TestVersions:
    @pytest.mark.asyncio
    async def test_lists_every_release_newest_first(self, fetcher):
        versions = await fetcher.get_template_versions(
            "published/Asset Interfaces Description"
        )

        assert [v["label"] for v in versions] == [
            "1.2.1",
            "1.2",
            "1.1.2",
            "1.1.1",
            "1.1",
            "1.0.1",
            "1.0",
        ]
        assert versions[0]["version"] == "1/2/1"
        assert versions[0]["path"] == "published/Asset Interfaces Description/1/2/1"

    @pytest.mark.asyncio
    async def test_version_values_select_exactly_that_release(self, fetcher):
        template = "published/Asset Interfaces Description"
        for version in await fetcher.get_template_versions(template):
            content = await fetcher.fetch_template_aasx(f"{template}/{version['version']}")
            assert content.startswith(f"AASX:{version['path']}/IDTA".encode()), version

    @pytest.mark.asyncio
    async def test_versions_of_a_part(self, fetcher):
        versions = await fetcher.get_template_versions(
            "published/Digital Battery Passport - 6_Material Composition"
        )
        assert [v["label"] for v in versions][0] == "1.0.2"

    @pytest.mark.asyncio
    async def test_falls_back_to_directory_names(self, fetcher, github):
        github.tree_status = 503

        versions = await fetcher.get_template_versions("published/Digital nameplate")

        assert [v["version"] for v in versions] == ["3"]
