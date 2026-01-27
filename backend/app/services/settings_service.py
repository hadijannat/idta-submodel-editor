"""
Settings service for secure storage and retrieval of LLM provider configuration.

Uses Fernet encryption for API keys and file-based JSON storage.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from app.config import get_settings

logger = logging.getLogger(__name__)


# Provider types
ProviderType = Literal["openai", "anthropic", "openrouter", "local"]


class LLMProviderConfig(BaseModel):
    """Configuration for an LLM provider."""

    provider: ProviderType
    api_key_encrypted: str | None = None
    base_url: str | None = None  # For local/custom endpoints
    model: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime | None = None


class LLMSettings(BaseModel):
    """Complete LLM settings including all providers."""

    active_provider: ProviderType = "openai"
    providers: dict[str, LLMProviderConfig] = Field(default_factory=dict)
    confidence_threshold: float = 0.80
    ocr_enabled: bool = True


def _get_encryption_key() -> bytes:
    """
    Get or generate the encryption key for API keys.

    Uses settings.settings_encryption_key if set, otherwise generates
    and stores a key in the settings directory.
    """
    settings = get_settings()

    # Use configured key if available
    if settings.settings_encryption_key:
        return settings.settings_encryption_key.encode()

    # Generate and store a key if not configured
    key_file = settings.settings_storage_dir / ".encryption_key"
    settings.settings_storage_dir.mkdir(parents=True, exist_ok=True)

    if key_file.exists():
        return key_file.read_bytes()

    # Generate new key
    try:
        from cryptography.fernet import Fernet

        key = Fernet.generate_key()
        key_file.write_bytes(key)
        # Restrict permissions (owner only)
        os.chmod(key_file, 0o600)
        logger.info("Generated new settings encryption key")
        return key
    except ImportError:
        # If cryptography not installed, use a fallback (less secure)
        key = secrets.token_bytes(32)
        key_file.write_bytes(key)
        os.chmod(key_file, 0o600)
        logger.warning("cryptography package not installed, using fallback encryption")
        return key


def _encrypt_api_key(api_key: str) -> str:
    """Encrypt an API key for storage."""
    try:
        from cryptography.fernet import Fernet

        key = _get_encryption_key()
        f = Fernet(key)
        return f.encrypt(api_key.encode()).decode()
    except ImportError:
        # Fallback: base64 encoding (NOT SECURE - for development only)
        import base64

        logger.warning("Using base64 fallback for API key storage - install cryptography for security")
        return base64.b64encode(api_key.encode()).decode()


def _decrypt_api_key(encrypted: str) -> str:
    """Decrypt an API key from storage."""
    try:
        from cryptography.fernet import Fernet

        key = _get_encryption_key()
        f = Fernet(key)
        return f.decrypt(encrypted.encode()).decode()
    except ImportError:
        # Fallback: base64 decoding
        import base64

        return base64.b64decode(encrypted.encode()).decode()


def _mask_api_key(api_key: str) -> str:
    """
    Mask an API key for display.

    Shows first 3 and last 3 characters: "sk-...abc"
    """
    if not api_key or len(api_key) < 8:
        return "***"
    return f"{api_key[:3]}...{api_key[-3:]}"


def _get_settings_path() -> Path:
    """Get the path to the settings JSON file."""
    settings = get_settings()
    settings.settings_storage_dir.mkdir(parents=True, exist_ok=True)
    return settings.settings_storage_dir / "llm_settings.json"


def load_llm_settings() -> LLMSettings:
    """Load LLM settings from storage."""
    path = _get_settings_path()

    if not path.exists():
        return LLMSettings()

    try:
        data = json.loads(path.read_text())
        return LLMSettings.model_validate(data)
    except Exception as e:
        logger.warning("Failed to load LLM settings: %s", e)
        return LLMSettings()


def save_llm_settings(settings: LLMSettings) -> None:
    """Save LLM settings to storage."""
    path = _get_settings_path()

    try:
        path.write_text(settings.model_dump_json(indent=2))
        # Restrict permissions
        os.chmod(path, 0o600)
    except Exception as e:
        logger.error("Failed to save LLM settings: %s", e)
        raise


def get_provider_config(provider: ProviderType) -> LLMProviderConfig | None:
    """Get configuration for a specific provider."""
    settings = load_llm_settings()
    return settings.providers.get(provider)


def update_provider_config(
    provider: ProviderType,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    is_active: bool = True,
) -> LLMProviderConfig:
    """
    Update or create provider configuration.

    Args:
        provider: Provider type
        api_key: Plain text API key (will be encrypted)
        model: Model identifier
        base_url: Custom base URL (for local/custom endpoints)
        is_active: Whether this provider is active

    Returns:
        Updated provider config
    """
    settings = load_llm_settings()

    # Get existing config or create new one
    existing = settings.providers.get(provider)

    config = LLMProviderConfig(
        provider=provider,
        api_key_encrypted=_encrypt_api_key(api_key) if api_key else (existing.api_key_encrypted if existing else None),
        base_url=base_url if base_url is not None else (existing.base_url if existing else None),
        model=model or (existing.model if existing else _get_default_model(provider)),
        is_active=is_active,
        created_at=existing.created_at if existing else datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    settings.providers[provider] = config
    save_llm_settings(settings)

    return config


def set_active_provider(provider: ProviderType) -> None:
    """Set the active LLM provider."""
    settings = load_llm_settings()
    settings.active_provider = provider
    save_llm_settings(settings)


def get_active_provider() -> ProviderType:
    """Get the currently active provider."""
    settings = load_llm_settings()
    return settings.active_provider


def get_decrypted_api_key(provider: ProviderType) -> str | None:
    """
    Get the decrypted API key for a provider.

    Returns None if no key is configured.
    """
    config = get_provider_config(provider)
    if not config or not config.api_key_encrypted:
        return None

    try:
        return _decrypt_api_key(config.api_key_encrypted)
    except Exception as e:
        logger.warning("Failed to decrypt API key for %s: %s", provider, e)
        return None


def get_masked_api_key(provider: ProviderType) -> str | None:
    """
    Get a masked version of the API key for display.

    Returns None if no key is configured.
    """
    api_key = get_decrypted_api_key(provider)
    if not api_key:
        return None
    return _mask_api_key(api_key)


def is_provider_configured(provider: ProviderType) -> bool:
    """Check if a provider has an API key configured."""
    # Check stored settings first
    config = get_provider_config(provider)
    if config and config.api_key_encrypted:
        return True

    # Fall back to environment variables
    env_settings = get_settings()
    if provider == "openai":
        return bool(env_settings.openai_api_key)
    if provider == "anthropic":
        return bool(env_settings.anthropic_api_key)
    if provider == "openrouter":
        return bool(env_settings.openrouter_api_key)
    if provider == "local":
        # Local is always "configured" as it uses Ollama
        return True

    return False


def get_effective_api_key(provider: ProviderType) -> str | None:
    """
    Get the effective API key for a provider.

    Checks stored settings first, then falls back to environment variables.
    """
    # Check stored settings first
    stored_key = get_decrypted_api_key(provider)
    if stored_key:
        return stored_key

    # Fall back to environment variables
    env_settings = get_settings()
    if provider == "openai":
        return env_settings.openai_api_key
    if provider == "anthropic":
        return env_settings.anthropic_api_key
    if provider == "openrouter":
        return env_settings.openrouter_api_key

    return None


def get_effective_model(provider: ProviderType) -> str:
    """
    Get the effective model for a provider.

    Checks stored settings first, then falls back to environment default.
    """
    config = get_provider_config(provider)
    if config and config.model:
        return config.model

    return _get_default_model(provider)


def _get_default_model(provider: ProviderType) -> str:
    """Get default model for a provider."""
    defaults = {
        "openai": "gpt-4o-mini",
        "anthropic": "claude-3-5-sonnet-20241022",
        "openrouter": "anthropic/claude-3.5-sonnet",
        "local": "llama3.1:8b",
    }
    return defaults.get(provider, "gpt-4o-mini")


# Model lists by provider
PROVIDER_MODELS: dict[str, list[str]] = {
    "openai": [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-3.5-turbo",
    ],
    "anthropic": [
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229",
    ],
    "openrouter": [
        "anthropic/claude-3.5-sonnet",
        "anthropic/claude-3.5-haiku",
        "openai/gpt-4o",
        "openai/gpt-4o-mini",
        "google/gemini-pro-1.5",
        "meta-llama/llama-3.1-70b-instruct",
        "mistralai/mixtral-8x7b-instruct",
    ],
    "local": [
        "llama3.1:8b",
        "llama3.1:70b",
        "mistral:7b",
        "mixtral:8x7b",
        "codellama:7b",
    ],
}


def get_provider_models(provider: ProviderType) -> list[str]:
    """Get available models for a provider."""
    return PROVIDER_MODELS.get(provider, [])


def delete_provider_api_key(provider: ProviderType) -> bool:
    """
    Delete the stored API key for a provider.

    Returns True if a key was deleted, False if none existed.
    """
    settings = load_llm_settings()
    config = settings.providers.get(provider)

    if not config or not config.api_key_encrypted:
        return False

    config.api_key_encrypted = None
    config.updated_at = datetime.utcnow()
    save_llm_settings(settings)
    return True
