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

**Stage 2 — LLM Validation (Cost: ~$0.001/mention)**
- If top candidate has **confidence ≥ 0.75** and **gap to #2 ≥ 0.10**: Accept embedding result (no LLM call)
- Otherwise: Send mention + top-3 candidates to Gemini for contextual classification
- LLM can override embedding suggestion when context reveals the true intent

**Why this matters:**
- **40% of mentions** are classified by embeddings alone → zero LLM cost
- **Audit trail**: Every classification has either similarity scores (Stage 1) or LLM rationale (Stage 2)
- **At scale (10M mentions)**: Reduces LLM API costs by ~40% while maintaining accuracy

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

## 6. Scalability Considerations

### Current Architecture (100 mentions)
- In-memory processing, JSON file storage
- Sequential LLM calls with rate limiting

### Production Architecture (10M mentions)
- **PostgreSQL + pgvector** for mention storage and semantic search
- **Async LLM calls** with connection pooling and circuit breakers
- **Embedding-first classification** to reduce LLM calls by 40%
- **Incremental processing** — only process new mentions, not the full corpus
- **Caching layer** for repeated source/URL patterns
- **Estimated cost at 10M**: ~$4,000/month (Gemini Flash) vs ~$50,000/month (pure GPT-4o)
