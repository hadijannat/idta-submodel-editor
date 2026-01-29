"""Tests for Ollama embedding client."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from app.services.template_knowledge.embeddings import OllamaEmbeddingClient


class TestOllamaEmbeddingClient:
    """Tests for OllamaEmbeddingClient."""

    @pytest.fixture
    def client(self):
        """Create a client instance."""
        return OllamaEmbeddingClient(
            base_url="http://localhost:11434",
            model="nomic-embed-text",
        )

    def test_init_defaults(self):
        """Test default initialization values."""
        client = OllamaEmbeddingClient()
        assert client.base_url == "http://localhost:11434"
        assert client.model == "nomic-embed-text"
        assert client.EMBEDDING_DIM == 768

    def test_init_custom_values(self):
        """Test custom initialization values."""
        client = OllamaEmbeddingClient(
            base_url="http://custom:8080",
            model="custom-model",
        )
        assert client.base_url == "http://custom:8080"
        assert client.model == "custom-model"

    @pytest.mark.asyncio
    async def test_embed_empty_text_returns_zero_vector(self, client):
        """Test that empty text returns a zero vector."""
        result = await client.embed("")
        assert len(result) == 768
        assert all(v == 0.0 for v in result)

        result = await client.embed("   ")
        assert len(result) == 768
        assert all(v == 0.0 for v in result)

    @pytest.mark.asyncio
    async def test_embed_success(self, client):
        """Test successful embedding generation."""
        mock_embedding = [0.1] * 768

        with patch.object(client, "_get_client") as mock_get_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {"embedding": mock_embedding}
            mock_response.raise_for_status = MagicMock()

            mock_http_client = AsyncMock()
            mock_http_client.post.return_value = mock_response
            mock_get_client.return_value = mock_http_client

            result = await client.embed("test text")

            assert result == mock_embedding
            mock_http_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_embed_batch(self, client):
        """Test batch embedding generation."""
        mock_embedding = [0.1] * 768

        with patch.object(client, "embed", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = mock_embedding

            results = await client.embed_batch(["text1", "text2", "text3"])

            assert len(results) == 3
            assert all(r == mock_embedding for r in results)
            assert mock_embed.call_count == 3

    @pytest.mark.asyncio
    async def test_embed_batch_handles_errors(self, client):
        """Test that batch embedding handles individual failures."""
        mock_embedding = [0.1] * 768
        call_count = 0

        async def mock_embed(text):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise Exception("Simulated error")
            return mock_embedding

        with patch.object(client, "embed", side_effect=mock_embed):
            results = await client.embed_batch(["text1", "text2", "text3"])

            assert len(results) == 3
            # First and third should succeed
            assert results[0] == mock_embedding
            assert results[2] == mock_embedding
            # Second should be zero vector due to error
            assert results[1] == [0.0] * 768

    @pytest.mark.asyncio
    async def test_is_available_success(self, client):
        """Test availability check when model exists."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "models": [
                    {"name": "nomic-embed-text:latest"},
                    {"name": "llama3.1:8b"},
                ]
            }

            mock_http_client = AsyncMock()
            mock_http_client.get.return_value = mock_response
            mock_get_client.return_value = mock_http_client

            result = await client.is_available()
            assert result is True

    @pytest.mark.asyncio
    async def test_is_available_model_not_found(self, client):
        """Test availability check when model doesn't exist."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "models": [{"name": "llama3.1:8b"}]
            }

            mock_http_client = AsyncMock()
            mock_http_client.get.return_value = mock_response
            mock_get_client.return_value = mock_http_client

            result = await client.is_available()
            assert result is False

    @pytest.mark.asyncio
    async def test_is_available_server_unreachable(self, client):
        """Test availability check when server is unreachable."""
        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.get.side_effect = httpx.RequestError("Connection refused")
            mock_get_client.return_value = mock_http_client

            result = await client.is_available()
            assert result is False

    def test_cosine_similarity_identical_vectors(self):
        """Test cosine similarity of identical vectors."""
        vec = [0.1, 0.2, 0.3, 0.4, 0.5]
        similarity = OllamaEmbeddingClient.cosine_similarity(vec, vec)
        assert abs(similarity - 1.0) < 0.0001

    def test_cosine_similarity_orthogonal_vectors(self):
        """Test cosine similarity of orthogonal vectors."""
        vec_a = [1.0, 0.0, 0.0]
        vec_b = [0.0, 1.0, 0.0]
        similarity = OllamaEmbeddingClient.cosine_similarity(vec_a, vec_b)
        assert abs(similarity) < 0.0001

    def test_cosine_similarity_opposite_vectors(self):
        """Test cosine similarity of opposite vectors."""
        vec_a = [1.0, 2.0, 3.0]
        vec_b = [-1.0, -2.0, -3.0]
        similarity = OllamaEmbeddingClient.cosine_similarity(vec_a, vec_b)
        assert abs(similarity - (-1.0)) < 0.0001

    def test_cosine_similarity_zero_vector(self):
        """Test cosine similarity with zero vector."""
        vec_a = [1.0, 2.0, 3.0]
        vec_b = [0.0, 0.0, 0.0]
        similarity = OllamaEmbeddingClient.cosine_similarity(vec_a, vec_b)
        assert similarity == 0.0

    def test_cosine_similarity_dimension_mismatch(self):
        """Test that dimension mismatch raises error."""
        vec_a = [1.0, 2.0, 3.0]
        vec_b = [1.0, 2.0]
        with pytest.raises(ValueError, match="dimension mismatch"):
            OllamaEmbeddingClient.cosine_similarity(vec_a, vec_b)
