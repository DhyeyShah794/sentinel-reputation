"""
Classification engine — Hybrid embedding + LLM classification.

Stage 1: Embed mention text → compare to sub-driver description embeddings → top-3 candidates
Stage 2: If high confidence, accept. Otherwise, send to the configured LLM for validation.

Inputs:  List[CleanedMention] (relevant, non-duplicate)
Outputs: Same list with classification fields populated
"""

from __future__ import annotations

import logging
from typing import Dict, List, Tuple

import numpy as np

from app.config import settings
from app.models.mention import (
    CleanedMention,
    SUBDRIVER_TO_DRIVER,
    EmbeddingCandidate,
)
from app.prompts.loader import load_prompt
from app.services.embeddings import encode_texts, find_top_k
from app.services.llm import call_llm_batch_cached
from app.services.llm.schemas import ClassificationResult

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Sub-driver reference descriptions for embedding
# ──────────────────────────────────────────────

SUBDRIVER_DESCRIPTIONS: Dict[str, dict] = {
    "Thought Leadership": {
        "driver": "Brand Perception",
        "description": (
            "CXO and expert commentary, market outlook statements, industry viewpoints, "
            "fund manager interviews, investment philosophy discussions, economic analysis "
            "by company leadership, expert opinions on market trends, advisory statements. "
            "Examples: Fund manager's view on rate cuts, CIO interview on market conditions, "
            "market outlook op-ed, investment strategy discussion, asset allocation advice."
        ),
    },
    "Product Strategy": {
        "driver": "Brand Perception",
        "description": (
            "Product launches, new fund offers (NFO), fund positioning, pricing changes, "
            "expense ratio revisions, new SIP plans, festive offers, scheme modifications, "
            "product innovation, investment product features, fund category strategy. "
            "Examples: New NFO launch, revised expense ratio, new SIP plan, product segment "
            "like iSIF, index fund launch, thematic fund offering."
        ),
    },
    "Brand Visibility & Marketing": {
        "driver": "Brand Perception",
        "description": (
            "Advertising campaigns, sponsorships, brand ambassadors, awareness initiatives, "
            "marketing activities, brand recognition, media presence, PR activities, awards, "
            "brand partnerships, corporate events, investor awareness programs. "
            "Examples: Ad campaign, cricket sponsorship, brand ambassador announcement, "
            "investor awareness event, industry award."
        ),
    },
    "Product & Service Quality": {
        "driver": "User Experience",
        "description": (
            "Fund performance, scheme returns, NAV performance, benchmark comparison, "
            "product reliability, investment returns, fund rating, portfolio quality, "
            "risk-adjusted returns, historical performance, SIP returns. "
            "Examples: Fund returns vs benchmark, long-term SIP growth, scheme performance "
            "review, fund rating analysis, portfolio return comparison."
        ),
    },
    "Customer Support & Complaint Resolution": {
        "driver": "User Experience",
        "description": (
            "Customer service responsiveness, complaint handling, issue resolution speed, "
            "KYC process experience, redemption delays, transaction problems, helpline "
            "quality, grievance redressal, service recovery, support accessibility. "
            "Examples: Delayed redemption complaint, slow KYC process, quick complaint "
            "resolution, unresponsive helpline, service center experience."
        ),
    },
    "Digital & Omnichannel Experience": {
        "driver": "User Experience",
        "description": (
            "Mobile app experience, website usability, digital onboarding, app stability, "
            "transaction interface, login issues, app crashes, UI/UX quality, digital "
            "platform reliability, online transaction experience, app features. "
            "Examples: App crash during market hours, smooth digital onboarding, website "
            "downtime, confusing transaction screen, app update issues, login failures."
        ),
    },
    "Regulatory Compliance & Ethical Governance": {
        "driver": "Responsible Business Practices",
        "description": (
            "SEBI regulations, compliance actions, regulatory penalties, disclosure practices, "
            "corporate governance, ethical business conduct, mis-selling allegations, "
            "transparency initiatives, regulatory filings, audit observations. "
            "Examples: SEBI penalty, disclosure lapse, mis-selling allegation, transparent "
            "governance initiative, regulatory compliance achievement."
        ),
    },
    "Social Impact & Community (CSR)": {
        "driver": "Responsible Business Practices",
        "description": (
            "Corporate social responsibility, community engagement, financial literacy "
            "programs, charitable activities, sustainability initiatives, social welfare, "
            "education programs, rural outreach, women empowerment initiatives. "
            "Examples: Financial literacy drive, donation or relief activity, women investor "
            "programme, rural outreach initiative, environmental sustainability effort."
        ),
    },
}

# Pre-computed reference embeddings (cached in memory)
_ref_embeddings = None
_ref_labels = None


def _get_reference_embeddings():
    global _ref_embeddings, _ref_labels
    if _ref_embeddings is None:
        _ref_labels = list(SUBDRIVER_DESCRIPTIONS.keys())
        descriptions = [SUBDRIVER_DESCRIPTIONS[label]["description"] for label in _ref_labels]
        _ref_embeddings = encode_texts(descriptions)
        logger.info("Computed reference embeddings for %d sub-drivers", len(_ref_labels))
    return _ref_embeddings, _ref_labels


def classify_mentions(
    mentions: List[CleanedMention],
) -> Tuple[List[CleanedMention], dict]:
    """
    Classify each relevant, non-duplicate mention using hybrid approach.

    Stage 1: Embedding similarity → top-3 candidates
    Stage 2: If confident enough, accept. Otherwise, validate with LLM.
    """
    audit = {
        "total_classified": 0,
        "embedding_only": 0,
        "llm_validated": 0,
        "errors": 0,
        "cache_hits": 0,
        "cache_misses": 0,
        "batch_jobs_submitted": 0,
        "batch_requests_sent": 0,
        "driver_distribution": {},
        "sub_driver_distribution": {},
    }

    ref_embeddings, ref_labels = _get_reference_embeddings()
    active = [m for m in mentions if not m.is_duplicate and m.is_relevant]
    logger.info("Classifying %d active mentions…", len(active))

    texts = [m.combined_text[:512] for m in active]
    mention_embeddings = encode_texts(texts)

    llm_pending: list[tuple[CleanedMention, list]] = []
    batch_requests: list[tuple[str, str]] = []

    for i, mention in enumerate(active):
        top_k = find_top_k(mention_embeddings[i], ref_embeddings, ref_labels, k=3)
        top_score = top_k[0]["similarity"]
        gap = top_score - top_k[1]["similarity"] if len(top_k) > 1 else 1.0

        if (
            top_score >= settings.CLASSIFICATION_HIGH_CONFIDENCE
            and gap >= settings.CLASSIFICATION_CONFIDENCE_GAP
        ):
            sub_driver = top_k[0]["label"]
            driver = SUBDRIVER_DESCRIPTIONS[sub_driver]["driver"]

            mention.driver = driver
            mention.sub_driver = sub_driver
            mention.classification_confidence = round(top_score, 3)
            mention.classification_rationale = (
                f"High-confidence embedding match (similarity: {top_score:.3f}, "
                f"gap to next: {gap:.3f})"
            )
            mention.classification_method = "embedding_only"
            audit["embedding_only"] += 1
        else:
            candidates_str = "\n".join(
                f"  - {c['label']} (similarity: {c['similarity']:.3f})" for c in top_k
            )
            prompt = load_prompt(
                "classify",
                brand_name=settings.BRAND_NAME,
                title=mention.title,
                source=mention.source_name,
                source_type=mention.source_type,
                text=mention.combined_text[:1200],
                candidates=candidates_str,
            )
            llm_pending.append((mention, top_k))
            batch_requests.append((str(mention.row_number), prompt))

    llm_results: dict[str, tuple] = {}
    if batch_requests:
        logger.info(
            "Submitting %d classification requests to LLM provider", len(batch_requests)
        )
        llm_results, batch_stats = call_llm_batch_cached(
            "classification",
            batch_requests,
            model=settings.model_for_stage("classify"),
        )
        audit["cache_hits"] = batch_stats.cache_hits
        audit["cache_misses"] = batch_stats.cache_misses
        audit["batch_jobs_submitted"] = batch_stats.batch_jobs_submitted
        audit["batch_requests_sent"] = batch_stats.batch_requests_sent

    for mention, top_k in llm_pending:
        try:
            key = str(mention.row_number)
            result, _from_cache = llm_results.get(key, (None, False))
            top_score = top_k[0]["similarity"]

            if isinstance(result, dict) and "driver" in result:
                validated = ClassificationResult(**result)
                mention.driver = validated.driver
                mention.sub_driver = validated.sub_driver
                mention.classification_confidence = validated.confidence
                mention.classification_rationale = validated.rationale
                mention.classification_method = "hybrid_llm_validated"
            else:
                sub_driver = top_k[0]["label"]
                mention.driver = SUBDRIVER_DESCRIPTIONS[sub_driver]["driver"]
                mention.sub_driver = sub_driver
                mention.classification_confidence = round(top_score, 3)
                mention.classification_rationale = "LLM fallback to embedding top pick"
                mention.classification_method = "embedding_fallback"

            audit["llm_validated"] += 1

        except Exception as exc:
            logger.error("Classification failed for mention %s: %s", mention.id, exc)
            mention.driver = "Brand Perception"
            mention.sub_driver = "Thought Leadership"
            mention.classification_confidence = 0.3
            mention.classification_rationale = f"Error fallback: {str(exc)[:100]}"
            mention.classification_method = "error_fallback"
            audit["errors"] += 1

    for mention in active:
        d = mention.driver or "Unknown"
        sd = mention.sub_driver or "Unknown"
        audit["driver_distribution"][d] = audit["driver_distribution"].get(d, 0) + 1
        audit["sub_driver_distribution"][sd] = audit["sub_driver_distribution"].get(sd, 0) + 1
        audit["total_classified"] += 1

    logger.info(
        "Classification complete: %d classified (%d embedding-only, %d LLM-validated, "
        "%d batch jobs)",
        audit["total_classified"],
        audit["embedding_only"],
        audit["llm_validated"],
        audit["batch_jobs_submitted"],
    )
    return mentions, audit
