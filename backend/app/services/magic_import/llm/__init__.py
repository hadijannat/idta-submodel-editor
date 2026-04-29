"""
LLM Provider abstraction for Magic Import.

Supports multiple LLM providers:
- OpenAI (GPT-5.5, GPT-5.5 Pro)
- Anthropic (Claude 3.5 Sonnet, Claude 3 Haiku)
- Local (Ollama with Llama 3, Mistral, etc.)
"""

from app.services.magic_import.llm.provider_base import LLMProvider
from app.services.magic_import.llm.factory import get_provider

__all__ = ["LLMProvider", "get_provider"]
