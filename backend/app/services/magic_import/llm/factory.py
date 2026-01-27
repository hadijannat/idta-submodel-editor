"""
LLM Provider factory for Magic Import.

Creates the appropriate provider based on configuration.
"""

from __future__ import annotations

import logging

from app.config import Settings, get_settings
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

    provider_name = settings.magic_import_llm_provider.lower()

    if provider_name == "openai":
        from app.services.magic_import.llm.openai_provider import OpenAIProvider

        provider = OpenAIProvider()
        if not provider.is_available():
            raise RuntimeError(
                "OpenAI provider selected but OPENAI_API_KEY not configured"
            )
        return provider

    if provider_name == "anthropic":
        from app.services.magic_import.llm.anthropic_provider import AnthropicProvider

        provider = AnthropicProvider()
        if not provider.is_available():
            raise RuntimeError(
                "Anthropic provider selected but ANTHROPIC_API_KEY not configured"
            )
        return provider

    if provider_name == "openrouter":
        from app.services.magic_import.llm.openrouter_provider import OpenRouterProvider

        provider = OpenRouterProvider()
        if not provider.is_available():
            raise RuntimeError(
                "OpenRouter provider selected but OPENROUTER_API_KEY not configured"
            )
        return provider

    if provider_name == "local":
        from app.services.magic_import.llm.local_provider import LocalProvider

        provider = LocalProvider()
        if not provider.is_available():
            logger.warning(
                "Local provider selected but Ollama not available at %s",
                settings.ollama_base_url,
            )
            # Return anyway - might become available
        return provider

    raise RuntimeError(f"Unknown LLM provider: {provider_name}")


def get_available_providers() -> list[str]:
    """Get list of available (configured) providers."""
    settings = get_settings()
    available = []

    # Check OpenAI
    if settings.openai_api_key:
        available.append("openai")

    # Check Anthropic
    if settings.anthropic_api_key:
        available.append("anthropic")

    # Check OpenRouter
    if settings.openrouter_api_key:
        available.append("openrouter")

    # Check Local (Ollama)
    try:
        from app.services.magic_import.llm.local_provider import LocalProvider

        local = LocalProvider()
        if local.is_available():
            available.append("local")
    except Exception:
        pass

    return available
