"""
LLM Provider factory for Magic Import.

Creates the appropriate provider based on configuration.
Supports graceful fallback chains when preferred providers are unavailable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.config import Settings, get_settings
from app.services import settings_service
from app.services.magic_import.llm.provider_base import LLMProvider

logger = logging.getLogger(__name__)


@dataclass
class ProviderInfo:
    """Information about a provider's availability and capabilities."""

    name: str
    available: bool
    model: str | None
    is_local: bool
    privacy_note: str
    error: str | None = None


# Default fallback order: prefer local for privacy, then cloud providers
DEFAULT_FALLBACK_ORDER: list[str] = ["local", "anthropic", "openai", "openrouter"]


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


def get_provider_info() -> list[ProviderInfo]:
    """
    Get detailed information about all providers.

    Returns:
        List of ProviderInfo with availability and privacy details
    """
    info_list = []
    # Cloud providers with API keys
    cloud_providers = [
        ("openai", "OpenAI", "Data sent to OpenAI servers"),
        ("anthropic", "Anthropic", "Data sent to Anthropic servers"),
        ("openrouter", "OpenRouter", "Data routed through OpenRouter to model providers"),
    ]

    for provider_id, name, privacy_note in cloud_providers:
        configured = settings_service.is_provider_configured(provider_id)
        model = None
        error = None

        if configured:
            model = settings_service.get_effective_model(provider_id)
        else:
            error = "API key not configured"

        info_list.append(
            ProviderInfo(
                name=provider_id,
                available=configured,
                model=model,
                is_local=False,
                privacy_note=privacy_note,
                error=error,
            )
        )

    # Local provider (Ollama)
    try:
        from app.services.magic_import.llm.local_provider import LocalProvider

        base_url = settings_service.get_effective_base_url("local")
        local = LocalProvider(
            model=settings_service.get_effective_model("local"),
            base_url=base_url,
        )
        is_available = local.is_available()

        info_list.append(
            ProviderInfo(
                name="local",
                available=is_available,
                model=local.model if is_available else None,
                is_local=True,
                privacy_note="All data stays on your machine",
                error=None if is_available else f"Ollama not running at {base_url}",
            )
        )
    except Exception as e:
        info_list.append(
            ProviderInfo(
                name="local",
                available=False,
                model=None,
                is_local=True,
                privacy_note="All data stays on your machine",
                error=str(e),
            )
        )

    return info_list


def get_provider_with_fallback(
    preference: list[str] | None = None,
    settings: Settings | None = None,
) -> tuple[LLMProvider | None, str | None]:
    """
    Get a provider, falling back through alternatives if needed.

    Args:
        preference: Ordered list of provider IDs to try. Defaults to
                   [configured_provider, local, anthropic, openai, openrouter]
        settings: Optional settings override

    Returns:
        Tuple of (provider, fallback_reason). If fallback occurred,
        fallback_reason explains why the preferred provider wasn't used.
    """
    if settings is None:
        settings = get_settings()

    # Build preference order
    if preference is None:
        # Start with configured provider, then default fallback order
        configured = settings_service.get_effective_provider()
        preference = [configured] + [
            p for p in DEFAULT_FALLBACK_ORDER if p != configured
        ]

    fallback_reason = None
    primary_provider = preference[0] if preference else None

    for i, provider_id in enumerate(preference):
        try:
            provider = _create_provider(provider_id, settings)
            if provider and provider.is_available():
                if i > 0 and primary_provider:
                    fallback_reason = (
                        f"Switched from {primary_provider} to {provider_id}: "
                        f"primary provider unavailable"
                    )
                    logger.info(fallback_reason)
                return provider, fallback_reason
        except Exception as e:
            logger.debug("Provider %s unavailable: %s", provider_id, e)

    return None, "No providers available"


def _create_provider(provider_id: str, settings: Settings | None = None) -> LLMProvider | None:
    """
    Create a provider instance without availability checking.

    Args:
        provider_id: Provider identifier
        settings: Optional settings override

    Returns:
        LLMProvider instance or None if provider unknown
    """
    if settings is None:
        settings = get_settings()

    model = settings_service.get_effective_model(provider_id)
    api_key = settings_service.get_effective_api_key(provider_id)
    base_url = settings_service.get_effective_base_url(provider_id)

    if provider_id == "openai":
        from app.services.magic_import.llm.openai_provider import OpenAIProvider

        return OpenAIProvider(api_key=api_key, model=model)

    if provider_id == "anthropic":
        from app.services.magic_import.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider(api_key=api_key, model=model)

    if provider_id == "openrouter":
        from app.services.magic_import.llm.openrouter_provider import OpenRouterProvider

        return OpenRouterProvider(api_key=api_key, model=model)

    if provider_id == "local":
        from app.services.magic_import.llm.local_provider import LocalProvider

        return LocalProvider(model=model, base_url=base_url)

    return None
