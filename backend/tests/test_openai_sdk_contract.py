"""Contract tests for the OpenAI SDK surface used by the backend."""

from __future__ import annotations

import inspect


def test_async_openai_constructor_supports_openrouter_options() -> None:
    """Ensure options used by OpenRouterProvider remain supported."""
    from openai import AsyncOpenAI

    signature = inspect.signature(AsyncOpenAI.__init__)
    params = signature.parameters

    assert "base_url" in params
    assert "default_headers" in params


def test_async_openai_exposes_methods_used_by_backend() -> None:
    """Ensure methods used by OpenAI and OpenRouter providers exist."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key="test-key")

    assert callable(getattr(client.models, "list", None))
    assert callable(getattr(client.chat.completions, "create", None))
    assert callable(getattr(client.responses, "parse", None))
