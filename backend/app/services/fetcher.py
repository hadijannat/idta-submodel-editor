"""
Template Fetcher Service.

Integrates with GitHub API to discover and cache IDTA templates
from the admin-shell-io/submodel-templates repository.
"""

import base64
import hashlib
import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class TemplateFetcherService:
    """
    Service for fetching IDTA submodel templates from GitHub.

    Features:
    - Discovers templates from admin-shell-io/submodel-templates
    - Caches AASX files locally with configurable TTL
    - Supports authenticated requests for higher rate limits
    """

    def __init__(
        self,
        github_token: str | None = None,
        cache_dir: Path | None = None,
        cache_ttl_hours: int = 24,
    ):
        settings = get_settings()
        self.github_token = github_token or settings.github_token
        self.github_repo = settings.github_repo
        self.cache_dir = cache_dir or settings.cache_dir
        self.cache_ttl_hours = cache_ttl_hours or settings.cache_ttl_hours
        self.github_api_version = settings.github_api_version

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # In-memory index cache
        self._index_cache: dict[str, tuple[Any, datetime]] = {}

    @property
    def headers(self) -> dict[str, str]:
        """Get HTTP headers for GitHub API requests."""
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": self.github_api_version,
            "User-Agent": "IDTA-Submodel-Editor/1.0",
        }
        if self.github_token:
            headers["Authorization"] = f"Bearer {self.github_token}"
        return headers

    def _is_cache_valid(self, cache_time: datetime) -> bool:
        """Check if cached data is still within TTL."""
        return datetime.now() - cache_time < timedelta(hours=self.cache_ttl_hours)

    def _get_cache_path(self, template_path: str) -> Path:
        """Generate cache file path for a template."""
        cache_key = hashlib.md5(template_path.encode()).hexdigest()
        return self.cache_dir / f"{cache_key}.aasx"

    async def list_available_templates(self) -> list[dict]:
        """
        List all available IDTA templates from GitHub.

        Returns:
            List of template metadata dictionaries.
        """
        cache_key = "template_index"

        # Check in-memory cache
        if cache_key in self._index_cache:
            data, timestamp = self._index_cache[cache_key]
            if self._is_cache_valid(timestamp):
                logger.debug("Returning cached template index")
                return data

        logger.info("Fetching template index from GitHub")

        directories = None
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = f"https://api.github.com/repos/{self.github_repo}/contents/published"
            try:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                directories = response.json()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 403 and "rate limit" in exc.response.text.lower():
                    logger.warning(
                        "GitHub API rate limit hit while listing templates, falling back to HTML listing",
                    )
                    directories = await self._list_templates_via_html()
                else:
                    raise

        templates = []
        for item in directories or []:
            is_dir = item.get("type") == "dir" or item.get("contentType") == "directory"
            if is_dir:
                # Parse template name to extract IDTA number and title
                name = item.get("name")
                if not name:
                    continue
                template_info = self._parse_template_name(name)
                path = item.get("path") or f"published/{name}"
                url = item.get("url")
                if not url:
                    url_path = quote(path, safe="/")
                    url = f"https://github.com/{self.github_repo}/tree/main/{url_path}"
                templates.append(
                    {
                        "name": name,
                        "path": path,
                        "url": url,
                        "idta_number": template_info.get("idta_number"),
                        "title": template_info.get("title"),
                        "sha": item.get("sha"),
                    }
                )

        # Sort by IDTA number, falling back to a high value when missing.
        templates.sort(
            key=lambda x: (
                x.get("idta_number") or "99999",
                x.get("title") or x.get("name", ""),
            )
        )

        self._index_cache[cache_key] = (templates, datetime.now())
        return templates

    async def _list_templates_via_html(self) -> list[dict]:
        """
        Fallback to GitHub HTML tree listing for /published.
        """
        items = await self._fetch_github_tree_items("published")
        templates: dict[str, dict] = {}
        for item in items:
            if item.get("contentType") != "directory":
                continue

            raw_name = item.get("name") or ""
            raw_path = item.get("path") or ""
            if raw_path.startswith("published/"):
                root = raw_path.split("/", 2)[1]
            else:
                root = raw_name.split("/", 1)[0]

            if not root:
                continue

            path = f"published/{root}"
            url_path = quote(path, safe="/")
            templates.setdefault(
                root,
                {
                    "name": root,
                    "path": path,
                    "url": f"https://github.com/{self.github_repo}/tree/main/{url_path}",
                    "sha": None,
                    "type": "dir",
                    "contentType": "directory",
                },
            )

        return list(templates.values())

    def _parse_template_name(self, name: str) -> dict:
        """
        Parse template directory name to extract IDTA number and title.

        Examples:
            "IDTA 02006-2-0_Submodel_Digital Nameplate" ->
                {"idta_number": "02006", "title": "Digital Nameplate"}
        """
        parts = name.split("_", 2)
        result = {"idta_number": None, "title": name}

        if len(parts) >= 1 and parts[0].startswith("IDTA"):
            # Extract number from "IDTA 02006-2-0"
            idta_part = parts[0].replace("IDTA ", "").split("-")[0]
            result["idta_number"] = idta_part.strip()

        if len(parts) >= 3:
            result["title"] = parts[2].strip()
        elif len(parts) >= 2:
            result["title"] = parts[1].strip()

        return result

    async def fetch_template_aasx(self, template_path: str) -> bytes:
        """
        Fetch AASX file for a template.

        Args:
            template_path: Path to template directory (e.g., "published/IDTA 02006...")

        Returns:
            AASX file contents as bytes.
        """
        cache_file = self._get_cache_path(template_path)

        # Check disk cache
        if cache_file.exists():
            mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
            if self._is_cache_valid(mtime):
                logger.debug(f"Returning cached AASX for {template_path}")
                return cache_file.read_bytes()

        logger.info(f"Fetching AASX for {template_path} from GitHub")

        # Navigate to find the AASX file
        aasx_download_url = None
        async with httpx.AsyncClient(timeout=60.0) as client:
            contents_url = (
                f"https://api.github.com/repos/{self.github_repo}/contents/{template_path}"
            )
            try:
                response = await client.get(contents_url, headers=self.headers)
                response.raise_for_status()
                items = response.json()
                aasx_download_url = await self._find_aasx_file(items)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 403 and "rate limit" in exc.response.text.lower():
                    logger.warning(
                        "GitHub API rate limit hit while fetching %s, falling back to HTML listing",
                        template_path,
                    )
                    aasx_download_url = await self._find_aasx_file_via_html(
                        template_path
                    )
                else:
                    raise
        if not aasx_download_url:
            raise ValueError(f"No AASX file found in {template_path}")

        # Download the AASX file
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.get(aasx_download_url, follow_redirects=True)
            response.raise_for_status()
            aasx_bytes = response.content

        # Cache to disk
        cache_file.write_bytes(aasx_bytes)
        logger.info(f"Cached AASX to {cache_file}")

        return aasx_bytes

    async def _find_aasx_file(
        self, items: list[dict], depth: int = 0, max_depth: int = 3
    ) -> str | None:
        """
        Recursively find AASX file in directory listing.

        Searches through version directories to find the latest AASX file.
        """
        if depth > max_depth:
            return None

        aasx_files = []
        subdirs = []

        for item in items:
            if item["type"] == "file" and item["name"].endswith(".aasx"):
                aasx_files.append(item)
            elif item["type"] == "dir":
                subdirs.append(item)

        # If we found AASX files, return the download URL of the most recent one
        if aasx_files:
            # Sort by name to get the latest version
            aasx_files.sort(key=lambda x: x["name"], reverse=True)
            return aasx_files[0]["download_url"]

        # Otherwise, search in subdirectories (version folders)
        for subdir in subdirs:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(subdir["url"], headers=self.headers)
                if response.status_code == 200:
                    sub_items = response.json()
                    result = await self._find_aasx_file(sub_items, depth + 1, max_depth)
                    if result:
                        return result

        return None

    async def _find_aasx_file_via_html(
        self, template_path: str, depth: int = 0, max_depth: int = 3
    ) -> str | None:
        """
        Fallback to GitHub HTML directory listings when API is rate-limited.
        """
        if depth > max_depth:
            return None

        items = await self._fetch_github_tree_items(template_path)
        if not items:
            return None

        aasx_files = [
            item
            for item in items
            if item.get("contentType") == "file"
            and item.get("name", "").endswith(".aasx")
        ]
        subdirs = [
            item for item in items if item.get("contentType") == "directory"
        ]

        if aasx_files:
            aasx_files.sort(key=lambda x: x.get("name", ""), reverse=True)
            filename = aasx_files[0].get("name")
            if not filename:
                return None
            raw_path = quote(f"{template_path}/{filename}", safe="/")
            return (
                f"https://raw.githubusercontent.com/{self.github_repo}/main/{raw_path}"
            )

        for subdir in subdirs:
            name = subdir.get("name")
            if not name:
                continue
            result = await self._find_aasx_file_via_html(
                f"{template_path}/{name}",
                depth + 1,
                max_depth,
            )
            if result:
                return result

        return None

    async def _fetch_github_tree_items(self, path: str) -> list[dict]:
        """
        Parse GitHub HTML tree page to get directory items.
        """
        url_path = quote(path, safe="/")
        url = f"https://github.com/{self.github_repo}/tree/main/{url_path}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text

        match = re.search(
            r'data-target=\"react-app.embeddedData\"[^>]*>(.*?)</script>',
            html,
            re.S,
        )
        if not match:
            logger.warning("Failed to find embedded data on GitHub tree page: %s", url)
            return []

        raw_json = match.group(1).strip()
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse GitHub embedded data JSON: %s", exc)
            return []

        return data.get("payload", {}).get("tree", {}).get("items", []) or []

    async def get_template_versions(self, template_path: str) -> list[dict]:
        """
        Get available versions for a template.

        Returns:
            List of version metadata.
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = f"https://api.github.com/repos/{self.github_repo}/contents/{template_path}"
            response = await client.get(url, headers=self.headers)
            response.raise_for_status()
            items = response.json()

        versions = []
        for item in items:
            if item["type"] == "dir":
                versions.append(
                    {
                        "version": item["name"],
                        "path": item["path"],
                        "sha": item.get("sha"),
                    }
                )

        # Sort versions (newest first)
        versions.sort(key=lambda x: x["version"], reverse=True)
        return versions

    def clear_cache(self) -> int:
        """
        Clear all cached templates.

        Returns:
            Number of files removed.
        """
        count = 0
        for cache_file in self.cache_dir.glob("*.aasx"):
            cache_file.unlink()
            count += 1

        self._index_cache.clear()
        logger.info(f"Cleared {count} cached templates")
        return count

    def invalidate_template(self, template_path: str) -> bool:
        """
        Invalidate cache for a specific template.

        Returns:
            True if cache file was removed.
        """
        cache_file = self._get_cache_path(template_path)
        if cache_file.exists():
            cache_file.unlink()
            logger.info(f"Invalidated cache for {template_path}")
            return True
        return False
