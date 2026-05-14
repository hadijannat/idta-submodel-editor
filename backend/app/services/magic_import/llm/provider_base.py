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
        LLMCandidateResponse,
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
Return a JSON object with an "extractions" array. Each extraction must have:
- "path": The field path from the hints
- "value": The extracted value as a string
- "evidence_quote": The EXACT text from the snippet that contains this value
- "confidence": Your confidence in this extraction (0.0-1.0)
- "reasoning": Brief explanation of why you extracted this value (optional)

Example output:
{
  "extractions": [
    {
      "path": "ManufacturerName",
      "value": "Siemens AG",
      "evidence_quote": "Manufactured by Siemens AG",
      "confidence": 0.95,
      "reasoning": "Clear manufacturer attribution"
    }
  ]
}"""

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

Extract values for the target fields from the snippets above. Return ONLY a JSON object with an "extractions" array.
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

    # ========================================================================
    # Two-Pass Extraction: Candidate Generation (Pass A)
    # ========================================================================

    def build_candidate_system_prompt(self) -> str:
        """Build system prompt for multi-candidate generation (Pass A)."""
        return """You are a precise data extraction assistant. Your task is to extract specific field values from document snippets.

IMPORTANT: For each field, provide 1-3 CANDIDATE values ranked by confidence.

CRITICAL RULES:
1. ONLY extract values that are EXPLICITLY stated in the provided snippets
2. For EVERY candidate, you MUST provide the EXACT quote from the document as evidence
3. If a value is not found in the document, include "NOT_FOUND" as a candidate
4. Maintain the exact formatting of values (numbers, dates, units)
5. Never guess or infer values not directly stated in the text

CANDIDATE RANKING:
- Rank candidates by confidence (highest first)
- Include "NOT_FOUND" if there's any uncertainty about the value's presence
- Multiple candidates are useful when there are multiple possible values in the document

OUTPUT FORMAT:
Return a JSON object with "candidate_sets" array. Each set must have:
- "path": The field path from the hints
- "candidates": Array of 1-3 candidates, each with:
  - "value": The extracted value OR "NOT_FOUND"
  - "evidence_quote": The EXACT text from the snippet (required unless NOT_FOUND)
  - "llm_confidence": Your confidence in this candidate (0.0-1.0)
  - "reasoning": Brief explanation

Example output:
{
  "candidate_sets": [
    {
      "path": "ManufacturerName",
      "candidates": [
        {
          "value": "Siemens AG",
          "evidence_quote": "Manufactured by Siemens AG",
          "llm_confidence": 0.95,
          "reasoning": "Clear manufacturer attribution in header"
        },
        {
          "value": "NOT_FOUND",
          "evidence_quote": null,
          "llm_confidence": 0.05,
          "reasoning": "Alternative if 'Siemens AG' is not the manufacturer"
        }
      ]
    },
    {
      "path": "SerialNumber",
      "candidates": [
        {
          "value": "NOT_FOUND",
          "evidence_quote": null,
          "llm_confidence": 0.90,
          "reasoning": "No serial number found in any snippet"
        }
      ]
    }
  ]
}"""

    def build_candidate_user_prompt(
        self,
        hints: list["ExtractionHint"],
        snippets: list["Snippet"],
    ) -> str:
        """Build user prompt for candidate generation."""
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
            if hint.required:
                hints_text += " ⚠️ REQUIRED"
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

For each target field, provide 1-3 candidate values ranked by confidence.
Include "NOT_FOUND" as a candidate if the value might not be present.
Return ONLY a JSON object with "candidate_sets" array."""

    def build_candidate_response_schema(self) -> dict:
        """Build JSON schema for candidate generation output."""
        return {
            "type": "object",
            "properties": {
                "candidate_sets": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "candidates": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "value": {"type": "string"},
                                        "evidence_quote": {"type": ["string", "null"]},
                                        "llm_confidence": {
                                            "type": "number",
                                            "minimum": 0,
                                            "maximum": 1,
                                        },
                                        "reasoning": {"type": "string"},
                                    },
                                    "required": ["value", "llm_confidence"],
                                },
                                "minItems": 1,
                                "maxItems": 3,
                            },
                        },
                        "required": ["path", "candidates"],
                    },
                }
            },
            "required": ["candidate_sets"],
        }

    async def generate_candidates(
        self,
        hints: list["ExtractionHint"],
        snippets: list["Snippet"],
        max_tokens: int = 4096,
    ) -> "LLMCandidateResponse":
        """
        Generate extraction candidates (Pass A of two-pass extraction).

        Default implementation uses extract_structured and converts to candidates.
        Subclasses can override for native multi-candidate support.

        Args:
            hints: List of extraction hints describing target fields
            snippets: List of relevant document snippets
            max_tokens: Maximum tokens for response

        Returns:
            LLMCandidateResponse with candidate sets for each field
        """
        # Default implementation: use existing extraction and convert to single candidate
        from app.schemas.magic_import import (
            CandidateSet,
            ExtractionCandidate,
            LLMCandidateResponse,
        )

        response = await self.extract_structured(hints, snippets, max_tokens)

        candidate_sets = []
        extracted_paths = {e.path for e in response.extractions}

        # Convert extractions to candidate sets
        for extraction in response.extractions:
            candidate = ExtractionCandidate(
                path=extraction.path,
                value=extraction.value,
                evidence_quote=extraction.evidence_quote,
                llm_confidence=extraction.confidence,
                source="llm",
                reasoning=extraction.reasoning,
            )
            candidate_sets.append(
                CandidateSet(
                    path=extraction.path,
                    candidates=[candidate],
                )
            )

        # Add NOT_FOUND candidates for hints without extractions
        for hint in hints:
            if hint.path not in extracted_paths:
                candidate = ExtractionCandidate(
                    path=hint.path,
                    value="NOT_FOUND",
                    evidence_quote=None,
                    llm_confidence=0.8,
                    source="llm",
                    reasoning="Value not found in document snippets",
                )
                candidate_sets.append(
                    CandidateSet(
                        path=hint.path,
                        candidates=[candidate],
                    )
                )

        return LLMCandidateResponse(
            candidate_sets=candidate_sets,
            tokens_used=response.tokens_used,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            model=response.model,
        )
