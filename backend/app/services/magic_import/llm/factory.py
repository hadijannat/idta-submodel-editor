"""
LLM Provider factory for Magic Import.

Creates the appropriate provider based on configuration.
"""

from __future__ import annotations

import logging

from app.config import Settings, get_settings
from app.services import settings_service
from app.services.magic_import.llm.provider_base import LLMProvider

logger = logging.getLogger(__name__)


def get_provider(settings: Settings | None = None) -> LLMProvider:
    """
    Get the configured LLM provider.

    Args:
        settings: Optional settings override

    Returns:
        Configured LLMProvider instance

    Raises:
        RuntimeError: If provider is not available
    """
    if settings is None:
        settings = get_settings()

    if settings_service.has_llm_settings(settings):
        provider_name = settings_service.get_effective_provider().lower()
        model = settings_service.get_effective_model(provider_name)
        api_key = settings_service.get_effective_api_key(provider_name)
        base_url = settings_service.get_effective_base_url(provider_name)
    else:
        provider_name = getattr(settings, "magic_import_llm_provider", "openai").lower()
        model = getattr(settings, "magic_import_llm_model", settings_service._get_default_model(provider_name))
        api_key = None
        base_url = None
        if provider_name == "openai":
            api_key = getattr(settings, "openai_api_key", None)
        elif provider_name == "anthropic":
            api_key = getattr(settings, "anthropic_api_key", None)
        elif provider_name == "openrouter":
            api_key = getattr(settings, "openrouter_api_key", None)
        elif provider_name == "local":
            base_url = getattr(settings, "ollama_base_url", None)

    if provider_name == "openai":
        from app.services.magic_import.llm.openai_provider import OpenAIProvider

        provider = OpenAIProvider(api_key=api_key, model=model)
        if not provider.is_available():
            raise RuntimeError(
                "OpenAI provider selected but OPENAI_API_KEY not configured"
            )
        return provider

    if provider_name == "anthropic":
        from app.services.magic_import.llm.anthropic_provider import AnthropicProvider

        provider = AnthropicProvider(api_key=api_key, model=model)
        if not provider.is_available():
            raise RuntimeError(
                "Anthropic provider selected but ANTHROPIC_API_KEY not configured"
            )
        return provider

    if provider_name == "openrouter":
        from app.services.magic_import.llm.openrouter_provider import OpenRouterProvider

        provider = OpenRouterProvider(api_key=api_key, model=model)
        if not provider.is_available():
            raise RuntimeError(
                "OpenRouter provider selected but OPENROUTER_API_KEY not configured"
            )
        return provider

    if provider_name == "local":
        from app.services.magic_import.llm.local_provider import LocalProvider

        provider = LocalProvider(model=model, base_url=base_url)
        if not provider.is_available():
            logger.warning(
                "Local provider selected but Ollama not available at %s",
                base_url or settings.ollama_base_url,
            )
            # Return anyway - might become available
        return provider

    raise RuntimeError(f"Unknown LLM provider: {provider_name}")


def get_available_providers() -> list[str]:
    """Get list of available (configured) providers."""
    available = []

    if settings_service.has_llm_settings(get_settings()):
        if settings_service.is_provider_configured("openai"):
            available.append("openai")
        if settings_service.is_provider_configured("anthropic"):
            available.append("anthropic")
        if settings_service.is_provider_configured("openrouter"):
            available.append("openrouter")
    else:
        settings = get_settings()
        if getattr(settings, "openai_api_key", None):
            available.append("openai")
        if getattr(settings, "anthropic_api_key", None):
            available.append("anthropic")
        if getattr(settings, "openrouter_api_key", None):
            available.append("openrouter")

    # Check Local (Ollama)
    try:
        from app.services.magic_import.llm.local_provider import LocalProvider

        base_url = settings_service.get_effective_base_url("local")
        local = LocalProvider(
            model=settings_service.get_effective_model("local"),
            base_url=base_url,
        )
        if local.is_available():
            available.append("local")
    except Exception:
        pass

    return available
