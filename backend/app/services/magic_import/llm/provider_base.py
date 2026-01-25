"""
Base class for LLM providers.

All providers must implement the extract_structured method that returns
structured field extractions with evidence quotes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.schemas.magic_import import (
        ExtractionHint,
        LLMExtractionResponse,
        Snippet,
    )


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'openai', 'anthropic', 'local')."""
        ...

    @property
    @abstractmethod
    def model(self) -> str:
        """Model identifier being used."""
        ...

    @abstractmethod
    async def extract_structured(
        self,
        hints: list["ExtractionHint"],
        snippets: list["Snippet"],
        max_tokens: int = 4096,
    ) -> "LLMExtractionResponse":
        """
        Extract structured field values from document snippets.

        Args:
            hints: List of extraction hints describing target fields
            snippets: List of relevant document snippets
            max_tokens: Maximum tokens for response

        Returns:
            LLMExtractionResponse with extracted values and evidence quotes
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is properly configured and available."""
        ...

    def build_system_prompt(self) -> str:
        """Build the system prompt for extraction."""
        return """You are a precise data extraction assistant. Your task is to extract specific field values from document snippets.

IMPORTANT RULES:
1. Only extract values that are explicitly stated in the provided snippets
2. For each extraction, provide the EXACT quote from the document as evidence
3. If a value is not found or unclear, do not guess - skip that field
4. Maintain the exact formatting of values (numbers, dates, units)
5. For confidence, rate 0.0-1.0 based on how clearly the value is stated

OUTPUT FORMAT:
Return a JSON array of extractions. Each extraction must have:
- "path": The field path from the hints
- "value": The extracted value as a string
- "evidence_quote": The EXACT text from the snippet that contains this value
- "confidence": Your confidence in this extraction (0.0-1.0)
- "reasoning": Brief explanation of why you extracted this value (optional)

Example output:
[
  {
    "path": "ManufacturerName",
    "value": "Siemens AG",
    "evidence_quote": "Manufactured by Siemens AG",
    "confidence": 0.95,
    "reasoning": "Clear manufacturer attribution"
  }
]"""

    def build_user_prompt(
        self,
        hints: list["ExtractionHint"],
        snippets: list["Snippet"],
    ) -> str:
        """Build the user prompt with hints and snippets."""
        # Build hints section
        hints_text = "## Target Fields to Extract:\n\n"
        for hint in hints:
            hints_text += f"- **{hint.path}** ({hint.element_type})"
            if hint.value_type:
                hints_text += f" [type: {hint.value_type}]"
            if hint.semantic_label:
                hints_text += f" - {hint.semantic_label}"
            if hint.keywords:
                hints_text += f"\n  Keywords: {', '.join(hint.keywords[:5])}"
            hints_text += "\n"

        # Build snippets section
        snippets_text = "\n## Document Snippets:\n\n"
        for i, snippet in enumerate(snippets, 1):
            snippets_text += f"### Snippet {i} (Page {snippet.page + 1}):\n"
            if snippet.context_before:
                snippets_text += f"[...{snippet.context_before}...]\n"
            snippets_text += f"{snippet.text}\n"
            if snippet.context_after:
                snippets_text += f"[...{snippet.context_after}...]\n"
            snippets_text += "\n"

        return f"""{hints_text}
{snippets_text}

Extract values for the target fields from the snippets above. Return ONLY a JSON array of extractions.
If a field's value is not found in any snippet, do not include it in the output."""

    def build_response_schema(self) -> dict:
        """Build JSON schema for structured output."""
        return {
            "type": "object",
            "properties": {
                "extractions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "value": {"type": "string"},
                            "evidence_quote": {"type": "string"},
                            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                            "reasoning": {"type": "string"},
                        },
                        "required": ["path", "value", "evidence_quote", "confidence"],
                    },
                }
            },
            "required": ["extractions"],
        }
