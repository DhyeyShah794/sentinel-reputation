"""
Executive summary generator — Auto-generate consultant-ready intelligence brief.

Uses the configured LLM provider (defaults to a larger model for better narrative quality).
"""

from __future__ import annotations

import logging
from typing import List, Optional

from app.config import settings
from app.models.mention import (
    CleanedMention,
    ExecutiveSummary,
    ReputationScore,
    Theme,
)
from app.prompts.loader import load_prompt
from app.services.llm import call_llm_cached
from app.services.llm.schemas import SummaryResult
from app.services.llm_cache import prompt_cache_key

logger = logging.getLogger(__name__)


def generate_executive_summary(
    mentions: List[CleanedMention],
    rep_score: ReputationScore,
    themes: List[Theme],
    opportunities: List[dict],
) -> ExecutiveSummary:
    """Generate an AI-powered executive summary."""
    active = [m for m in mentions if not m.is_duplicate and m.is_relevant]

    if not active:
        return ExecutiveSummary(
            brand_name=settings.BRAND_NAME,
            period="N/A",
            reputation_score=50.0,
            total_mentions=0,
            key_findings=["Insufficient data for analysis."],
            top_positives=[],
            top_negatives=[],
            emerging_themes=[],
            recommended_actions=["Increase data collection coverage."],
            risk_alerts=[],
        )

    dates = [m.date for m in active if m.date]
    period = (
        f"{min(dates).strftime('%b %Y')} – {max(dates).strftime('%b %Y')}"
        if dates
        else "Period not available"
    )

    def _sent(m: CleanedMention) -> str:
        s = m.sentiment
        return s if isinstance(s, str) else (s.value if hasattr(s, "value") else str(s))

    positive = sum(1 for m in active if _sent(m) == "positive")
    neutral = sum(1 for m in active if _sent(m) == "neutral")
    negative = sum(1 for m in active if _sent(m) == "negative")

    driver_counts: dict = {}
    for m in active:
        d = m.driver or "Unclassified"
        driver_counts[d] = driver_counts.get(d, 0) + 1

    themes_text = "\n".join(
        f"- {t.theme_name}: {t.description} (Sentiment: {t.sentiment_skew})"
        for t in themes[:5]
    ) or "No themes extracted."

    high_risk = [m for m in active if m.risk_level in ("high", "medium")]
    risk_text = "\n".join(
        f"- [{m.risk_level.upper()}] {m.title[:80]} — {m.risk_signal or 'No signal'}"
        for m in high_risk[:5]
    ) or "No high-risk mentions."

    opp_text = "\n".join(
        f"- {o.get('title', '')[:80]} (Impact: {o.get('impact_score', 0):.2f})"
        for o in opportunities[:5]
    ) or "No opportunities identified."

    prompt = load_prompt(
        "executive_summary",
        brand_name=settings.BRAND_NAME,
        period=period,
        rep_score=rep_score.overall_score,
        total_mentions=len(active),
        positive=positive,
        neutral=neutral,
        negative=negative,
        driver_breakdown=str(driver_counts),
        themes_text=themes_text,
        risk_mentions=risk_text,
        opportunities=opp_text,
    )

    try:
        cache_key = prompt_cache_key(prompt)
        result, from_cache = call_llm_cached(
            "executive_summary",
            cache_key,
            prompt,
            model=settings.model_for_stage("executive_summary"),
        )
        logger.info(
            "Executive summary %s", "loaded from cache" if from_cache else "generated via LLM"
        )

        if isinstance(result, dict):
            validated = SummaryResult(**result)
            return ExecutiveSummary(
                brand_name=settings.BRAND_NAME,
                period=period,
                reputation_score=rep_score.overall_score,
                total_mentions=len(active),
                key_findings=validated.key_findings,
                top_positives=validated.top_positives,
                top_negatives=validated.top_negatives,
                emerging_themes=validated.emerging_themes,
                recommended_actions=validated.recommended_actions,
                risk_alerts=validated.risk_alerts,
            )

    except Exception as exc:
        logger.error("Executive summary generation failed: %s", exc)

    # Fallback: rule-based summary without LLM
    return ExecutiveSummary(
        brand_name=settings.BRAND_NAME,
        period=period,
        reputation_score=rep_score.overall_score,
        total_mentions=len(active),
        key_findings=[
            f"Analyzed {len(active)} digital mentions across "
            f"{len(set(m.source_name for m in active))} sources.",
            f"Sentiment split: {positive} positive, {neutral} neutral, {negative} negative.",
            f"Overall reputation score: {rep_score.overall_score}/100.",
        ],
        top_positives=[
            ds.driver
            for ds in rep_score.driver_scores
            if ds.score > 65 and ds.mention_count > 0
        ][:3],
        top_negatives=[
            ds.driver
            for ds in rep_score.driver_scores
            if ds.score < 50 and ds.mention_count > 0
        ][:3],
        emerging_themes=[t.theme_name for t in themes[:3]],
        recommended_actions=[
            "Review and address negative sentiment drivers.",
            "Amplify positive brand perception narratives.",
        ],
        risk_alerts=[
            f"{sum(1 for m in active if m.risk_level in ('high', 'medium'))} "
            "mentions flagged as medium/high risk."
        ],
    )
