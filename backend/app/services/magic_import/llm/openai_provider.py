"""
OpenAI LLM provider for Magic Import.

Uses GPT-5.5 with the Responses API and structured outputs.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from pydantic import BaseModel

from app.config import get_settings
from app.services.magic_import.llm.provider_base import LLMProvider

if TYPE_CHECKING:
    from app.schemas.magic_import import ExtractionHint, Snippet

from app.schemas.magic_import import LLMExtractionResponse, LLMFieldExtraction

logger = logging.getLogger(__name__)


class OpenAIExtractionOutput(BaseModel):
    """Structured output shape returned by the OpenAI Responses API."""

    extractions: list[LLMFieldExtraction]


class OpenAIProvider(LLMProvider):
    """OpenAI GPT provider for structured extraction."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.settings = get_settings()
        self._client = None
        self._api_key = api_key or self.settings.openai_api_key
        self._model = model or self.settings.magic_import_llm_model
        timeout = getattr(self.settings, "magic_import_llm_request_timeout_seconds", 60.0)
        retries = getattr(self.settings, "magic_import_llm_max_retries", 2)
        self._request_timeout_seconds = max(float(timeout), 1.0)
        self._max_retries = max(int(retries), 0)

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

                self._client = AsyncOpenAI(
                    api_key=self._api_key,
                    timeout=self._request_timeout_seconds,
                    max_retries=self._max_retries,
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
        """Extract fields using OpenAI's structured output."""
        if not self.is_available():
            raise RuntimeError("OpenAI API key not configured")

        system_prompt = self._build_responses_system_prompt()
        user_prompt = self._build_responses_user_prompt(hints, snippets)

        try:
            parse_kwargs = {
                "model": self._model,
                "input": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_output_tokens": max_tokens,
                "store": False,
                "text_format": OpenAIExtractionOutput,
            }
            if self._supports_reasoning_controls():
                parse_kwargs["reasoning"] = {"effort": "low"}

            response = await self.client.responses.parse(**parse_kwargs)

            prompt_tokens = response.usage.input_tokens if response.usage else 0
            completion_tokens = response.usage.output_tokens if response.usage else 0
            tokens_used = (
                response.usage.total_tokens
                if response.usage and response.usage.total_tokens is not None
                else prompt_tokens + completion_tokens
            )

            parsed = response.output_parsed
            if parsed is None:
                output_text = getattr(response, "output_text", "")
                extractions = self._parse_response(output_text)
            else:
                extractions = parsed.extractions

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

    def _supports_reasoning_controls(self) -> bool:
        """Return True when the selected OpenAI model accepts reasoning options."""
        return self._model.startswith("gpt-5")

    def _build_responses_system_prompt(self) -> str:
        """Build instructions for schema-enforced OpenAI Responses calls."""
        return """You are a precise data extraction assistant. Extract specific field values from document snippets.

IMPORTANT RULES:
1. Only extract values that are explicitly stated in the provided snippets
2. For each extraction, provide the EXACT quote from the document as evidence
3. If a value is not found or unclear, skip that field
4. Maintain the exact formatting of values (numbers, dates, units)
5. For confidence, rate 0.0-1.0 based on how clearly the value is stated"""

    def _build_responses_user_prompt(
        self,
        hints: list["ExtractionHint"],
        snippets: list["Snippet"],
    ) -> str:
        """Build the user prompt while letting Structured Outputs own the schema."""
        prompt = self.build_user_prompt(hints, snippets)
        return prompt.replace(
            'Extract values for the target fields from the snippets above. Return ONLY a JSON object with an "extractions" array.\n'
            "If a field's value is not found in any snippet, do not include it in the output.",
            "Extract values for the target fields from the snippets above. "
            "If a field's value is not found in any snippet, do not include it in the output.",
        )
