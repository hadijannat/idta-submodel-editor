"""Tests for ETag caching in the fetcher service."""

import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.fetcher import TemplateFetcherService


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create a temporary cache directory."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return cache_dir


@pytest.fixture
def fetcher(temp_cache_dir):
    """Create a fetcher service with temp cache."""
    with patch("app.services.fetcher.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            github_token="test-token",
            github_repo="admin-shell-io/submodel-templates",
            cache_dir=temp_cache_dir,
            cache_ttl_hours=24,
            github_api_version="2022-11-28",
            local_templates_enabled=False,
            local_templates_dir=temp_cache_dir / "local",
        )
        return TemplateFetcherService()


class TestETagPathGeneration:
    """Tests for ETag path generation."""

    def test_get_etag_path_generates_consistent_path(self, fetcher):
        """Test that ETag path is deterministic for same template."""
        path1 = fetcher._get_etag_path("published/IDTA-02006")
        path2 = fetcher._get_etag_path("published/IDTA-02006")
        assert path1 == path2

    def test_get_etag_path_different_for_different_templates(self, fetcher):
        """Test that different templates get different ETag paths."""
        path1 = fetcher._get_etag_path("published/IDTA-02006")
        path2 = fetcher._get_etag_path("published/IDTA-02007")
        assert path1 != path2

    def test_get_etag_path_is_alongside_cache_file(self, fetcher):
        """Test that ETag file is in same directory as cache file."""
        cache_path = fetcher._get_cache_path("published/IDTA-02006")
        etag_path = fetcher._get_etag_path("published/IDTA-02006")
        assert cache_path.parent == etag_path.parent

    def test_etag_file_has_etag_extension(self, fetcher):
        """Test that ETag files have .etag extension."""
        etag_path = fetcher._get_etag_path("published/IDTA-02006")
        assert etag_path.suffix == ".etag"


class TestETagStorage:
    """Tests for ETag storage and retrieval."""

    def test_save_and_get_etag(self, fetcher):
        """Test saving and retrieving an ETag."""
        template_path = "published/IDTA-02006"
        etag = '"abc123"'

        fetcher._save_etag(template_path, etag)
        retrieved = fetcher._get_cached_etag(template_path)

        assert retrieved == etag

    def test_get_cached_etag_returns_none_when_missing(self, fetcher):
        """Test that missing ETag returns None."""
        retrieved = fetcher._get_cached_etag("nonexistent/template")
        assert retrieved is None

    def test_etag_file_content(self, fetcher):
        """Test that ETag is stored as plain text."""
        template_path = "published/IDTA-02006"
        etag = '"W/sha123"'

        fetcher._save_etag(template_path, etag)

        etag_path = fetcher._get_etag_path(template_path)
        assert etag_path.read_text() == etag


class TestCacheClearingWithETag:
    """Tests for cache clearing that includes ETags."""

    def test_clear_cache_removes_etag_files(self, fetcher, temp_cache_dir):
        """Test that clearing cache also removes ETag files."""
        # Create some cache and ETag files
        template_path = "published/IDTA-02006"
        cache_file = fetcher._get_cache_path(template_path)
        cache_file.write_bytes(b"test content")
        fetcher._save_etag(template_path, '"etag123"')

        # Verify files exist
        assert cache_file.exists()
        assert fetcher._get_etag_path(template_path).exists()

        # Clear cache
        fetcher.clear_cache()

        # Verify all files removed
        assert not cache_file.exists()
        assert not fetcher._get_etag_path(template_path).exists()

    def test_invalidate_template_removes_etag(self, fetcher):
        """Test that invalidating a template also removes its ETag."""
        template_path = "published/IDTA-02006"
        cache_file = fetcher._get_cache_path(template_path)
        cache_file.write_bytes(b"test content")
        fetcher._save_etag(template_path, '"etag123"')

        # Invalidate
        result = fetcher.invalidate_template(template_path)

        assert result is True
        assert not cache_file.exists()
        assert not fetcher._get_etag_path(template_path).exists()


class TestConditionalFetch:
    """Tests for conditional fetch with ETag."""

    @pytest.mark.asyncio
    async def test_304_returns_cached_content(self, fetcher):
        """Test that 304 Not Modified returns cached content."""
        template_path = "published/IDTA-02006"
        cache_file = fetcher._get_cache_path(template_path)
        cached_content = b"cached aasx content"
        cache_file.write_bytes(cached_content)
        fetcher._save_etag(template_path, '"etag123"')

        # Mock httpx to return 304
        mock_response_304 = MagicMock()
        mock_response_304.status_code = 304

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response_304

            result = await fetcher.fetch_template_aasx(template_path)

        assert result == cached_content

    @pytest.mark.asyncio
    async def test_304_extends_cache_ttl(self, fetcher):
        """Test that 304 response touches cache file to extend TTL."""
        template_path = "published/IDTA-02006"
        cache_file = fetcher._get_cache_path(template_path)
        cache_file.write_bytes(b"cached content")
        fetcher._save_etag(template_path, '"etag123"')

        # Set old mtime (1 day ago)
        old_time = time.time() - 86400
        os.utime(cache_file, (old_time, old_time))
        old_mtime = cache_file.stat().st_mtime

        # Mock 304 response
        mock_response_304 = MagicMock()
        mock_response_304.status_code = 304

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response_304

            await fetcher.fetch_template_aasx(template_path)

        # Verify mtime was updated (should be much newer than 1 day ago)
        new_mtime = cache_file.stat().st_mtime
        assert new_mtime > old_mtime
        # Should be within last few seconds
        assert time.time() - new_mtime < 5

    @pytest.mark.asyncio
    async def test_if_none_match_header_sent(self, fetcher):
        """Test that If-None-Match header is sent when ETag is cached and cache is expired."""
        template_path = "published/IDTA-02006"
        cache_file = fetcher._get_cache_path(template_path)
        cache_file.write_bytes(b"cached content")
        etag = '"etag123"'
        fetcher._save_etag(template_path, etag)

        # Make cache expired (older than TTL)
        old_time = time.time() - (fetcher.cache_ttl_hours * 3600 + 100)
        os.utime(cache_file, (old_time, old_time))

        # Track headers sent
        captured_headers = []

        # Mock 304 response
        mock_response_304 = MagicMock()
        mock_response_304.status_code = 304

        async def capture_get(url, headers=None, **kwargs):
            if headers:
                captured_headers.append(dict(headers))
            return mock_response_304

        with patch("app.services.fetcher.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get = capture_get

            await fetcher.fetch_template_aasx(template_path)

        # Verify If-None-Match was in headers
        assert len(captured_headers) > 0, "Expected at least one HTTP request to be made"
        # The first call should have the If-None-Match header
        assert any(h.get("If-None-Match") == etag for h in captured_headers)


class TestFindAasxWithSha:
    """Tests for _find_aasx_file_with_sha method."""

    @pytest.mark.asyncio
    async def test_returns_url_and_sha(self, fetcher):
        """Test that method returns both URL and SHA."""
        items = [
            {
                "type": "file",
                "name": "template.aasx",
                "download_url": "https://example.com/template.aasx",
                "sha": "abc123",
            }
        ]

        url, sha = await fetcher._find_aasx_file_with_sha(items)

        assert url == "https://example.com/template.aasx"
        assert sha == "abc123"

    @pytest.mark.asyncio
    async def test_returns_none_when_no_aasx(self, fetcher):
        """Test that method returns None when no AASX found."""
        items = [{"type": "file", "name": "readme.md", "download_url": "..."}]

        url, sha = await fetcher._find_aasx_file_with_sha(items)

        assert url is None
        assert sha is None

    @pytest.mark.asyncio
    async def test_selects_latest_version(self, fetcher):
        """Test that latest version AASX is selected."""
        items = [
            {
                "type": "file",
                "name": "template_v1.aasx",
                "download_url": "https://example.com/v1.aasx",
                "sha": "sha-v1",
            },
            {
                "type": "file",
                "name": "template_v2.aasx",
                "download_url": "https://example.com/v2.aasx",
                "sha": "sha-v2",
            },
        ]

        url, sha = await fetcher._find_aasx_file_with_sha(items)

        # v2 should be selected (sorted reverse)
        assert url == "https://example.com/v2.aasx"
        assert sha == "sha-v2"

    @pytest.mark.asyncio
    async def test_find_aasx_file_delegates(self, fetcher):
        """Test that _find_aasx_file delegates to _find_aasx_file_with_sha."""
        items = [
            {
                "type": "file",
                "name": "template.aasx",
                "download_url": "https://example.com/template.aasx",
                "sha": "abc123",
            }
        ]

        # Original method should still work
        url = await fetcher._find_aasx_file(items)
        assert url == "https://example.com/template.aasx"
