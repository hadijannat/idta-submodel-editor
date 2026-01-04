"""
Template Fetcher Service.

Integrates with GitHub API to discover and cache IDTA templates
from the admin-shell-io/submodel-templates repository.
"""

import base64
import hashlib
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

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

        async with httpx.AsyncClient(timeout=30.0) as client:
            url = f"https://api.github.com/repos/{self.github_repo}/contents/published"
            response = await client.get(url, headers=self.headers)
            response.raise_for_status()
            directories = response.json()

        templates = []
        for item in directories:
            if item["type"] == "dir":
                # Parse template name to extract IDTA number and title
                name = item["name"]
                template_info = self._parse_template_name(name)
                templates.append(
                    {
                        "name": name,
                        "path": item["path"],
                        "url": item["url"],
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
        async with httpx.AsyncClient(timeout=60.0) as client:
            contents_url = (
                f"https://api.github.com/repos/{self.github_repo}/contents/{template_path}"
            )
            response = await client.get(contents_url, headers=self.headers)
            response.raise_for_status()
            items = response.json()

        # Find the AASX file (may be in a version subdirectory)
        aasx_download_url = await self._find_aasx_file(items)
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
