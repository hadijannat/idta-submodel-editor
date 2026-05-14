"""
OpenRouter LLM provider for Magic Import.

OpenRouter provides access to 100+ models through an OpenAI-compatible API,
including Claude, GPT-family models, Gemini, Llama, and more.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from app.config import get_settings
from app.services.magic_import.llm.provider_base import LLMProvider

if TYPE_CHECKING:
    from app.schemas.magic_import import ExtractionHint, Snippet

from app.schemas.magic_import import LLMExtractionResponse, LLMFieldExtraction

logger = logging.getLogger(__name__)


class OpenRouterProvider(LLMProvider):
    """OpenRouter provider - OpenAI-compatible API for 100+ models."""

    # OpenRouter API base URL
    API_BASE = "https://openrouter.ai/api/v1"

    # Popular models available on OpenRouter
    RECOMMENDED_MODELS = [
        "anthropic/claude-3.5-sonnet",
        "anthropic/claude-3.5-haiku",
        "openai/gpt-4o",
        "openai/gpt-4o-mini",
        "google/gemini-pro-1.5",
        "meta-llama/llama-3.1-70b-instruct",
        "mistralai/mixtral-8x7b-instruct",
    ]

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        """
        Initialize OpenRouter provider.

        Args:
            api_key: Optional API key override (for runtime configuration)
            model: Optional model override
        """
        self.settings = get_settings()
        self._client = None
        self._api_key = api_key or self.settings.openrouter_api_key
        self._model = model or self.settings.magic_import_llm_model
        timeout = getattr(self.settings, "magic_import_llm_request_timeout_seconds", 60.0)
        retries = getattr(self.settings, "magic_import_llm_max_retries", 2)
        self._request_timeout_seconds = max(float(timeout), 1.0)
        self._max_retries = max(int(retries), 0)

    @property
    def name(self) -> str:
        return "openrouter"

    @property
    def model(self) -> str:
        return self._model

    def is_available(self) -> bool:
        """Check if OpenRouter API key is configured."""
        return bool(self._api_key)

    @property
    def client(self):
        """Lazy-load OpenAI-compatible client with OpenRouter base URL."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(
                    api_key=self._api_key,
                    base_url=self.API_BASE,
                    timeout=self._request_timeout_seconds,
                    max_retries=self._max_retries,
                    default_headers={
                        "HTTP-Referer": "https://idta-submodel-editor.app",
                        "X-Title": "IDTA Submodel Editor - Magic Import",
                    },
                )
            except ImportError:
                raise RuntimeError("openai package not installed")
        return self._client

    async def extract_structured(
        self,
        hints: list["ExtractionHint"],
        snippets: list["Snippet"],
        max_tokens: int = 4096,
    ) -> LLMExtractionResponse:
        """Extract fields using OpenRouter's API."""
        if not self.is_available():
            raise RuntimeError("OpenRouter API key not configured")

        system_prompt = self.build_system_prompt()
        user_prompt = self.build_user_prompt(hints, snippets)

        try:
            response = await self.client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=max_tokens,
                temperature=0.1,
                response_format={"type": "json_object"},
            )

            # Parse response
            content = response.choices[0].message.content
            prompt_tokens = response.usage.prompt_tokens if response.usage else 0
            completion_tokens = response.usage.completion_tokens if response.usage else 0
            tokens_used = (
                response.usage.total_tokens
                if response.usage and response.usage.total_tokens is not None
                else prompt_tokens + completion_tokens
            )

            extractions = self._parse_response(content)

            logger.info(
                "OpenRouter extracted %d fields using %d tokens (model: %s)",
                len(extractions),
                tokens_used,
                self._model,
            )

            return LLMExtractionResponse(
                extractions=extractions,
                tokens_used=tokens_used,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                model=self._model,
            )

        except Exception as e:
            logger.exception("OpenRouter extraction failed")
            raise RuntimeError(f"OpenRouter extraction failed: {e}")

    def _parse_response(self, content: str) -> list[LLMFieldExtraction]:
        """Parse LLM response into structured extractions."""
        try:
            data = json.loads(content)

            # Handle both direct array and wrapped object
            if isinstance(data, list):
                raw_extractions = data
            elif isinstance(data, dict) and "extractions" in data:
                raw_extractions = data["extractions"]
            else:
                logger.warning("Unexpected response format: %s", type(data))
                return []

            extractions = []
            for item in raw_extractions:
                if not isinstance(item, dict):
                    continue

                path = item.get("path", "")
                value = item.get("value", "")
                evidence = item.get("evidence_quote", "")
                confidence = item.get("confidence", 0.5)

                if not path or not value:
                    continue

                extractions.append(
                    LLMFieldExtraction(
                        path=path,
                        value=str(value),
                        evidence_quote=evidence,
                        confidence=float(confidence),
                        reasoning=item.get("reasoning"),
                    )
                )

            return extractions

        except json.JSONDecodeError as e:
            logger.warning("Failed to parse JSON response: %s", e)
            return []

    @classmethod
    async def list_models(cls, api_key: str) -> list[dict]:
        """
        Fetch available models from OpenRouter API.

        Args:
            api_key: OpenRouter API key

        Returns:
            List of model info dicts with 'id', 'name', 'context_length'
        """
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(
                api_key=api_key,
                base_url=cls.API_BASE,
                timeout=10.0,
                max_retries=0,
            )
            response = await client.models.list()

            models = []
            for model in response.data:
                models.append({
                    "id": model.id,
                    "name": getattr(model, "name", model.id),
                    "context_length": getattr(model, "context_length", None),
                })

            return models

        except Exception as e:
            logger.warning("Failed to list OpenRouter models: %s", e)
            return []

    @classmethod
    async def validate_api_key(cls, api_key: str) -> tuple[bool, str]:
        """
        Validate an OpenRouter API key by making a test request.

        Args:
            api_key: API key to validate

        Returns:
            Tuple of (is_valid, message)
        """
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(
                api_key=api_key,
                base_url=cls.API_BASE,
                timeout=10.0,
                max_retries=0,
            )
            # List models is a lightweight way to validate the key
            await client.models.list()
            return True, "API key is valid"

        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg or "Unauthorized" in error_msg:
                return False, "Invalid API key"
            if "403" in error_msg or "Forbidden" in error_msg:
                return False, "API key does not have required permissions"
            return False, f"Validation failed: {error_msg}"
