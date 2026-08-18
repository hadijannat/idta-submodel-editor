"""Contract tests for the OpenAI SDK surface used by the backend."""

from __future__ import annotations

import inspect

import pytest


def test_async_openai_constructor_supports_openrouter_options() -> None:
    """Ensure options used by OpenRouterProvider remain supported."""
    from openai import AsyncOpenAI

    signature = inspect.signature(AsyncOpenAI.__init__)
    params = signature.parameters

    assert "base_url" in params
    assert "default_headers" in params


@pytest.mark.asyncio
async def test_async_openai_constructs_backend_clients_and_exposes_methods() -> None:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key="test-key", timeout=60.0, max_retries=2)
    openrouter_client = AsyncOpenAI(
        api_key="test-key",
        base_url="https://openrouter.ai/api/v1",
        timeout=60.0,
        max_retries=2,
        default_headers={
            "HTTP-Referer": "https://idta-submodel-editor.app",
            "X-Title": "IDTA Submodel Editor - Magic Import",
        },
    )

    try:
        assert callable(getattr(client.models, "list", None))
        assert callable(getattr(client.responses, "parse", None))
        assert callable(getattr(openrouter_client.chat.completions, "create", None))
        assert str(openrouter_client.base_url).rstrip("/") == (
            "https://openrouter.ai/api/v1"
        )
    finally:
        await client.close()
        await openrouter_client.close()
