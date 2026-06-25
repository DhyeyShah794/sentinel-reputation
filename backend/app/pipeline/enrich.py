"""
Enrichment module — Theme extraction, risk detection, opportunity detection.

Inputs:  List[CleanedMention] (fully classified + sentiment)
Outputs: Themes, risks, opportunities as structured data
"""

from __future__ import annotations

import logging
import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Tuple

import numpy as np

from app.config import settings
from app.models.mention import CleanedMention, RiskLevel, Theme
from app.prompts.loader import load_prompt
from app.services.embeddings import encode_texts
from app.services.llm import call_llm_batch_cached, call_llm_cached
from app.services.llm.schemas import RiskResult, ThemeItem
from app.services.llm_cache import prompt_cache_key

logger = logging.getLogger(__name__)

# Common stop-words to exclude when building theme keyword sets
_THEME_STOP_WORDS = {
    "with", "from", "that", "this", "have", "will", "your", "what",
    "into", "over", "more", "also", "about", "their", "which",
}


def _theme_content_keywords(theme_name: str) -> list[str]:
    """
    Extract content keywords from a theme name for matching.

    Strips punctuation/conjunctions, filters words ≤ 3 chars and stop-words,
    and returns the remaining significant words.
    """
    clean = re.sub(r"[&,/()\-]", " ", theme_name)
    words = [
        w for w in clean.lower().split()
        if len(w) > 3 and w not in _THEME_STOP_WORDS
    ]
    return words


# ──────────────────────────────────────────────
# Theme Extraction
# ──────────────────────────────────────────────

def extract_themes(
    mentions: List[CleanedMention],
) -> Tuple[List[Theme], dict]:
    """Extract major themes from the mention corpus via LLM."""
    active = [m for m in mentions if not m.is_duplicate and m.is_relevant]

    if not active:
        return [], {"error": "No active mentions to analyze"}

    sentiment_counts: Dict[str, int] = {"positive": 0, "neutral": 0, "negative": 0}
    driver_counts: Dict[str, int] = {}
    for m in active:
        sent = m.sentiment if isinstance(m.sentiment, str) else m.sentiment.value
        sentiment_counts[sent] = sentiment_counts.get(sent, 0) + 1
        d = m.driver or "Unclassified"
        driver_counts[d] = driver_counts.get(d, 0) + 1

    samples = _select_diverse_samples(active, n=20)
    sample_text = "\n\n".join(
        f"[{m.source_name} | {m.sentiment} | {m.driver}] {m.combined_text[:400]}"
        for m in samples
    )

    prompt = load_prompt(
        "themes",
        brand_name=settings.BRAND_NAME,
        total_mentions=len(active),
        sentiment_breakdown=str(sentiment_counts),
        driver_breakdown=str(driver_counts),
        sample_mentions=sample_text,
    )

    try:
        cache_key = prompt_cache_key(prompt)
        result, from_cache = call_llm_cached(
            "themes",
            cache_key,
            prompt,
            model=settings.model_for_stage("themes"),
        )

        themes: List[Theme] = []
        if isinstance(result, list):
            for item in result:
                if not isinstance(item, dict):
                    continue
                validated = ThemeItem(**item)
                themes.append(
                    Theme(
                        theme_name=validated.theme_name,
                        description=validated.description,
                        mention_count=validated.mention_count,
                        sentiment_skew=validated.sentiment_skew,
                        representative_quotes=validated.representative_quotes,
                        business_implication=validated.business_implication,
                    )
                )

        logger.info("Extracted %d themes (cache_hit=%s)", len(themes), from_cache)
        return themes, {"theme_count": len(themes), "cache_hit": from_cache}

    except Exception as exc:
        logger.error("Theme extraction failed: %s", exc)
        return [], {"error": str(exc)}


# ──────────────────────────────────────────────
# Risk Detection
# ──────────────────────────────────────────────

def detect_risks(
    mentions: List[CleanedMention],
) -> Tuple[List[CleanedMention], dict]:
    """Detect reputation risks for each active mention."""
    active = [m for m in mentions if not m.is_duplicate and m.is_relevant]
    audit = {
        "total_assessed": 0,
        "cache_hits": 0,
        "cache_misses": 0,
        "batch_jobs_submitted": 0,
        "batch_requests_sent": 0,
        "risk_distribution": {"low": 0, "medium": 0, "high": 0},
    }

    if not active:
        return mentions, audit

    batch_requests = [
        (
            str(mention.row_number),
            load_prompt(
                "risk",
                brand_name=settings.BRAND_NAME,
                title=mention.title,
                source=mention.source_name,
                sentiment=mention.sentiment,
                driver=mention.driver or "Unclassified",
                sub_driver=mention.sub_driver or "Unclassified",
                text=mention.combined_text[:1000],
            ),
        )
        for mention in active
    ]

    results, batch_stats = call_llm_batch_cached(
        "risk",
        batch_requests,
        model=settings.model_for_stage("risk"),
    )
    audit["cache_hits"] = batch_stats.cache_hits
    audit["cache_misses"] = batch_stats.cache_misses
    audit["batch_jobs_submitted"] = batch_stats.batch_jobs_submitted
    audit["batch_requests_sent"] = batch_stats.batch_requests_sent

    for mention in active:
        key = str(mention.row_number)
        try:
            result, _from_cache = results.get(key, (None, False))

            if isinstance(result, dict):
                validated = RiskResult(**result)
                mention.risk_level = validated.risk_level
                # Only carry risk_type / risk_signal for genuinely elevated risk.
                # Low-risk mentions should not have these set — they add noise and
                # create inconsistent states in downstream filters.
                if validated.risk_level == "low":
                    mention.risk_type = None
                    mention.risk_signal = None
                else:
                    mention.risk_type = validated.risk_type
                    mention.risk_signal = validated.risk_signal
                audit["risk_distribution"][validated.risk_level] = (
                    audit["risk_distribution"].get(validated.risk_level, 0) + 1
                )
            else:
                mention.risk_level = "low"
                mention.risk_type = None
                mention.risk_signal = None

        except Exception as exc:
            logger.error("Risk detection failed for %s: %s", mention.id, exc)
            mention.risk_level = "low"
            mention.risk_type = None
            mention.risk_signal = None

        audit["total_assessed"] += 1

    logger.info(
        "Risk detection complete: %s (%d batch jobs)",
        audit["risk_distribution"],
        audit["batch_jobs_submitted"],
    )
    return mentions, audit


# ──────────────────────────────────────────────
# Opportunity Detection (rule-based, no LLM)
# ──────────────────────────────────────────────

def detect_opportunities(mentions: List[CleanedMention]) -> List[dict]:
    """Identify amplifiable positive narratives (rule-based, no LLM required)."""
    positive: List[CleanedMention] = []
    for m in mentions:
        if m.is_duplicate or not m.is_relevant:
            continue
        sent = m.sentiment if isinstance(m.sentiment, str) else m.sentiment.value
        if sent == "positive":
            positive.append(m)

    if not positive:
        return []

    positive.sort(key=lambda m: m.impact_score, reverse=True)

    # Category labels derived from driver
    _driver_category = {
        "Brand Perception": "brand_narrative",
        "User Experience": "product_experience",
        "Responsible Business Practices": "trust_governance",
    }

    opportunities = []
    for rank, m in enumerate(positive[:10], start=1):
        amp = "high" if m.impact_score > 0.7 else "medium" if m.impact_score > 0.4 else "low"
        opportunities.append(
            {
                "mention_id": m.id,
                "title": m.title[:100],
                "driver": m.driver,
                "sub_driver": m.sub_driver,
                "impact_score": m.impact_score,
                "reach": m.reach,
                "description": m.sentiment_explanation or m.title,
                "amplification_potential": amp,
                # category groups opportunities by the reputation pillar they serve
                "category": _driver_category.get(m.driver or "", "general"),
                # priority is rank within the sorted-by-impact list (1 = highest)
                "priority": rank,
            }
        )

    logger.info("Identified %d amplification opportunities", len(opportunities))
    return opportunities


# ──────────────────────────────────────────────
# Theme Tagging (keyword-based, no LLM)
# ──────────────────────────────────────────────

_THEME_SIMILARITY_THRESHOLD = 0.40


def tag_mentions_with_themes(
    mentions: List[CleanedMention],
    themes: List[Theme],
) -> Tuple[List[CleanedMention], List[Theme]]:
    """
    Tag each mention with relevant theme names using semantic similarity.

    Uses the same sentence-transformer embedding model as the classification
    stage.  Each theme is represented by "{name}: {description}" and compared
    to the mention's combined_text via cosine similarity.  A mention is tagged
    with a theme if similarity exceeds the threshold.

    After tagging:
    - Each theme's mention_count is set to the actual number of tagged mentions.
    - Themes with zero actual mentions are removed (LLM hallucination guard).

    Returns:
        (updated mentions list, pruned + count-corrected themes list)
    """
    if not themes:
        return mentions, themes

    active = [m for m in mentions if not m.is_duplicate and m.is_relevant]
    if not active:
        return mentions, themes

    theme_texts = [f"{t.theme_name}: {t.description}" for t in themes]
    theme_embeddings = encode_texts(theme_texts)

    mention_texts = [m.combined_text[:512] for m in active]
    mention_embeddings = encode_texts(mention_texts)

    # Normalize for cosine similarity via dot product
    theme_norms = theme_embeddings / (np.linalg.norm(theme_embeddings, axis=1, keepdims=True) + 1e-9)
    mention_norms = mention_embeddings / (np.linalg.norm(mention_embeddings, axis=1, keepdims=True) + 1e-9)

    # similarity_matrix[i][j] = similarity of mention i to theme j
    similarity_matrix = mention_norms @ theme_norms.T

    for i, mention in enumerate(active):
        scores = similarity_matrix[i]
        matched = [
            themes[j].theme_name
            for j in np.argsort(scores)[::-1]
            if scores[j] >= _THEME_SIMILARITY_THRESHOLD
        ]
        mention.themes = matched[:3]

    tag_counts: Counter = Counter(
        tag for m in active for tag in m.themes
    )
    updated_themes: List[Theme] = []
    for theme in themes:
        count = tag_counts.get(theme.theme_name, 0)
        if count == 0:
            logger.warning(
                "Pruning theme '%s' — zero mentions tagged",
                theme.theme_name,
            )
            continue
        theme.mention_count = count
        updated_themes.append(theme)

    logger.info(
        "Theme tagging complete: %d/%d themes retained, %d total tags assigned",
        len(updated_themes),
        len(themes),
        sum(tag_counts.values()),
    )
    return mentions, updated_themes


# ──────────────────────────────────────────────
# Helper
# ──────────────────────────────────────────────

def _select_diverse_samples(mentions: List[CleanedMention], n: int = 20) -> List[CleanedMention]:
    """Select diverse samples across drivers and sentiments."""
    buckets: Dict[str, List[CleanedMention]] = defaultdict(list)
    for m in mentions:
        key = f"{m.driver}_{m.sentiment}"
        buckets[key].append(m)

    selected: List[CleanedMention] = []
    per_bucket = max(1, n // max(len(buckets), 1))

    for bucket in buckets.values():
        bucket.sort(key=lambda m: m.impact_score, reverse=True)
        selected.extend(bucket[:per_bucket])

    if len(selected) < n:
        remaining = sorted(
            [m for m in mentions if m not in selected],
            key=lambda m: m.impact_score,
            reverse=True,
        )
        selected.extend(remaining[: n - len(selected)])

    return selected[:n]
