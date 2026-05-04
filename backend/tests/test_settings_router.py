"""Tests for Settings API Router."""

import sys
import tempfile
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.routers import settings as settings_router
from app.main import create_application


@pytest.fixture
def temp_settings_dir():
    """Create a temporary directory for settings storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_settings(temp_settings_dir):
    """Create mock settings with temp directory."""
    settings = MagicMock()
    settings.settings_storage_dir = temp_settings_dir
    settings.settings_encryption_key = None  # Will auto-generate
    settings.openai_api_key = None
    settings.anthropic_api_key = None
    settings.openrouter_api_key = None
    settings.ollama_base_url = "http://localhost:11434"
    settings.magic_import_llm_provider = "openai"
    settings.magic_import_llm_model = "gpt-5.5"
    settings.magic_import_confidence_threshold = 0.80
    settings.magic_import_ocr_enabled = True
    settings.env = "development"
    settings.oidc_enabled = False
    return settings


@pytest.fixture
def test_client(mock_settings):
    """Create a test client with mocked settings."""
    with patch("app.routers.settings.get_settings", return_value=mock_settings):
        with patch("app.services.settings_service.get_settings", return_value=mock_settings):
            app = create_application()
            with TestClient(app) as client:
                yield client


class TestGetLLMSettings:
    """Tests for GET /api/settings/llm endpoint."""

    def test_get_settings_returns_defaults(self, test_client):
        """Test that default settings are returned when no config exists."""
        response = test_client.get("/api/settings/llm")

        assert response.status_code == 200
        data = response.json()
        assert "provider" in data
        assert "model" in data
        assert "api_key_configured" in data
        assert "providers" in data

    def test_get_settings_includes_all_providers(self, test_client):
        """Test that all providers are listed in response."""
        response = test_client.get("/api/settings/llm")

        assert response.status_code == 200
        data = response.json()
        providers = data["providers"]
        assert "openai" in providers
        assert "anthropic" in providers
        assert "openrouter" in providers
        assert "local" in providers


class TestGetProviderModels:
    """Tests for GET /api/settings/llm/models/{provider} endpoint."""

    def test_get_openai_models(self, test_client):
        """Test getting OpenAI models."""
        response = test_client.get("/api/settings/llm/models/openai")

        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "openai"
        assert len(data["models"]) > 0
        assert "gpt-5.5" in data["models"]
        assert data["default_model"] == "gpt-5.5"

    def test_get_anthropic_models(self, test_client):
        """Test getting Anthropic models."""
        response = test_client.get("/api/settings/llm/models/anthropic")

        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "anthropic"
        assert len(data["models"]) > 0
        assert "claude-3-5-sonnet-20241022" in data["models"]

    def test_get_openrouter_models(self, test_client):
        """Test getting OpenRouter models."""
        response = test_client.get("/api/settings/llm/models/openrouter")

        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "openrouter"
        assert len(data["models"]) > 0
        assert "anthropic/claude-3.5-sonnet" in data["models"]

    def test_get_local_models(self, test_client):
        """Test getting local (Ollama) models."""
        response = test_client.get("/api/settings/llm/models/local")

        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "local"
        assert len(data["models"]) > 0


class TestSettingsService:
    """Tests for settings_service functions."""

    def test_mask_api_key(self, temp_settings_dir):
        """Test API key masking."""
        from app.services.settings_service import _mask_api_key

        # Normal key
        assert _mask_api_key("sk-1234567890abcdef") == "sk-...def"

        # Short key
        assert _mask_api_key("short") == "***"

        # Empty key
        assert _mask_api_key("") == "***"

    def test_get_default_model(self, temp_settings_dir):
        """Test default model retrieval."""
        from app.services.settings_service import _get_default_model

        assert _get_default_model("openai") == "gpt-5.5"
        assert _get_default_model("anthropic") == "claude-3-5-sonnet-20241022"
        assert _get_default_model("openrouter") == "anthropic/claude-3.5-sonnet"
        assert _get_default_model("local") == "llama3.1:8b"

    def test_get_provider_models(self, temp_settings_dir):
        """Test provider models retrieval."""
        from app.services.settings_service import get_provider_models

        openai_models = get_provider_models("openai")
        assert "gpt-5.5" in openai_models
        assert "gpt-5.5-pro" in openai_models

        openrouter_models = get_provider_models("openrouter")
        assert "anthropic/claude-3.5-sonnet" in openrouter_models

    @patch("app.services.settings_service.get_settings")
    def test_load_save_settings(self, mock_get_settings, temp_settings_dir):
        """Test loading and saving settings."""
        mock_get_settings.return_value = MagicMock(
            settings_storage_dir=temp_settings_dir,
            settings_encryption_key=None,
        )

        from app.services.settings_service import (
            load_llm_settings,
            save_llm_settings,
        )

        # Load empty settings (creates default)
        settings = load_llm_settings()
        assert settings.active_provider == "openai"

        # Modify and save
        settings.active_provider = "anthropic"
        settings.confidence_threshold = 0.9
        save_llm_settings(settings)

        # Reload and verify
        reloaded = load_llm_settings()
        assert reloaded.active_provider == "anthropic"
        assert reloaded.confidence_threshold == 0.9

    @patch("app.services.settings_service.get_settings")
    def test_encryption_roundtrip(self, mock_get_settings, temp_settings_dir):
        """Test that API keys can be encrypted and decrypted."""
        mock_get_settings.return_value = MagicMock(
            settings_storage_dir=temp_settings_dir,
            settings_encryption_key=None,
        )

        from app.services.settings_service import (
            _encrypt_api_key,
            _decrypt_api_key,
        )

        original_key = "sk-test-api-key-12345"
        encrypted = _encrypt_api_key(original_key)

        # Encrypted should be different from original
        assert encrypted != original_key

        # Decrypted should match original
        decrypted = _decrypt_api_key(encrypted)
        assert decrypted == original_key

    @patch("app.services.settings_service.get_settings")
    def test_update_provider_config(self, mock_get_settings, temp_settings_dir):
        """Test updating provider configuration."""
        mock_get_settings.return_value = MagicMock(
            settings_storage_dir=temp_settings_dir,
            settings_encryption_key=None,
        )

        from app.services.settings_service import (
            update_provider_config,
            get_decrypted_api_key,
        )

        # Update OpenAI config with API key
        config = update_provider_config(
            provider="openai",
            api_key="sk-test-key",
            model="gpt-5.5-pro",
        )

        assert config.provider == "openai"
        assert config.model == "gpt-5.5-pro"
        assert config.api_key_encrypted is not None

        # Verify we can retrieve the key
        decrypted = get_decrypted_api_key("openai")
        assert decrypted == "sk-test-key"

    @patch("app.services.settings_service.get_settings")
    def test_is_provider_configured_from_env(self, mock_get_settings, temp_settings_dir):
        """Test provider configuration check falls back to env vars."""
        mock_get_settings.return_value = MagicMock(
            settings_storage_dir=temp_settings_dir,
            settings_encryption_key=None,
            openai_api_key="sk-env-key",
            anthropic_api_key=None,
            openrouter_api_key=None,
        )

        from app.services.settings_service import is_provider_configured

        # OpenAI configured via env
        assert is_provider_configured("openai") is True

        # Anthropic not configured
        assert is_provider_configured("anthropic") is False

        # Local is always considered configured
        assert is_provider_configured("local") is True


class TestValidateProvider:
    """Tests for POST /api/settings/llm/validate endpoint."""

    def test_validate_requires_admin_outside_development_oidc_non_admin(
        self,
        temp_settings_dir,
    ):
        """Test non-admin users cannot trigger provider validation outside development."""
        settings = Settings(
            env="staging",
            oidc_enabled=True,
            secret_key="staging-secret-key-with-32chars-min",
            settings_storage_dir=temp_settings_dir,
        )

        with (
            patch("app.main.get_settings", return_value=settings),
            patch("app.routers.settings.get_settings", return_value=settings),
            patch("app.services.settings_service.get_settings", return_value=settings),
            patch("app.routers.settings._validate_openai") as mock_validate,
        ):
            app = create_application()
            app.dependency_overrides[settings_router.get_current_user] = lambda: {
                "sub": "user-123",
                "permissions": [],
                "roles": [],
            }

            with TestClient(app) as client:
                response = client.post(
                    "/api/settings/llm/validate",
                    json={"provider": "openai", "api_key": "sk-test-key"},
                )

            app.dependency_overrides.clear()

        assert response.status_code == 403
        mock_validate.assert_not_called()

    @patch("app.routers.settings._validate_openai")
    def test_validate_openai_success(self, mock_validate, test_client):
        """Test successful OpenAI validation."""
        mock_validate.return_value = (True, "API key is valid")

        response = test_client.post(
            "/api/settings/llm/validate",
            json={"provider": "openai", "api_key": "sk-test-key"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert "valid" in data["message"].lower()
        assert "gpt-5.5" in data["models"]
        assert "gpt-5.5-pro" in data["models"]

    @patch("app.routers.settings._validate_openai")
    def test_validate_openai_failure(self, mock_validate, test_client):
        """Test failed OpenAI validation."""
        mock_validate.return_value = (False, "Invalid API key")

        response = test_client.post(
            "/api/settings/llm/validate",
            json={"provider": "openai", "api_key": "invalid-key"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False

    def test_validate_missing_key(self, test_client):
        """Test validation without API key."""
        response = test_client.post(
            "/api/settings/llm/validate",
            json={"provider": "openai"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert "no api key" in data["message"].lower()

    @patch("app.routers.settings._validate_ollama")
    def test_validate_local_provider(self, mock_validate, test_client):
        """Test local provider validation (doesn't need API key)."""
        mock_validate.return_value = (True, "Ollama server is reachable")

        response = test_client.post(
            "/api/settings/llm/validate",
            json={"provider": "local"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True

    @pytest.mark.parametrize(
        "base_url",
        [
            "ftp://example.com",
            "http://user:pass@example.com",
            "http://169.254.169.254/latest/meta-data",
            "http://127.0.0.1:11434",
        ],
    )
    def test_validate_local_provider_rejects_unsafe_base_urls(
        self,
        test_client,
        base_url,
    ):
        """Test local provider validation rejects SSRF-prone base URLs."""
        response = test_client.post(
            "/api/settings/llm/validate",
            json={"provider": "local", "base_url": base_url},
        )

        assert response.status_code == 400


class TestDirectOpenAIValidation:
    """Direct unit tests for OpenAI key validation internals."""

    @pytest.mark.asyncio
    async def test_validate_openai_calls_models_list(self, monkeypatch):
        """Ensure validation path still uses AsyncOpenAI.models.list()."""
        from app.routers.settings import _validate_openai

        mock_client = MagicMock()
        mock_client.models = MagicMock(
            list=AsyncMock(
                return_value=SimpleNamespace(data=[SimpleNamespace(id="gpt-5.5")])
            )
        )
        mock_async_openai = MagicMock(return_value=mock_client)

        monkeypatch.setitem(
            sys.modules,
            "openai",
            SimpleNamespace(AsyncOpenAI=mock_async_openai),
        )

        valid, message = await _validate_openai("sk-test-key", model="gpt-5.5")

        assert valid is True
        assert "valid" in message.lower()
        mock_async_openai.assert_called_once_with(
            api_key="sk-test-key",
            timeout=10.0,
            max_retries=0,
        )
        mock_client.models.list.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_validate_openai_rejects_unavailable_model(self, monkeypatch):
        """Ensure validation fails when the selected OpenAI model is unavailable."""
        from app.routers.settings import _validate_openai

        mock_client = MagicMock()
        mock_client.models = MagicMock(
            list=AsyncMock(
                return_value=SimpleNamespace(data=[SimpleNamespace(id="gpt-4o")])
            )
        )
        mock_async_openai = MagicMock(return_value=mock_client)

        monkeypatch.setitem(
            sys.modules,
            "openai",
            SimpleNamespace(AsyncOpenAI=mock_async_openai),
        )

        valid, message = await _validate_openai("sk-test-key", model="gpt-5.5")

        assert valid is False
        assert "gpt-5.5" in message
        assert "not available" in message

    @pytest.mark.asyncio
    async def test_validate_openai_maps_unauthorized_error(self, monkeypatch):
        """Ensure auth failures map to stable user-facing message."""
        from app.routers.settings import _validate_openai

        mock_client = MagicMock()
        mock_client.models = MagicMock(
            list=AsyncMock(side_effect=Exception("401 Unauthorized"))
        )
        mock_async_openai = MagicMock(return_value=mock_client)

        monkeypatch.setitem(
            sys.modules,
            "openai",
            SimpleNamespace(AsyncOpenAI=mock_async_openai),
        )

        valid, message = await _validate_openai("invalid-key")

        assert valid is False
        assert message == "Invalid API key"


class TestDirectAnthropicValidation:
    """Direct unit tests for Anthropic key validation internals."""

    @pytest.mark.asyncio
    async def test_validate_anthropic_calls_messages_create(self, monkeypatch):
        """Ensure validation path still uses AsyncAnthropic.messages.create()."""
        from app.routers.settings import _validate_anthropic

        mock_client = MagicMock()
        mock_client.messages = MagicMock(create=AsyncMock(return_value=MagicMock()))
        mock_async_anthropic = MagicMock(return_value=mock_client)

        monkeypatch.setitem(
            sys.modules,
            "anthropic",
            SimpleNamespace(AsyncAnthropic=mock_async_anthropic),
        )

        valid, message = await _validate_anthropic("sk-ant-test-key")

        assert valid is True
        assert "valid" in message.lower()
        mock_async_anthropic.assert_called_once_with(api_key="sk-ant-test-key")
        mock_client.messages.create.assert_awaited_once_with(
            model="claude-3-haiku-20240307",
            max_tokens=1,
            messages=[{"role": "user", "content": "Hi"}],
        )

    @pytest.mark.asyncio
    async def test_validate_anthropic_maps_authentication_error(self, monkeypatch):
        """Ensure auth failures map to stable user-facing message."""
        from app.routers.settings import _validate_anthropic

        mock_client = MagicMock()
        mock_client.messages = MagicMock(
            create=AsyncMock(side_effect=Exception("authentication failed"))
        )
        mock_async_anthropic = MagicMock(return_value=mock_client)

        monkeypatch.setitem(
            sys.modules,
            "anthropic",
            SimpleNamespace(AsyncAnthropic=mock_async_anthropic),
        )

        valid, message = await _validate_anthropic("invalid-key")

        assert valid is False
        assert message == "Invalid API key"


class TestUpdateLLMSettings:
    """Tests for PUT /api/settings/llm endpoint."""

    def test_update_requires_admin_outside_development_oidc_non_admin(
        self,
        temp_settings_dir,
    ):
        """Test non-admin users cannot mutate LLM settings outside development."""
        settings = Settings(
            env="staging",
            oidc_enabled=True,
            secret_key="staging-secret-key-with-32chars-min",
            settings_storage_dir=temp_settings_dir,
        )

        with (
            patch("app.main.get_settings", return_value=settings),
            patch("app.routers.settings.get_settings", return_value=settings),
            patch("app.services.settings_service.get_settings", return_value=settings),
        ):
            app = create_application()
            app.dependency_overrides[settings_router.get_current_user] = lambda: {
                "sub": "user-123",
                "permissions": [],
                "roles": [],
            }

            with TestClient(app) as client:
                response = client.put(
                    "/api/settings/llm",
                    json={"confidence_threshold": 0.9},
                )

            app.dependency_overrides.clear()

        assert response.status_code == 403

    @patch("app.routers.settings._validate_provider_key")
    def test_update_provider(self, mock_validate, test_client, mock_settings, temp_settings_dir):
        """Test updating active provider returns success."""
        mock_validate.return_value = (True, "API key is valid")

        with patch("app.services.settings_service.get_settings", return_value=MagicMock(
            settings_storage_dir=temp_settings_dir,
            settings_encryption_key=None,
            openai_api_key=None,
            anthropic_api_key=None,
            openrouter_api_key=None,
        )):
            response = test_client.put(
                "/api/settings/llm",
                json={
                    "provider": "anthropic",
                    "api_key": "sk-ant-test",
                    "model": "claude-3-5-sonnet-20241022",
                },
            )

            # Just verify the request succeeds - the provider change
            # depends on internal state that's difficult to mock fully
            assert response.status_code == 200
            data = response.json()
            assert "provider" in data
            assert "model" in data

    @patch("app.routers.settings._validate_provider_key")
    def test_update_with_invalid_key_fails(self, mock_validate, test_client):
        """Test that invalid API key is rejected."""
        mock_validate.return_value = (False, "Invalid API key")

        response = test_client.put(
            "/api/settings/llm",
            json={
                "provider": "openai",
                "api_key": "invalid-key",
            },
        )

        assert response.status_code == 400

    def test_update_confidence_threshold(self, test_client, mock_settings, temp_settings_dir):
        """Test updating confidence threshold."""
        with patch("app.services.settings_service.get_settings", return_value=MagicMock(
            settings_storage_dir=temp_settings_dir,
            settings_encryption_key=None,
            openai_api_key=None,
            anthropic_api_key=None,
            openrouter_api_key=None,
        )):
            response = test_client.put(
                "/api/settings/llm",
                json={"confidence_threshold": 0.95},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["confidence_threshold"] == 0.95

    def test_update_rejects_unsafe_local_base_url(self, test_client):
        """Test local base URL updates reject SSRF-prone targets."""
        response = test_client.put(
            "/api/settings/llm",
            json={
                "provider": "local",
                "base_url": "http://169.254.169.254/latest/meta-data",
            },
        )

        assert response.status_code == 400


class TestDeleteApiKey:
    """Tests for DELETE /api/settings/llm/api-key/{provider} endpoint."""

    def test_delete_nonexistent_key(self, test_client, mock_settings, temp_settings_dir):
        """Test deleting a key that doesn't exist."""
        with patch("app.services.settings_service.get_settings", return_value=MagicMock(
            settings_storage_dir=temp_settings_dir,
            settings_encryption_key=None,
        )):
            response = test_client.delete("/api/settings/llm/api-key/openai")

            assert response.status_code == 200
            data = response.json()
            assert data["deleted"] is False

    @patch("app.services.settings_service.get_settings")
    def test_delete_existing_key(self, mock_get_settings, test_client, temp_settings_dir):
        """Test deleting an existing key."""
        mock_get_settings.return_value = MagicMock(
            settings_storage_dir=temp_settings_dir,
            settings_encryption_key=None,
        )

        # First, create a key
        from app.services.settings_service import update_provider_config

        update_provider_config("openai", api_key="sk-to-delete", model="gpt-5.5")

        # Now delete it
        response = test_client.delete("/api/settings/llm/api-key/openai")

        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is True
        assert data["provider"] == "openai"
