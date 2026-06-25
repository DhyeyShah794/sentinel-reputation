"""
Data cleaning module — Fix quality issues, infer missing fields, normalize values.

Inputs:  List[RawMention]
Outputs: List[CleanedMention] + cleaning audit
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime
from typing import List, Optional, Tuple
from urllib.parse import urlparse

from app.config import settings
from app.models.mention import (
    CleanedMention,
    RawMention,
    Sentiment,
    SourceType,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Source inference rules: URL domain → source name
# ──────────────────────────────────────────────
DOMAIN_TO_SOURCE = {
    "play.google.com": "Play Store",
    "apps.apple.com": "App Store",
    "reddit.com": None,  # Handled specially — uses subreddit
    "linkedin.com": "LinkedIn",
    "twitter.com": "X (Twitter)",
    "x.com": "X (Twitter)",
    "mouthshut.com": "Mouthshut",
    "economictimes.indiatimes.com": "The Economic Times",
    "moneycontrol.com": "Moneycontrol.com",
    "cnbctv18.com": "CNBC-TV18",
    "businessworld.in": "BW BusinessWorld",
    "livemint.com": "Mint",
    "ndtv.com": "NDTV",
    "businesstoday.in": "Business Today",
    "financialexpress.com": "The Financial Express",
    "thehindu.com": "The Hindu",
    "thehindubusinessline.com": "The Hindu Business Line",
    "zeebiz.com": "Zee Business",
    "business-standard.com": "Business Standard",
    "news18.com": "News18",
    "timesofindia.indiatimes.com": "The Times of India",
    "msn.com": "MSN India",
    "dailyhunt.in": "DailyHunt",
    "newspointapp.com": "newspoint",
    "fortune.com": "Fortune India",
    "fortuneindia.com": "Fortune India",
    "goodreturns.in": "Goodreturns",
    "equitymaster.com": "Equitymaster.com",
    "etnow.in": "ET Now",
    "angelone.in": "Angel One",
    "upstox.com": "Upstox",
    "shiksha.com": "Shiksha.com",
    "money9live.com": "Money9live",
}

# Source name → SourceType
SOURCE_TYPE_MAP = {
    "The Economic Times": SourceType.NEWS,
    "CNBC-TV18": SourceType.NEWS,
    "Moneycontrol.com": SourceType.NEWS,
    "BW BusinessWorld": SourceType.NEWS,
    "Business Today": SourceType.NEWS,
    "The Financial Express": SourceType.NEWS,
    "The Hindu Business Line": SourceType.NEWS,
    "Zee Business": SourceType.NEWS,
    "Business Standard": SourceType.NEWS,
    "News18": SourceType.NEWS,
    "The Times of India": SourceType.NEWS,
    "Fortune India": SourceType.NEWS,
    "Goodreturns": SourceType.NEWS,
    "Equitymaster.com": SourceType.NEWS,
    "ET Now": SourceType.NEWS,
    "Mint": SourceType.NEWS,
    "NDTV": SourceType.NEWS,
    "Money9live": SourceType.NEWS,
    "Shiksha.com": SourceType.NEWS,
    "MSN India": SourceType.AGGREGATOR,
    "DailyHunt": SourceType.AGGREGATOR,
    "newspoint": SourceType.AGGREGATOR,
    "OBnews": SourceType.AGGREGATOR,
    "Play Store": SourceType.REVIEW,
    "App Store": SourceType.REVIEW,
    "Mouthshut": SourceType.REVIEW,
    "LinkedIn": SourceType.PROFESSIONAL,
    "Angel One": SourceType.PROFESSIONAL,
    "Upstox": SourceType.PROFESSIONAL,
    "X (Twitter)": SourceType.FORUM,
}


def _infer_source_from_url(url: str) -> Optional[str]:
    """Extract source name from URL domain."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower().replace("www.", "")

        # Special case: Reddit — use subreddit as source
        if "reddit.com" in domain:
            # Extract subreddit from path: /r/mutualfunds/...
            match = re.search(r"/r/([^/]+)", parsed.path)
            if match:
                return f"reddit.com/r/{match.group(1)}"
            return "reddit.com"

        # Try exact domain match
        for key, source in DOMAIN_TO_SOURCE.items():
            if key in domain:
                return source

        # Fallback: use domain
        return domain

    except Exception:
        return None


def _classify_source_type(source_name: str, url: str) -> SourceType:
    """Determine source type from source name."""
    # Direct lookup
    if source_name in SOURCE_TYPE_MAP:
        return SOURCE_TYPE_MAP[source_name]

    # Pattern-based
    lower = source_name.lower()
    if "reddit" in lower:
        return SourceType.FORUM
    if "play store" in lower or "app store" in lower or "mouthshut" in lower:
        return SourceType.REVIEW
    if "linkedin" in lower:
        return SourceType.PROFESSIONAL

    # URL-based fallback
    if "reddit.com" in url:
        return SourceType.FORUM
    if "play.google.com" in url:
        return SourceType.REVIEW

    return SourceType.NEWS  # Default for unrecognized sources


def _normalize_sentiment(sentiment_raw: Optional[str]) -> Sentiment:
    """Normalize sentiment string to enum (handle casing issues)."""
    if not sentiment_raw:
        return Sentiment.NEUTRAL

    lower = sentiment_raw.strip().lower()
    if lower == "positive":
        return Sentiment.POSITIVE
    elif lower == "negative":
        return Sentiment.NEGATIVE
    else:
        return Sentiment.NEUTRAL


def _normalize_date(dt: object) -> Optional[date]:
    """Convert datetime to date, handling various formats."""
    if dt is None:
        return None

    # Already a datetime → extract date (check datetime before date; datetime is a subclass)
    if isinstance(dt, datetime):
        return dt.date()

    # Already a plain date
    if isinstance(dt, date):
        return dt

    # String → parse
    if isinstance(dt, str):
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(dt.strip(), fmt).date()
            except ValueError:
                continue

    return None


def _merge_text_fields(
    title: Optional[str],
    opening: Optional[str],
    hit: Optional[str],
) -> str:
    """Merge available text fields into a single combined text."""
    parts = []
    if title:
        parts.append(title.strip())
    if opening:
        parts.append(opening.strip())
    if hit and hit.strip() not in (title or ""):
        # Only add hit sentence if it's not redundant with title
        parts.append(hit.strip())
    return " ".join(parts) if parts else ""


def _fill_title(
    title: Optional[str],
    opening: Optional[str],
    hit: Optional[str],
) -> str:
    """Create a title from available fields if missing."""
    if title and title.strip():
        return title.strip()
    # Use first 120 chars of opening text
    if opening and opening.strip():
        text = opening.strip()
        if len(text) > 120:
            return text[:117] + "..."
        return text
    # Use hit sentence
    if hit and hit.strip():
        text = hit.strip()
        if len(text) > 120:
            return text[:117] + "..."
        return text
    return "Untitled Mention"


def clean_mentions(
    raw_mentions: List[RawMention],
) -> Tuple[List[CleanedMention], dict]:
    """
    Clean and standardize raw mentions.

    Operations (in order):
    1. Normalize sentiment casing
    2. Infer missing source names from URLs
    3. Classify source types
    4. Normalize dates
    5. Fill missing titles
    6. Merge text fields
    7. Normalize reach values
    8. Trim whitespace

    Returns:
        Tuple of (cleaned_mentions, audit_log)
    """
    cleaned: List[CleanedMention] = []
    audit = {
        "total_input": len(raw_mentions),
        "sentiment_fixes": 0,
        "source_inferred": 0,
        "title_filled": 0,
        "date_missing": 0,
        "reach_missing": 0,
        "issues": [],
    }

    for raw in raw_mentions:
        notes: List[str] = []

        # 1. Normalize sentiment
        sentiment = _normalize_sentiment(raw.sentiment_raw)
        if raw.sentiment_raw and raw.sentiment_raw != sentiment.value:
            notes.append(f"Sentiment normalized: '{raw.sentiment_raw}' → '{sentiment.value}'")
            audit["sentiment_fixes"] += 1

        # 2. Infer source name
        source_name = raw.source_name_raw
        if not source_name or not source_name.strip():
            inferred = _infer_source_from_url(raw.url)
            if inferred:
                source_name = inferred
                notes.append(f"Source inferred from URL: '{inferred}'")
                audit["source_inferred"] += 1
            else:
                source_name = "Unknown"
                notes.append("Could not infer source from URL")
        source_name = source_name.strip()

        # 3. Classify source type
        source_type = _classify_source_type(source_name, raw.url)

        # 4. Normalize date
        normalized_date = _normalize_date(raw.date_raw)
        if raw.date_raw and not normalized_date:
            notes.append(f"Date parse failed: {raw.date_raw}")
        if not normalized_date:
            audit["date_missing"] += 1

        # 5. Fill title
        title = _fill_title(
            raw.title_raw, raw.opening_text_raw, raw.hit_sentence_raw
        )
        if not raw.title_raw or not raw.title_raw.strip():
            notes.append(f"Title filled from text: '{title[:50]}...'")
            audit["title_filled"] += 1

        # 6. Merge text
        combined = _merge_text_fields(
            raw.title_raw, raw.opening_text_raw, raw.hit_sentence_raw
        )

        # 7. Normalize reach
        reach = raw.reach_raw if raw.reach_raw and raw.reach_raw > 0 else 0
        if reach == 0 and raw.reach_raw is None:
            audit["reach_missing"] += 1

        # Build cleaned mention
        cleaned_mention = CleanedMention(
            id=raw.id,
            row_number=raw.row_number,
            date=normalized_date,
            url=raw.url.strip(),
            source_name=source_name,
            source_type=source_type,
            title=title,
            opening_text=raw.opening_text_raw.strip() if raw.opening_text_raw else None,
            hit_sentence=raw.hit_sentence_raw.strip() if raw.hit_sentence_raw else None,
            combined_text=combined,
            sentiment_original=sentiment,
            reach=reach,
            cleaning_notes=notes,
        )
        cleaned.append(cleaned_mention)

    logger.info(
        f"Cleaning complete: {len(cleaned)} mentions cleaned. "
        f"Fixes: sentiment={audit['sentiment_fixes']}, "
        f"source_inferred={audit['source_inferred']}, "
        f"title_filled={audit['title_filled']}"
    )

    return cleaned, audit


def save_cleaned_mentions(
    mentions: List[CleanedMention],
    output_dir=None,
) -> None:
    """Save cleaned mentions as JSON."""
    output_dir = output_dir or settings.DATA_PROCESSED_DIR
    output_path = output_dir / "02_cleaned_mentions.json"

    data = [m.model_dump(mode="json") for m in mentions]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str, ensure_ascii=False)

    logger.info(f"Saved {len(mentions)} cleaned mentions to {output_path}")
