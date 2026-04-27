"""Tests for LLM Providers."""

import json
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.magic_import import ExtractionHint, Snippet
from app.services.magic_import.llm.provider_base import LLMProvider


@pytest.fixture
def sample_hints() -> list[ExtractionHint]:
    """Create sample extraction hints."""
    return [
        ExtractionHint(
            path="SerialNumber",
            label="Serial Number",
            element_type="Property",
            value_type="xs:string",
            keywords=["serial", "number"],
            required=True,
        ),
    ]


@pytest.fixture
def sample_snippets() -> list[Snippet]:
    """Create sample snippets."""
    return [
        Snippet(
            text="The device serial number is SN-12345",
            page=0,
            start_word_idx=0,
            end_word_idx=10,
            score=0.9,
        ),
    ]


class TestLLMProviderBase:
    """Test suite for LLMProvider base class."""

    def test_build_system_prompt(self, sample_hints, sample_snippets):
        """Test system prompt generation."""
        # Create a concrete implementation for testing
        class TestProvider(LLMProvider):
            @property
            def name(self):
                return "test"

            @property
            def model(self):
                return "test-model"

            def is_available(self):
                return True

            async def extract_structured(self, hints, snippets, max_tokens=4096):
                return None

        provider = TestProvider()
        prompt = provider.build_system_prompt()

        assert "extract" in prompt.lower()
        assert "JSON" in prompt
        assert "evidence" in prompt.lower()

    def test_build_user_prompt(self, sample_hints, sample_snippets):
        """Test user prompt generation."""

        class TestProvider(LLMProvider):
            @property
            def name(self):
                return "test"

            @property
            def model(self):
                return "test-model"

            def is_available(self):
                return True

            async def extract_structured(self, hints, snippets, max_tokens=4096):
                return None

        provider = TestProvider()
        prompt = provider.build_user_prompt(sample_hints, sample_snippets)

        assert "SerialNumber" in prompt
        assert "SN-12345" in prompt
        assert "Target Fields" in prompt
        assert "Snippet" in prompt


class TestOpenAIProvider:
    """Test suite for OpenAI provider."""

    @patch("app.services.magic_import.llm.openai_provider.get_settings")
    def test_is_available_with_key(self, mock_settings):
        """Test availability check when API key is set."""
        mock_settings.return_value = MagicMock(
            openai_api_key="sk-test-key",
            magic_import_llm_model="gpt-4o-mini",
        )

        from app.services.magic_import.llm.openai_provider import OpenAIProvider

        provider = OpenAIProvider()
        assert provider.is_available() is True

    @patch("app.services.magic_import.llm.openai_provider.get_settings")
    def test_is_available_without_key(self, mock_settings):
        """Test availability check when API key is not set."""
        mock_settings.return_value = MagicMock(
            openai_api_key=None,
            magic_import_llm_model="gpt-4o-mini",
        )

        from app.services.magic_import.llm.openai_provider import OpenAIProvider

        provider = OpenAIProvider()
        assert provider.is_available() is False

    @patch("app.services.magic_import.llm.openai_provider.get_settings")
    def test_client_uses_configured_timeout_and_retries(self, mock_settings):
        """Test OpenAI client uses configured timeout/retry values."""
        mock_settings.return_value = MagicMock(
            openai_api_key="sk-test-key",
            magic_import_llm_model="gpt-4o-mini",
            magic_import_llm_request_timeout_seconds=45.0,
            magic_import_llm_max_retries=1,
        )

        mock_client = MagicMock()
        mock_async_openai = MagicMock(return_value=mock_client)

        with patch.dict("sys.modules", {"openai": MagicMock(AsyncOpenAI=mock_async_openai)}):
            from app.services.magic_import.llm.openai_provider import OpenAIProvider

            provider = OpenAIProvider()
            assert provider.client is mock_client

        mock_async_openai.assert_called_once_with(
            api_key="sk-test-key",
            timeout=45.0,
            max_retries=1,
        )

    def test_parse_response_valid_json(self):
        """Test parsing valid JSON response."""
        from app.services.magic_import.llm.openai_provider import OpenAIProvider

        provider = OpenAIProvider.__new__(OpenAIProvider)

        response = json.dumps(
            {
                "extractions": [
                    {
                        "path": "SerialNumber",
                        "value": "SN-12345",
                        "evidence_quote": "serial number SN-12345",
                        "confidence": 0.95,
                    }
                ]
            }
        )

        extractions = provider._parse_response(response)

        assert len(extractions) == 1
        assert extractions[0].path == "SerialNumber"
        assert extractions[0].value == "SN-12345"
        assert extractions[0].confidence == 0.95

    def test_parse_response_invalid_json(self):
        """Test parsing invalid JSON response."""
        from app.services.magic_import.llm.openai_provider import OpenAIProvider

        provider = OpenAIProvider.__new__(OpenAIProvider)

        extractions = provider._parse_response("not valid json")
        assert extractions == []

    @pytest.mark.asyncio
    @patch("app.services.magic_import.llm.openai_provider.get_settings")
    async def test_extract_structured_uses_expected_chat_completions_call(
        self,
        mock_settings,
        sample_hints,
        sample_snippets,
    ):
        """Test OpenAI extraction call shape for SDK compatibility."""
        mock_settings.return_value = MagicMock(
            openai_api_key="sk-test-key",
            magic_import_llm_model="gpt-4o-mini",
        )

        from app.services.magic_import.llm.openai_provider import OpenAIProvider

        provider = OpenAIProvider()

        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content=json.dumps(
                        {
                            "extractions": [
                                {
                                    "path": "SerialNumber",
                                    "value": "SN-12345",
                                    "evidence_quote": "serial number SN-12345",
                                    "confidence": 0.95,
                                }
                            ]
                        }
                    )
                )
            )
        ]
        mock_response.usage = MagicMock(
            prompt_tokens=7,
            completion_tokens=5,
            total_tokens=12,
        )

        create_mock = AsyncMock(return_value=mock_response)
        provider._client = MagicMock(
            chat=MagicMock(
                completions=MagicMock(
                    create=create_mock,
                )
            )
        )

        result = await provider.extract_structured(
            hints=sample_hints,
            snippets=sample_snippets,
            max_tokens=123,
        )

        create_mock.assert_awaited_once()
        call_kwargs = create_mock.await_args.kwargs
        assert call_kwargs["model"] == "gpt-4o-mini"
        assert call_kwargs["max_tokens"] == 123
        assert call_kwargs["temperature"] == 0.1
        assert call_kwargs["response_format"] == {"type": "json_object"}
        assert len(call_kwargs["messages"]) == 2
        assert result.tokens_used == 12
        assert result.prompt_tokens == 7
        assert result.completion_tokens == 5
        assert result.extractions[0].path == "SerialNumber"

    @pytest.mark.asyncio
    @patch("app.services.magic_import.llm.openai_provider.get_settings")
    async def test_extract_structured_requires_api_key(self, mock_settings, sample_hints, sample_snippets):
        """Test extraction fails fast when API key is missing."""
        mock_settings.return_value = MagicMock(
            openai_api_key=None,
            magic_import_llm_model="gpt-4o-mini",
        )

        from app.services.magic_import.llm.openai_provider import OpenAIProvider

        provider = OpenAIProvider()

        with pytest.raises(RuntimeError, match="not configured"):
            await provider.extract_structured(
                hints=sample_hints,
                snippets=sample_snippets,
            )


class TestAnthropicProvider:
    """Test suite for Anthropic provider."""

    @patch("app.services.magic_import.llm.anthropic_provider.get_settings")
    def test_is_available_with_key(self, mock_settings):
        """Test availability check when API key is set."""
        mock_settings.return_value = MagicMock(
            anthropic_api_key="sk-ant-test-key",
            magic_import_llm_model="claude-3-haiku",
        )

        from app.services.magic_import.llm.anthropic_provider import (
            AnthropicProvider,
        )

        provider = AnthropicProvider()
        assert provider.is_available() is True

    @patch("app.services.magic_import.llm.anthropic_provider.get_settings")
    def test_model_alias_resolution(self, mock_settings):
        """Test that model aliases are resolved."""
        mock_settings.return_value = MagicMock(
            anthropic_api_key="sk-ant-test-key",
            magic_import_llm_model="claude-3-haiku",
        )

        from app.services.magic_import.llm.anthropic_provider import (
            AnthropicProvider,
        )

        provider = AnthropicProvider()
        assert provider.model == "claude-3-haiku-20240307"

    def test_parse_response_with_markdown(self):
        """Test parsing response with markdown code blocks."""
        from app.services.magic_import.llm.anthropic_provider import (
            AnthropicProvider,
        )

        provider = AnthropicProvider.__new__(AnthropicProvider)

        response = """Here are the extractions:

```json
{
  "extractions": [
    {
      "path": "SerialNumber",
      "value": "SN-12345",
      "evidence_quote": "serial number SN-12345",
      "confidence": 0.9
    }
  ]
}
```"""

        extractions = provider._parse_response(response)

        assert len(extractions) == 1
        assert extractions[0].path == "SerialNumber"

    @pytest.mark.asyncio
    @patch("app.services.magic_import.llm.anthropic_provider.get_settings")
    async def test_extract_structured_calls_anthropic_messages_api(
        self,
        mock_settings,
        monkeypatch,
        sample_hints,
        sample_snippets,
    ):
        """Ensure Anthropic extraction uses the SDK surface expected by the backend."""
        mock_settings.return_value = MagicMock(
            anthropic_api_key="sk-ant-test-key",
            magic_import_llm_model="claude-3-haiku",
        )

        mock_response = MagicMock(
            content=[
                MagicMock(
                    text=json.dumps(
                        {
                            "extractions": [
                                {
                                    "path": "SerialNumber",
                                    "value": "SN-12345",
                                    "evidence_quote": "serial number is SN-12345",
                                    "confidence": 0.92,
                                }
                            ]
                        }
                    )
                )
            ],
            usage=MagicMock(input_tokens=7, output_tokens=5),
        )
        mock_client = MagicMock()
        mock_client.messages = MagicMock(create=AsyncMock(return_value=mock_response))
        mock_async_anthropic = MagicMock(return_value=mock_client)

        monkeypatch.setitem(
            sys.modules,
            "anthropic",
            SimpleNamespace(AsyncAnthropic=mock_async_anthropic),
        )

        from app.services.magic_import.llm.anthropic_provider import (
            AnthropicProvider,
        )

        provider = AnthropicProvider()
        result = await provider.extract_structured(
            hints=sample_hints,
            snippets=sample_snippets,
            max_tokens=123,
        )

        mock_async_anthropic.assert_called_once_with(api_key="sk-ant-test-key")
        mock_client.messages.create.assert_awaited_once()
        call_kwargs = mock_client.messages.create.await_args.kwargs
        assert call_kwargs["model"] == "claude-3-haiku-20240307"
        assert call_kwargs["max_tokens"] == 123
        assert call_kwargs["messages"][0]["role"] == "user"
        assert "Respond with ONLY a valid JSON object" in call_kwargs["messages"][0]["content"]
        assert call_kwargs["temperature"] == 0.1

        assert result.tokens_used == 12
        assert result.prompt_tokens == 7
        assert result.completion_tokens == 5
        assert result.extractions[0].path == "SerialNumber"


class TestLocalProvider:
    """Test suite for Local (Ollama) provider."""

    @patch("app.services.magic_import.llm.local_provider.get_settings")
    @patch("app.services.magic_import.llm.local_provider.httpx")
    def test_is_available_ollama_running(self, mock_httpx, mock_settings):
        """Test availability when Ollama is running."""
        mock_settings.return_value = MagicMock(
            ollama_base_url="http://localhost:11434",
            magic_import_llm_model="llama3",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [{"name": "llama3:latest"}]
        }
        mock_httpx.get.return_value = mock_response

        from app.services.magic_import.llm.local_provider import LocalProvider

        provider = LocalProvider()
        assert provider.is_available() is True

    @patch("app.services.magic_import.llm.local_provider.get_settings")
    @patch("app.services.magic_import.llm.local_provider.httpx")
    def test_is_available_ollama_not_running(self, mock_httpx, mock_settings):
        """Test availability when Ollama is not running."""
        mock_settings.return_value = MagicMock(
            ollama_base_url="http://localhost:11434",
            magic_import_llm_model="llama3",
        )

        import httpx

        mock_httpx.get.side_effect = httpx.ConnectError("Connection refused")

        from app.services.magic_import.llm.local_provider import LocalProvider

        provider = LocalProvider()
        assert provider.is_available() is False


class TestOpenRouterProvider:
    """Test suite for OpenRouter provider."""

    @patch("app.services.magic_import.llm.openrouter_provider.get_settings")
    def test_is_available_with_key(self, mock_settings):
        """Test availability check when API key is set."""
        mock_settings.return_value = MagicMock(
            openrouter_api_key="sk-or-test-key",
            magic_import_llm_model="anthropic/claude-3.5-sonnet",
        )

        from app.services.magic_import.llm.openrouter_provider import OpenRouterProvider

        provider = OpenRouterProvider()
        assert provider.is_available() is True

    @patch("app.services.magic_import.llm.openrouter_provider.get_settings")
    def test_is_available_without_key(self, mock_settings):
        """Test availability check when API key is not set."""
        mock_settings.return_value = MagicMock(
            openrouter_api_key=None,
            magic_import_llm_model="anthropic/claude-3.5-sonnet",
        )

        from app.services.magic_import.llm.openrouter_provider import OpenRouterProvider

        provider = OpenRouterProvider()
        assert provider.is_available() is False

    @patch("app.services.magic_import.llm.openrouter_provider.get_settings")
    def test_provider_name(self, mock_settings):
        """Test provider name is 'openrouter'."""
        mock_settings.return_value = MagicMock(
            openrouter_api_key="sk-or-test-key",
            magic_import_llm_model="openai/gpt-4o",
        )

        from app.services.magic_import.llm.openrouter_provider import OpenRouterProvider

        provider = OpenRouterProvider()
        assert provider.name == "openrouter"

    @patch("app.services.magic_import.llm.openrouter_provider.get_settings")
    def test_api_key_override(self, mock_settings):
        """Test that API key can be overridden in constructor."""
        mock_settings.return_value = MagicMock(
            openrouter_api_key=None,
            magic_import_llm_model="openai/gpt-4o",
        )

        from app.services.magic_import.llm.openrouter_provider import OpenRouterProvider

        provider = OpenRouterProvider(api_key="override-key")
        assert provider.is_available() is True

    @patch("app.services.magic_import.llm.openrouter_provider.get_settings")
    def test_model_override(self, mock_settings):
        """Test that model can be overridden in constructor."""
        mock_settings.return_value = MagicMock(
            openrouter_api_key="sk-or-test-key",
            magic_import_llm_model="default-model",
        )

        from app.services.magic_import.llm.openrouter_provider import OpenRouterProvider

        provider = OpenRouterProvider(model="custom-model")
        assert provider.model == "custom-model"

    @patch("app.services.magic_import.llm.openrouter_provider.get_settings")
    def test_client_uses_configured_timeout_and_retries(self, mock_settings):
        """Test OpenRouter client uses configured timeout/retry values."""
        mock_settings.return_value = MagicMock(
            openrouter_api_key="sk-or-test-key",
            magic_import_llm_model="openai/gpt-4o",
            magic_import_llm_request_timeout_seconds=30.0,
            magic_import_llm_max_retries=3,
        )

        mock_client = MagicMock()
        mock_async_openai = MagicMock(return_value=mock_client)

        with patch.dict("sys.modules", {"openai": MagicMock(AsyncOpenAI=mock_async_openai)}):
            from app.services.magic_import.llm.openrouter_provider import OpenRouterProvider

            provider = OpenRouterProvider()
            assert provider.client is mock_client

        mock_async_openai.assert_called_once_with(
            api_key="sk-or-test-key",
            base_url="https://openrouter.ai/api/v1",
            timeout=30.0,
            max_retries=3,
            default_headers={
                "HTTP-Referer": "https://idta-submodel-editor.app",
                "X-Title": "IDTA Submodel Editor - Magic Import",
            },
        )

    @pytest.mark.asyncio
    async def test_validate_api_key_uses_fast_client_options(self):
        """Test OpenRouter key validation uses short timeout and no retries."""
        from app.services.magic_import.llm.openrouter_provider import OpenRouterProvider

        mock_client = MagicMock()
        mock_client.models.list = AsyncMock(return_value=MagicMock())
        mock_async_openai = MagicMock(return_value=mock_client)

        with patch.dict("sys.modules", {"openai": MagicMock(AsyncOpenAI=mock_async_openai)}):
            valid, message = await OpenRouterProvider.validate_api_key("sk-or-test-key")

        assert valid is True
        assert "valid" in message.lower()
        mock_async_openai.assert_called_once_with(
            api_key="sk-or-test-key",
            base_url="https://openrouter.ai/api/v1",
            timeout=10.0,
            max_retries=0,
        )
        mock_client.models.list.assert_awaited_once()

    def test_parse_response_valid_json(self):
        """Test parsing valid JSON response."""
        from app.services.magic_import.llm.openrouter_provider import OpenRouterProvider

        provider = OpenRouterProvider.__new__(OpenRouterProvider)

        response = json.dumps(
            {
                "extractions": [
                    {
                        "path": "ManufacturerName",
                        "value": "Siemens AG",
                        "evidence_quote": "Manufactured by Siemens AG",
                        "confidence": 0.95,
                    }
                ]
            }
        )

        extractions = provider._parse_response(response)

        assert len(extractions) == 1
        assert extractions[0].path == "ManufacturerName"
        assert extractions[0].value == "Siemens AG"
        assert extractions[0].confidence == 0.95

    def test_parse_response_array_format(self):
        """Test parsing direct array format (not wrapped in object)."""
        from app.services.magic_import.llm.openrouter_provider import OpenRouterProvider

        provider = OpenRouterProvider.__new__(OpenRouterProvider)

        response = json.dumps(
            [
                {
                    "path": "SerialNumber",
                    "value": "SN-12345",
                    "evidence_quote": "Serial: SN-12345",
                    "confidence": 0.9,
                }
            ]
        )

        extractions = provider._parse_response(response)

        assert len(extractions) == 1
        assert extractions[0].path == "SerialNumber"

    def test_parse_response_invalid_json(self):
        """Test parsing invalid JSON returns empty list."""
        from app.services.magic_import.llm.openrouter_provider import OpenRouterProvider

        provider = OpenRouterProvider.__new__(OpenRouterProvider)

        extractions = provider._parse_response("not valid json {")
        assert extractions == []

    def test_parse_response_missing_required_fields(self):
        """Test parsing skips entries missing required fields."""
        from app.services.magic_import.llm.openrouter_provider import OpenRouterProvider

        provider = OpenRouterProvider.__new__(OpenRouterProvider)

        response = json.dumps(
            {
                "extractions": [
                    {"path": "ValidField", "value": "Test", "confidence": 0.9},
                    {"path": "", "value": "Empty path", "confidence": 0.8},  # Empty path
                    {"path": "NoValue", "confidence": 0.7},  # Missing value
                ]
            }
        )

        extractions = provider._parse_response(response)

        assert len(extractions) == 1
        assert extractions[0].path == "ValidField"

    def test_recommended_models_list(self):
        """Test that recommended models list exists."""
        from app.services.magic_import.llm.openrouter_provider import OpenRouterProvider

        assert len(OpenRouterProvider.RECOMMENDED_MODELS) > 0
        assert "anthropic/claude-3.5-sonnet" in OpenRouterProvider.RECOMMENDED_MODELS
        assert "openai/gpt-4o" in OpenRouterProvider.RECOMMENDED_MODELS


class TestProviderFactory:
    """Test suite for provider factory."""

    @patch("app.services.magic_import.llm.openai_provider.get_settings")
    @patch("app.services.magic_import.llm.factory.get_settings")
    def test_get_openai_provider(self, mock_factory_settings, mock_openai_settings):
        """Test getting OpenAI provider."""
        mock_settings = MagicMock(
            magic_import_llm_provider="openai",
            openai_api_key="sk-test",
            magic_import_llm_model="gpt-4o-mini",
        )
        mock_factory_settings.return_value = mock_settings
        mock_openai_settings.return_value = mock_settings

        from app.services.magic_import.llm.factory import get_provider

        provider = get_provider()
        assert provider.name == "openai"

    @patch("app.services.magic_import.llm.openai_provider.get_settings")
    @patch("app.services.magic_import.llm.factory.get_settings")
    def test_get_provider_no_key_raises(self, mock_factory_settings, mock_openai_settings):
        """Test that missing API key raises error."""
        mock_settings = MagicMock(
            magic_import_llm_provider="openai",
            openai_api_key=None,
            magic_import_llm_model="gpt-4o-mini",
        )
        mock_factory_settings.return_value = mock_settings
        mock_openai_settings.return_value = mock_settings

        from app.services.magic_import.llm.factory import get_provider

        with pytest.raises(RuntimeError, match="not configured"):
            get_provider()

    @patch("app.services.magic_import.llm.factory.get_settings")
    def test_get_unknown_provider_raises(self, mock_settings):
        """Test that unknown provider raises error."""
        mock_settings.return_value = MagicMock(
            magic_import_llm_provider="unknown_provider",
        )

        from app.services.magic_import.llm.factory import get_provider

        with pytest.raises(RuntimeError, match="Unknown LLM provider"):
            get_provider()

    @patch("app.services.magic_import.llm.openrouter_provider.get_settings")
    @patch("app.services.magic_import.llm.factory.get_settings")
    def test_get_openrouter_provider(self, mock_factory_settings, mock_openrouter_settings):
        """Test getting OpenRouter provider."""
        mock_settings = MagicMock(
            magic_import_llm_provider="openrouter",
            openrouter_api_key="sk-or-test",
            magic_import_llm_model="anthropic/claude-3.5-sonnet",
        )
        mock_factory_settings.return_value = mock_settings
        mock_openrouter_settings.return_value = mock_settings

        from app.services.magic_import.llm.factory import get_provider

        provider = get_provider()
        assert provider.name == "openrouter"

    @patch("app.services.magic_import.llm.openrouter_provider.get_settings")
    @patch("app.services.magic_import.llm.factory.get_settings")
    def test_get_openrouter_no_key_raises(self, mock_factory_settings, mock_openrouter_settings):
        """Test that missing OpenRouter API key raises error."""
        mock_settings = MagicMock(
            magic_import_llm_provider="openrouter",
            openrouter_api_key=None,
            magic_import_llm_model="anthropic/claude-3.5-sonnet",
        )
        mock_factory_settings.return_value = mock_settings
        mock_openrouter_settings.return_value = mock_settings

        from app.services.magic_import.llm.factory import get_provider

        with pytest.raises(RuntimeError, match="not configured"):
            get_provider()

    @patch("app.services.magic_import.llm.factory.get_settings")
    def test_get_available_providers_includes_openrouter(self, mock_settings):
        """Test that OpenRouter is included in available providers when configured."""
        mock_settings.return_value = MagicMock(
            openai_api_key=None,
            anthropic_api_key=None,
            openrouter_api_key="sk-or-test",
        )

        from app.services.magic_import.llm.factory import get_available_providers

        available = get_available_providers()
        assert "openrouter" in available
