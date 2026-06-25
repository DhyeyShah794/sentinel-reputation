"""
Prompt loader — reads versioned prompt templates from .md files.

Prompts use Python str.format() placeholders: {variable_name}.
Literal curly braces inside JSON examples must be escaped: {{ and }}.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent


@lru_cache(maxsize=None)
def _load_raw(name: str) -> str:
    """Load and cache raw prompt text from a .md file."""
    path = _PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    return path.read_text(encoding="utf-8")


def load_prompt(name: str, **kwargs: Any) -> str:
    """
    Load a named prompt template and substitute variables.

    Args:
        name:   Prompt filename without extension (e.g. "relevance").
        **kwargs: Variables to substitute into the template.

    Returns:
        Formatted prompt string ready to send to the LLM.
    """
    template = _load_raw(name)
    if kwargs:
        try:
            return template.format(**kwargs)
        except KeyError as exc:
            raise ValueError(
                f"Prompt '{name}' requires variable {exc} which was not provided. "
                f"Available variables: {list(kwargs.keys())}"
            ) from exc
    return template


def reload_prompts() -> None:
    """Clear the prompt cache so files are re-read from disk (useful during development)."""
    _load_raw.cache_clear()
    logger.info("Prompt cache cleared — templates will be re-read from disk")
