"""
Pipeline orchestrator — Runs the complete intelligence pipeline end-to-end.

Raw Data → Clean → Dedup → Relevance → Classify → Sentiment → Enrich → Score → Summarize
"""

from __future__ import annotations

import csv
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings
from app.models.mention import (
    CleanedMention,
    ExecutiveSummary,
    ProcessedMention,
    ReputationScore,
    Theme,
)
from app.pipeline.classify import classify_mentions
from app.pipeline.clean import clean_mentions, save_cleaned_mentions
from app.pipeline.dedup import deduplicate
from app.pipeline.enrich import (
    detect_opportunities,
    detect_risks,
    extract_themes,
    tag_mentions_with_themes,
)
from app.pipeline.ingest import ingest_xlsx, save_raw_mentions
from app.pipeline.relevance import filter_relevance
from app.pipeline.score import compute_reputation_score
from app.pipeline.sentiment import analyze_sentiment
from app.pipeline.summarize import generate_executive_summary
from app.services.llm_cache import get_llm_cache, init_llm_cache

logger = logging.getLogger(__name__)


class PipelineResult:
    """Container for all pipeline outputs."""

    def __init__(self):
        self.mentions: List[CleanedMention] = []
        self.active_mentions: List[CleanedMention] = []
        self.reputation_score: Optional[ReputationScore] = None
        self.themes: List[Theme] = []
        self.opportunities: List[dict] = []
        self.executive_summary: Optional[ExecutiveSummary] = None
        self.audit: Dict[str, Any] = {}
        self.duration_seconds: float = 0.0

    def get_active(self) -> List[CleanedMention]:
        """Get non-duplicate, relevant mentions."""
        return [m for m in self.mentions if not m.is_duplicate and m.is_relevant]

    def to_processed_mentions(self) -> List[ProcessedMention]:
        """Convert CleanedMentions to ProcessedMentions for API responses."""
        result = []
        for m in self.get_active():
            pm = ProcessedMention(
                id=m.id,
                row_number=m.row_number,
                date=m.date,
                url=m.url,
                source_name=m.source_name,
                source_type=m.source_type,
                title=m.title,
                opening_text=m.opening_text,
                hit_sentence=m.hit_sentence,
                combined_text=m.combined_text,
                reach=m.reach,
                is_duplicate=m.is_duplicate,
                duplicate_group_id=m.duplicate_group_id,
                relevance_score=m.relevance_score,
                relevance_level=m.relevance_level,
                is_relevant=m.is_relevant,
                driver=m.driver,
                sub_driver=m.sub_driver,
                classification_confidence=getattr(m, 'classification_confidence', 0.0) or 0.0,
                classification_rationale=getattr(m, 'classification_rationale', None),
                classification_method=getattr(m, 'classification_method', None),
                sentiment=m.sentiment if isinstance(m.sentiment, str) else m.sentiment,
                sentiment_confidence=getattr(m, 'sentiment_confidence', 0.0) or 0.0,
                sentiment_explanation=getattr(m, 'sentiment_explanation', None),
                sentiment_original=m.sentiment_original,
                sentiment_agreement=getattr(m, 'sentiment_agreement', True),
                emotional_intensity=getattr(m, 'emotional_intensity', 'medium'),
                impact_score=getattr(m, 'impact_score', 0.0) or 0.0,
                risk_level=getattr(m, 'risk_level', 'low') or 'low',
                risk_type=getattr(m, 'risk_type', None),
                risk_signal=getattr(m, 'risk_signal', None),
                themes=getattr(m, 'themes', []),
                reputation_contribution=getattr(m, 'reputation_contribution', 0.0) or 0.0,
            )
            result.append(pm)
        return result

    def save_outputs(self, output_dir: Path | None = None) -> None:
        """Save all pipeline outputs to disk."""
        output_dir = output_dir or settings.DATA_OUTPUTS_DIR

        # Save processed mentions
        processed = self.to_processed_mentions()
        _save_json(
            [m.model_dump(mode="json") for m in processed],
            output_dir / "processed_mentions.json",
        )

        # Save reputation score
        if self.reputation_score:
            _save_json(
                self.reputation_score.model_dump(mode="json"),
                output_dir / "reputation_score.json",
            )

        # Save themes
        if self.themes:
            _save_json(
                [t.model_dump(mode="json") for t in self.themes],
                output_dir / "themes.json",
            )

        # Save opportunities
        if self.opportunities:
            _save_json(self.opportunities, output_dir / "opportunities.json")

        # Save executive summary
        if self.executive_summary:
            _save_json(
                self.executive_summary.model_dump(mode="json"),
                output_dir / "executive_summary.json",
            )

        # Save audit trail
        _save_json(self.audit, output_dir / "pipeline_audit.json")

        # Save as CSV for the assignment deliverable
        _save_csv(processed, output_dir / "classified_dataset.csv")

        logger.info(f"All outputs saved to {output_dir}")


def run_pipeline(skip_llm: bool = False, force_refresh_llm: bool = False) -> PipelineResult:
    """
    Execute the complete reputation intelligence pipeline.

    Args:
        skip_llm: If True, skip LLM-dependent steps (for testing)
        force_refresh_llm: If True, ignore cached LLM results and re-call the LLM provider
    """
    result = PipelineResult()
    start_time = time.time()

    try:
        # ── Phase 1: Ingest ──
        logger.info("=" * 60)
        logger.info("PHASE 1: INGESTION")
        logger.info("=" * 60)
        raw_mentions, ingest_audit = ingest_xlsx()
        save_raw_mentions(raw_mentions)
        result.audit["ingest"] = ingest_audit

        # ── Phase 2: Clean ──
        logger.info("=" * 60)
        logger.info("PHASE 2: CLEANING & STANDARDIZATION")
        logger.info("=" * 60)
        cleaned, clean_audit = clean_mentions(raw_mentions)
        save_cleaned_mentions(cleaned)
        result.audit["clean"] = clean_audit

        # ── Phase 3: Deduplicate ──
        logger.info("=" * 60)
        logger.info("PHASE 3: DEDUPLICATION")
        logger.info("=" * 60)
        cleaned, dedup_audit = deduplicate(cleaned)
        result.audit["dedup"] = dedup_audit

        # Initialize LLM result cache (reuses prior provider responses on reruns)
        if not skip_llm:
            init_llm_cache(cleaned, force_refresh=force_refresh_llm)
            logger.info("LLM cache ready at %s", settings.LLM_CACHE_FILE)

        # ── Phase 4: Relevance ──
        if not skip_llm:
            logger.info("=" * 60)
            logger.info("PHASE 4: RELEVANCE FILTERING")
            logger.info("=" * 60)
            cleaned, relevance_audit = filter_relevance(cleaned)
            result.audit["relevance"] = relevance_audit
        else:
            logger.info("PHASE 4: SKIPPED (skip_llm=True)")

        # ── Phase 5: Classification ──
        if not skip_llm:
            logger.info("=" * 60)
            logger.info("PHASE 5: CLASSIFICATION")
            logger.info("=" * 60)
            cleaned, classify_audit = classify_mentions(cleaned)
            result.audit["classify"] = classify_audit
        else:
            logger.info("PHASE 5: SKIPPED (skip_llm=True)")

        # ── Phase 6: Sentiment ──
        if not skip_llm:
            logger.info("=" * 60)
            logger.info("PHASE 6: SENTIMENT ANALYSIS")
            logger.info("=" * 60)
            cleaned, sentiment_audit = analyze_sentiment(cleaned)
            result.audit["sentiment"] = sentiment_audit
        else:
            logger.info("PHASE 6: SKIPPED (skip_llm=True)")

        # ── Phase 7: Enrichment ──
        if not skip_llm:
            logger.info("=" * 60)
            logger.info("PHASE 7: ENRICHMENT (Risks, Themes, Opportunities)")
            logger.info("=" * 60)

            # Risk detection
            cleaned, risk_audit = detect_risks(cleaned)
            result.audit["risk"] = risk_audit

            # Theme extraction
            themes, theme_audit = extract_themes(cleaned)
            result.themes = themes
            result.audit["themes"] = theme_audit

            # Tag mentions with themes (returns pruned theme list with corrected counts)
            cleaned, themes = tag_mentions_with_themes(cleaned, themes)
            result.themes = themes

            # Opportunity detection
            opportunities = detect_opportunities(cleaned)
            result.opportunities = opportunities
        else:
            logger.info("PHASE 7: SKIPPED (skip_llm=True)")
            themes = []
            opportunities = []

        # ── Phase 8: Reputation Score ──
        logger.info("=" * 60)
        logger.info("PHASE 8: REPUTATION SCORING")
        logger.info("=" * 60)
        rep_score, score_audit = compute_reputation_score(cleaned)
        result.reputation_score = rep_score
        result.audit["score"] = score_audit

        # ── Phase 9: Executive Summary ──
        if not skip_llm:
            logger.info("=" * 60)
            logger.info("PHASE 9: EXECUTIVE SUMMARY")
            logger.info("=" * 60)
            summary = generate_executive_summary(
                cleaned, rep_score, themes, opportunities
            )
            result.executive_summary = summary
        else:
            logger.info("PHASE 9: SKIPPED (skip_llm=True)")

        # ── Store results ──
        result.mentions = cleaned
        result.active_mentions = [m for m in cleaned if not m.is_duplicate and m.is_relevant]

        # ── Save outputs ──
        result.duration_seconds = time.time() - start_time
        result.audit["duration_seconds"] = result.duration_seconds
        if not skip_llm:
            result.audit["llm_cache"] = get_llm_cache().stats()
        result.save_outputs()

        logger.info("=" * 60)
        logger.info(f"PIPELINE COMPLETE in {result.duration_seconds:.1f}s")
        logger.info(f"  Total records:  {len(cleaned)}")
        logger.info(f"  Active records: {len(result.active_mentions)}")
        logger.info(f"  Rep Score:      {rep_score.overall_score}/100")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        result.audit["error"] = str(e)
        raise

    return result


def _save_json(data: Any, path: Path) -> None:
    """Save data as JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str, ensure_ascii=False)


def _save_csv(mentions: list, path: Path) -> None:
    """Save processed mentions as CSV for assignment deliverable."""
    path.parent.mkdir(parents=True, exist_ok=True)

    if not mentions:
        return

    # Get fields from first mention
    first = mentions[0]
    if hasattr(first, 'model_dump'):
        fields = list(first.model_dump().keys())
    else:
        fields = list(first.__dict__.keys())

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for m in mentions:
            if hasattr(m, 'model_dump'):
                row = m.model_dump(mode="json")
            else:
                row = {k: str(v) for k, v in m.__dict__.items()}
            # Convert lists to strings for CSV
            for key, value in row.items():
                if isinstance(value, list):
                    row[key] = "; ".join(str(v) for v in value)
            writer.writerow(row)

    logger.info(f"Saved CSV with {len(mentions)} records to {path}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    force_refresh = "--force-refresh-llm" in sys.argv
    result = run_pipeline(force_refresh_llm=force_refresh)
    print(f"\nPipeline completed in {result.duration_seconds:.1f}s")
    print(f"Active mentions: {len(result.active_mentions)}")
    if result.reputation_score:
        print(f"Reputation Score: {result.reputation_score.overall_score}/100")
