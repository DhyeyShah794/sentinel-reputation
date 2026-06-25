# Sentinel — Reputation Intelligence Operating System

> AI-powered reputation intelligence platform built for Eminence Strategy Consulting.  
> Transforms raw digital mentions into structured reputation intelligence that consultants can immediately act on.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![Next.js](https://img.shields.io/badge/Next.js-16-black)
![LLM](https://img.shields.io/badge/LLM-Ollama%20%C2%B7%20Gemini%20%C2%B7%20OpenAI-orange)

---

## 🎯 What This Is

Sentinel is a **reputation intelligence operating system** that processes 100 digital mentions about ICICI Prudential AMC and produces:

- **Automated classification** into 3 reputation drivers and 8 sub-drivers using a hybrid embedding + LLM approach
- **Sentiment analysis** with confidence scores, explanations, and agreement tracking against original labels
- **Reputation Score (0–100)** with weighted driver breakdown
- **Theme extraction** discovering emergent narratives across the mention corpus
- **Risk detection** flagging regulatory, customer experience, digital trust, and brand perception risks
- **Executive summary generation** producing consultant-ready intelligence briefs
- **6-page dashboard** designed for consulting partners, not data scientists

> **Pre-computed outputs are committed.** The full pipeline results live in `backend/data/outputs/`,
> so you can start the API and dashboard immediately — no LLM, API key, or pipeline run required.
> Re-running the pipeline is optional (see [Run the Intelligence Pipeline](#optional--run-the-intelligence-pipeline)).

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│          Next.js Dashboard              │
│  Overview · Command Center · Explorer   │
│  Intelligence · Sources · Themes        │
├─────────────────────────────────────────┤
│            FastAPI REST API             │
├─────────────────────────────────────────┤
│         Intelligence Pipeline           │
│  Ingest → Clean → Dedup → Relevance    │
│  → Classify → Sentiment → Enrich       │
│  → Score → Summarize                    │
├─────────────────────────────────────────┤
│  LLM Provider (Ollama / Gemini /        │
│  OpenAI) · Sentence-Transformers        │
└─────────────────────────────────────────┘
```

---

## 🔌 LLM Provider

Sentinel is **provider-agnostic**. The active backend is selected with the `LLM_PROVIDER`
environment variable and resolved through a small factory (`backend/app/services/llm/`):

| `LLM_PROVIDER` | Backend | Requires |
|----------------|---------|----------|
| `ollama` (default) | Local inference via [Ollama](https://ollama.com) | Ollama running locally — **no API key** |
| `gemini` | Google Gemini API | `GEMINI_API_KEY` |
| `openai` | OpenAI / OpenAI-compatible API (LM Studio, vLLM, …) | `OPENAI_API_KEY` |

Every LLM result is cached on disk (`backend/data/cache/llm_cache.json`), so re-running the
pipeline reuses prior responses instead of paying for them again.

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+ (required by Next.js 16)
- **To re-run the pipeline only:** an LLM provider — either [Ollama](https://ollama.com) running
  locally (default, no key) **or** a Gemini / OpenAI API key. Serving the committed outputs needs neither.

### 1. Set Up the Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt   # full pipeline
# pip install -r requirements-api.txt   # API only (serve pre-computed outputs)
```

### 2. Configure Environment

The app loads `.env` from the **project root** (`Eminence/.env`), not from `backend/`.

```bash
cd ..                 # project root
cp .env.example .env
# Defaults to LLM_PROVIDER=ollama. Edit only if you switch providers.
```

### 3. Start the API Server

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

The API serves the committed pipeline outputs from `backend/data/outputs/`.
Interactive docs are available at [http://localhost:8000/docs](http://localhost:8000/docs).

### 4. Start the Dashboard

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### (Optional) — Run the Intelligence Pipeline

Only needed if you want to regenerate the outputs from the raw dataset.

```bash
cd backend
# Default: local Ollama
python -m app.pipeline.orchestrator

# Or use Gemini instead
LLM_PROVIDER=gemini GEMINI_API_KEY=your_key python -m app.pipeline.orchestrator
```

This processes all 100 mentions through the full pipeline. Runtime depends on the provider and
whether results are already cached (a warm cache completes in seconds).

---

## 📊 Dashboard Pages

| Page | Purpose |
|------|---------|
| **Executive Overview** | KPIs, sentiment distribution, driver breakdown, volume trends |
| **Command Center** | Hero page — reputation score gauge, biggest drivers, emerging theme, primary risk, recommended actions |
| **Content Explorer** | Full-text search, multi-filter, expandable mention cards with classification rationale |
| **Intelligence Hub** | AI-generated executive brief, risk alerts, amplification opportunities |
| **Source Analysis** | Source type distribution, reach analysis, source-level sentiment table |
| **Theme Explorer** | AI-discovered narrative themes with business implications |

---

## 🧠 Classification Methodology

### Hybrid Approach: Embeddings + LLM

1. **Stage 1 — Embedding Similarity:** Each mention is encoded using `all-MiniLM-L6-v2` and compared against pre-computed sub-driver description embeddings. Top 3 candidates are identified.

2. **Stage 2 — LLM Validation:** If the top embedding candidate clears a high-confidence bar (similarity ≥ 0.75 with a ≥ 0.10 gap to the second), it's accepted directly with no LLM call. Otherwise the configured LLM validates the candidates with full context and may override.

### Why Hybrid?
- **Cost-efficient by design:** the embedding-first gate lets unambiguous mentions skip the LLM entirely. How many qualify depends on the corpus — on this short, nuanced 100-mention dataset the gate is conservative and most mentions are LLM-validated; on larger, more templated corpora the embedding shortcut resolves a large fraction for free.
- **High accuracy:** the LLM handles ambiguous cases with full context.
- **Auditable:** every classification records either its similarity scores or its LLM rationale (see `backend/data/outputs/pipeline_audit.json`).
- **Scalable:** the same embedding-first design is what keeps LLM spend bounded at millions of mentions (see [`docs/scalability.md`](docs/scalability.md)).

Full details: [`docs/methodology.md`](docs/methodology.md).

---

## 📁 Project Structure

```
Eminence/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI application (all routes)
│   │   ├── config.py            # Configuration (env-driven settings)
│   │   ├── models/mention.py    # Pydantic data models
│   │   ├── pipeline/
│   │   │   ├── ingest.py        # XLSX parser
│   │   │   ├── clean.py         # Data cleaning
│   │   │   ├── dedup.py         # 3-tier deduplication
│   │   │   ├── relevance.py     # LLM relevance filtering
│   │   │   ├── classify.py      # Hybrid classification
│   │   │   ├── sentiment.py     # Sentiment + impact scoring
│   │   │   ├── enrich.py        # Themes, risks, opportunities
│   │   │   ├── score.py         # Reputation scoring
│   │   │   ├── summarize.py     # Executive summary
│   │   │   └── orchestrator.py  # Pipeline orchestration
│   │   ├── prompts/             # Prompt templates (.md) + loader
│   │   └── services/
│   │       ├── llm/             # Provider-agnostic LLM layer
│   │       │   ├── factory.py   #   Provider selection (LLM_PROVIDER)
│   │       │   ├── base.py      #   Provider interface
│   │       │   ├── ollama_provider.py
│   │       │   ├── gemini_provider.py
│   │       │   ├── openai_provider.py
│   │       │   └── schemas.py   #   Typed LLM result models
│   │       ├── llm_cache.py     # On-disk LLM response cache
│   │       └── embeddings.py    # Sentence-transformers
│   ├── data/
│   │   ├── raw/                 # Original dataset
│   │   ├── processed/           # Intermediate outputs
│   │   └── outputs/             # Final pipeline outputs (committed)
│   ├── requirements.txt        # Full pipeline dependencies
│   └── requirements-api.txt    # API-only dependencies
├── frontend/
│   └── src/app/                # Next.js pages
├── docs/                       # Methodology & scalability docs
└── README.md
```

---

## 🔧 Technology Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **LLM** | Ollama (default, local) · Gemini · OpenAI — pluggable via `LLM_PROVIDER` | No lock-in; run fully local or on a hosted API |
| **Embeddings** | sentence-transformers (all-MiniLM-L6-v2) | Lightweight, accurate for semantic similarity |
| **Backend** | FastAPI | Async, auto-docs, production-grade |
| **Frontend** | Next.js 16 + TypeScript | Modern React, SSR capability |
| **Charts** | Recharts | React-native, composable |
| **Styling** | Tailwind CSS | Utility-first, responsive |

---

## 📜 License

Built as an assignment submission for Eminence Strategy Consulting.
