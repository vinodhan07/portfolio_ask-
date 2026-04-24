# AI Log: portfolio-ask

## Overview
**Project:** AI-powered portfolio Q&A CLI with RAG + 4-node agentic pipeline
**Model Stack:**
- Query classification & allocation/metrics RAG: `gemini-2.0-flash`
- News impact analysis (Node 4): `gemini-1.5-pro`
- Embeddings: `sentence-transformers/all-MiniLM-L6-v2` (FAISS)

**Key Architecture:**
```
Query → Router → allocation   → RAG → AllocationResponse
               → metrics     → RAG → MetricsResponse
               → news_impact → 4-Node Agent → NewsImpactResponse
                                 Node 1: FAISS news search
                                 Node 2: Cross-reference to tickers
                                 Node 3: Rank by portfolio exposure
                                 Node 4: Gemini Pro typed JSON
```

---

## Design Decisions

### 1. Query Routing Strategy
- **Why three separate response types?**
  - Allocation (composition) is purely informational
  - Metrics (performance) requires specific calculations
  - News impact requires temporal reasoning + multi-hop inference
  - Splitting allows each handler to optimize for its task

- **Fallback behavior:** If classification fails, default to `news_impact` (most general)

### 2. Vector Store & Retrieval
- **FAISS + cosine similarity (L2 norm):** Fast, deterministic, works offline
- **Chunking strategy:**
  - Portfolio: One chunk per holding + embedded news per holding
  - Augmented: One chunk per analyst entry (ratings, thesis, risk factors)
  - Glossary: One chunk per term definition (15+ chunks)
  - News: Full document per chunk (20 files)
- **Cache:** `.faiss_store/` stored after first build; `--rebuild` forces reindex

### 3. Data Schema
- **Portfolio:** 10 holdings (all equities) with live yfinance data
  - RELIANCE, TCS, HDFCBANK, INFY, ICICIBANK, BHARTIARTL, TATAPOWER, ZOMATO, LT, DIXON
  - Each holding includes financials (PE, EPS, market cap, 52w range) and 2-3 news items
  - Total portfolio value: ~₹24.6 lakh
- **Augmented:** Analyst ratings, target prices, risk factors, investment thesis per holding
- **Glossary:** 15+ wealth-tech terms (XIRR, CAGR, NIM, etc.)
- **News:** 20 markdown files covering RBI policy, IT trends, banking, infrastructure, etc.

### 4. Gemini JSON Mode
- `response_mime_type="application/json"` ensures structured output
- `temperature=0.1` for deterministic, factual responses
- No prompt caching needed — Gemini handles context efficiently

### 5. 4-Node News Impact Pipeline (Variant C)
- **Node 1 (Retriever):** Broad search for any news matching query
- **Node 2 (Cross-ref):** Map news text to portfolio tickers via:
  - Exact ticker match (e.g., "RELIANCE" → RELIANCE.NS)
  - Company name fragments (e.g., "Reliance" → RELIANCE.NS)
- **Node 3 (Ranker):** Score = portfolio weight + FAISS score:
  - High-weight holdings amplify news relevance
  - Top 6 ranked news pass to Node 4
- **Node 4 (Formatter):** Gemini Pro generates typed JSON + rationale:
  - Exposure levels: HIGH (direct), MEDIUM (sector), LOW (sentiment)
  - Source citations (e.g., `news_05.md`)

---

## Eval Framework

**5 test cases in `evals/cases.yaml`:**
1. Allocation + sector filtering (Banking & Finance) → `AllocationResponse`
2. Metrics + P&L calculation → `MetricsResponse`
3. News impact + RBI rates → `NewsImpactResponse` (multi-hop)
4. News impact + IT sector → `NewsImpactResponse` (sector cross-cut)
5. Allocation + sector filtering (Technology) → `AllocationResponse`

**Scoring:** Each case checks:
- Response type correctness (allocation vs. metrics vs. news_impact)
- Fact presence (expected keywords/tickers in JSON output)

**Pass threshold:** 5/5 (100%)

---

## Known Limitations

1. **Cross-cutting analysis:** News mentions "Reliance" but no explicit ticker match → misses unless company name fuzzy match triggers
2. **Temporal reasoning:** No date-based filtering for news (all news treated as current)
3. **XIRR calculation:** Requires exact cashflow dates; fallback to unrealized P&L
4. **No mutual funds or bonds:** Current portfolio is equity-only
5. **Static prices:** Portfolio uses point-in-time yfinance pulls, not live feeds

---

## Future Enhancements (2 more days)

- [ ] Live market data integration (ticker prices, NAV feeds)
- [ ] Date-aware news filtering (e.g., "news from last 30 days")
- [ ] XIRR computation with cashflow history
- [ ] Sector correlation matrix + risk analysis
- [ ] Voice input via Gemini audio API
- [ ] Web UI dashboard with Streamlit
- [ ] Portfolio optimization suggestions (sector rebalancing)

---

## Repository Structure

```
byld-portfolio-ask/
├── data/
│   ├── portfolio.json             10 holdings with financials + news
│   ├── portfolio_augmented.json   Analyst ratings, risk factors, thesis
│   ├── glossary.md                15+ wealth-tech term definitions
│   └── news/
│       ├── news_01.md ... news_20.md   Market news articles
│
├── portfolio_ask/
│   ├── __init__.py                Package marker
│   ├── __main__.py                Interactive REPL + one-shot CLI
│   ├── models.py                  Pydantic schemas (Holding, Portfolio, Responses)
│   ├── retriever.py               FAISS VectorStore, chunking, caching
│   ├── agent.py                   QueryRouter, 4-node pipeline (Variant C)
│   └── prompts.py                 System prompts for Gemini
│
├── evals/
│   ├── __init__.py
│   ├── cases.yaml                 5 test cases with expected facts
│   └── run_eval.py                Eval harness: type + fact checking
│
├── scripts/
│   └── build_index.py             Build FAISS index from data/
│
├── .faiss_store/                  Auto-generated FAISS index (gitignored)
├── .env                           GOOGLE_API_KEY (never commit)
├── .env.example                   Template
├── .gitignore
├── AI_LOG.md                      This file
├── README.md                      User-facing docs
├── Makefile                       setup / run / eval targets
└── pyproject.toml                 Dependencies (google-generativeai, faiss-cpu, etc.)
```

---

**Last Updated:** 2026-04-24
**Status:** ✅ Full project restructured for Gemini API
