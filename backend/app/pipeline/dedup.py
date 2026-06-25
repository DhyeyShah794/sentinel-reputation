"""
Deduplication module — 3-tier dedup: exact URL, fuzzy text, semantic similarity.

Inputs:  List[CleanedMention]
Outputs: List[CleanedMention] with dedup flags set
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from typing import Dict, List, Set, Tuple

from app.config import settings
from app.models.mention import CleanedMention

try:
    from rapidfuzz import fuzz as _rapidfuzz_fuzz
    _RAPIDFUZZ_AVAILABLE = True
except ImportError:
    _rapidfuzz_fuzz = None  # type: ignore[assignment]
    _RAPIDFUZZ_AVAILABLE = False

try:
    import numpy as np
    from sentence_transformers import SentenceTransformer
    _SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    np = None  # type: ignore[assignment]
    SentenceTransformer = None  # type: ignore[assignment,misc]
    _SENTENCE_TRANSFORMERS_AVAILABLE = False

logger = logging.getLogger(__name__)


def _count_nulls(mention: CleanedMention) -> int:
    """Count empty/null fields for quality ranking."""
    count = 0
    if not mention.date:
        count += 1
    if not mention.opening_text:
        count += 1
    if not mention.hit_sentence:
        count += 1
    if mention.reach == 0:
        count += 1
    return count


def _select_primary(group: List[CleanedMention]) -> CleanedMention:
    """From a duplicate group, select the best record to keep."""
    return max(
        group,
        key=lambda m: (
            m.reach,                              # Highest reach
            -_count_nulls(m),                     # Fewest nulls
            1 if m.source_type == "news" else 0,  # Prefer original source
            len(m.combined_text),                  # Longest text
        ),
    )


def tier1_exact_url_dedup(
    mentions: List[CleanedMention],
) -> Tuple[List[CleanedMention], dict]:
    """
    Tier 1: Group by exact URL.

    Special handling for Play Store / review URLs where multiple reviews
    share the same app URL — these are compared by text content, not just URL.
    """
    audit = {"exact_duplicates_found": 0, "groups": []}

    # Group by URL
    url_groups: Dict[str, List[CleanedMention]] = defaultdict(list)
    for m in mentions:
        url_groups[m.url.strip()].append(m)

    result: List[CleanedMention] = []
    review_urls = {"play.google.com", "apps.apple.com", "mouthshut.com"}

    for url, group in url_groups.items():
        if len(group) == 1:
            result.append(group[0])
            continue

        # Check if this is a review platform (multiple reviews = different content)
        is_review_url = any(domain in url for domain in review_urls)

        if is_review_url:
            # For review platforms, compare text content — keep unique texts
            seen_texts: Set[str] = set()
            for m in group:
                # Normalize text for comparison
                normalized = m.combined_text.lower().strip()[:200]
                if normalized not in seen_texts:
                    seen_texts.add(normalized)
                    result.append(m)
                else:
                    m.is_duplicate = True
                    m.duplicate_method = "exact_url_same_text"
                    m.duplicate_group_id = str(uuid.uuid4())
                    result.append(m)
                    audit["exact_duplicates_found"] += 1
        else:
            # Non-review URLs: keep best from group, mark others
            group_id = str(uuid.uuid4())
            primary = _select_primary(group)

            for m in group:
                if m.id == primary.id:
                    result.append(m)
                else:
                    m.is_duplicate = True
                    m.duplicate_method = "exact_url"
                    m.duplicate_group_id = group_id
                    result.append(m)
                    audit["exact_duplicates_found"] += 1

            if len(group) > 1:
                audit["groups"].append({
                    "url": url[:100],
                    "count": len(group),
                    "kept": primary.id,
                })

    logger.info(f"Tier 1 (exact URL): {audit['exact_duplicates_found']} duplicates found")
    return result, audit


def tier2_fuzzy_dedup(
    mentions: List[CleanedMention],
    threshold: float | None = None,
) -> Tuple[List[CleanedMention], dict]:
    """
    Tier 2: Fuzzy text matching using RapidFuzz.

    Only compares non-duplicate mentions from Tier 1.
    """
    if not _RAPIDFUZZ_AVAILABLE:
        logger.warning("rapidfuzz not installed, skipping fuzzy dedup")
        return mentions, {"fuzzy_duplicates_found": 0, "skipped": True}

    threshold = threshold or settings.FUZZY_DEDUP_THRESHOLD
    audit = {"fuzzy_duplicates_found": 0, "pairs": []}

    # Only check non-duplicates
    active = [m for m in mentions if not m.is_duplicate]
    already_marked: Set[str] = set()

    for i in range(len(active)):
        if active[i].id in already_marked:
            continue

        for j in range(i + 1, len(active)):
            if active[j].id in already_marked:
                continue

            # Compare combined text
            score = _rapidfuzz_fuzz.token_sort_ratio(
                active[i].combined_text[:500],
                active[j].combined_text[:500],
            ) / 100.0

            if score >= threshold:
                group_id = active[i].duplicate_group_id or str(uuid.uuid4())

                # Keep the one with higher reach / quality
                primary = _select_primary([active[i], active[j]])
                duplicate = active[j] if primary.id == active[i].id else active[i]

                duplicate.is_duplicate = True
                duplicate.duplicate_method = "fuzzy"
                duplicate.duplicate_group_id = group_id
                already_marked.add(duplicate.id)

                audit["fuzzy_duplicates_found"] += 1
                audit["pairs"].append({
                    "primary": primary.id,
                    "duplicate": duplicate.id,
                    "score": round(score, 3),
                })

    logger.info(f"Tier 2 (fuzzy): {audit['fuzzy_duplicates_found']} duplicates found")
    return mentions, audit


def tier3_semantic_dedup(
    mentions: List[CleanedMention],
    threshold: float | None = None,
) -> Tuple[List[CleanedMention], dict]:
    """
    Tier 3: Semantic similarity using sentence-transformers.

    Catches paraphrased / syndicated content (e.g., same article on
    DailyHunt, MSN, newspoint).
    """
    if not _SENTENCE_TRANSFORMERS_AVAILABLE:
        logger.warning("sentence-transformers not installed, skipping semantic dedup")
        return mentions, {"semantic_duplicates_found": 0, "skipped": True}

    threshold = threshold or settings.SEMANTIC_DEDUP_THRESHOLD
    audit = {"semantic_duplicates_found": 0, "pairs": []}

    # Only check non-duplicates
    active = [m for m in mentions if not m.is_duplicate]

    if len(active) < 2:
        return mentions, audit

    # Encode texts
    logger.info(f"Encoding {len(active)} texts for semantic dedup...")
    model = SentenceTransformer(settings.EMBEDDING_MODEL)
    texts = [m.combined_text[:512] for m in active]
    embeddings = model.encode(texts, show_progress_bar=False)

    # Compute pairwise cosine similarity
    already_marked: Set[str] = set()
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1  # Avoid division by zero
    normalized = embeddings / norms

    for i in range(len(active)):
        if active[i].id in already_marked:
            continue

        for j in range(i + 1, len(active)):
            if active[j].id in already_marked:
                continue

            similarity = float(np.dot(normalized[i], normalized[j]))

            if similarity >= threshold:
                group_id = active[i].duplicate_group_id or str(uuid.uuid4())

                primary = _select_primary([active[i], active[j]])
                duplicate = active[j] if primary.id == active[i].id else active[i]

                duplicate.is_duplicate = True
                duplicate.duplicate_method = "semantic"
                duplicate.duplicate_group_id = group_id
                already_marked.add(duplicate.id)

                audit["semantic_duplicates_found"] += 1
                audit["pairs"].append({
                    "primary": primary.id,
                    "duplicate": duplicate.id,
                    "similarity": round(similarity, 4),
                })

    logger.info(f"Tier 3 (semantic): {audit['semantic_duplicates_found']} duplicates found")
    return mentions, audit


def deduplicate(
    mentions: List[CleanedMention],
) -> Tuple[List[CleanedMention], dict]:
    """
    Run full 3-tier deduplication pipeline.

    Returns all mentions (with is_duplicate flags set), NOT just unique ones.
    This preserves the full audit trail.
    """
    full_audit = {}

    # Tier 1: Exact URL
    mentions, audit1 = tier1_exact_url_dedup(mentions)
    full_audit["tier1_exact_url"] = audit1

    # Tier 2: Fuzzy text
    mentions, audit2 = tier2_fuzzy_dedup(mentions)
    full_audit["tier2_fuzzy"] = audit2

    # Tier 3: Semantic
    mentions, audit3 = tier3_semantic_dedup(mentions)
    full_audit["tier3_semantic"] = audit3

    # Summary
    total_dupes = sum(1 for m in mentions if m.is_duplicate)
    total_unique = sum(1 for m in mentions if not m.is_duplicate)
    full_audit["summary"] = {
        "total_records": len(mentions),
        "unique_records": total_unique,
        "duplicate_records": total_dupes,
    }

    logger.info(
        f"Deduplication complete: {total_unique} unique, "
        f"{total_dupes} duplicates out of {len(mentions)} total"
    )

    return mentions, full_audit
