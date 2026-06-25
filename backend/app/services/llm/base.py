"""
Abstract base class for LLM providers.

All providers must implement `generate()`. Higher-level task methods
(classify, sentiment, etc.) are implemented here using `generate_json()`
so they are automatically available to every concrete provider.
"""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from .schemas import (
    ClassificationResult,
    RelevanceResult,
    RiskResult,
    SentimentResult,
    SummaryResult,
    ThemeItem,
    ThemeResult,
)

logger = logging.getLogger(__name__)


@dataclass
class BatchRunStats:
    """Aggregated stats for a batch LLM call (kept compatible with legacy code)."""

    cache_hits: int = 0
    cache_misses: int = 0
    batch_jobs_submitted: int = 0
    batch_requests_sent: int = 0


class BaseLLMProvider(ABC):
    """
    Provider-agnostic LLM interface.

    Concrete providers implement `generate()`. Everything else is derived.
    """

    # Subclasses may override to advertise the name shown in logs.
    provider_name: str = "base"

    # ------------------------------------------------------------------
    # Core: must implement
    # ------------------------------------------------------------------

    @abstractmethod
    def generate(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_retries: int = 3,
    ) -> str:
        """Return raw text response for the given prompt."""

    # ------------------------------------------------------------------
    # JSON generation (shared logic)
    # ------------------------------------------------------------------

    def generate_json(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_retries: int = 3,
    ) -> Any:
        """Generate and parse JSON. Retries on parse failures."""
        last_exc: Optional[Exception] = None

        for attempt in range(max_retries):
            try:
                text = self.generate(
                    prompt,
                    model=model,
                    temperature=temperature,
                    max_retries=1,  # retry loop is here
                )
                parsed = self._extract_json(text)
                if parsed is not None:
                    return parsed
                raise ValueError(f"JSON extraction returned None from: {text[:200]}")
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "[%s] generate_json attempt %d/%d failed: %s",
                    self.provider_name,
                    attempt + 1,
                    max_retries,
                    exc,
                )

        logger.error(
            "[%s] generate_json exhausted %d retries. Last error: %s",
            self.provider_name,
            max_retries,
            last_exc,
        )
        raise RuntimeError(
            f"{self.provider_name}: generate_json failed after {max_retries} retries"
        ) from last_exc

    def generate_batch(
        self,
        requests: list[tuple[str, str]],
        *,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """
        Batch generation. Default implementation: sequential calls.

        Providers with native batch APIs (e.g. Gemini) should override this
        for better throughput. The return dict maps cache_key → parsed result.
        """
        results: dict[str, Any] = {}
        for cache_key, prompt in requests:
            try:
                results[cache_key] = self.generate_json(
                    prompt,
                    model=model,
                    temperature=temperature,
                    max_retries=max_retries,
                )
            except Exception as exc:
                logger.error(
                    "[%s] Batch item '%s' failed: %s",
                    self.provider_name,
                    cache_key,
                    exc,
                )
                results[cache_key] = None
        return results

    # ------------------------------------------------------------------
    # High-level task methods with Pydantic validation
    # ------------------------------------------------------------------

    def classify(self, prompt: str, **kwargs: Any) -> ClassificationResult:
        raw = self.generate_json(prompt, **kwargs)
        return self._validate(ClassificationResult, raw, "classification")

    def sentiment(self, prompt: str, **kwargs: Any) -> SentimentResult:
        raw = self.generate_json(prompt, **kwargs)
        return self._validate(SentimentResult, raw, "sentiment")

    def relevance(self, prompt: str, **kwargs: Any) -> RelevanceResult:
        raw = self.generate_json(prompt, **kwargs)
        return self._validate(RelevanceResult, raw, "relevance")

    def risk_analysis(self, prompt: str, **kwargs: Any) -> RiskResult:
        raw = self.generate_json(prompt, **kwargs)
        return self._validate(RiskResult, raw, "risk")

    def themes(self, prompt: str, **kwargs: Any) -> ThemeResult:
        raw = self.generate_json(prompt, **kwargs)
        if isinstance(raw, list):
            items = [ThemeItem(**item) for item in raw if isinstance(item, dict)]
            return ThemeResult(themes=items)
        return self._validate(ThemeResult, raw, "themes")

    def summarize(self, prompt: str, **kwargs: Any) -> SummaryResult:
        raw = self.generate_json(prompt, **kwargs)
        return self._validate(SummaryResult, raw, "summarize")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate(model_cls: type, raw: Any, task: str) -> Any:
        """Validate raw dict against a Pydantic schema; log and re-raise on failure."""
        if not isinstance(raw, dict):
            raise ValueError(
                f"{task}: expected dict from LLM, got {type(raw).__name__}: {raw!r:.200}"
            )
        try:
            return model_cls(**raw)
        except Exception as exc:
            logger.error("%s validation failed: %s — raw: %s", task, exc, str(raw)[:300])
            raise ValueError(f"{task} schema validation failed: {exc}") from exc

    @staticmethod
    def _extract_json(text: str) -> Any:
        """
        Extract JSON from LLM response, handling markdown code blocks
        and stray preamble text.
        """
        cleaned = text.strip()

        # Strip <think>...</think> blocks (qwen3 reasoning traces)
        cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL).strip()

        # Strip markdown fences
        if "```json" in cleaned:
            cleaned = cleaned.split("```json", 1)[1]
            cleaned = cleaned.split("```", 1)[0] if "```" in cleaned else cleaned
        elif "```" in cleaned:
            cleaned = cleaned.split("```", 1)[1]
            cleaned = cleaned.split("```", 1)[0] if "```" in cleaned else cleaned

        cleaned = cleaned.strip()

        # Direct parse
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Try extracting the first JSON object or array
        for start_char, end_char in [("{", "}"), ("[", "]")]:
            start = cleaned.find(start_char)
            end = cleaned.rfind(end_char)
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(cleaned[start : end + 1])
                except json.JSONDecodeError:
                    continue

        logger.warning("Could not parse JSON from response: %s", text[:300])
        return None
