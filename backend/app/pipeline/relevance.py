"""
Relevance filtering — LLM-powered relevance scoring for brand mentions.

Inputs:  List[CleanedMention] (non-duplicates)
Outputs: Same list with relevance_score, relevance_level, is_relevant updated
"""

from __future__ import annotations

import logging
from typing import List, Tuple

from app.config import settings
from app.models.mention import CleanedMention, RelevanceLevel
from app.prompts.loader import load_prompt
from app.services.llm import call_llm_batch_cached
from app.services.llm.schemas import RelevanceResult

logger = logging.getLogger(__name__)


def _score_to_level(score: float) -> RelevanceLevel:
    if score >= 0.8:
        return RelevanceLevel.HIGH
    elif score >= 0.5:
        return RelevanceLevel.MEDIUM
    elif score >= 0.2:
        return RelevanceLevel.LOW
    else:
        return RelevanceLevel.IRRELEVANT


def filter_relevance(
    mentions: List[CleanedMention],
    threshold: float | None = None,
) -> Tuple[List[CleanedMention], dict]:
    """
    Score relevance for each non-duplicate mention using the configured LLM provider.

    Mentions below threshold get is_relevant=False but are NOT removed
    (preserved for audit trail).
    """
    threshold = threshold or settings.RELEVANCE_THRESHOLD
    audit = {
        "total_scored": 0,
        "relevant": 0,
        "irrelevant": 0,
        "errors": 0,
        "cache_hits": 0,
        "cache_misses": 0,
        "batch_jobs_submitted": 0,
        "batch_requests_sent": 0,
        "score_distribution": {"high": 0, "medium": 0, "low": 0, "irrelevant": 0},
    }

    active = [m for m in mentions if not m.is_duplicate]
    logger.info("Scoring relevance for %d non-duplicate mentions…", len(active))

    if not active:
        return mentions, audit

    aliases = ", ".join(settings.BRAND_ALIASES)
    batch_requests = [
        (
            str(mention.row_number),
            load_prompt(
                "relevance",
                brand_name=settings.BRAND_NAME,
                aliases=aliases,
                title=mention.title,
                source=mention.source_name,
                source_type=mention.source_type,
                text=mention.combined_text[:1200],
            ),
        )
        for mention in active
    ]

    results, batch_stats = call_llm_batch_cached(
        "relevance",
        batch_requests,
        model=settings.model_for_stage("relevance"),
    )
    audit["cache_hits"] = batch_stats.cache_hits
    audit["cache_misses"] = batch_stats.cache_misses
    audit["batch_jobs_submitted"] = batch_stats.batch_jobs_submitted
    audit["batch_requests_sent"] = batch_stats.batch_requests_sent

    for mention in active:
        key = str(mention.row_number)
        try:
            result, _from_cache = results.get(key, (None, False))

            if isinstance(result, dict) and "relevance_score" in result:
                validated = RelevanceResult(**result)
                level = _score_to_level(validated.relevance_score)

                mention.relevance_score = validated.relevance_score
                mention.relevance_level = level.value
                mention.relevance_reason = validated.reason
                mention.is_relevant = validated.relevance_score >= threshold

                audit["score_distribution"][level.value] += 1
            else:
                mention.relevance_score = 0.7
                mention.relevance_level = RelevanceLevel.MEDIUM.value
                mention.is_relevant = True
                audit["errors"] += 1

            audit["total_scored"] += 1
            if mention.is_relevant:
                audit["relevant"] += 1
            else:
                audit["irrelevant"] += 1

        except Exception as exc:
            logger.error("Relevance scoring failed for mention %s: %s", mention.id, exc)
            mention.relevance_score = 0.7
            mention.is_relevant = True
            audit["errors"] += 1
            audit["total_scored"] += 1
            audit["relevant"] += 1

    logger.info(
        "Relevance filtering complete: %d relevant, %d irrelevant out of %d "
        "(%d cache hits, %d batch jobs)",
        audit["relevant"],
        audit["irrelevant"],
        audit["total_scored"],
        audit["cache_hits"],
        audit["batch_jobs_submitted"],
    )
    return mentions, audit
