"""
Settings API endpoints for LLM provider configuration.

Provides secure management of API keys and provider settings.
"""

from __future__ import annotations

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.config import get_settings
from app.dependencies import get_current_user
from app.services import settings_service
from app.services.settings_service import (
    ProviderType,
    get_provider_models,
)
from app.utils.url_safety import (
    UnsafeURL,
    get_provider_base_url_allowlist,
    validate_provider_base_url,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])


# ============================================================================
# Request/Response Schemas
# ============================================================================


class ProviderStatus(BaseModel):
    """Status of a single provider."""

    configured: bool = Field(description="Whether API key is configured")
    healthy: bool | None = Field(default=None, description="Connection health status")
    latency_ms: int | None = Field(default=None, description="Response latency in ms")


class LLMSettingsResponse(BaseModel):
    """Response for GET /api/settings/llm."""

    provider: ProviderType = Field(description="Active provider")
    model: str = Field(description="Active model")
    api_key_configured: bool = Field(description="Whether active provider has API key")
    api_key_masked: str | None = Field(description="Masked API key (e.g., 'sk-...abc')")
    base_url: str | None = Field(description="Custom base URL if set")
    confidence_threshold: float = Field(description="Confidence threshold for extractions")
    ocr_enabled: bool = Field(description="Whether OCR is enabled")
    providers: dict[str, ProviderStatus] = Field(description="Status of all providers")


class LLMSettingsUpdate(BaseModel):
    """Request for PUT /api/settings/llm."""

    provider: ProviderType | None = Field(default=None, description="Provider to activate")
    api_key: str | None = Field(default=None, description="API key (will be encrypted)")
    model: str | None = Field(default=None, description="Model to use")
    base_url: str | None = Field(default=None, description="Custom base URL (for local)")
    confidence_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    ocr_enabled: bool | None = Field(default=None)


class ProviderValidationRequest(BaseModel):
    """Request for POST /api/settings/llm/validate."""

    provider: ProviderType
    api_key: str | None = Field(default=None, description="API key to validate")
    model: str | None = Field(default=None, description="Model to validate access for")
    base_url: str | None = Field(default=None, description="Custom base URL")


class ProviderValidationResponse(BaseModel):
    """Response for POST /api/settings/llm/validate."""

    valid: bool
    message: str
    models: list[str] = Field(default_factory=list, description="Available models")


class ModelsResponse(BaseModel):
    """Response for GET /api/settings/llm/models/{provider}."""

    provider: ProviderType
    models: list[str]
    default_model: str


class FeatureFlagsResponse(BaseModel):
    """Response for GET /api/settings/features."""

    dataspace_enabled: bool
    source: Literal["settings", "env"]


class FeatureFlagsUpdate(BaseModel):
    """Request for PUT /api/settings/features."""

    dataspace_enabled: bool | None = Field(
        default=None, description="Enable or disable dataspace integration"
    )


def _is_admin_user(user: dict | None) -> bool:
    """Return True when the authenticated user has admin privileges."""
    if user is None:
        return False
    permissions = user.get("permissions", [])
    roles = user.get("roles", [])
    return "admin" in permissions or any("role:admin" in str(role) for role in roles)


def _require_admin_outside_development(user: dict | None, action: str) -> None:
    """Require admin privileges for sensitive runtime mutations outside dev."""
    app_settings = get_settings()
    if app_settings.env != "development" and not _is_admin_user(user):
        raise HTTPException(
            status_code=403 if user is not None else 401,
            detail=f"Admin authentication is required to {action}",
        )


def _validate_provider_base_url(url: str) -> str:
    """Validate and normalize a provider base URL, raising HTTP 400 on failure."""
    app_settings = get_settings()
    try:
        return validate_provider_base_url(
            url,
            configured_ollama_base_url=app_settings.ollama_base_url,
            allowlist=get_provider_base_url_allowlist(app_settings),
        )
    except UnsafeURL as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/llm", response_model=LLMSettingsResponse)
async def get_llm_settings(
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> LLMSettingsResponse:
    """
    Get current LLM configuration.

    API keys are masked for security.
    """
    settings = settings_service.load_llm_settings()
    env_settings = get_settings()
    use_env_defaults = not settings_service.has_llm_settings()

    # Get active provider info
    active_provider = settings_service.get_effective_provider()

    # Build provider status for all providers
    providers_status: dict[str, ProviderStatus] = {}
    for provider in ["openai", "anthropic", "openrouter", "local"]:
        configured = settings_service.is_provider_configured(provider)
        providers_status[provider] = ProviderStatus(
            configured=configured,
            healthy=None,  # Health check done separately
            latency_ms=None,
        )

    return LLMSettingsResponse(
        provider=active_provider,
        model=settings_service.get_effective_model(active_provider),
        api_key_configured=settings_service.is_provider_configured(active_provider),
        api_key_masked=settings_service.get_masked_api_key(active_provider),
        base_url=settings_service.get_effective_base_url(active_provider),
        confidence_threshold=env_settings.magic_import_confidence_threshold if use_env_defaults else settings.confidence_threshold,
        ocr_enabled=env_settings.magic_import_ocr_enabled if use_env_defaults else settings.ocr_enabled,
        providers=providers_status,
    )


@router.put("/llm", response_model=LLMSettingsResponse)
async def update_llm_settings(
    request: LLMSettingsUpdate,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> LLMSettingsResponse:
    """
    Update LLM provider settings.

    If an API key is provided, it will be validated before storing.
    """
    _require_admin_outside_development(user, "update LLM settings")

    # Determine provider to update
    provider = request.provider or settings_service.get_effective_provider()
    base_url = (
        _validate_provider_base_url(request.base_url)
        if request.base_url is not None
        else None
    )

    # Validate API key if provided
    if request.api_key:
        is_valid, message = await _validate_provider_key(
            provider,
            request.api_key,
            base_url,
            model=request.model,
        )
        if not is_valid:
            raise HTTPException(status_code=400, detail=message)

    # Update provider config (handles its own load/save)
    settings_service.update_provider_config(
        provider=provider,
        api_key=request.api_key,
        model=request.model,
        base_url=base_url,
    )

    # Update active provider if specified (handles its own load/save)
    if request.provider:
        settings_service.set_active_provider(request.provider)

    # Update other settings - RELOAD to get fresh state first
    if request.confidence_threshold is not None or request.ocr_enabled is not None:
        settings = settings_service.load_llm_settings()  # Fresh load after helper changes
        if request.confidence_threshold is not None:
            settings.confidence_threshold = request.confidence_threshold
        if request.ocr_enabled is not None:
            settings.ocr_enabled = request.ocr_enabled
        settings_service.save_llm_settings(settings)

    logger.info("Updated LLM settings for provider: %s", provider)

    # Return updated settings
    return await get_llm_settings(user)


@router.get("/features", response_model=FeatureFlagsResponse)
async def get_feature_flags(
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> FeatureFlagsResponse:
    """Get effective runtime feature flags."""
    flags = settings_service.load_feature_flags()
    effective = settings_service.get_effective_feature_flag("dataspace_enabled")
    source: Literal["settings", "env"] = (
        "settings" if flags.dataspace_enabled is not None else "env"
    )

    return FeatureFlagsResponse(
        dataspace_enabled=effective,
        source=source,
    )


@router.put("/features", response_model=FeatureFlagsResponse)
async def update_feature_flags(
    request: FeatureFlagsUpdate,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> FeatureFlagsResponse:
    """Update runtime feature flags."""
    _require_admin_outside_development(user, "update runtime feature flags")

    if request.dataspace_enabled is not None:
        settings_service.update_feature_flags(
            dataspace_enabled=request.dataspace_enabled,
        )
        logger.info(
            "Updated runtime feature flag dataspace_enabled=%s by user=%s",
            request.dataspace_enabled,
            user.get("sub", "unknown") if user else "anonymous",
        )

    return await get_feature_flags(user)


@router.post("/llm/validate", response_model=ProviderValidationResponse)
async def validate_provider(
    request: ProviderValidationRequest,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> ProviderValidationResponse:
    """
    Validate API credentials without storing.

    Returns validation status and available models.
    """
    _require_admin_outside_development(user, "validate LLM provider settings")

    # Use provided key or stored/env key
    api_key = request.api_key or settings_service.get_effective_api_key(request.provider)

    if not api_key and request.provider != "local":
        return ProviderValidationResponse(
            valid=False,
            message="No API key provided or configured",
            models=[],
        )

    is_valid, message = await _validate_provider_key(
        request.provider,
        api_key,
        request.base_url,
        model=request.model,
    )

    models = get_provider_models(request.provider) if is_valid else []

    return ProviderValidationResponse(
        valid=is_valid,
        message=message,
        models=models,
    )


@router.get("/llm/models/{provider}", response_model=ModelsResponse)
async def get_models_for_provider(
    provider: ProviderType,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> ModelsResponse:
    """
    Get available models for a provider.

    Returns static model list. For dynamic lists (OpenRouter, Ollama),
    use the validate endpoint with an API key.
    """
    models = get_provider_models(provider)
    default = settings_service._get_default_model(provider)

    return ModelsResponse(
        provider=provider,
        models=models,
        default_model=default,
    )


@router.delete("/llm/api-key/{provider}")
async def delete_api_key(
    provider: ProviderType,
    user: Annotated[dict | None, Depends(get_current_user)] = None,
) -> dict:
    """Delete the stored API key for a provider."""
    _require_admin_outside_development(user, "delete LLM API keys")

    deleted = settings_service.delete_provider_api_key(provider)

    if deleted:
        logger.info("Deleted API key for provider: %s", provider)
        return {"deleted": True, "provider": provider}
    else:
        return {"deleted": False, "provider": provider, "message": "No key was stored"}


# ============================================================================
# Helper Functions
# ============================================================================


async def _validate_provider_key(
    provider: ProviderType,
    api_key: str | None,
    base_url: str | None = None,
    model: str | None = None,
) -> tuple[bool, str]:
    """
    Validate an API key for a provider.

    Returns (is_valid, message).
    """
    if provider == "local":
        # For local (Ollama), check if server is reachable
        return await _validate_ollama(base_url)

    if not api_key:
        return False, "API key is required"

    if provider == "openai":
        model_to_validate = model or settings_service.get_effective_model("openai")
        return await _validate_openai(api_key, model_to_validate)
    if provider == "anthropic":
        return await _validate_anthropic(api_key)
    if provider == "openrouter":
        return await _validate_openrouter(api_key)

    return False, f"Unknown provider: {provider}"


async def _validate_openai(api_key: str, model: str | None = None) -> tuple[bool, str]:
    """Validate OpenAI API key."""
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=api_key,
            timeout=10.0,
            max_retries=0,
        )
        # List models is a lightweight validation
        response = await client.models.list()
        if model:
            available_ids = {
                item.id
                for item in getattr(response, "data", response)
                if getattr(item, "id", None)
            }
            if available_ids and model not in available_ids:
                return False, f"API key is valid, but model '{model}' is not available"
        return True, "API key is valid"
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "Unauthorized" in error_msg:
            return False, "Invalid API key"
        if "429" in error_msg:
            return False, "Rate limited - please try again later"
        return False, f"Validation failed: {error_msg[:100]}"


async def _validate_anthropic(api_key: str) -> tuple[bool, str]:
    """Validate Anthropic API key."""
    try:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=api_key)
        # Make a minimal request to validate
        # Note: Anthropic doesn't have a simple list endpoint,
        # so we make a minimal completion request
        await client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1,
            messages=[{"role": "user", "content": "Hi"}],
        )
        return True, "API key is valid"
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "authentication" in error_msg.lower():
            return False, "Invalid API key"
        if "429" in error_msg:
            return False, "Rate limited - please try again later"
        return False, f"Validation failed: {error_msg[:100]}"


async def _validate_openrouter(api_key: str) -> tuple[bool, str]:
    """Validate OpenRouter API key."""
    from app.services.magic_import.llm.openrouter_provider import OpenRouterProvider

    return await OpenRouterProvider.validate_api_key(api_key)


async def _validate_ollama(base_url: str | None = None) -> tuple[bool, str]:
    """Validate Ollama connectivity."""
    import httpx

    url = _validate_provider_base_url(base_url or get_settings().ollama_base_url)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{url}/api/tags")
            if response.status_code == 200:
                return True, "Ollama server is reachable"
            return False, f"Ollama returned status {response.status_code}"
    except Exception as e:
        return False, f"Cannot connect to Ollama at {url}: {str(e)[:50]}"
