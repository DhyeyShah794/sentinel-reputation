"""
Gemini provider — wraps the Google Gemini API.

Uses the Gemini Batch API for bulk requests (separate quota from realtime)
and falls back to realtime generate_content for single calls.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Optional

from .base import BaseLLMProvider

logger = logging.getLogger(__name__)

_TERMINAL_BATCH_STATES = frozenset(
    {
        "JOB_STATE_SUCCEEDED",
        "JOB_STATE_FAILED",
        "JOB_STATE_CANCELLED",
        "JOB_STATE_EXPIRED",
    }
)


class GeminiProvider(BaseLLMProvider):
    """
    Inference provider backed by Google Gemini.

    Uses the Batch API for generate_batch() (better throughput, separate quota)
    and realtime generate_content for single generate() calls.
    """

    provider_name = "gemini"

    def __init__(
        self,
        api_key: str,
        default_model: str = "gemini-2.0-flash",
        batch_poll_seconds: float = 5.0,
        batch_chunk_size: int = 50,
        batch_chunk_delay: float = 10.0,
    ) -> None:
        self.api_key = api_key
        self.default_model = default_model
        self.batch_poll_seconds = batch_poll_seconds
        self.batch_chunk_size = batch_chunk_size
        self.batch_chunk_delay = batch_chunk_delay
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self.api_key)
        return self._client

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
        client = self._get_client()
        config = {"temperature": temperature, "top_p": 0.95, "max_output_tokens": 2048}

        last_exc: Optional[Exception] = None
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=resolved_model,
                    contents=prompt,
                    config=config,
                )
                return response.text.strip()
            except Exception as exc:
                last_exc = exc
                wait = self._retry_delay(exc, attempt)
                logger.warning(
                    "[gemini] generate attempt %d/%d failed: %s. Retrying in %.0fs…",
                    attempt + 1,
                    max_retries,
                    exc,
                    wait,
                )
                if attempt < max_retries - 1:
                    time.sleep(wait)

        raise RuntimeError(
            f"Gemini generate failed after {max_retries} attempts"
        ) from last_exc

    # ------------------------------------------------------------------
    # Batch — Gemini Batch API
    # ------------------------------------------------------------------

    def generate_batch(
        self,
        requests: list[tuple[str, str]],
        *,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        resolved_model = model or self.default_model
        results: dict[str, Any] = {}
        pending = list(requests)
        num_chunks = (len(pending) + self.batch_chunk_size - 1) // self.batch_chunk_size

        for chunk_idx, chunk_start in enumerate(
            range(0, len(pending), self.batch_chunk_size)
        ):
            if chunk_idx > 0 and self.batch_chunk_delay > 0:
                logger.info(
                    "[gemini] Waiting %.0fs before chunk %d/%d",
                    self.batch_chunk_delay,
                    chunk_idx + 1,
                    num_chunks,
                )
                time.sleep(self.batch_chunk_delay)

            chunk = pending[chunk_start : chunk_start + self.batch_chunk_size]
            try:
                chunk_results = self._run_batch_job(
                    chunk,
                    model=resolved_model,
                    temperature=temperature,
                    display_name=f"sentinel-batch-{chunk_idx + 1}",
                )
                results.update(chunk_results)
            except Exception as exc:
                logger.error(
                    "[gemini] Batch chunk %d/%d failed: %s", chunk_idx + 1, num_chunks, exc
                )
                for key, _ in chunk:
                    results[key] = None

        return results

    # ------------------------------------------------------------------
    # Internal Batch API helpers
    # ------------------------------------------------------------------

    def _run_batch_job(
        self,
        items: list[tuple[str, str]],
        *,
        model: str,
        temperature: float,
        display_name: str,
        max_retries: int = 5,
    ) -> dict[str, Any]:
        client = self._get_client()
        config = {"temperature": temperature, "top_p": 0.95, "max_output_tokens": 2048}

        inlined = [
            {
                "contents": [{"parts": [{"text": prompt}], "role": "user"}],
                "metadata": {"key": key},
                "config": config,
            }
            for key, prompt in items
        ]

        batch_job = self._submit_with_retry(
            client, model=model, inlined=inlined, display_name=display_name, max_retries=max_retries
        )
        job_name = batch_job.name
        logger.info(
            "[gemini] Submitted batch job %s with %d requests (model=%s)",
            job_name,
            len(items),
            model,
        )

        while True:
            batch_job = client.batches.get(name=job_name)
            state = self._job_state(batch_job)
            if state in _TERMINAL_BATCH_STATES:
                break
            logger.info(
                "[gemini] Batch %s state: %s — waiting %.0fs", job_name, state, self.batch_poll_seconds
            )
            time.sleep(self.batch_poll_seconds)

        if state != "JOB_STATE_SUCCEEDED":
            error = getattr(batch_job, "error", None)
            raise RuntimeError(f"Gemini batch job {job_name} ended with {state}: {error}")

        results: dict[str, Any] = {}
        inlined_responses = (
            batch_job.dest.inlined_responses
            if batch_job.dest and batch_job.dest.inlined_responses
            else []
        )
        for idx, resp in enumerate(inlined_responses):
            key = None
            if resp.metadata and resp.metadata.get("key"):
                key = resp.metadata["key"]
            elif idx < len(items):
                key = items[idx][0]
            if not key:
                continue
            if resp.error:
                logger.error("[gemini] Batch item %s failed: %s", key, resp.error)
                results[key] = None
            elif resp.response:
                text = resp.response.text.strip()
                results[key] = self._extract_json(text)
            else:
                results[key] = None

        for key, _ in items:
            results.setdefault(key, None)

        logger.info("[gemini] Batch job %s complete — %d responses", job_name, len(results))
        return results

    def _submit_with_retry(
        self,
        client: Any,
        *,
        model: str,
        inlined: list,
        display_name: str,
        max_retries: int,
    ) -> Any:
        last_exc: Optional[Exception] = None
        for attempt in range(max_retries):
            try:
                return client.batches.create(
                    model=model,
                    src={"inlined_requests": inlined},
                    config={"display_name": display_name},
                )
            except Exception as exc:
                last_exc = exc
                if not self._is_rate_limit(exc) or attempt >= max_retries - 1:
                    raise
                wait = self._retry_delay(exc, attempt)
                logger.warning(
                    "[gemini] Batch submission rate-limited (attempt %d/%d). Waiting %.0fs…",
                    attempt + 1,
                    max_retries,
                    wait,
                )
                time.sleep(wait)
        raise RuntimeError("Batch submission retries exhausted") from last_exc

    @staticmethod
    def _job_state(batch_job: Any) -> str:
        state = batch_job.state
        if state is None:
            return "JOB_STATE_PENDING"
        if hasattr(state, "name"):
            return state.name
        if hasattr(state, "value"):
            return state.value
        return str(state)

    @staticmethod
    def _is_rate_limit(exc: Exception) -> bool:
        msg = str(exc).lower()
        return "429" in msg or "resource_exhausted" in msg or "quota" in msg

    @staticmethod
    def _retry_delay(exc: Exception, attempt: int) -> float:
        match = re.search(r"retry in (\d+(?:\.\d+)?)s", str(exc), re.IGNORECASE)
        if match:
            return float(match.group(1)) + 1.0
        return min(60.0, (2**attempt) * 5.0)
