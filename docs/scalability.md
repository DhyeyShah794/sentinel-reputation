# Scalability Proposal: From 100 Mentions to 10M

## Executive Summary

Sentinel is designed with scalability in mind from day one. This document outlines the concrete architectural changes needed to scale from 100 digital mentions to 10 million while maintaining classification accuracy, sentiment analysis quality, and sub-second dashboard response times.

---

## 1. Current Architecture (100 Mentions)

| Component | Current | Limitation at Scale |
|-----------|---------|-------------------|
| **Storage** | JSON files on disk | No querying, no indexing |
| **Processing** | Sequential, in-memory | 100 mentions: ~5 min. 10M would take years. |
| **LLM Calls** | 1 per mention, sequential | 10M × $0.001 = $10,000; rate limited |
| **Embeddings** | Computed per run | Recomputed unnecessarily |
| **API** | Single process, loads all data | Memory exhaustion at scale |

---

## 2. Target Architecture (10M Mentions)

### 2.1 Data Layer

```
PostgreSQL (mentions, scores, audits)
  + pgvector extension (semantic search, dedup)
  + TimescaleDB (time-series analytics)
Redis (caching, rate limiting, session)
```

**Why PostgreSQL over MongoDB?**
- Structured reputation data benefits from relational integrity
- pgvector provides native vector similarity search (replaces in-memory dedup)
- Rich SQL aggregations for dashboard analytics
- JSONB columns for flexible metadata

### 2.2 Processing Pipeline

```
                    ┌────────────────────┐
  Raw Mentions ──→  │  Apache Kafka      │  ──→  Worker Pool
                    │  (Event Stream)    │       (Celery + Redis)
                    └────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │                   │
              Embedding-First      LLM Validation
              Classification       (Gemini Batch API)
              (~60% resolved)      (~40% remaining)
                    │                   │
                    └─────────┬─────────┘
                              │
                    ┌─────────┴─────────┐
                    │  PostgreSQL        │
                    │  + pgvector        │
                    └───────────────────┘
```

**Key changes:**
1. **Kafka ingestion**: Mentions arrive as events, decoupled from processing
2. **Celery workers**: Parallel processing with horizontal scaling
3. **Embedding-first**: ~60% of mentions classified without any LLM call
4. **Gemini Batch API**: Process remaining 40% in efficient batches
5. **Incremental processing**: Only new/changed mentions are processed

### 2.3 Cost Projection

| Cost Component | 100 Mentions | 10M Mentions/month |
|----------------|-------------|-------------------|
| **LLM (Gemini Flash)** | ~$0.10 | ~$4,000 (40% of 10M × $0.001) |
| **Embeddings** | ~$0 (local) | ~$200 (GPU instance) |
| **PostgreSQL** | N/A | ~$300 (managed, 500GB) |
| **Kafka + Workers** | N/A | ~$500 (managed Kafka + 4 workers) |
| **CDN + Frontend** | ~$0 | ~$50 (Vercel Pro) |
| **Total** | ~$0.10 | **~$5,050/month** |

Compare: Pure GPT-4o approach would cost **~$50,000/month** for 10M mentions.

### 2.4 Performance Targets

| Metric | Current (100) | Target (10M) |
|--------|--------------|-------------|
| **Pipeline throughput** | ~20 mentions/min | ~50,000 mentions/min |
| **Dashboard load time** | <1s (JSON) | <500ms (cached aggregates) |
| **Search latency** | N/A (in-memory) | <200ms (pgvector + full-text) |
| **Classification accuracy** | ~85% (est.) | ≥85% (same model, more training data) |

---

## 3. Dashboard Scalability

### Pre-computed Aggregations

At 10M mentions, we cannot compute analytics on every page load. Instead:

1. **Materialized views** in PostgreSQL for common aggregations (sentiment by driver, monthly trends)
2. **Redis cache** with 5-minute TTL for dashboard data
3. **Incremental updates** — when new mentions arrive, update aggregates, don't recompute

### Search

Replace in-memory filtering with:
- **PostgreSQL full-text search** (GIN indexes) for keyword search
- **pgvector similarity search** for semantic queries ("find mentions similar to this complaint")

---

## 4. Multi-Brand Support

The current system analyzes one brand. At scale, Sentinel should support multiple brands simultaneously:

```sql
-- Each brand gets its own configuration
CREATE TABLE brands (
  id UUID PRIMARY KEY,
  name TEXT,
  aliases TEXT[],
  driver_weights JSONB,  -- Custom weights per brand
  classification_prompts JSONB  -- Brand-specific prompt tuning
);

-- Mentions are partitioned by brand
CREATE TABLE mentions (
  id UUID,
  brand_id UUID REFERENCES brands(id),
  ...
) PARTITION BY HASH (brand_id);
```

---

## 5. Real-time Monitoring

For enterprise deployment, add:

1. **Webhook ingestion**: Real-time mention feeds from Meltwater/Brandwatch
2. **Stream processing**: Kafka Streams for real-time classification
3. **Alert system**: Slack/email alerts when risk level crosses threshold
4. **Live dashboard**: WebSocket updates for real-time mention feed

---

## 6. Migration Path

| Phase | Timeline | Changes |
|-------|----------|---------|
| **Phase 1** | Week 1-2 | PostgreSQL migration, pgvector dedup |
| **Phase 2** | Week 3-4 | Celery workers, parallel processing |
| **Phase 3** | Week 5-6 | Kafka ingestion, incremental processing |
| **Phase 4** | Week 7-8 | Dashboard caching, pre-computed aggregates |
| **Phase 5** | Week 9-10 | Multi-brand support, real-time alerts |

This is a 10-week migration path that can be executed by a 2-person engineering team.
