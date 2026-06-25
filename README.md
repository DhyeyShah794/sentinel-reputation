# Sentinel — Reputation Intelligence Operating System

> AI-powered reputation intelligence platform built for Eminence Strategy Consulting.  
> Transforms raw digital mentions into structured reputation intelligence that consultants can immediately act on.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![Next.js](https://img.shields.io/badge/Next.js-16-black)
![Gemini](https://img.shields.io/badge/Gemini-2.0-yellow)

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
│  Gemini LLM · Sentence-Transformers    │
└─────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Google Gemini API Key ([Get one here](https://aistudio.google.com/app/apikey))

### 1. Clone & Setup Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp ../.env.example .env
# Edit .env and add your GEMINI_API_KEY
```

### 3. Run the Intelligence Pipeline

```bash
cd backend
GEMINI_API_KEY=your_key_here python -m app.pipeline.orchestrator
```

This processes all 100 mentions through the full pipeline (~5-10 minutes depending on API rate limits).

### 4. Start the API Server

```bash
cd backend
GEMINI_API_KEY=your_key_here uvicorn app.main:app --reload --port 8000
```

### 5. Start the Dashboard

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

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

2. **Stage 2 — LLM Validation:** If the top embedding candidate has high confidence (>0.75) with a clear gap (>0.10) to the second, it's accepted directly. Otherwise, Gemini validates and may override.

### Why Hybrid?
- **Cost-efficient:** ~40% of mentions are classified by embeddings alone (no LLM cost)
- **High accuracy:** LLM handles ambiguous cases with full context
- **Auditable:** Every classification has either similarity scores or LLM rationale
- **Scalable:** At 10M records, embedding-first reduces LLM costs by 40%

---

## 📁 Project Structure

```
Eminence/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI application
│   │   ├── config.py            # Configuration
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
│   │   └── services/
│   │       ├── llm.py           # Gemini abstraction
│   │       └── embeddings.py    # Sentence-transformers
│   ├── data/
│   │   ├── raw/                 # Original dataset
│   │   ├── processed/           # Intermediate outputs
│   │   └── outputs/             # Final pipeline outputs
│   └── requirements.txt
├── frontend/
│   └── src/app/                 # Next.js pages
├── docs/                        # Methodology & scalability docs
└── README.md
```

---

## 🔧 Technology Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **LLM** | Google Gemini 2.0 Flash | Fast, cost-effective for classification/sentiment |
| **Embeddings** | sentence-transformers (all-MiniLM-L6-v2) | Lightweight, accurate for semantic similarity |
| **Backend** | FastAPI | Async, auto-docs, production-grade |
| **Frontend** | Next.js 16 + TypeScript | Modern React, SSR capability |
| **Charts** | Recharts | React-native, composable |
| **Styling** | Tailwind CSS | Utility-first, responsive |

---

## 📜 License

Built as an assignment submission for Eminence Strategy Consulting.
