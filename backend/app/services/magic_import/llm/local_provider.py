"""
Local LLM provider for Magic Import using Ollama.

Supports local models like Llama 3, Mistral, Mixtral, etc.
Provides model recommendations based on system capabilities.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx

from app.config import get_settings
from app.services.magic_import.llm.provider_base import LLMProvider

if TYPE_CHECKING:
    from app.schemas.magic_import import ExtractionHint, Snippet

from app.schemas.magic_import import LLMExtractionResponse, LLMFieldExtraction

logger = logging.getLogger(__name__)


@dataclass
class ModelRecommendation:
    """Recommendation for a local LLM model."""

    model_id: str
    display_name: str
    description: str
    min_memory_gb: int
    recommended_memory_gb: int
    quality_tier: str  # "high", "medium", "fast"
    parameters: str  # e.g., "8B", "70B"
    quantization: str | None  # e.g., "Q4_0", "Q8_0"


# Recommended models for Magic Import extraction
RECOMMENDED_MODELS: dict[str, list[ModelRecommendation]] = {
    "extraction": [
        ModelRecommendation(
            model_id="llama3.1:8b-instruct-q8_0",
            display_name="Llama 3.1 8B (Q8)",
            description="Best quality/speed balance. Strong extraction accuracy.",
            min_memory_gb=8,
            recommended_memory_gb=12,
            quality_tier="high",
            parameters="8B",
            quantization="Q8_0",
        ),
        ModelRecommendation(
            model_id="llama3.1:8b",
            display_name="Llama 3.1 8B",
            description="Excellent extraction quality. Default quantization.",
            min_memory_gb=6,
            recommended_memory_gb=8,
            quality_tier="high",
            parameters="8B",
            quantization=None,
        ),
        ModelRecommendation(
            model_id="mistral:7b-instruct-v0.3-q4_0",
            display_name="Mistral 7B Instruct (Q4)",
            description="Good extraction quality. Lower memory footprint.",
            min_memory_gb=4,
            recommended_memory_gb=6,
            quality_tier="medium",
            parameters="7B",
            quantization="Q4_0",
        ),
        ModelRecommendation(
            model_id="phi3:3.8b-mini-128k-instruct-q4_0",
            display_name="Phi-3 Mini 3.8B (Q4)",
            description="Compact model for systems with limited RAM.",
            min_memory_gb=3,
            recommended_memory_gb=4,
            quality_tier="fast",
            parameters="3.8B",
            quantization="Q4_0",
        ),
    ],
    "fast": [
        ModelRecommendation(
            model_id="gemma2:2b-instruct-q4_0",
            display_name="Gemma 2 2B (Q4)",
            description="Very fast inference. Good for quick iterations.",
            min_memory_gb=2,
            recommended_memory_gb=3,
            quality_tier="fast",
            parameters="2B",
            quantization="Q4_0",
        ),
        ModelRecommendation(
            model_id="qwen2.5:1.5b-instruct-q4_0",
            display_name="Qwen 2.5 1.5B (Q4)",
            description="Ultra-compact. Works on low-memory systems.",
            min_memory_gb=2,
            recommended_memory_gb=3,
            quality_tier="fast",
            parameters="1.5B",
            quantization="Q4_0",
        ),
    ],
    "high_quality": [
        ModelRecommendation(
            model_id="llama3.1:70b-instruct-q4_0",
            display_name="Llama 3.1 70B (Q4)",
            description="Best extraction accuracy. Requires high-end GPU.",
            min_memory_gb=40,
            recommended_memory_gb=48,
            quality_tier="high",
            parameters="70B",
            quantization="Q4_0",
        ),
        ModelRecommendation(
            model_id="mixtral:8x7b-instruct-v0.1-q4_0",
            display_name="Mixtral 8x7B (Q4)",
            description="Mixture of Experts. Excellent quality.",
            min_memory_gb=24,
            recommended_memory_gb=32,
            quality_tier="high",
            parameters="8x7B",
            quantization="Q4_0",
        ),
    ],
}


class LocalProvider(LLMProvider):
    """Local Ollama provider for structured extraction."""

    # Default timeout for local inference (can be slow)
    DEFAULT_TIMEOUT = 120.0

    # Model recommendations by use case
    MODEL_RECOMMENDATIONS = RECOMMENDED_MODELS

    def __init__(self, model: str | None = None, base_url: str | None = None) -> None:
        self.settings = get_settings()
        self._model = model or self.settings.magic_import_llm_model
        base = base_url or self.settings.ollama_base_url
        self._base_url = base.rstrip("/")

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
                    prompt_tokens=prompt_tokens,
                    completion_tokens=response_tokens,
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

    async def list_available_models(self) -> list[str]:
        """Get list of locally available Ollama models."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self._base_url}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    return [m.get("name", "") for m in data.get("models", [])]
        except Exception as e:
            logger.debug("Failed to list Ollama models: %s", e)
        return []

    async def get_best_model(
        self, use_case: str = "extraction"
    ) -> str | None:
        """
        Select the best available model for the given use case.

        Checks which recommended models are already downloaded and
        returns the highest quality one available.

        Args:
            use_case: One of "extraction", "fast", "high_quality"

        Returns:
            Model identifier if found, None if no suitable model available
        """
        recommendations = self.MODEL_RECOMMENDATIONS.get(use_case, [])
        if not recommendations:
            recommendations = self.MODEL_RECOMMENDATIONS["extraction"]

        available = await self.list_available_models()
        if not available:
            return None

        # Normalize model names for comparison (remove tag if not specified)
        def normalize(name: str) -> str:
            return name.split(":")[0]

        available_bases = {normalize(m) for m in available}

        # Try recommendations in order (they're sorted by quality)
        for rec in recommendations:
            rec_base = normalize(rec.model_id)
            if rec_base in available_bases:
                # Find the exact match with tag if possible
                for avail in available:
                    if avail == rec.model_id or normalize(avail) == rec_base:
                        logger.info(
                            "Selected best model for %s: %s", use_case, avail
                        )
                        return avail

        # Fallback: return any available model
        if available:
            logger.info(
                "No recommended model found for %s, using: %s",
                use_case,
                available[0],
            )
            return available[0]

        return None

    @classmethod
    def get_model_recommendations(
        cls, use_case: str = "extraction"
    ) -> list[ModelRecommendation]:
        """
        Get recommended models for a use case.

        Args:
            use_case: One of "extraction", "fast", "high_quality"

        Returns:
            List of ModelRecommendation objects
        """
        return cls.MODEL_RECOMMENDATIONS.get(use_case, [])

    @classmethod
    def get_all_recommendations(cls) -> dict[str, list[ModelRecommendation]]:
        """Get all model recommendations by use case."""
        return cls.MODEL_RECOMMENDATIONS
