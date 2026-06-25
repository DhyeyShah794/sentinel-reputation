"""
Persistent JSON cache for Gemini LLM results.

Keys are scoped by pipeline stage and stable row identifiers (row_number)
so reruns skip API calls when the dataset is unchanged.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)

CACHE_VERSION = 1

_cache: Optional["LLMCache"] = None


def compute_dataset_fingerprint(mentions: List[Any]) -> str:
    """Stable hash from sorted mention URLs."""
    urls = sorted(getattr(m, "url", str(m)) for m in mentions)
    digest = hashlib.sha256("\n".join(urls).encode("utf-8")).hexdigest()
    return digest[:16]


def prompt_cache_key(prompt: str) -> str:
    """Hash a prompt for corpus-level cache entries."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]


def init_llm_cache(
    mentions: List[Any],
    *,
    force_refresh: bool = False,
) -> "LLMCache":
    """Initialize (or reset) the global LLM cache for a pipeline run."""
    global _cache
    _cache = LLMCache(settings.LLM_CACHE_FILE)
    _cache.prepare(
        fingerprint=compute_dataset_fingerprint(mentions),
        force_refresh=force_refresh,
    )
    return _cache


def get_llm_cache() -> "LLMCache":
    """Return the active cache, loading from disk if needed."""
    global _cache
    if _cache is None:
        _cache = LLMCache(settings.LLM_CACHE_FILE)
        _cache.load()
    return _cache


class LLMCache:
    """File-backed store for LLM responses keyed by stage + identifier."""

    def __init__(self, cache_path: Path):
        self.cache_path = cache_path
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._data: Dict[str, Any] = {
            "meta": {"version": CACHE_VERSION, "dataset_fingerprint": None},
            "entries": {},
        }
        self.hits = 0
        self.misses = 0
        self._dirty = False

    def load(self) -> None:
        if not self.cache_path.exists():
            return
        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict) and "entries" in loaded:
                self._data = loaded
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Could not load LLM cache ({self.cache_path}): {e}")

    def prepare(
        self,
        *,
        fingerprint: str,
        force_refresh: bool = False,
    ) -> None:
        self.load()
        meta = self._data.setdefault("meta", {})
        stored_fp = meta.get("dataset_fingerprint")

        if force_refresh:
            logger.info("LLM cache: force refresh — clearing all entries")
            self._data["entries"] = {}
            self._dirty = True
        elif stored_fp and stored_fp != fingerprint:
            logger.info(
                "LLM cache: dataset changed (%s → %s) — clearing stale entries",
                stored_fp,
                fingerprint,
            )
            self._data["entries"] = {}
            self._dirty = True

        meta["version"] = CACHE_VERSION
        meta["dataset_fingerprint"] = fingerprint
        meta["updated_at"] = _now_iso()
        if force_refresh or self._dirty:
            self.save()

    def _entry_key(self, stage: str, key: str) -> str:
        return f"{stage}:{key}"

    def get(self, stage: str, key: str) -> Optional[Any]:
        entry = self._data.get("entries", {}).get(self._entry_key(stage, key))
        if entry is None:
            self.misses += 1
            return None
        self.hits += 1
        logger.debug("LLM cache hit: %s:%s", stage, key)
        return entry.get("result")

    def set(self, stage: str, key: str, result: Any) -> None:
        self._data.setdefault("entries", {})[self._entry_key(stage, key)] = {
            "result": result,
            "cached_at": _now_iso(),
        }
        self._dirty = True
        self.save()

    def save(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._data.setdefault("meta", {})["updated_at"] = _now_iso()
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, default=str, ensure_ascii=False)
        self._dirty = False

    def stats(self) -> dict:
        entries = self._data.get("entries", {})
        by_stage: Dict[str, int] = {}
        for full_key in entries:
            stage = full_key.split(":", 1)[0]
            by_stage[stage] = by_stage.get(stage, 0) + 1
        return {
            "cache_file": str(self.cache_path),
            "total_entries": len(entries),
            "entries_by_stage": by_stage,
            "hits_this_run": self.hits,
            "misses_this_run": self.misses,
            "dataset_fingerprint": self._data.get("meta", {}).get("dataset_fingerprint"),
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
