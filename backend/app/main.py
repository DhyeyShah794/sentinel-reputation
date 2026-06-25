"""
FastAPI application — Sentinel Reputation Intelligence API.

Serves processed data from the pipeline to the Next.js dashboard.
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.pipeline.orchestrator import run_pipeline

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Data Store (loaded from pipeline outputs)
# ──────────────────────────────────────────────

_data_store: Dict[str, Any] = {
    "mentions": [],
    "reputation_score": None,
    "themes": [],
    "opportunities": [],
    "executive_summary": None,
    "pipeline_audit": None,
    "loaded": False,
}


def _load_data():
    """Load pipeline outputs from disk."""
    output_dir = settings.DATA_OUTPUTS_DIR

    files = {
        "mentions": "processed_mentions.json",
        "reputation_score": "reputation_score.json",
        "themes": "themes.json",
        "opportunities": "opportunities.json",
        "executive_summary": "executive_summary.json",
        "pipeline_audit": "pipeline_audit.json",
    }

    for key, filename in files.items():
        filepath = output_dir / filename
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                _data_store[key] = json.load(f)
            logger.info(f"Loaded {key} from {filepath}")
        else:
            logger.warning(f"File not found: {filepath}")

    _data_store["loaded"] = True
    mention_count = len(_data_store.get("mentions", []))
    logger.info(f"Data store loaded: {mention_count} mentions")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load data on startup."""
    _load_data()
    yield


# ──────────────────────────────────────────────
# App
# ──────────────────────────────────────────────

app = FastAPI(
    title="Sentinel — Reputation Intelligence API",
    description="API for the Sentinel Reputation Intelligence Platform. Built for Eminence Strategy Consulting.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────
# Health
# ──────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {
        "status": "healthy",
        "data_loaded": _data_store["loaded"],
        "mentions_count": len(_data_store.get("mentions", [])),
    }


# ──────────────────────────────────────────────
# Mentions
# ──────────────────────────────────────────────

@app.get("/api/mentions")
async def list_mentions(
    driver: Optional[str] = None,
    sub_driver: Optional[str] = None,
    sentiment: Optional[str] = None,
    source_type: Optional[str] = None,
    source_name: Optional[str] = None,
    risk_level: Optional[str] = None,
    theme: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = "impact_score",
    sort_order: str = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List mentions with filtering, search, sorting, and pagination."""
    mentions = _data_store.get("mentions", [])

    # Filtering
    if driver:
        mentions = [m for m in mentions if m.get("driver") == driver]
    if sub_driver:
        mentions = [m for m in mentions if m.get("sub_driver") == sub_driver]
    if sentiment:
        mentions = [m for m in mentions if m.get("sentiment") == sentiment]
    if source_type:
        mentions = [m for m in mentions if m.get("source_type") == source_type]
    if source_name:
        mentions = [m for m in mentions if m.get("source_name") == source_name]
    if risk_level:
        mentions = [m for m in mentions if m.get("risk_level") == risk_level]
    if theme:
        mentions = [
            m for m in mentions
            if theme.lower() in " ".join(m.get("themes", [])).lower()
        ]

    # Search
    if search:
        search_lower = search.lower()
        mentions = [
            m for m in mentions
            if search_lower in m.get("combined_text", "").lower()
            or search_lower in m.get("title", "").lower()
            or search_lower in m.get("source_name", "").lower()
        ]

    # Sorting
    reverse = sort_order == "desc"
    if sort_by == "date":
        mentions.sort(key=lambda m: m.get("date") or "", reverse=reverse)
    else:
        mentions.sort(key=lambda m: m.get(sort_by) or 0, reverse=reverse)

    # Pagination
    total = len(mentions)
    start = (page - 1) * page_size
    end = start + page_size
    paginated = mentions[start:end]

    return {
        "data": paginated,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@app.get("/api/mentions/{mention_id}")
async def get_mention(mention_id: str):
    """Get a single mention by ID."""
    mentions = _data_store.get("mentions", [])
    for m in mentions:
        if m.get("id") == mention_id:
            return m
    raise HTTPException(status_code=404, detail="Mention not found")


# ──────────────────────────────────────────────
# Analytics
# ──────────────────────────────────────────────

@app.get("/api/analytics/overview")
async def get_overview():
    """Dashboard overview KPIs."""
    mentions = _data_store.get("mentions", [])
    rep_score = _data_store.get("reputation_score", {})

    if not mentions:
        return {"error": "No data available. Run the pipeline first."}

    # Sentiment distribution
    sentiment_dist = {"positive": 0, "neutral": 0, "negative": 0}
    for m in mentions:
        s = m.get("sentiment", "neutral")
        sentiment_dist[s] = sentiment_dist.get(s, 0) + 1

    # Driver distribution
    driver_dist = {}
    for m in mentions:
        d = m.get("driver", "Unclassified")
        driver_dist[d] = driver_dist.get(d, 0) + 1

    # Sub-driver distribution
    sub_driver_dist = {}
    for m in mentions:
        sd = m.get("sub_driver", "Unclassified")
        sub_driver_dist[sd] = sub_driver_dist.get(sd, 0) + 1

    # Source distribution
    source_dist = {}
    for m in mentions:
        s = m.get("source_name", "Unknown")
        source_dist[s] = source_dist.get(s, 0) + 1

    # Source type distribution
    source_type_dist = {}
    for m in mentions:
        st = m.get("source_type", "unknown")
        source_type_dist[st] = source_type_dist.get(st, 0) + 1

    # Risk distribution
    risk_dist = {"low": 0, "medium": 0, "high": 0}
    for m in mentions:
        r = m.get("risk_level", "low")
        risk_dist[r] = risk_dist.get(r, 0) + 1

    # Timeline (mentions by month)
    timeline = {}
    for m in mentions:
        date = m.get("date")
        if date:
            month = date[:7]  # "YYYY-MM"
            timeline[month] = timeline.get(month, 0) + 1
    mention_trend = [
        {"date": k, "count": v}
        for k, v in sorted(timeline.items())
    ]

    return {
        "total_mentions": len(mentions),
        "reputation_score": rep_score.get("overall_score", 0) if rep_score else 0,
        "sentiment_distribution": sentiment_dist,
        "driver_distribution": driver_dist,
        "sub_driver_distribution": sub_driver_dist,
        "source_distribution": source_dist,
        "source_type_distribution": source_type_dist,
        "risk_summary": risk_dist,
        "mention_trend": mention_trend,
    }


@app.get("/api/analytics/sentiment")
async def get_sentiment_analytics():
    """Detailed sentiment analytics."""
    mentions = _data_store.get("mentions", [])

    # Sentiment by driver
    by_driver = {}
    for m in mentions:
        d = m.get("driver", "Unclassified")
        s = m.get("sentiment", "neutral")
        if d not in by_driver:
            by_driver[d] = {"positive": 0, "neutral": 0, "negative": 0}
        by_driver[d][s] = by_driver[d].get(s, 0) + 1

    # Sentiment by source type
    by_source = {}
    for m in mentions:
        st = m.get("source_type", "unknown")
        s = m.get("sentiment", "neutral")
        if st not in by_source:
            by_source[st] = {"positive": 0, "neutral": 0, "negative": 0}
        by_source[st][s] = by_source[st].get(s, 0) + 1

    # Agreement rate
    total = len(mentions)
    agreements = sum(1 for m in mentions if m.get("sentiment_agreement", True))
    disagreements = total - agreements

    return {
        "by_driver": by_driver,
        "by_source_type": by_source,
        "agreement_rate": agreements / total if total > 0 else 1.0,
        "total_agreements": agreements,
        "total_disagreements": disagreements,
    }


@app.get("/api/analytics/drivers")
async def get_driver_analytics():
    """Driver and sub-driver distribution analytics."""
    mentions = _data_store.get("mentions", [])
    rep_score = _data_store.get("reputation_score", {})

    # Build detailed driver data
    driver_data = {}
    for m in mentions:
        d = m.get("driver", "Unclassified")
        sd = m.get("sub_driver", "Unclassified")
        s = m.get("sentiment", "neutral")
        impact = m.get("impact_score", 0)

        if d not in driver_data:
            driver_data[d] = {
                "count": 0,
                "sentiment": {"positive": 0, "neutral": 0, "negative": 0},
                "sub_drivers": {},
                "avg_impact": 0,
                "total_impact": 0,
            }

        driver_data[d]["count"] += 1
        driver_data[d]["sentiment"][s] += 1
        driver_data[d]["total_impact"] += impact

        if sd not in driver_data[d]["sub_drivers"]:
            driver_data[d]["sub_drivers"][sd] = {
                "count": 0,
                "sentiment": {"positive": 0, "neutral": 0, "negative": 0},
            }
        driver_data[d]["sub_drivers"][sd]["count"] += 1
        driver_data[d]["sub_drivers"][sd]["sentiment"][s] += 1

    # Compute averages
    for d, data in driver_data.items():
        if data["count"] > 0:
            data["avg_impact"] = round(data["total_impact"] / data["count"], 3)

    return {
        "drivers": driver_data,
        "driver_scores": rep_score.get("driver_scores", []) if rep_score else [],
    }


@app.get("/api/analytics/sources")
async def get_source_analytics():
    """Source breakdown analytics."""
    mentions = _data_store.get("mentions", [])

    source_data = {}
    for m in mentions:
        src = m.get("source_name", "Unknown")
        st = m.get("source_type", "unknown")
        s = m.get("sentiment", "neutral")
        reach = m.get("reach", 0)

        if src not in source_data:
            source_data[src] = {
                "source_type": st,
                "count": 0,
                "sentiment": {"positive": 0, "neutral": 0, "negative": 0},
                "total_reach": 0,
                "avg_reach": 0,
            }

        source_data[src]["count"] += 1
        source_data[src]["sentiment"][s] += 1
        source_data[src]["total_reach"] += reach

    # Compute averages and sort
    sources_list = []
    for src, data in source_data.items():
        data["source_name"] = src
        if data["count"] > 0:
            data["avg_reach"] = data["total_reach"] // data["count"]
        sources_list.append(data)

    sources_list.sort(key=lambda s: s["count"], reverse=True)

    return {"sources": sources_list}


@app.get("/api/analytics/timeline")
async def get_timeline():
    """Time-series analytics."""
    mentions = _data_store.get("mentions", [])

    # Monthly breakdown
    monthly = {}
    for m in mentions:
        date = m.get("date")
        if not date:
            continue

        month = date[:7]
        s = m.get("sentiment", "neutral")

        if month not in monthly:
            monthly[month] = {
                "month": month,
                "total": 0,
                "positive": 0,
                "neutral": 0,
                "negative": 0,
            }

        monthly[month]["total"] += 1
        monthly[month][s] += 1

    timeline = sorted(monthly.values(), key=lambda x: x["month"])

    return {"timeline": timeline}


# ──────────────────────────────────────────────
# Intelligence
# ──────────────────────────────────────────────

@app.get("/api/intelligence/score")
async def get_reputation_score():
    """Reputation score with full breakdown."""
    score = _data_store.get("reputation_score")
    if not score:
        raise HTTPException(status_code=404, detail="Score not computed yet")
    return score


@app.get("/api/intelligence/themes")
async def get_themes():
    """Extracted themes."""
    return {"themes": _data_store.get("themes", [])}


@app.get("/api/intelligence/risks")
async def get_risks():
    """Risk analysis."""
    mentions = _data_store.get("mentions", [])
    risks = [
        {
            "mention_id": m.get("id"),
            "title": m.get("title"),
            "risk_level": m.get("risk_level"),
            "risk_type": m.get("risk_type"),
            "risk_signal": m.get("risk_signal"),
            "source_name": m.get("source_name"),
            "sentiment": m.get("sentiment"),
            "impact_score": m.get("impact_score"),
        }
        for m in mentions
        if m.get("risk_level") in ("medium", "high")
    ]
    risks.sort(key=lambda r: {"high": 2, "medium": 1}.get(r["risk_level"], 0), reverse=True)
    return {"risks": risks, "total": len(risks)}


@app.get("/api/intelligence/opportunities")
async def get_opportunities():
    """Amplification opportunities."""
    return {"opportunities": _data_store.get("opportunities", [])}


@app.get("/api/intelligence/summary")
async def get_executive_summary():
    """Executive summary."""
    summary = _data_store.get("executive_summary")
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not generated yet")
    return summary


@app.get("/api/intelligence/command-center")
async def get_command_center():
    """Command center hero data — aggregates key intelligence."""
    mentions = _data_store.get("mentions", [])
    rep_score = _data_store.get("reputation_score", {})
    themes = _data_store.get("themes", [])
    summary = _data_store.get("executive_summary", {})

    if not mentions:
        raise HTTPException(status_code=404, detail="No data available")

    # Biggest positive driver
    biggest_positive = None
    biggest_negative = None

    driver_scores = rep_score.get("driver_scores", [])
    if driver_scores:
        scored = [ds for ds in driver_scores if ds.get("mention_count", 0) > 0]
        if scored:
            best = max(scored, key=lambda d: d.get("score", 0))
            worst = min(scored, key=lambda d: d.get("score", 0))

            # Get representative mention for best driver
            best_mentions = [
                m for m in mentions
                if m.get("driver") == best.get("driver")
                and m.get("sentiment") == "positive"
            ]
            best_mentions.sort(key=lambda m: m.get("impact_score", 0), reverse=True)

            biggest_positive = {
                "driver": best.get("driver"),
                "score": best.get("score"),
                "mention_count": best.get("positive_count", best.get("mention_count")),
                "representative": best_mentions[0].get("title", "") if best_mentions else "",
            }

            # Representative mention for worst driver
            worst_mentions = [
                m for m in mentions
                if m.get("driver") == worst.get("driver")
                and m.get("sentiment") == "negative"
            ]
            worst_mentions.sort(key=lambda m: m.get("impact_score", 0), reverse=True)

            biggest_negative = {
                "driver": worst.get("driver"),
                "score": worst.get("score"),
                "mention_count": worst.get("negative_count", worst.get("mention_count")),
                "representative": worst_mentions[0].get("title", "") if worst_mentions else "",
            }

    # Emerging theme
    emerging_theme = themes[0] if themes else None

    # Primary risk
    high_risk = [
        m for m in mentions if m.get("risk_level") == "high"
    ]
    medium_risk = [
        m for m in mentions if m.get("risk_level") == "medium"
    ]
    primary_risk_mentions = high_risk or medium_risk
    primary_risk = None
    if primary_risk_mentions:
        pr = max(primary_risk_mentions, key=lambda m: m.get("impact_score", 0))
        primary_risk = {
            "title": pr.get("title"),
            "risk_level": pr.get("risk_level"),
            "risk_type": pr.get("risk_type"),
            "risk_signal": pr.get("risk_signal"),
        }

    # Score waterfall
    waterfall = []
    for ds in driver_scores:
        if ds.get("mention_count", 0) > 0:
            sub_scores = ds.get("sub_scores", {})
            for sd_name, sd_score in sub_scores.items():
                contribution = sd_score - 50  # Deviation from neutral
                waterfall.append({
                    "name": sd_name,
                    "driver": ds.get("driver"),
                    "value": round(contribution, 1),
                    "type": "positive" if contribution > 0 else "negative",
                })

    waterfall.sort(key=lambda w: abs(w["value"]), reverse=True)

    return {
        "reputation_score": rep_score.get("overall_score", 0),
        "driver_scores": driver_scores,
        "biggest_positive_driver": biggest_positive,
        "biggest_negative_driver": biggest_negative,
        "emerging_theme": emerging_theme,
        "primary_risk": primary_risk,
        "recommended_actions": summary.get("recommended_actions", []) if summary else [],
        "score_waterfall": waterfall[:8],
    }


# ──────────────────────────────────────────────
# Pipeline trigger
# ──────────────────────────────────────────────

@app.post("/api/pipeline/run")
async def trigger_pipeline():
    """Trigger a full pipeline run (synchronous for demo)."""
    try:
        result = run_pipeline()
        _load_data()  # Reload outputs
        return {
            "status": "complete",
            "active_mentions": len(result.active_mentions),
            "reputation_score": result.reputation_score.overall_score if result.reputation_score else None,
            "duration_seconds": result.duration_seconds,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/pipeline/status")
async def pipeline_status():
    """Check if pipeline outputs exist."""
    output_dir = settings.DATA_OUTPUTS_DIR
    files_exist = {
        "processed_mentions": (output_dir / "processed_mentions.json").exists(),
        "reputation_score": (output_dir / "reputation_score.json").exists(),
        "themes": (output_dir / "themes.json").exists(),
        "executive_summary": (output_dir / "executive_summary.json").exists(),
    }
    return {
        "pipeline_ready": all(files_exist.values()),
        "files": files_exist,
    }
