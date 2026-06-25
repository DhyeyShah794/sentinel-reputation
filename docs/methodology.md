# Methodology Document: Classification & Sentiment Analysis Framework

## 1. Classification Methodology

### 1.1 Framework Design

Our classification system maps each digital mention to Eminence's three-tier reputation framework:

| Driver | Sub-Drivers |
|--------|------------|
| **Brand Perception** | Thought Leadership · Product Strategy · Brand Visibility & Marketing |
| **User Experience** | Product & Service Quality · Customer Support · Digital Experience |
| **Responsible Business** | Regulatory Compliance · Social Impact (CSR) |

### 1.2 Hybrid Approach: Why Not Pure LLM?

We use a **two-stage hybrid classification** that combines semantic embeddings with LLM validation:

**Stage 1 — Embedding Similarity (Cost: ~$0)**
- Each mention is encoded using `all-MiniLM-L6-v2` sentence-transformer
- Compared against 8 pre-computed sub-driver description embeddings via cosine similarity
- Top 3 candidates identified with similarity scores

**Stage 2 — LLM Validation**
- If top candidate has **confidence ≥ 0.75** and **gap to #2 ≥ 0.10**: Accept embedding result (no LLM call)
- Otherwise: Send mention + top-3 candidates to the configured LLM for contextual classification
- The LLM can override the embedding suggestion when context reveals the true intent

**Why this matters:**
- **Embedding-first gating** lets unambiguous mentions bypass the LLM entirely. The share that
  qualifies is corpus-dependent: on this short, nuanced 100-mention dataset the gate is conservative
  and most mentions are LLM-validated (see `backend/data/outputs/pipeline_audit.json`), whereas
  larger, more templated corpora resolve a large fraction at the embedding stage for free.
- **Audit trail**: Every classification has either similarity scores (Stage 1) or LLM rationale (Stage 2)
- **At scale (10M mentions)**: The same gate is what keeps LLM API spend bounded while maintaining accuracy

### 1.3 Sub-Driver Descriptions

Each sub-driver has a rich description (80-150 words) covering:
- Core topics and keywords
- Specific examples from the BFSI domain
- Edge cases and disambiguation cues

These descriptions serve as the "embedding anchors" that the model compares against.

### 1.4 Confidence Scoring

Every classification includes a confidence score (0.0–1.0):
- **≥ 0.8**: High confidence — clear, unambiguous match
- **0.6–0.8**: Moderate — correct but could fit multiple categories
- **< 0.6**: Low — ambiguous, review recommended

---

## 2. Sentiment Analysis Methodology

### 2.1 Beyond Simple Labels

Our sentiment engine doesn't just label mentions as positive/neutral/negative. For each mention, we produce:

| Output | Description |
|--------|-------------|
| **Sentiment** | Positive, Neutral, or Negative |
| **Confidence** | 0.0–1.0 certainty in the label |
| **Explanation** | 1-2 sentence rationale explaining what drives the sentiment |
| **Emotional Intensity** | Low / Medium / High |
| **Agreement** | Whether our analysis agrees with the original dataset label |

### 2.2 Brand-Centric Analysis

Critically, we analyze sentiment **toward the brand**, not general text sentiment:

> "Market conditions are deteriorating, but ICICI Prudential's defensive strategy is well-positioned"

A generic sentiment model would label this **negative** (due to "deteriorating"). Our brand-centric prompt correctly labels it **positive** — the brand is being praised for strategic foresight.

### 2.3 Agreement Tracking

We track agreement/disagreement with original labels because:
- It surfaces labeling errors in the source data
- It quantifies the value-add of AI re-analysis
- Disagreements are flagged with explanations for human review

---

## 3. Reputation Scoring

### 3.1 Score Formula

```
Overall_Score = Σ (Driver_Weight × Driver_Score)
```

**Driver Weights:**
- Brand Perception: 40%
- User Experience: 35%
- Responsible Business: 25%

**Per-Driver Score (0–100):**
```
Score = 50 (base)
      + positive_ratio × 40   (positive bonus)
      - negative_ratio × 50   (negative penalty — weighted heavier)
      + volume_bonus           (min(count/10, 5))
      + reach_bonus            (reach distribution adjustment)
```

### 3.2 Design Decisions

1. **Negative weighs more than positive**: A single viral complaint damages reputation more than a positive article builds it. This is well-established in reputation research.

2. **Base of 50, not 0**: A brand with zero mentions isn't "bad" — it's unknown. 50 represents neutral.

3. **Reach-weighted**: A positive mention in The Economic Times (reach: 5M) contributes more than a Play Store review (reach: 0).

---

## 4. Impact Scoring

Each mention gets an impact score (0.0–1.0) combining four factors:

```
Impact = 0.35 × Reach_norm + 0.20 × Source_quality + 0.25 × Sentiment_magnitude + 0.20 × Relevance
```

| Factor | Weight | Description |
|--------|--------|-------------|
| **Reach** | 35% | Log-normalized reach vs. max in corpus |
| **Source Quality** | 20% | News (0.9) > Professional (0.8) > Review (0.7) > Forum (0.6) > Aggregator (0.5) |
| **Sentiment Magnitude** | 25% | Strong positive/negative > neutral |
| **Relevance** | 20% | How directly this mention affects the brand |

---

## 5. Deduplication Strategy

### Three-Tier Approach

| Tier | Method | Catches |
|------|--------|---------|
| **Tier 1** | Exact URL match | Identical articles scraped twice |
| **Tier 2** | Fuzzy text (RapidFuzz, threshold: 85%) | Minor rewrites, typo variants |
| **Tier 3** | Semantic similarity (sentence-transformers, threshold: 92%) | Syndicated content across DailyHunt, MSN, newspoint |

### Special Case: Play Store Reviews
15 Play Store entries share the same app URL but are **different reviews**. We handle this by comparing text content for Play Store/App Store/Mouthshut URLs rather than treating same-URL as duplicates.

---

## 6. Key Assumptions

| # | Assumption | Rationale |
|---|------------|-----------|
| 1 | **Dataset represents a single brand (ICICI Prudential AMC)** | All mentions are pre-filtered to one brand; no cross-brand disambiguation is needed |
| 2 | **Original sentiment labels are a reference, not ground truth** | The source data contains human-labeled sentiment that may be inconsistent; we re-classify independently and track agreement |
| 3 | **Reach values are valid proxies for source influence** | Higher reach → greater public exposure; we use log-normalisation to prevent extreme outliers from dominating |
| 4 | **Sub-driver descriptions generalise to unseen BFSI content** | The 8 pre-computed anchor descriptions were crafted using domain knowledge; they may need updating for new financial products or regulatory contexts |
| 5 | **Deduplication threshold (85% fuzzy, 92% semantic) is conservative** | We prefer false negatives (keeping a near-duplicate) over false positives (merging distinct mentions) |
| 6 | **Play Store / App Store reviews with identical URLs are distinct records** | Each review is authored independently even though all share the same app URL |

---

## 7. Limitations

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| **Small corpus (83 relevant mentions)** | Sentiment ratios and reputation scores are sensitive to individual outliers; a single viral negative article can shift the score by 5–10 points | Flag low-volume sub-drivers; apply confidence intervals at scale |
| **LLM classification is non-deterministic** | Re-running the pipeline may produce slightly different classifications for borderline cases | Caching layer preserves results across runs; high-confidence embedding-only classifications are fully deterministic |
| **No temporal trend analysis** | The dataset spans ~2 months; we cannot distinguish a sustained shift from a one-off event | Resolve at scale with rolling 30/90-day windows |
| **Reach data is sparse** | Many mentions have reach = 0 (unverified sources); impact scoring underweights these | Treat zero-reach mentions as "unverified" tier with a floor weight of 0.1 |
| **No cross-brand benchmarking** | Reputation Score (0–100) is relative to this brand's own corpus, not industry peers | Requires multi-brand dataset to enable competitive benchmarking |
| **English-only classification** | Prompts and embeddings are optimised for English; non-English mentions may be misclassified | Add language detection + translated prompt variants for regional content |

---

## 8. Scalability Considerations

### Current Architecture (100 mentions)
- In-memory processing, JSON file storage
- Sequential LLM calls with rate limiting

### Production Architecture (10M mentions)
- **PostgreSQL + pgvector** for mention storage and semantic search
- **Async LLM calls** with connection pooling and circuit breakers
- **Embedding-first classification** to skip the LLM for high-confidence matches
- **Incremental processing** — only process new mentions, not the full corpus
- **Caching layer** for repeated source/URL patterns
- **Estimated cost at 10M**: ~$4,000/month (Gemini Flash) vs ~$50,000/month (pure GPT-4o)
