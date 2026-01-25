"""
Local LLM provider for Magic Import using Ollama.

Supports local models like Llama 3, Mistral, Mixtral, etc.
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

import httpx

from app.config import get_settings
from app.services.magic_import.llm.provider_base import LLMProvider

if TYPE_CHECKING:
    from app.schemas.magic_import import ExtractionHint, Snippet

from app.schemas.magic_import import LLMExtractionResponse, LLMFieldExtraction

logger = logging.getLogger(__name__)


class LocalProvider(LLMProvider):
    """Local Ollama provider for structured extraction."""

    # Default timeout for local inference (can be slow)
    DEFAULT_TIMEOUT = 120.0

    def __init__(self) -> None:
        self.settings = get_settings()
        self._model = self.settings.magic_import_llm_model
        self._base_url = self.settings.ollama_base_url.rstrip("/")

    @property
    def name(self) -> str:
        return "local"

    @property
    def model(self) -> str:
        return self._model

    def is_available(self) -> bool:
        """Check if Ollama is running and model is available."""
        try:
            # Quick health check
            response = httpx.get(
                f"{self._base_url}/api/tags",
                timeout=5.0,
            )
            if response.status_code != 200:
                return False

            # Check if model is available
            data = response.json()
            models = [m.get("name", "").split(":")[0] for m in data.get("models", [])]
            model_base = self._model.split(":")[0]

            return model_base in models

        except Exception as e:
            logger.debug("Ollama not available: %s", e)
            return False

    async def extract_structured(
        self,
        hints: list["ExtractionHint"],
        snippets: list["Snippet"],
        max_tokens: int = 4096,
    ) -> LLMExtractionResponse:
        """Extract fields using local Ollama model."""
        system_prompt = self.build_system_prompt()
        user_prompt = self.build_user_prompt(hints, snippets)

        # Add explicit JSON instruction
        json_instruction = "\n\nRespond with ONLY a valid JSON object containing an 'extractions' array. No markdown, no explanation, just JSON."
        user_prompt += json_instruction

        try:
            async with httpx.AsyncClient(timeout=self.DEFAULT_TIMEOUT) as client:
                response = await client.post(
                    f"{self._base_url}/api/chat",
                    json={
                        "model": self._model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "stream": False,
                        "options": {
                            "num_predict": max_tokens,
                            "temperature": 0.1,
                        },
                        "format": "json",
                    },
                )

                if response.status_code != 200:
                    raise RuntimeError(f"Ollama returned {response.status_code}: {response.text}")

                data = response.json()
                content = data.get("message", {}).get("content", "")

                # Estimate tokens (Ollama doesn't always return token counts)
                prompt_tokens = data.get("prompt_eval_count", 0)
                response_tokens = data.get("eval_count", 0)
                tokens_used = prompt_tokens + response_tokens

                extractions = self._parse_response(content)

                logger.info(
                    "Local LLM extracted %d fields using ~%d tokens",
                    len(extractions),
                    tokens_used,
                )

                return LLMExtractionResponse(
                    extractions=extractions,
                    tokens_used=tokens_used,
                    model=self._model,
                )

        except httpx.TimeoutException:
            raise RuntimeError(f"Ollama request timed out after {self.DEFAULT_TIMEOUT}s")
        except Exception as e:
            logger.exception("Local LLM extraction failed")
            raise RuntimeError(f"Local LLM extraction failed: {e}")

    def _parse_response(self, content: str) -> list[LLMFieldExtraction]:
        """Parse LLM response into structured extractions."""
        json_str = content.strip()

        # Handle markdown code blocks (local models often add these)
        if "```json" in json_str:
            match = re.search(r"```json\s*(.*?)\s*```", json_str, re.DOTALL)
            if match:
                json_str = match.group(1)
        elif "```" in json_str:
            match = re.search(r"```\s*(.*?)\s*```", json_str, re.DOTALL)
            if match:
                json_str = match.group(1)

        # Try to find JSON object in response
        if not json_str.startswith("{") and not json_str.startswith("["):
            # Look for JSON in the response
            json_match = re.search(r"(\{.*\}|\[.*\])", json_str, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)

        try:
            data = json.loads(json_str)

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
            logger.warning("Failed to parse JSON from local LLM: %s\nContent: %s", e, content[:500])
            return []

    async def pull_model(self) -> bool:
        """Pull the configured model if not already available."""
        try:
            async with httpx.AsyncClient(timeout=600.0) as client:
                response = await client.post(
                    f"{self._base_url}/api/pull",
                    json={"name": self._model, "stream": False},
                )
                return response.status_code == 200
        except Exception as e:
            logger.warning("Failed to pull model %s: %s", self._model, e)
            return False
