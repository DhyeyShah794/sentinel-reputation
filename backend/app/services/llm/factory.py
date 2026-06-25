"""
LLM provider factory — instantiates the correct provider based on
the LLM_PROVIDER environment variable (or config.settings).

Usage:
    provider = LLMFactory.get_provider()

Supported values for LLM_PROVIDER:
    ollama   (default) — local inference via Ollama
    gemini             — Google Gemini API
    openai             — OpenAI / OpenAI-compatible API
"""

from __future__ import annotations

import logging
from typing import Optional

from .base import BaseLLMProvider

logger = logging.getLogger(__name__)

_provider: Optional[BaseLLMProvider] = None


class LLMFactory:
    """Singleton factory for the configured LLM provider."""

    @staticmethod
    def get_provider(force_new: bool = False) -> BaseLLMProvider:
        """
        Return the cached provider instance, creating it if necessary.

        Args:
            force_new: If True, discard the cached instance and create a fresh one.
        """
        global _provider
        if _provider is None or force_new:
            _provider = LLMFactory._create_provider()
        return _provider

    @staticmethod
    def _create_provider() -> BaseLLMProvider:
        from app.config import settings  # late import to avoid circular deps

        provider_name = settings.LLM_PROVIDER.lower()
        logger.info("[llm:factory] Creating provider: %s", provider_name)

        if provider_name == "ollama":
            from .ollama_provider import OllamaProvider

            return OllamaProvider(
                base_url=settings.OLLAMA_BASE_URL,
                default_model=settings.OLLAMA_MODEL,
                timeout=settings.OLLAMA_TIMEOUT,
                num_ctx=settings.OLLAMA_NUM_CTX,
                num_predict=settings.OLLAMA_NUM_PREDICT,
            )

        if provider_name == "gemini":
            from .gemini_provider import GeminiProvider

            if not settings.GEMINI_API_KEY:
                raise ValueError(
                    "GEMINI_API_KEY is required when LLM_PROVIDER=gemini"
                )
            return GeminiProvider(
                api_key=settings.GEMINI_API_KEY,
                default_model=settings.GEMINI_FLASH_MODEL,
                batch_poll_seconds=settings.LLM_BATCH_POLL_SECONDS,
                batch_chunk_size=settings.LLM_BATCH_SIZE,
                batch_chunk_delay=settings.LLM_BATCH_CHUNK_DELAY_SECONDS,
            )

        if provider_name == "openai":
            from .openai_provider import OpenAIProvider

            if not settings.OPENAI_API_KEY:
                raise ValueError(
                    "OPENAI_API_KEY is required when LLM_PROVIDER=openai"
                )
            return OpenAIProvider(
                api_key=settings.OPENAI_API_KEY,
                default_model=settings.OPENAI_MODEL,
                base_url=settings.OPENAI_BASE_URL,
            )

        raise ValueError(
            f"Unknown LLM_PROVIDER '{provider_name}'. "
            "Supported values: ollama, gemini, openai"
        )

    @staticmethod
    def reset() -> None:
        """Clear the cached provider instance (useful in tests)."""
        global _provider
        _provider = None
