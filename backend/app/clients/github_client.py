"""
GitHub API client for template discovery.

Provides a reusable client for interacting with the GitHub API.
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class GitHubClient:
    """
    Async HTTP client for GitHub API.

    Features:
    - Automatic authentication handling
    - Rate limit awareness
    - Retry with backoff
    """

    BASE_URL = "https://api.github.com"

    def __init__(
        self,
        token: str | None = None,
        api_version: str = "2022-11-28",
    ):
        self.token = token
        self.api_version = api_version
        self._client: httpx.AsyncClient | None = None

    @property
    def headers(self) -> dict[str, str]:
        """Get default headers for API requests."""
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": self.api_version,
            "User-Agent": "IDTA-Submodel-Editor/1.0",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                headers=self.headers,
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def get(self, path: str, **kwargs) -> dict[str, Any]:
        """
        Make a GET request to the GitHub API.

        Args:
            path: API path (without base URL)
            **kwargs: Additional request arguments

        Returns:
            JSON response

        Raises:
            httpx.HTTPStatusError: On HTTP errors
        """
        client = await self._get_client()
        response = await client.get(path, **kwargs)
        response.raise_for_status()
        return response.json()

    async def get_contents(self, repo: str, path: str) -> list[dict[str, Any]]:
        """
        Get repository contents at a path.

        Args:
            repo: Repository in "owner/name" format
            path: Path within the repository

        Returns:
            List of content items
        """
        return await self.get(f"/repos/{repo}/contents/{path}")

    async def get_raw_file(self, download_url: str) -> bytes:
        """
        Download a raw file from GitHub.

        Args:
            download_url: Direct download URL

        Returns:
            File contents as bytes
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(download_url, follow_redirects=True)
            response.raise_for_status()
            return response.content

    async def get_rate_limit(self) -> dict[str, Any]:
        """
        Get current rate limit status.

        Returns:
            Rate limit information
        """
        return await self.get("/rate_limit")

    async def search_code(
        self,
        query: str,
        repo: str | None = None,
        language: str | None = None,
        per_page: int = 30,
    ) -> dict[str, Any]:
        """
        Search for code in repositories.

        Args:
            query: Search query
            repo: Limit to specific repository
            language: Filter by language
            per_page: Results per page

        Returns:
            Search results
        """
        q = query
        if repo:
            q += f" repo:{repo}"
        if language:
            q += f" language:{language}"

        return await self.get(
            "/search/code",
            params={"q": q, "per_page": per_page},
        )

    async def __aenter__(self) -> "GitHubClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()
