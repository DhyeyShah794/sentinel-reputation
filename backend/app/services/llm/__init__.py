"""
Provider-agnostic LLM service — public API for the pipeline.

All pipeline stages call either:
    call_llm_batch_cached(stage, requests, ...)
    call_llm_cached(stage, key, prompt, ...)

Both functions:
  1. Check the persistent disk cache first.
  2. For cache misses, delegate to the configured provider (Ollama / Gemini / OpenAI).
  3. Persist new results to the cache.
  4. Return typed results + stats compatible with legacy pipeline code.

The active provider is resolved via LLMFactory and cached as a module-level singleton.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.services.llm_cache import get_llm_cache
from .base import BatchRunStats, BaseLLMProvider
from .factory import LLMFactory
from .schemas import (
    ClassificationResult,
    RelevanceResult,
    RiskResult,
    SentimentResult,
    SummaryResult,
    ThemeItem,
    ThemeResult,
)

__all__ = [
    # Primary API
    "call_llm_batch_cached",
    "call_llm_cached",
    "get_provider",
    # Schemas (re-exported for convenience)
    "ClassificationResult",
    "RelevanceResult",
    "RiskResult",
    "SentimentResult",
    "SummaryResult",
    "ThemeItem",
    "ThemeResult",
    # Stats
    "BatchRunStats",
]

logger = logging.getLogger(__name__)


def get_provider() -> BaseLLMProvider:
    """Return the currently configured LLM provider singleton."""
    return LLMFactory.get_provider()


def call_llm_batch_cached(
    stage: str,
    requests: list[tuple[str, str]],
    *,
    model: Optional[str] = None,
    temperature: float = 0.1,
    max_retries: int = 3,
    parse_json: bool = True,  # kept for API compat; JSON is always parsed
) -> tuple[dict[str, tuple[Any, bool]], BatchRunStats]:
    """
    Resolve LLM results from cache, then from the active provider for misses.

    Args:
        stage:     Pipeline stage name used as cache namespace (e.g. "relevance").
        requests:  List of (cache_key, prompt) pairs.
        model:     Override the provider's default model for this batch.
        temperature: Sampling temperature.
        max_retries: Per-item retry count passed to the provider.
        parse_json:  Ignored — kept for backward compatibility.

    Returns:
        A 2-tuple of:
          - dict mapping cache_key → (result, from_cache)
          - BatchRunStats with hit/miss/job counts
    """
    if not requests:
        return {}, BatchRunStats()

    cache = get_llm_cache()
    output: dict[str, tuple[Any, bool]] = {}
    pending: list[tuple[str, str]] = []
    stats = BatchRunStats()

    for cache_key, prompt in requests:
        cached = cache.get(stage, cache_key)
        if cached is not None:
            output[cache_key] = (cached, True)
            stats.cache_hits += 1
        else:
            pending.append((cache_key, prompt))

    stats.cache_misses = len(pending)

    if not pending:
        return output, stats

    provider = get_provider()
    logger.info(
        "[llm] Stage='%s' — %d cache hits, %d misses → calling %s",
        stage,
        stats.cache_hits,
        stats.cache_misses,
        provider.provider_name,
    )

    try:
        batch_results = provider.generate_batch(
            pending,
            model=model,
            temperature=temperature,
            max_retries=max_retries,
        )
        stats.batch_jobs_submitted = 1
        stats.batch_requests_sent = len(pending)

        for cache_key, _ in pending:
            result = batch_results.get(cache_key)
            if result is not None:
                cache.set(stage, cache_key, result)
            output[cache_key] = (result, False)

    except Exception as exc:
        logger.error(
            "[llm] Provider '%s' batch failed for stage '%s': %s",
            provider.provider_name,
            stage,
            exc,
        )
        for cache_key, _ in pending:
            output[cache_key] = (None, False)

    return output, stats


def call_llm_cached(
    stage: str,
    cache_key: str,
    prompt: str,
    *,
    model: Optional[str] = None,
    temperature: float = 0.1,
    max_retries: int = 3,
    parse_json: bool = True,  # kept for API compat
) -> tuple[Any, bool]:
    """
    Single-item version of call_llm_batch_cached.

    Returns (result, from_cache).
    """
    results, _ = call_llm_batch_cached(
        stage,
        [(cache_key, prompt)],
        model=model,
        temperature=temperature,
        max_retries=max_retries,
    )
    return results[cache_key]
