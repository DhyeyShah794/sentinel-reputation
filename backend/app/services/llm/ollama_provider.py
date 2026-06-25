"""
Ollama provider — local LLM inference via the official Ollama REST API.

Endpoints used:
  POST /api/generate  — single prompt completion (stream=false)

JSON mode is enforced via Ollama's built-in "format": "json" parameter so
the model is constrained to valid JSON output without free-form parsing.

Thinking traces from qwen3 models (<think>…</think>) are stripped before
JSON extraction by the base class.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Optional

import httpx

from .base import BaseLLMProvider

logger = logging.getLogger(__name__)

# How many parallel Ollama requests to run in generate_batch.
# Keep low to avoid exhausting the single-GPU concurrency slot.
_BATCH_WORKERS = 4


class OllamaProvider(BaseLLMProvider):
    """
    Inference provider backed by a locally running Ollama server.

    Args:
        base_url:    Ollama server URL (default http://localhost:11434).
        default_model: Model tag to use when no model is specified per-call.
        timeout:     HTTP request timeout in seconds.
        num_ctx:     Context window size passed to Ollama (tokens).
    """

    provider_name = "ollama"

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        default_model: str = "qwen3:30b-a3b",
        timeout: int = 300,
        num_ctx: int = 32768,
        num_predict: int = 8192,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.timeout = timeout
        self.num_ctx = num_ctx
        self.num_predict = num_predict
        self._client = httpx.Client(timeout=timeout)

    # ------------------------------------------------------------------
    # Core
    # ------------------------------------------------------------------

    def generate(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_retries: int = 3,
    ) -> str:
        resolved_model = model or self.default_model
        payload: dict[str, Any] = {
            "model": resolved_model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": temperature,
                "num_ctx": self.num_ctx,
                "num_predict": self.num_predict,
            },
        }

        # Disable thinking traces for qwen3 models to get cleaner output
        if "qwen3" in resolved_model.lower():
            payload["think"] = False

        last_exc: Optional[Exception] = None
        for attempt in range(max_retries):
            try:
                response = self._client.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                return data.get("response", "")

            except httpx.ConnectError as exc:
                last_exc = exc
                wait = 2.0 ** attempt
                logger.warning(
                    "[ollama] Connection refused (attempt %d/%d). "
                    "Is Ollama running at %s? Retrying in %.0fs…",
                    attempt + 1,
                    max_retries,
                    self.base_url,
                    wait,
                )
                time.sleep(wait)

            except httpx.TimeoutException as exc:
                last_exc = exc
                wait = min(60.0, 5.0 * (2 ** attempt))
                logger.warning(
                    "[ollama] Request timed out (attempt %d/%d, timeout=%ds). "
                    "Retrying in %.0fs…",
                    attempt + 1,
                    max_retries,
                    self.timeout,
                    wait,
                )
                time.sleep(wait)

            except httpx.HTTPStatusError as exc:
                last_exc = exc
                logger.error(
                    "[ollama] HTTP %d from server (attempt %d/%d): %s",
                    exc.response.status_code,
                    attempt + 1,
                    max_retries,
                    exc.response.text[:300],
                )
                if exc.response.status_code < 500:
                    raise  # 4xx: client error, don't retry
                time.sleep(2.0 ** attempt)

            except Exception as exc:
                last_exc = exc
                logger.error(
                    "[ollama] Unexpected error (attempt %d/%d): %s",
                    attempt + 1,
                    max_retries,
                    exc,
                )
                time.sleep(2.0 ** attempt)

        raise RuntimeError(
            f"Ollama generate failed after {max_retries} attempts"
        ) from last_exc

    # ------------------------------------------------------------------
    # Batch: concurrent sequential calls
    # ------------------------------------------------------------------

    def generate_batch(
        self,
        requests: list[tuple[str, str]],
        *,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """Run up to _BATCH_WORKERS Ollama requests concurrently."""
        results: dict[str, Any] = {}

        def _call(item: tuple[str, str]) -> tuple[str, Any]:
            cache_key, prompt = item
            try:
                return cache_key, self.generate_json(
                    prompt,
                    model=model,
                    temperature=temperature,
                    max_retries=max_retries,
                )
            except Exception as exc:
                logger.error("[ollama] Batch item '%s' failed: %s", cache_key, exc)
                return cache_key, None

        with ThreadPoolExecutor(max_workers=_BATCH_WORKERS) as pool:
            futures = {pool.submit(_call, item): item[0] for item in requests}
            for future in as_completed(futures):
                key, result = future.result()
                results[key] = result

        return results

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Return True if the Ollama server is reachable."""
        try:
            resp = self._client.get(f"{self.base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def list_models(self) -> list[str]:
        """Return a list of model tags available on the server."""
        try:
            resp = self._client.get(f"{self.base_url}/api/tags", timeout=10)
            resp.raise_for_status()
            return [m["name"] for m in resp.json().get("models", [])]
        except Exception as exc:
            logger.warning("[ollama] Could not fetch model list: %s", exc)
            return []

    def __del__(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass
