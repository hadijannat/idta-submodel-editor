"""
Template Fetcher Service.

Integrates with GitHub API to discover and cache IDTA templates
from the admin-shell-io/submodel-templates repository.
"""

import hashlib
import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlencode, urlparse, urlunparse

import httpx

from app.config import get_settings
from app.metrics import record_template_fetch, template_fetch_duration_seconds

logger = logging.getLogger(__name__)


class TemplateFetcherService:
    """
    Service for fetching IDTA submodel templates from GitHub and local filesystem.

    Features:
    - Discovers templates from admin-shell-io/submodel-templates
    - Supports local templates stored in configurable directory
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
        self.github_template_ref = settings.github_template_ref

        # Local templates configuration
        self.local_templates_enabled = settings.local_templates_enabled
        self.local_templates_dir = settings.local_templates_dir

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Ensure local templates directory exists if enabled
        if self.local_templates_enabled:
            self.local_templates_dir.mkdir(parents=True, exist_ok=True)

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

    def _normalize_template_key(self, name: str) -> str:
        """Normalize template names for loose matching."""
        return re.sub(r"[^a-z0-9]+", "", name.lower())

    def _extract_idta_number(self, name: str) -> str | None:
        """Extract IDTA number from a template name if present."""
        match = re.search(r"(?:IDTA\s*)?(\d{5})", name, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    async def resolve_template(
        self,
        template_name: str,
        statuses: list[str] | None = None,
        include_local: bool = False,
    ) -> dict | None:
        """
        Resolve a template name to a known template entry.

        Matches case-insensitively and by normalized keys to avoid GitHub path
        mismatches (e.g., "Digital Nameplate" vs "Digital nameplate").
        """
        roots = statuses or ["published"]
        templates, _ = await self.list_available_templates(
            roots, include_local=include_local
        )
        if not templates:
            return None

        # Exact match
        for template in templates:
            if template.get("name") == template_name:
                return template

        # Case-insensitive match
        name_lower = template_name.lower()
        for template in templates:
            if template.get("name", "").lower() == name_lower:
                return template

        # Normalized match against name/title
        target_key = self._normalize_template_key(template_name)
        if target_key:
            for template in templates:
                for field in ("name", "title"):
                    value = template.get(field) or ""
                    if value and self._normalize_template_key(value) == target_key:
                        return template

        # IDTA number match
        idta_number = self._extract_idta_number(template_name)
        if idta_number:
            for template in templates:
                if template.get("idta_number") == idta_number:
                    return template

        return None

    async def resolve_template_path(self, template_path: str) -> str:
        """
        Resolve a template path to the canonical name.

        Keeps version suffixes intact while fixing case/format mismatches.
        """
        if template_path.startswith("local/"):
            return template_path

        parts = template_path.split("/", 2)
        if len(parts) < 2:
            return template_path

        status, name = parts[0], parts[1]
        remainder = parts[2] if len(parts) > 2 else ""
        resolved = await self.resolve_template(name, [status], include_local=False)
        if not resolved:
            return template_path

        resolved_name = resolved.get("name") or name
        if resolved_name == name:
            return template_path

        if remainder:
            return f"{status}/{resolved_name}/{remainder}"
        return f"{status}/{resolved_name}"

    def _add_ref_param(self, url: str, ref: str) -> str:
        """Add or update the ref query parameter in a URL."""
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        params["ref"] = [ref]
        new_query = urlencode(params, doseq=True)
        return urlunparse(parsed._replace(query=new_query))

    def _get_cache_path(self, template_path: str) -> Path:
        """Generate cache file path for a template."""
        cache_key = hashlib.md5(template_path.encode()).hexdigest()
        return self.cache_dir / f"{cache_key}.aasx"

    def _get_etag_path(self, template_path: str) -> Path:
        """Generate ETag file path for a template."""
        cache_key = hashlib.md5(template_path.encode()).hexdigest()
        return self.cache_dir / f"{cache_key}.etag"

    def _get_cached_etag(self, template_path: str) -> str | None:
        """Get cached ETag for a template if it exists."""
        etag_path = self._get_etag_path(template_path)
        if etag_path.exists():
            return etag_path.read_text().strip()
        return None

    def _save_etag(self, template_path: str, etag: str) -> None:
        """Save ETag for a template."""
        etag_path = self._get_etag_path(template_path)
        etag_path.write_text(etag)

    async def list_available_templates(
        self, statuses: list[str] | None = None, include_local: bool = True
    ) -> tuple[list[dict], bool]:
        """
        List all available IDTA templates from GitHub and local filesystem.

        Args:
            statuses: List of GitHub statuses to include (published, deprecated)
            include_local: Whether to include local templates

        Returns:
            Tuple of (template list, cached flag).
        """
        roots = statuses or ["published"]
        cache_key = f"template_index:{','.join(sorted(roots))}:local={include_local}"

        # Check in-memory cache
        if cache_key in self._index_cache:
            data, timestamp = self._index_cache[cache_key]
            if self._is_cache_valid(timestamp):
                logger.debug("Returning cached template index")
                return data, True

        logger.info("Fetching template index from GitHub")

        templates: list[dict] = []
        for root in roots:
            templates.extend(await self._list_templates_for_root(root))

        # Add local templates if enabled and requested
        if include_local and self.local_templates_enabled:
            templates.extend(self._list_local_templates())

        # Sort by IDTA number, falling back to a high value when missing.
        # Local templates (status="local") come after published but before deprecated
        status_order = {"published": 0, "local": 1, "deprecated": 2}
        templates.sort(
            key=lambda x: (
                status_order.get(x.get("status", "published"), 99),
                x.get("idta_number") or "99999",
                x.get("title") or x.get("name", ""),
            )
        )

        self._index_cache[cache_key] = (templates, datetime.now())
        return templates, False

    def _list_local_templates(self) -> list[dict]:
        """
        List all local templates from the local templates directory.

        Returns:
            List of template metadata dictionaries.
        """
        templates = []

        if not self.local_templates_dir.exists():
            return templates

        for aasx_file in self.local_templates_dir.glob("*.aasx"):
            name = aasx_file.stem  # filename without extension
            template_info = self._parse_template_name(name)
            templates.append(
                {
                    "name": name,
                    "path": f"local/{name}",
                    "url": None,  # No URL for local templates
                    "idta_number": template_info.get("idta_number"),
                    "title": template_info.get("title"),
                    "sha": None,
                    "status": "local",
                    "source": "local",
                    "file_path": str(aasx_file),
                }
            )

        return templates

    async def _list_templates_for_root(self, root: str) -> list[dict]:
        """
        List templates under a specific root (e.g. published, deprecated).
        """
        directories = None
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = (
                "https://api.github.com/repos/"
                f"{self.github_repo}/contents/{root}?ref={self.github_template_ref}"
            )
            try:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                directories = response.json()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 403 and "rate limit" in exc.response.text.lower():
                    logger.warning(
                        "GitHub API rate limit hit while listing templates, falling back to HTML listing",
                    )
                    directories = await self._list_templates_via_html(root)
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
                path = item.get("path") or f"{root}/{name}"
                url = item.get("url")
                if not url:
                    url_path = quote(path, safe="/")
                    url = (
                        "https://github.com/"
                        f"{self.github_repo}/tree/{self.github_template_ref}/{url_path}"
                    )
                templates.append(
                    {
                        "name": name,
                        "path": path,
                        "url": url,
                        "idta_number": template_info.get("idta_number"),
                        "title": template_info.get("title"),
                        "sha": item.get("sha"),
                        "status": root,
                    }
                )
        return templates

    async def _list_templates_via_html(self, root: str) -> list[dict]:
        """
        Fallback to GitHub HTML tree listing for a given root.
        """
        items = await self._fetch_github_tree_items(root)
        templates: dict[str, dict] = {}
        for item in items:
            if item.get("contentType") != "directory":
                continue

            raw_name = item.get("name") or ""
            raw_path = item.get("path") or raw_name
            if not raw_path:
                continue
            if raw_path.startswith(f"{root}/"):
                template_name = raw_path.split("/", 1)[1].split("/", 1)[0]
            else:
                template_name = raw_path.split("/", 1)[0]

            if not template_name:
                continue

            path = f"{root}/{template_name}"
            url_path = quote(path, safe="/")
            templates.setdefault(
                template_name,
                {
                    "name": template_name,
                    "path": path,
                    "url": (
                        "https://github.com/"
                        f"{self.github_repo}/tree/{self.github_template_ref}/{url_path}"
                    ),
                    "sha": None,
                    "type": "dir",
                    "contentType": "directory",
                    "status": root,
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

        Uses ETag-based conditional requests to reduce GitHub API pressure.
        If we have a cached file and ETag, sends If-None-Match header.
        On 304 Not Modified, returns cached content and extends TTL.

        Args:
            template_path: Path to template directory (e.g., "published/IDTA 02006...")
                          For local templates, use "local/{template_name}"

        Returns:
            AASX file contents as bytes.
        """
        import time
        fetch_start = time.perf_counter()

        template_path = await self.resolve_template_path(template_path)

        # Handle local templates
        if template_path.startswith("local/"):
            content = self._fetch_local_template_aasx(template_path)
            record_template_fetch(source="local", cache_hit=True)
            template_fetch_duration_seconds.labels(source="local").observe(
                time.perf_counter() - fetch_start
            )
            return content

        cache_file = self._get_cache_path(template_path)
        cached_etag = self._get_cached_etag(template_path)

        # Check disk cache
        if cache_file.exists():
            mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
            if self._is_cache_valid(mtime):
                logger.debug(f"Returning cached AASX for {template_path}")
                record_template_fetch(source="github", cache_hit=True)
                template_fetch_duration_seconds.labels(source="github").observe(
                    time.perf_counter() - fetch_start
                )
                return cache_file.read_bytes()

        logger.info(f"Fetching AASX for {template_path} from GitHub")

        # Navigate to find the AASX file
        aasx_download_url = None
        aasx_sha = None
        async with httpx.AsyncClient(timeout=60.0) as client:
            contents_url = (
                "https://api.github.com/repos/"
                f"{self.github_repo}/contents/{template_path}"
                f"?ref={self.github_template_ref}"
            )

            # Build request headers - add If-None-Match if we have a cached ETag
            request_headers = dict(self.headers)
            if cached_etag and cache_file.exists():
                request_headers["If-None-Match"] = cached_etag

            try:
                response = await client.get(contents_url, headers=request_headers)

                # Handle 304 Not Modified - return cached content
                if response.status_code == 304:
                    logger.debug(
                        f"ETag match for {template_path}, returning cached content"
                    )
                    # Touch cache file to extend TTL
                    cache_file.touch()
                    record_template_fetch(source="github", cache_hit=True)
                    template_fetch_duration_seconds.labels(source="github").observe(
                        time.perf_counter() - fetch_start
                    )
                    return cache_file.read_bytes()

                response.raise_for_status()
                items = response.json()
                aasx_download_url, aasx_sha = await self._find_aasx_file_with_sha(items)

                # Store ETag from response if present
                etag = response.headers.get("ETag")
                if etag:
                    self._save_etag(template_path, etag)

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

        # Download the AASX file with conditional request if we have a SHA
        async with httpx.AsyncClient(timeout=120.0) as client:
            download_headers = {}
            if aasx_sha and cache_file.exists():
                download_headers["If-None-Match"] = f'"{aasx_sha}"'

            response = await client.get(
                aasx_download_url, follow_redirects=True, headers=download_headers
            )

            # Handle 304 Not Modified for the actual download
            if response.status_code == 304:
                logger.debug(f"File unchanged for {template_path}, extending cache TTL")
                cache_file.touch()
                record_template_fetch(source="github", cache_hit=True)
                template_fetch_duration_seconds.labels(source="github").observe(
                    time.perf_counter() - fetch_start
                )
                return cache_file.read_bytes()

            response.raise_for_status()
            aasx_bytes = response.content

        # Cache to disk
        cache_file.write_bytes(aasx_bytes)
        # Store file SHA as ETag for future conditional downloads
        if aasx_sha:
            self._save_etag(template_path, f'"{aasx_sha}"')
        logger.info(f"Cached AASX to {cache_file}")

        # Record cache miss (full fetch)
        record_template_fetch(source="github", cache_hit=False)
        template_fetch_duration_seconds.labels(source="github").observe(
            time.perf_counter() - fetch_start
        )

        return aasx_bytes

    async def _find_aasx_file(
        self, items: list[dict], depth: int = 0, max_depth: int = 3
    ) -> str | None:
        """
        Recursively find AASX file in directory listing.

        Searches through version directories to find the latest AASX file.
        """
        result, _ = await self._find_aasx_file_with_sha(items, depth, max_depth)
        return result

    async def _find_aasx_file_with_sha(
        self, items: list[dict], depth: int = 0, max_depth: int = 3
    ) -> tuple[str | None, str | None]:
        """
        Recursively find AASX file in directory listing, returning both URL and SHA.

        The SHA can be used for conditional requests (ETag) on subsequent downloads.

        Returns:
            Tuple of (download_url, sha) where sha may be None.
        """
        if depth > max_depth:
            return None, None

        aasx_files = []
        subdirs = []

        for item in items:
            if item["type"] == "file" and item["name"].endswith(".aasx"):
                aasx_files.append(item)
            elif item["type"] == "dir":
                subdirs.append(item)

        # If we found AASX files, return the download URL and SHA of the most recent one
        if aasx_files:
            # Sort by name to get the latest version
            aasx_files.sort(key=lambda x: x["name"], reverse=True)
            selected = aasx_files[0]
            return selected.get("download_url"), selected.get("sha")

        # Otherwise, search in subdirectories (version folders)
        for subdir in subdirs:
            async with httpx.AsyncClient(timeout=30.0) as client:
                url = self._add_ref_param(subdir["url"], self.github_template_ref)
                response = await client.get(url, headers=self.headers)
                if response.status_code == 200:
                    sub_items = response.json()
                    url, sha = await self._find_aasx_file_with_sha(
                        sub_items, depth + 1, max_depth
                    )
                    if url:
                        return url, sha

        return None, None

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
            selected = aasx_files[0]
            raw_file_path = selected.get("path")
            filename = selected.get("name")
            if not raw_file_path and not filename:
                return None
            raw_path = quote(raw_file_path or f"{template_path}/{filename}", safe="/")
            return (
                "https://raw.githubusercontent.com/"
                f"{self.github_repo}/{self.github_template_ref}/{raw_path}"
            )

        for subdir in subdirs:
            subdir_path = subdir.get("path")
            name = subdir.get("name")
            if not subdir_path and not name:
                continue
            result = await self._find_aasx_file_via_html(
                subdir_path or f"{template_path}/{name}",
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
        url = (
            "https://github.com/"
            f"{self.github_repo}/tree/{self.github_template_ref}/{url_path}"
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text

        matches = re.finditer(
            r'data-target="react-app\.embeddedData"[^>]*>(.*?)</script>',
            html,
            re.S,
        )
        for match in matches:
            raw_json = match.group(1).strip()
            try:
                data = json.loads(raw_json)
            except json.JSONDecodeError as exc:
                logger.warning("Failed to parse GitHub embedded data JSON: %s", exc)
                continue

            payload = data.get("payload", {})
            tree = payload.get("tree", {})
            items = tree.get("items")
            if items:
                return items

            code_view_tree = payload.get("codeViewTreeRoute", {}).get("tree", {})
            items = code_view_tree.get("items")
            if items:
                return items

        if 'data-target="react-app.embeddedData"' not in html:
            logger.warning("Failed to find embedded data on GitHub tree page: %s", url)
        return []

    async def get_template_versions(self, template_path: str) -> list[dict]:
        """
        Get available versions for a template.

        Returns:
            List of version metadata.
        """
        template_path = await self.resolve_template_path(template_path)
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = (
                "https://api.github.com/repos/"
                f"{self.github_repo}/contents/{template_path}"
                f"?ref={self.github_template_ref}"
            )
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
        Clear all cached templates and ETags.

        Returns:
            Number of files removed.
        """
        count = 0
        for cache_file in self.cache_dir.glob("*.aasx"):
            cache_file.unlink()
            count += 1
        # Also clear ETag files
        for etag_file in self.cache_dir.glob("*.etag"):
            etag_file.unlink()

        self._index_cache.clear()
        logger.info(f"Cleared {count} cached templates")
        return count

    def invalidate_template(self, template_path: str) -> bool:
        """
        Invalidate cache for a specific template.

        Also removes the associated ETag file.

        Returns:
            True if cache file was removed.
        """
        cache_file = self._get_cache_path(template_path)
        etag_file = self._get_etag_path(template_path)
        removed = False

        if cache_file.exists():
            cache_file.unlink()
            removed = True

        if etag_file.exists():
            etag_file.unlink()

        if removed:
            logger.info(f"Invalidated cache for {template_path}")
        return removed

    # -------------------------------------------------------------------------
    # Local Template Management
    # -------------------------------------------------------------------------

    def _fetch_local_template_aasx(self, template_path: str) -> bytes:
        """
        Fetch AASX file from local templates directory.

        Args:
            template_path: Path in format "local/{template_name}"

        Returns:
            AASX file contents as bytes.

        Raises:
            ValueError: If local templates are disabled or template not found.
        """
        if not self.local_templates_enabled:
            raise ValueError("Local templates are disabled")

        # Extract template name from path (e.g., "local/MyTemplate" -> "MyTemplate")
        parts = template_path.split("/", 1)
        if len(parts) < 2:
            raise ValueError(f"Invalid local template path: {template_path}")

        template_name = parts[1]
        aasx_file = self.local_templates_dir / f"{template_name}.aasx"

        if not aasx_file.exists():
            raise ValueError(f"Local template not found: {template_name}")

        logger.debug(f"Reading local template: {aasx_file}")
        return aasx_file.read_bytes()

    def save_local_template(self, name: str, aasx_bytes: bytes) -> dict:
        """
        Save an AASX file as a local template.

        Args:
            name: Template name (will be sanitized)
            aasx_bytes: AASX file contents

        Returns:
            Template metadata dictionary.

        Raises:
            ValueError: If local templates are disabled or name is invalid.
        """
        if not self.local_templates_enabled:
            raise ValueError("Local templates are disabled")

        # Sanitize the name to prevent path traversal
        safe_name = self._sanitize_template_name(name)
        if not safe_name:
            raise ValueError("Invalid template name")

        aasx_file = self.local_templates_dir / f"{safe_name}.aasx"
        aasx_file.write_bytes(aasx_bytes)

        # Invalidate index cache to include the new template
        self._invalidate_index_cache()

        logger.info(f"Saved local template: {safe_name}")

        template_info = self._parse_template_name(safe_name)
        return {
            "name": safe_name,
            "path": f"local/{safe_name}",
            "url": None,
            "idta_number": template_info.get("idta_number"),
            "title": template_info.get("title"),
            "sha": None,
            "status": "local",
            "source": "local",
            "file_path": str(aasx_file),
        }

    def delete_local_template(self, name: str) -> bool:
        """
        Delete a local template.

        Args:
            name: Template name

        Returns:
            True if template was deleted, False if not found.

        Raises:
            ValueError: If local templates are disabled.
        """
        if not self.local_templates_enabled:
            raise ValueError("Local templates are disabled")

        safe_name = self._sanitize_template_name(name)
        aasx_file = self.local_templates_dir / f"{safe_name}.aasx"

        if aasx_file.exists():
            aasx_file.unlink()
            self._invalidate_index_cache()
            logger.info(f"Deleted local template: {safe_name}")
            return True

        return False

    def _sanitize_template_name(self, name: str) -> str:
        """
        Sanitize a template name to prevent path traversal and invalid characters.

        Args:
            name: Raw template name

        Returns:
            Sanitized name safe for filesystem use.
        """
        # Remove path separators and dangerous characters
        sanitized = name.replace("/", "_").replace("\\", "_").replace("..", "_")
        # Remove leading/trailing whitespace and dots
        sanitized = sanitized.strip().strip(".")
        # Ensure we have a valid name
        if not sanitized or sanitized in (".", ".."):
            return ""
        return sanitized

    def _invalidate_index_cache(self) -> None:
        """Invalidate the in-memory template index cache."""
        # Clear all entries that include local templates
        keys_to_remove = [k for k in self._index_cache if "local=" in k]
        for key in keys_to_remove:
            del self._index_cache[key]
        logger.debug("Invalidated local template index cache")
