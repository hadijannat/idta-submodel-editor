"""Contract tests for the Anthropic SDK surface used by the backend."""

from __future__ import annotations

import inspect


def test_async_anthropic_constructor_supports_backend_options() -> None:
    """Ensure the backend can keep constructing the async Anthropic client."""
    from anthropic import AsyncAnthropic

    signature = inspect.signature(AsyncAnthropic.__init__)
    params = signature.parameters

    assert "api_key" in params


def test_async_anthropic_exposes_messages_create_used_by_backend() -> None:
    """Ensure methods and arguments used by Anthropic paths remain supported."""
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key="test-key")
    create = client.messages.create
    params = inspect.signature(create).parameters

    assert callable(create)
    assert "model" in params
    assert "max_tokens" in params
    assert "messages" in params
    assert "system" in params
    assert "temperature" in params
