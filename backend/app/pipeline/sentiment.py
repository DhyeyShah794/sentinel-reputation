"""
Sentiment analysis engine — LLM-powered sentiment with confidence and explanation.

Re-validates existing labels, adds confidence scores and explanations.

Inputs:  List[CleanedMention] (classified, relevant, non-duplicate)
Outputs: Same list with sentiment fields populated
"""

from __future__ import annotations

import logging
import math
from typing import List, Tuple

from app.config import settings
from app.models.mention import CleanedMention, Sentiment
from app.prompts.loader import load_prompt
from app.services.llm import call_llm_batch_cached
from app.services.llm.schemas import SentimentResult

logger = logging.getLogger(__name__)

# Source quality weights for impact scoring
SOURCE_QUALITY = {
    "news": 0.90,
    "professional": 0.80,
    "review": 0.70,
    "forum": 0.60,
    "aggregator": 0.50,
    "unknown": 0.40,
}


def analyze_sentiment(
    mentions: List[CleanedMention],
) -> Tuple[List[CleanedMention], dict]:
    """
    Analyze sentiment for each active mention using the configured LLM provider.

    Also computes impact scores based on reach, source quality,
    sentiment magnitude, and content specificity.
    """
    audit = {
        "total_analyzed": 0,
        "agreements": 0,
        "disagreements": 0,
        "errors": 0,
        "cache_hits": 0,
        "cache_misses": 0,
        "batch_jobs_submitted": 0,
        "batch_requests_sent": 0,
        "distribution": {"positive": 0, "neutral": 0, "negative": 0},
        "disagreement_details": [],
    }

    active = [m for m in mentions if not m.is_duplicate and m.is_relevant]
    logger.info("Analyzing sentiment for %d active mentions…", len(active))

    all_reaches = [m.reach for m in active if m.reach > 0]
    max_reach = max(all_reaches) if all_reaches else 1

    batch_requests = [
        (
            str(mention.row_number),
            load_prompt(
                "sentiment",
                brand_name=settings.BRAND_NAME,
                title=mention.title,
                source=mention.source_name,
                source_type=mention.source_type,
                text=mention.combined_text[:1200],
            ),
        )
        for mention in active
    ]

    results, batch_stats = call_llm_batch_cached(
        "sentiment",
        batch_requests,
        model=settings.model_for_stage("sentiment"),
    )
    audit["cache_hits"] = batch_stats.cache_hits
    audit["cache_misses"] = batch_stats.cache_misses
    audit["batch_jobs_submitted"] = batch_stats.batch_jobs_submitted
    audit["batch_requests_sent"] = batch_stats.batch_requests_sent

    for mention in active:
        key = str(mention.row_number)
        try:
            result, _from_cache = results.get(key, (None, False))

            if isinstance(result, dict) and "sentiment" in result:
                validated = SentimentResult(**result)
                try:
                    sentiment = Sentiment(validated.sentiment)
                except ValueError:
                    sentiment = Sentiment.NEUTRAL

                mention.sentiment = sentiment.value
                mention.sentiment_confidence = validated.confidence
                mention.sentiment_explanation = validated.explanation
                mention.emotional_intensity = validated.emotional_intensity

                original = mention.sentiment_original
                original_val = (
                    original
                    if isinstance(original, str)
                    else (original.value if hasattr(original, "value") else str(original))
                )
                agreement = sentiment.value == original_val
                mention.sentiment_agreement = agreement

                if agreement:
                    audit["agreements"] += 1
                else:
                    audit["disagreements"] += 1
                    audit["disagreement_details"].append(
                        {
                            "mention_id": mention.id,
                            "original": original_val,
                            "new": sentiment.value,
                            "explanation": mention.sentiment_explanation[:100],
                        }
                    )

                audit["distribution"][sentiment.value] += 1
            else:
                mention.sentiment = mention.sentiment_original
                mention.sentiment_confidence = 0.5
                mention.sentiment_explanation = "Fallback to original label"
                audit["errors"] += 1

        except Exception as exc:
            logger.error("Sentiment analysis failed for %s: %s", mention.id, exc)
            mention.sentiment = mention.sentiment_original
            mention.sentiment_confidence = 0.5
            mention.sentiment_explanation = f"Error: {str(exc)[:80]}"
            audit["errors"] += 1

        mention.impact_score = _compute_impact_score(mention, max_reach)
        audit["total_analyzed"] += 1

    logger.info(
        "Sentiment analysis complete: %d analyzed, %d agreements, %d disagreements "
        "(%d batch jobs)",
        audit["total_analyzed"],
        audit["agreements"],
        audit["disagreements"],
        audit["batch_jobs_submitted"],
    )
    return mentions, audit


def _compute_impact_score(mention: CleanedMention, max_reach: int) -> float:
    """
    Compute reputation impact score (0.0–1.0).

    Formula:
      Impact = w1×Reach_norm + w2×Source_quality + w3×Sentiment_magnitude + w4×Relevance

    Weights: reach=0.35, source=0.20, sentiment=0.25, relevance=0.20
    """
    if mention.reach > 0 and max_reach > 0:
        reach_norm = math.log10(mention.reach + 1) / math.log10(max_reach + 1)
    else:
        reach_norm = 0.0

    source_type = mention.source_type
    if isinstance(source_type, str):
        source_quality = SOURCE_QUALITY.get(source_type, 0.4)
    else:
        source_quality = SOURCE_QUALITY.get(
            source_type.value if hasattr(source_type, "value") else str(source_type), 0.4
        )

    sentiment_val = mention.sentiment
    sent_str = (
        sentiment_val
        if isinstance(sentiment_val, str)
        else (sentiment_val.value if hasattr(sentiment_val, "value") else str(sentiment_val))
    )
    sent_magnitude = mention.sentiment_confidence if sent_str in ("positive", "negative") else 0.2

    impact = (
        0.35 * reach_norm
        + 0.20 * source_quality
        + 0.25 * sent_magnitude
        + 0.20 * mention.relevance_score
    )
    return round(min(max(impact, 0.0), 1.0), 3)
