"""
Ollama Embedding Client - Generate embeddings using local Ollama server.

Uses nomic-embed-text model for 768-dimensional embeddings that run entirely
locally, ensuring data privacy for industrial use cases.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class OllamaEmbeddingClient:
    """Generate embeddings using local Ollama server."""

    DEFAULT_MODEL = "nomic-embed-text"
    DEFAULT_BASE_URL = "http://localhost:11434"
    EMBEDDING_DIM = 768  # nomic-embed-text produces 768-dim vectors

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        """
        Initialize Ollama embedding client.

        Args:
            base_url: Ollama server URL (default: http://localhost:11434)
            model: Embedding model name (default: nomic-embed-text)
            timeout: Request timeout in seconds
        """
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.model = model or self.DEFAULT_MODEL
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def embed(self, text: str) -> list[float]:
        """
        Generate embedding vector for text.

        Args:
            text: Text to embed

        Returns:
            768-dimensional embedding vector

        Raises:
            httpx.HTTPError: If request fails
            ValueError: If response is malformed
        """
        if not text or not text.strip():
            # Return zero vector for empty text
            return [0.0] * self.EMBEDDING_DIM

        client = await self._get_client()

        try:
            response = await client.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": text.strip()},
            )
            response.raise_for_status()

            data = response.json()
            embedding = data.get("embedding")

            if not embedding or not isinstance(embedding, list):
                raise ValueError(f"Invalid embedding response: {data}")

            return embedding

        except httpx.TimeoutException:
            logger.warning("Ollama embedding request timed out for text: %s...", text[:50])
            raise
        except httpx.HTTPStatusError as e:
            logger.error("Ollama embedding failed with status %d: %s", e.response.status_code, e)
            raise
        except Exception as e:
            logger.error("Ollama embedding error: %s", e)
            raise

    async def embed_batch(
        self,
        texts: list[str],
        max_concurrent: int = 5,
    ) -> list[list[float]]:
        """
        Generate embeddings for multiple texts with concurrency control.

        Ollama doesn't natively support batching, so we parallelize requests
        with a semaphore to avoid overwhelming the server.

        Args:
            texts: List of texts to embed
            max_concurrent: Maximum concurrent requests

        Returns:
            List of embedding vectors (same order as input)
        """
        if not texts:
            return []

        semaphore = asyncio.Semaphore(max_concurrent)

        async def embed_with_semaphore(text: str) -> list[float]:
            async with semaphore:
                return await self.embed(text)

        # Process in parallel with concurrency limit
        tasks = [embed_with_semaphore(text) for text in texts]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any exceptions by returning zero vectors
        embeddings = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(
                    "Failed to embed text %d: %s. Using zero vector.",
                    i,
                    str(result)[:100],
                )
                embeddings.append([0.0] * self.EMBEDDING_DIM)
            else:
                embeddings.append(result)

        return embeddings

    async def is_available(self) -> bool:
        """
        Check if Ollama server and embedding model are available.

        Returns:
            True if server is reachable and model is loaded
        """
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/api/tags")

            if response.status_code != 200:
                return False

            data = response.json()
            models = data.get("models", [])

            # Check if our embedding model is available
            for model_info in models:
                model_name = model_info.get("name", "")
                # Match exact name or name:tag format
                if model_name == self.model or model_name.startswith(f"{self.model}:"):
                    return True

            logger.warning(
                "Ollama model '%s' not found. Available models: %s",
                self.model,
                [m.get("name") for m in models],
            )
            return False

        except httpx.RequestError as e:
            logger.debug("Ollama server not reachable: %s", e)
            return False
        except Exception as e:
            logger.warning("Error checking Ollama availability: %s", e)
            return False

    async def ensure_model_available(self) -> bool:
        """
        Ensure the embedding model is available, pulling if necessary.

        Returns:
            True if model is available after check/pull
        """
        if await self.is_available():
            return True

        # Try to pull the model
        logger.info("Pulling Ollama model '%s'...", self.model)

        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.base_url}/api/pull",
                json={"name": self.model},
                timeout=600.0,  # Model downloads can take a while
            )

            if response.status_code == 200:
                logger.info("Successfully pulled model '%s'", self.model)
                return True

            logger.error("Failed to pull model '%s': %s", self.model, response.text)
            return False

        except Exception as e:
            logger.error("Error pulling model '%s': %s", self.model, e)
            return False

    @staticmethod
    def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
        """
        Compute cosine similarity between two vectors.

        Args:
            vec_a: First vector
            vec_b: Second vector

        Returns:
            Cosine similarity score (-1 to 1, typically 0 to 1 for text embeddings)
        """
        if len(vec_a) != len(vec_b):
            raise ValueError(f"Vector dimension mismatch: {len(vec_a)} vs {len(vec_b)}")

        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = sum(a * a for a in vec_a) ** 0.5
        norm_b = sum(b * b for b in vec_b) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)
