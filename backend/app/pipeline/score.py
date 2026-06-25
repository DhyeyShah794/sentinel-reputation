"""
Reputation scoring engine — Proprietary 0–100 score with driver breakdown.

Inspired by (but not copying) Eminence's RepScore™ methodology.

Score = Σ (Driver_Weight × Driver_Score)
Each Driver_Score is a composite of sentiment ratios, volume, and reach.
"""

from __future__ import annotations

import logging
import math
from typing import Dict, List, Tuple

from app.models.mention import (
    CleanedMention,
    DriverScore,
    ReputationScore,
)

logger = logging.getLogger(__name__)


# Driver weights (must sum to 1.0)
DRIVER_WEIGHTS = {
    "Brand Perception": 0.40,
    "User Experience": 0.35,
    "Responsible Business Practices": 0.25,
}

# Base score when no mentions exist for a driver (neutral assumption)
NEUTRAL_BASE = 60.0


def compute_reputation_score(
    mentions: List[CleanedMention],
) -> Tuple[ReputationScore, dict]:
    """
    Compute overall reputation score (0–100) with driver breakdown.

    Formula per driver:
      Driver_Score = base + positive_bonus - negative_penalty + reach_bonus + volume_bonus

    Where:
      base = 50
      positive_bonus = (positive_ratio) × 40
      negative_penalty = (negative_ratio) × 50  (negative weighs more)
      reach_bonus = avg_positive_reach_ratio × 5
      volume_bonus = min(mention_count / 10, 5)
    """
    active = [m for m in mentions if not m.is_duplicate and m.is_relevant]

    if not active:
        return ReputationScore(
            overall_score=50.0,
            methodology_note="No active mentions to score.",
        ), {"error": "No active mentions"}

    # Group by driver
    driver_mentions: Dict[str, List[CleanedMention]] = {}
    for m in active:
        d = m.driver or "Unknown"
        if d not in driver_mentions:
            driver_mentions[d] = []
        driver_mentions[d].append(m)

    # Max reach for normalization
    max_reach = max((m.reach for m in active if m.reach > 0), default=1)

    driver_scores: List[DriverScore] = []
    weighted_total = 0.0
    total_weight = 0.0

    for driver_name, weight in DRIVER_WEIGHTS.items():
        group = driver_mentions.get(driver_name, [])

        if not group:
            # No mentions: neutral score
            ds = DriverScore(
                driver=driver_name,
                score=NEUTRAL_BASE,
                mention_count=0,
            )
            driver_scores.append(ds)
            weighted_total += NEUTRAL_BASE * weight
            total_weight += weight
            continue

        # Count sentiments
        positive = sum(1 for m in group if _get_sentiment(m) == "positive")
        negative = sum(1 for m in group if _get_sentiment(m) == "negative")
        neutral = sum(1 for m in group if _get_sentiment(m) == "neutral")
        total = len(group)

        positive_ratio = positive / total if total > 0 else 0
        negative_ratio = negative / total if total > 0 else 0

        # Compute sub-driver scores
        sub_scores = _compute_sub_scores(group, max_reach)

        # Driver score calculation
        base = 50.0
        positive_bonus = positive_ratio * 40
        negative_penalty = negative_ratio * 50  # Negative weighs more
        volume_bonus = min(total / 10, 5)

        # Reach bonus: if positives have higher reach than negatives
        pos_reach = sum(m.reach for m in group if _get_sentiment(m) == "positive")
        neg_reach = sum(m.reach for m in group if _get_sentiment(m) == "negative")
        total_reach = pos_reach + neg_reach
        reach_bonus = 0.0
        if total_reach > 0:
            reach_bonus = ((pos_reach - neg_reach) / total_reach) * 5

        score = base + positive_bonus - negative_penalty + volume_bonus + reach_bonus
        score = max(0.0, min(100.0, score))

        ds = DriverScore(
            driver=driver_name,
            score=round(score, 1),
            sub_scores=sub_scores,
            mention_count=total,
            positive_count=positive,
            negative_count=negative,
            neutral_count=neutral,
        )
        driver_scores.append(ds)
        weighted_total += score * weight
        total_weight += weight

    # Overall score
    overall = weighted_total / total_weight if total_weight > 0 else 50.0
    overall = round(max(0.0, min(100.0, overall)), 1)

    # Determine top positive/negative drivers
    scored_drivers = [ds for ds in driver_scores if ds.mention_count > 0]
    top_positive = max(scored_drivers, key=lambda d: d.score).driver if scored_drivers else None
    top_negative = min(scored_drivers, key=lambda d: d.score).driver if scored_drivers else None

    rep_score = ReputationScore(
        overall_score=overall,
        driver_scores=driver_scores,
        top_positive_driver=top_positive,
        top_negative_driver=top_negative,
        methodology_note=(
            "Weighted composite score (0–100) based on sentiment ratios, "
            "volume, reach distribution, and source quality across three "
            "reputation drivers. Weights: Brand Perception (40%), "
            "User Experience (35%), Responsible Business (25%)."
        ),
    )

    # Set contribution scores on individual mentions
    for m in active:
        _set_contribution(m, rep_score, max_reach)

    audit = {
        "overall_score": overall,
        "driver_scores": {ds.driver: ds.score for ds in driver_scores},
        "total_active_mentions": len(active),
    }

    logger.info(f"Reputation Score: {overall}/100")
    return rep_score, audit


def _get_sentiment(m: CleanedMention) -> str:
    """Safely get sentiment string."""
    s = m.sentiment
    return s if isinstance(s, str) else (s.value if hasattr(s, 'value') else str(s))


def _compute_sub_scores(
    mentions: List[CleanedMention],
    max_reach: int,
) -> Dict[str, float]:
    """Compute scores for each sub-driver within a driver group."""
    from collections import defaultdict

    sub_groups: Dict[str, List[CleanedMention]] = defaultdict(list)
    for m in mentions:
        sd = m.sub_driver or "Unknown"
        sub_groups[sd].append(m)

    sub_scores = {}
    for sd, group in sub_groups.items():
        total = len(group)
        positive = sum(1 for m in group if _get_sentiment(m) == "positive")
        negative = sum(1 for m in group if _get_sentiment(m) == "negative")

        pos_ratio = positive / total if total > 0 else 0
        neg_ratio = negative / total if total > 0 else 0

        score = 50 + pos_ratio * 40 - neg_ratio * 50
        sub_scores[sd] = round(max(0, min(100, score)), 1)

    return sub_scores


def _set_contribution(
    mention: CleanedMention,
    rep_score: ReputationScore,
    max_reach: int,
) -> None:
    """Set the reputation contribution score for a single mention."""
    sent = _get_sentiment(mention)
    direction = 1.0 if sent == "positive" else (-1.0 if sent == "negative" else 0.0)
    reach_factor = (
        math.log10(mention.reach + 1) / math.log10(max_reach + 1)
        if mention.reach > 0 and max_reach > 0
        else 0.1
    )
    mention.reputation_contribution = round(
        direction * mention.impact_score * reach_factor, 4
    )
