"""
OpenAI LLM provider for Magic Import.

Supports GPT-4o and GPT-4o-mini with structured outputs.
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


class OpenAIProvider(LLMProvider):
    """OpenAI GPT provider for structured extraction."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.settings = get_settings()
        self._client = None
        self._api_key = api_key or self.settings.openai_api_key
        self._model = model or self.settings.magic_import_llm_model

    @property
    def name(self) -> str:
        return "openai"

    @property
    def model(self) -> str:
        return self._model

    def is_available(self) -> bool:
        """Check if OpenAI API key is configured."""
        return bool(self._api_key)

    @property
    def client(self):
        """Lazy-load OpenAI client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(api_key=self._api_key)
            except ImportError:
                raise RuntimeError("openai package not installed")
        return self._client

    async def extract_structured(
        self,
        hints: list["ExtractionHint"],
        snippets: list["Snippet"],
        max_tokens: int = 4096,
    ) -> LLMExtractionResponse:
        """Extract fields using OpenAI's structured output."""
        if not self.is_available():
            raise RuntimeError("OpenAI API key not configured")

        system_prompt = self.build_system_prompt()
        user_prompt = self.build_user_prompt(hints, snippets)

        try:
            # Use structured output with response_format
            response = await self.client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=max_tokens,
                temperature=0.1,  # Low temperature for precise extraction
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
                "OpenAI extracted %d fields using %d tokens",
                len(extractions),
                tokens_used,
            )

            return LLMExtractionResponse(
                extractions=extractions,
                tokens_used=tokens_used,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                model=self._model,
            )

        except Exception as e:
            logger.exception("OpenAI extraction failed")
            raise RuntimeError(f"OpenAI extraction failed: {e}")

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
