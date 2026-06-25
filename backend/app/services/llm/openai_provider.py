"""
OpenAI provider — inference via the OpenAI Chat Completions API.

Also compatible with OpenAI-API-compatible services (e.g. LM Studio,
vLLM, Together AI) by setting OPENAI_BASE_URL to the custom endpoint.

JSON mode is enforced via response_format={"type": "json_object"} when
the model supports it (gpt-4o, gpt-4o-mini, gpt-4-turbo, etc.).
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from .base import BaseLLMProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    """
    Inference provider backed by OpenAI (or compatible) API.

    Args:
        api_key:       OpenAI API key.
        default_model: Model name (default "gpt-4o-mini").
        base_url:      API base URL — override for OpenAI-compatible services.
        timeout:       HTTP timeout in seconds.
    """

    provider_name = "openai"

    def __init__(
        self,
        api_key: str,
        default_model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        timeout: int = 60,
    ) -> None:
        self.api_key = api_key
        self.default_model = default_model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from openai import OpenAI

                self._client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                    timeout=self.timeout,
                )
            except ImportError as exc:
                raise ImportError(
                    "openai package is required for the OpenAI provider. "
                    "Install it with: pip install openai"
                ) from exc
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

        last_exc: Optional[Exception] = None
        for attempt in range(max_retries):
            try:
                response = client.chat.completions.create(
                    model=resolved_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    response_format={"type": "json_object"},
                    max_tokens=2048,
                )
                return response.choices[0].message.content or ""

            except Exception as exc:
                last_exc = exc
                wait = min(60.0, (2**attempt) * 2.0)
                logger.warning(
                    "[openai] generate attempt %d/%d failed: %s. Retrying in %.0fs…",
                    attempt + 1,
                    max_retries,
                    exc,
                    wait,
                )
                if attempt < max_retries - 1:
                    time.sleep(wait)

        raise RuntimeError(
            f"OpenAI generate failed after {max_retries} attempts"
        ) from last_exc
