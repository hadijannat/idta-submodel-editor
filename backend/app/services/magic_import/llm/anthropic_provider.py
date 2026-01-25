"""
Anthropic LLM provider for Magic Import.

Supports Claude 3.5 Sonnet, Claude 3 Haiku, and Claude 3 Opus.
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

from app.config import get_settings
from app.services.magic_import.llm.provider_base import LLMProvider

if TYPE_CHECKING:
    from app.schemas.magic_import import ExtractionHint, Snippet

from app.schemas.magic_import import LLMExtractionResponse, LLMFieldExtraction

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider for structured extraction."""

    # Model mapping for common names
    MODEL_ALIASES = {
        "claude-3-haiku": "claude-3-haiku-20240307",
        "claude-3-sonnet": "claude-3-5-sonnet-20241022",
        "claude-3-5-sonnet": "claude-3-5-sonnet-20241022",
        "claude-3-opus": "claude-3-opus-20240229",
    }

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = None
        # Resolve model alias if needed
        model = self.settings.magic_import_llm_model
        self._model = self.MODEL_ALIASES.get(model, model)

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def model(self) -> str:
        return self._model

    def is_available(self) -> bool:
        """Check if Anthropic API key is configured."""
        return bool(self.settings.anthropic_api_key)

    @property
    def client(self):
        """Lazy-load Anthropic client."""
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic

                self._client = AsyncAnthropic(api_key=self.settings.anthropic_api_key)
            except ImportError:
                raise RuntimeError("anthropic package not installed")
        return self._client

    async def extract_structured(
        self,
        hints: list["ExtractionHint"],
        snippets: list["Snippet"],
        max_tokens: int = 4096,
    ) -> LLMExtractionResponse:
        """Extract fields using Anthropic's Claude."""
        if not self.is_available():
            raise RuntimeError("Anthropic API key not configured")

        system_prompt = self.build_system_prompt()
        user_prompt = self.build_user_prompt(hints, snippets)

        # Add explicit JSON instruction for Claude
        json_instruction = "\n\nRespond with ONLY a valid JSON object containing an 'extractions' array. No other text."
        user_prompt += json_instruction

        try:
            response = await self.client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
            )

            # Extract text content
            content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    content += block.text

            # Calculate tokens
            tokens_used = (
                response.usage.input_tokens + response.usage.output_tokens
                if response.usage
                else 0
            )

            extractions = self._parse_response(content)

            logger.info(
                "Anthropic extracted %d fields using %d tokens",
                len(extractions),
                tokens_used,
            )

            return LLMExtractionResponse(
                extractions=extractions,
                tokens_used=tokens_used,
                model=self._model,
            )

        except Exception as e:
            logger.exception("Anthropic extraction failed")
            raise RuntimeError(f"Anthropic extraction failed: {e}")

    def _parse_response(self, content: str) -> list[LLMFieldExtraction]:
        """Parse LLM response into structured extractions."""
        # Try to extract JSON from response
        json_str = content.strip()

        # Handle markdown code blocks
        if "```json" in json_str:
            match = re.search(r"```json\s*(.*?)\s*```", json_str, re.DOTALL)
            if match:
                json_str = match.group(1)
        elif "```" in json_str:
            match = re.search(r"```\s*(.*?)\s*```", json_str, re.DOTALL)
            if match:
                json_str = match.group(1)

        try:
            data = json.loads(json_str)

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
            logger.warning("Failed to parse JSON response: %s\nContent: %s", e, content[:500])
            return []
